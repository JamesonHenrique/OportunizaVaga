import { execFileSync } from 'node:child_process';
import { createHash, timingSafeEqual } from 'node:crypto';
import { buildDemoSnapshot } from '../../../demo.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const MAX_BODY_BYTES = 1_500_000;
const SEM_SINAL_MS = 7 * 60 * 1000;
const TZ = process.env.BOT_TZ || 'America/Sao_Paulo';
const DEMO = ['1', 'true', 'sim'].includes((process.env.MONITOR_DEMO || '').toLowerCase());
const LOCAL = !process.env.VERCEL && process.env.MONITOR_LOCAL !== '0';
const AUTH_COOKIE = 'monitor_auth';
const NO_CACHE = { 'Cache-Control': 'no-store, max-age=0' };
const INSTANCE_ID = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
const STARTED_AT = new Date().toISOString();

// The daemon republishes state after a cold start. Ordering and history are per instance.
let latestSnapshot = null;
const history = [];
let posts = 0;
let localCache = null;

const emptySnapshot = {
  tz: TZ, loops: {}, applied: [], blocked: [], linkedin: { convites: [], bloqueios: [] }, events: [],
  totals: { candidaturas: 0, convites: 0, bloqueios: 0, eventos: 0 }
};

const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const isCount = value => Number.isSafeInteger(value) && value >= 0;
const isText = value => typeof value === 'string';
const nullableText = value => value === null || isText(value);
const isTimestamp = value => isText(value) &&
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) &&
  Number.isFinite(Date.parse(value));
const nullableTimestamp = value => value === null || isTimestamp(value);
const isTimeZone = value => {
  if (!isText(value) || value.length > 64 || !/^[A-Za-z0-9_+/-]+$/.test(value)) return false;
  try { new Intl.DateTimeFormat('en', { timeZone: value }); return true; }
  catch { return false; }
};
const isMap = validate => value => isRecord(value) && Object.values(value).every(validate);
const isArray = validate => value => Array.isArray(value) && value.every(validate);
const hasShape = (value, fields) => isRecord(value) &&
  Object.entries(fields).every(([key, validate]) => !Object.hasOwn(value, key) || validate(value[key]));
const countMap = isMap(isCount);
const recordArray = isArray(isRecord);
const loopShape = {
  state: isText, phase: nullableText, nextSite: nullableText, message: nullableText,
  roundsToday: isCount, rodadasHoje: isCount, ultimoEvento: nullableTimestamp, proximaEm: nullableTimestamp
};
const healthShape = { checkedAt: nullableTimestamp, evidence: nullableText, reason: nullableText };
const optionalFields = {
  applied: recordArray, blocked: recordArray, blocks: recordArray, events: recordArray,
  terminal: isArray(value => isText(value) || isRecord(value)),
  aguardandoLogin: recordArray, porFonte: countMap, porDia: countMap, porStatus: countMap, eventCounts: countMap,
  portais: isMap(isText),
  saudePortais: isMap(value => hasShape(value, healthShape) && isText(value.state)),
  descoberta: value => value === null || hasShape(value, {
    porStatus: countMap, filtradasTotal: countMap, ultima: item => item === null || isRecord(item), proximas: recordArray
  }),
  telemetry: value => hasShape(value, { totals: countMap, porFonte: countMap, porStatus: countMap, perfis: recordArray }),
  logTail: isMap(isArray(isText))
};

function validSnapshot(value) {
  return hasShape(value, optionalFields) && isTimestamp(value.builtAt) && isTimeZone(value.tz) &&
    countMap(value.totals) && isMap(loop => hasShape(loop, loopShape) && isText(loop.state))(value.loops);
}

