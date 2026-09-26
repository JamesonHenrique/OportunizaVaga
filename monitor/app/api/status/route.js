import { NextResponse } from 'next/server';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { createHash, timingSafeEqual } from 'node:crypto';
import { buildDemoSnapshot } from '../../../demo.mjs';

// Guardado em memoria de proposito: a maquina local e a fonte de verdade e reenvia
// o historico inteiro a cada heartbeat. Zero banco = zero custo, sem conta nem cota.
// Limitacao conhecida: POST e GET podem cair em instancias diferentes da Vercel, entao
// um GET pode voltar vazio mesmo com o publisher ativo. O cliente trata isso mantendo
// o ultimo retrato bom (em memoria + localStorage) em vez de piscar vazio.
//
// Fallbacks when nothing was POSTed yet (in this order):
//   MONITOR_DEMO=1  -> fictional data generated on the fly (public demo / Docker / GIF);
//   off Vercel      -> reads the bot state from disk via snapshot.mjs (CANDIDATURAS_ROOT),
//                      so `npm run dev` works locally without running the publisher.
//
// v2: diagnostico de instancia (_meta) + endpoint leve de keep-warm (?ping=1) +
// auth opcional via MONITOR_SECRET (se definido na Vercel, o POST precisa mandar
// o header x-monitor-secret; se nao definido, continua aberto por compatibilidade
// com o publicador atual no PC) + historico curto de heartbeats para ver gaps.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const vazio = {
  updatedAt: null,
  updatedAtLocal: null,
  tz: process.env.BOT_TZ || 'America/Sao_Paulo',
  loops: {},
  applied: [],
  blocked: [],
  linkedin: { convites: [], bloqueios: [] },
  events: [],
  totals: { candidaturas: 0, convites: 0, bloqueios: 0, eventos: 0 }
};

const INSTANCE_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const STARTED_AT = new Date().toISOString();

globalThis.__monitorSnapshot ??= { ...vazio };
// Anel curto de heartbeats: so carimbos, para diagnosticar gaps sem estourar memoria.
globalThis.__monitorHistory ??= []; // [{ at, instanceId }]
globalThis.__monitorStats ??= { posts: 0, lastPostAt: null, lastError: null };

function meta() {
  return {
    instanceId: INSTANCE_ID,
    startedAt: STARTED_AT,
    now: new Date().toISOString(),
    posts: globalThis.__monitorStats.posts,
    lastPostAt: globalThis.__monitorStats.lastPostAt,
    history: globalThis.__monitorHistory.slice(-20)
  };
}

const DEMO = ['1', 'true', 'sim'].includes((process.env.MONITOR_DEMO || '').toLowerCase());
const LOCAL = !process.env.VERCEL && process.env.MONITOR_LOCAL !== '0';

// Local disk read in a child process: snapshot.mjs computes at import time,
// so a fresh process per request always sees the current state files.
let localCache = { at: 0, snap: null };
function localSnapshot() {
  if (Date.now() - localCache.at < 5000 && localCache.snap) return localCache.snap;
  try {
    const out = execFileSync(process.execPath, ['--input-type=module', '-e',
      "import { buildSnapshot } from './snapshot.mjs'; console.log(JSON.stringify(buildSnapshot()));"],
      { cwd: path.join(process.cwd()), encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024 });
    const snap = { ...JSON.parse(out), updatedAt: new Date().toISOString(), _local: true };
    localCache = { at: Date.now(), snap };
    return snap;
  } catch {
    return null;
  }
}

function currentSnapshot() {
  const posted = globalThis.__monitorSnapshot;
  if (posted?.updatedAt) return posted;
  if (DEMO) return { ...buildDemoSnapshot(Date.now()), updatedAt: new Date().toISOString(), _demo: true };
  if (LOCAL) return localSnapshot() || posted;
  return posted;
}

// Browser session: a valid ?secret= is exchanged for an httpOnly cookie holding a
// hash of the secret (never the secret itself), so the page never stores it.
const AUTH_COOKIE = 'monitor_auth';
const digest = (v) => createHash('sha256').update(`monitor:${v}`).digest('hex');
const sameText = (a, b) => {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && timingSafeEqual(x, y);
};