const digest = value => createHash('sha256').update(`monitor:${value}`).digest('hex');
function sameText(a, b) {
  if (!a || !b) return false;
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

function getCookie(request) {
  return request.headers.get('cookie')?.split(';').map(part => part.trim())
    .find(part => part.startsWith(`${AUTH_COOKIE}=`))?.slice(AUTH_COOKIE.length + 1);
}

function meta() {
  return {
    instanceId: INSTANCE_ID, startedAt: STARTED_AT, now: new Date().toISOString(),
    posts, lastPostAt: latestSnapshot?.receivedAt ?? null, history: history.slice(-20)
  };
}

function currentSnapshot(now) {
  const at = new Date(now).toISOString();
  if (DEMO) return { ...buildDemoSnapshot(now), updatedAt: at, receivedAt: at, _demo: true };
  if (latestSnapshot) return latestSnapshot;
  if (LOCAL) {
    if (localCache && now - Date.parse(localCache.receivedAt) < 5000) return localCache;
    try {
      const out = execFileSync(process.execPath, ['--input-type=module', '-e',
        "import { buildSnapshot } from './snapshot.mjs'; console.log(JSON.stringify(buildSnapshot()));"],
      { encoding: 'utf8', timeout: 10000, maxBuffer: 8 * 1024 * 1024 });
      const receivedAt = new Date().toISOString();
      localCache = { ...JSON.parse(out), updatedAt: receivedAt, receivedAt, _local: true };
    } catch {
      // Retain the last valid disk snapshot so freshness can signal a read failure.
    }
    if (localCache) return localCache;
  }
  return { ...emptySnapshot, builtAt: null, receivedAt: null, updatedAt: null };
}

function freshnessOf(snapshot, now) {
  const ageMs = snapshot.builtAt ? Math.max(0, now - Date.parse(snapshot.builtAt)) : null;
  return {
    state: ageMs === null ? 'cold_start' : ageMs >= SEM_SINAL_MS ? 'stale' : 'live',
    ageMs, thresholdMs: SEM_SINAL_MS
  };
}

// Public keys and categorical values are fixed here. Numeric values get type checked
// too, so a nested object or arbitrary string cannot cross the public boundary.
const SOURCES = ['gupy', 'linkedin', 'indeed', 'remotar', 'inhire', 'email', 'outro', 'telegram',
  'programathor', 'geekhunter', 'infojobs', 'catho', 'solides', 'vagas', 'eudev', 'glassdoor', 'trampos',
  'empregare', 'abler', 'pandape', 'boards'];
const PORTAL_STATES = ['login_necessario', 'indisponivel', 'falha_recente', 'sem_vagas_compativeis',
  'funcionando', 'nao_verificado'];
const LOOP_STATES = ['desconhecido', 'quebrado', 'quota', 'retentando', 'interrompido', 'rodando',
  'parado', 'dormindo', 'ocioso', 'idle', 'running', 'sleeping', 'retrying', 'stopped', 'error'];
const LOOP_PHASES = ['idle', 'discovering', 'screening', 'applying', 'waiting', 'cooldown',
  'descoberta', 'triagem', 'candidatura', 'espera', 'rodada', 'fila', 'rodizio'];
const TOTALS = ['candidaturas', 'convites', 'bloqueios', 'eventos', 'aplicadas', 'descartes',
  'enviosPendentes', 'rodadasHoje'];
const JOB_STATES = ['enviada', 'etapa_teste', 'proxima_etapa', 'entrevista', 'rejeitada', 'contratada',
  'nova', 'processada', 'filtrada', 'expirada', 'descartada'];
const APPLICATION_STATES = [...JOB_STATES, 'respondida', 'encerrada', 'em_analise'];
const EVENT_KINDS = ['cascata', 'modelo', 'quota', 'alerta', 'rodada', 'ok', 'falha', 'lock', 'sistema', 'evento'];
const DISCOVERY_COUNTS = ['novas', 'descricao', 'nivel', 'modelo', 'stack', 'tipo', 'antiga',
  'duplicada', 'duplicada_cross_portal', 'lidas'];

function pickCounts(value, keys) {
  return Object.fromEntries(keys.filter(key => isCount(value?.[key])).map(key => [key, value[key]]));
}

function publicSnapshot(snapshot, freshness) {
  const loops = {};
  for (const key of ['candidaturas', 'linkedin']) {
    const loop = snapshot.loops?.[key];
    if (!LOOP_STATES.includes(loop?.state)) continue;
    loops[key] = { state: loop.state };
    if (LOOP_PHASES.includes(loop.phase)) loops[key].phase = loop.phase;
    if (SOURCES.includes(loop.nextSite)) loops[key].nextSite = loop.nextSite;
    const roundsToday = loop.roundsToday ?? loop.rodadasHoje;
    if (isCount(roundsToday)) loops[key].roundsToday = roundsToday;
  }
  const saudePortais = {};
  for (const key of SOURCES) {
    const health = snapshot.saudePortais?.[key];
    const state = health?.state ?? snapshot.portais?.[key];
    if (PORTAL_STATES.includes(state)) {
      saudePortais[key] = { state, checkedAt: isTimestamp(health?.checkedAt) ? health.checkedAt : null };
    }
  }
  const dayKeys = Object.keys(snapshot.porDia || {}).filter(key => /^\d{4}-\d{2}-\d{2}$/.test(key));
  return {
    tz: isTimeZone(snapshot.tz) ? snapshot.tz : 'UTC',
    builtAt: snapshot.builtAt, receivedAt: snapshot.receivedAt, updatedAt: snapshot.updatedAt,
    freshness, publicMode: true, loops, saudePortais,
    totals: pickCounts(snapshot.totals, TOTALS),
    ...(snapshot.porDia && { porDia: pickCounts(snapshot.porDia, dayKeys) }),
    porFonte: pickCounts(snapshot.porFonte, SOURCES), eventCounts: pickCounts(snapshot.eventCounts, EVENT_KINDS),
    ...(snapshot.telemetry && { telemetry: {
      totals: pickCounts(snapshot.telemetry.totals, TOTALS),
      porFonte: pickCounts(snapshot.telemetry.porFonte, SOURCES),
      ...(snapshot.telemetry.porStatus && { porStatus: pickCounts(snapshot.telemetry.porStatus, APPLICATION_STATES) })
    } }),
    ...(snapshot.descoberta && { descoberta: {
      porStatus: pickCounts(snapshot.descoberta.porStatus, JOB_STATES),
      ...(isTimestamp(snapshot.descoberta.ultimaColeta) && { ultimaColeta: snapshot.descoberta.ultimaColeta }),
      ...(snapshot.descoberta.ultima && { ultima: pickCounts(snapshot.descoberta.ultima, DISCOVERY_COUNTS) }),
      ...(snapshot.descoberta.filtradasTotal && {
        filtradasTotal: pickCounts(snapshot.descoberta.filtradasTotal, DISCOVERY_COUNTS)
      })
    } })
  };
}

export async function GET(request) {
  const { searchParams } = new URL(request.url);
  const now = Date.now();
  const snapshot = currentSnapshot(now);
  const freshness = freshnessOf(snapshot, now);
  if (searchParams.get('ping') === '1') {
    const { builtAt, receivedAt, updatedAt } = snapshot;
    return Response.json({ ok: true, ping: true, builtAt, receivedAt, updatedAt, freshness }, { headers: NO_CACHE });
  }

  const secret = process.env.MONITOR_SECRET;
  const exchange = sameText(searchParams.get('secret'), secret);
  const authorized = exchange || sameText(request.headers.get('x-monitor-secret'), secret) ||
    (secret && sameText(getCookie(request), digest(secret)));
  const body = DEMO || authorized ? { ...snapshot, freshness, _meta: meta() } : publicSnapshot(snapshot, freshness);
  const headers = new Headers(NO_CACHE);
  if (exchange) {
    headers.set('Set-Cookie', `${AUTH_COOKIE}=${digest(secret)}; Max-Age=2592000; Path=/; HttpOnly; Secure; SameSite=Strict`);
  }
  return Response.json(body, { headers });
}

const errorResponse = (status, error) => Response.json({ ok: false, error }, { status });
const BODY_LIMIT = Symbol('body_limit');

async function readBoundedJson(request) {
  if (Number(request.headers.get('content-length')) > MAX_BODY_BYTES) throw BODY_LIMIT;
  if (!request.body) throw new SyntaxError('Missing body');

  const reader = request.body.getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let bytes = 0;
  let text = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_BODY_BYTES) throw BODY_LIMIT;
      text += decoder.decode(value, { stream: true });
    }
    return JSON.parse(text + decoder.decode());
  } catch (error) {
    // Cancellation should not delay or replace the HTTP error for an oversized stream.
    reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
}