function isAuthorized(request) {
  const secret = process.env.MONITOR_SECRET;
  if (!secret) return true;
  const hdr = request.headers.get('x-monitor-secret');
  if (hdr && sameText(hdr, secret)) return true;
  const qp = new URL(request.url).searchParams.get('secret');
  if (qp && sameText(qp, secret)) return true;
  const ck = request.cookies?.get(AUTH_COOKIE)?.value;
  if (ck && sameText(ck, digest(secret))) return true;
  return false;
}

function redactSnapshot(snap) {
  if (!snap || typeof snap !== 'object') return snap;
  // Remove PII mais sensível quando a requisição não está autenticada.
  // Mantém telemetry/totals/loops para o painel público continuar útil.
  const { contasCriadas, publisher, logTail, ...rest } = snap;
  return {
    ...rest,
    publisher: publisher ? { host: 'redacted', pid: 0, node: publisher.node, root: 'redacted' } : publisher,
    contasCriadas: {},
    logTail: { candidaturas: [], linkedin: [] },
  };
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  // Keep-warm barato para UptimeRobot/cron: nao devolve o snapshot inteiro.
  if (searchParams.get('ping') === '1') {
    return NextResponse.json(
      { ok: true, ping: true, ...meta(), updatedAt: currentSnapshot()?.updatedAt ?? null },
      { headers: { 'Cache-Control': 'no-store, max-age=0' } }
    );
  }
  const snap = currentSnapshot();
  // The demo is fictional data: nothing to redact, show every panel.
  const body = snap?._demo ? { ...snap, _meta: meta() }
    : isAuthorized(request) ? { ...snap, _meta: meta() }
    : { ...redactSnapshot(snap), _meta: meta(), _redacted: true };
  const res = NextResponse.json(body, { headers: { 'Cache-Control': 'no-store, max-age=0' } });
  const qp = searchParams.get('secret');
  if (process.env.MONITOR_SECRET && qp && sameText(qp, process.env.MONITOR_SECRET)) {
    res.cookies.set(AUTH_COOKIE, digest(process.env.MONITOR_SECRET), {
      httpOnly: true, secure: true, sameSite: 'strict', path: '/', maxAge: 60 * 60 * 24 * 30
    });
  }
  return res;
}

export async function POST(request) {
  // Auth opcional: so exige se MONITOR_SECRET estiver definido na Vercel.
  // Sem env continua aberto (compatibilidade); defina MONITOR_SECRET ao expor o painel.
  if (DEMO) return NextResponse.json({ ok: false, error: 'demo_read_only' }, { status: 403 });
  const secret = process.env.MONITOR_SECRET;
  if (secret) {
    const got = request.headers.get('x-monitor-secret');
    if (!got || !sameText(got, secret)) {
      globalThis.__monitorStats.lastError = 'POST negado: segredo invalido';
      return NextResponse.json({ ok: false, error: 'unauthorized' }, { status: 401 });
    }
  }
  let payload;
  try {
    // Guarda de tamanho: o snapshot cresceu (logTail cru); protege a memoria
    // da funcao contra POST acidental/gigante. 1.5MB folga o normal (~100KB).
    const len = Number(request.headers.get('content-length') || 0);
    if (len > 1500000) {
      return NextResponse.json({ ok: false, error: 'payload_too_large' }, { status: 413 });
    }
    payload = await request.json();
  } catch {
    globalThis.__monitorStats.lastError = 'POST com JSON invalido';
    return NextResponse.json({ ok: false, error: 'invalid_json' }, { status: 400 });
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    globalThis.__monitorStats.lastError = 'POST com corpo inesperado';
    return NextResponse.json({ ok: false, error: 'invalid_body' }, { status: 400 });
  }
  const at = new Date().toISOString();
  globalThis.__monitorSnapshot = { ...payload, updatedAt: at };
  globalThis.__monitorStats.posts += 1;
  globalThis.__monitorStats.lastPostAt = at;
  globalThis.__monitorStats.lastError = null;
  globalThis.__monitorHistory.push({ at, instanceId: INSTANCE_ID });
  if (globalThis.__monitorHistory.length > 60) {
    globalThis.__monitorHistory = globalThis.__monitorHistory.slice(-60);
  }
  return NextResponse.json({ ok: true, updatedAt: at, instanceId: INSTANCE_ID });
}