export async function POST(request) {
  if (DEMO) return errorResponse(403, 'demo_read_only');
  const secrets = [process.env.MONITOR_SECRET, process.env.MONITOR_INGEST_SECRET].filter(Boolean);
  if (!secrets.length) return errorResponse(503, 'ingest_unavailable');
  const provided = request.headers.get('x-monitor-secret');
  if (!secrets.some(secret => sameText(provided, secret))) return errorResponse(401, 'unauthorized');

  let payload;
  try { payload = await readBoundedJson(request); }
  catch (error) {
    return error === BODY_LIMIT ? errorResponse(413, 'payload_too_large') : errorResponse(400, 'invalid_json');
  }
  if (!validSnapshot(payload)) return errorResponse(400, 'invalid_snapshot');

  // Both accepted secrets authorize the same feed. Compare after reading so a slow,
  // older request cannot overwrite a newer request accepted in the meantime.
  if (latestSnapshot && Date.parse(payload.builtAt) < Date.parse(latestSnapshot.builtAt)) {
    return errorResponse(409, 'out_of_order');
  }
  for (const key of ['_demo', '_local', '_meta', '_redacted', 'publicMode', 'freshness', 'updatedAt', 'receivedAt']) {
    delete payload[key];
  }
  const receivedAt = new Date(Date.now()).toISOString();
  latestSnapshot = { ...payload, receivedAt, updatedAt: receivedAt };
  posts += 1;
  history.push({ at: receivedAt, instanceId: INSTANCE_ID });
  if (history.length > 60) history.shift();
  return Response.json({ ok: true, builtAt: payload.builtAt, receivedAt, updatedAt: receivedAt, instanceId: INSTANCE_ID });
}
