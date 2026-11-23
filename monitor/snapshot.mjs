// Monta o retrato da operacao a partir dos arquivos locais.
// A maquina local e a fonte de verdade. O monitor publica agregados por padrao;
// detalhes brutos so entram quando MONITOR_INCLUDE_DETAILS=1 e explicitamente opt-in.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TZ = process.env.BOT_TZ || process.env.OV_TZ || 'America/Fortaleza';
process.env.TZ = TZ;
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.CANDIDATURAS_ROOT || path.join(HERE, '..', 'bot');
const INCLUDE_DETAILS = ['1', 'true', 'True', 'sim', 'Sim'].includes(process.env.MONITOR_INCLUDE_DETAILS || '');
const TELEMETRY_MODE = process.env.MONITOR_TELEMETRY_MODE || 'aggregate';

const readJson = (file, fallback) => {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
};
const asObj = value => value && typeof value === 'object' && !Array.isArray(value) ? value : null;
const localDate = new Intl.DateTimeFormat('en-CA', { timeZone: TZ });
const EVENT_LOG_BYTES = 4 * 1024 * 1024; // Exceeds the loop's 2 MiB rotation threshold.
const TAIL_LOG_BYTES = 256 * 1024;
const timestamp = value => {
  const parsed = typeof value === 'string' ? Date.parse(value) : NaN;
  return Number.isFinite(parsed) ? parsed : -Infinity;
};

function readLines(file, limit) {
  let fd;
  try {
    fd = fs.openSync(file, 'r');
    const size = fs.fstatSync(fd).size;
    const start = Math.max(0, size - limit - 1);
    const buffer = Buffer.alloc(size - start);
    let read = 0;
    while (read < buffer.length) {
      const sizeRead = fs.readSync(fd, buffer, read, buffer.length - read, start + read);
      if (!sizeRead) break;
      read += sizeRead;
    }
    const text = buffer.toString('utf8', 0, read);
    const newline = text.indexOf('\n');
    if (start && newline === -1) return [];
    return (start ? text.slice(newline + 1) : text).split('\n').filter(Boolean);
  } catch {
    return [];
  } finally {
    if (fd !== undefined) fs.closeSync(fd);
  }
}

const tailOf = (files, n) => files.flatMap(file => readLines(file, TAIL_LOG_BYTES).slice(-n))
  .slice(-n).map(line => (line.length > 300 ? line.slice(0, 300) + '…' : line));

function stateLocations() {
  // Keep resolution aligned with bot/vagas_filtros.py: explicit state directory,
  // then the profile slug, then the root. Read other profile dirs for aggregation.
  const state = path.join(ROOT, 'state');
  const profile = process.env.STATE_DIR ? null : readJson(process.env.BOT_PERFIL || path.join(ROOT, 'perfil.json'), null);
  const profileName = asObj(profile) && String(profile.nome_perfil ?? 'perfil');
  const slug = profileName && (profileName.toLowerCase().replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '').slice(0, 48) || 'perfil');
  const active = path.resolve(process.env.STATE_DIR || (slug ? path.join(state, slug) : ROOT));
  const files = new Map();
  const dirs = new Set();
  function add(dir, name, file = path.join(dir, 'aplicadas.json')) {
    dirs.add(path.resolve(dir));
    const resolved = path.resolve(file);
    if (!files.has(resolved)) files.set(resolved, { profile: name, doc: asObj(readJson(resolved, null)) });
  }
  const appliedFile = process.env.APLICADAS_FILE || path.join(active, 'aplicadas.json');
  const activeName = active === path.resolve(ROOT) ? 'default' : path.basename(active);
  add(active, activeName, appliedFile);
  if (active !== path.resolve(ROOT)) add(ROOT, 'default');
  if (process.env.APLICADAS_FILE) dirs.add(path.dirname(path.resolve(appliedFile)));
  if (fs.existsSync(state)) {
    for (const entry of fs.readdirSync(state, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const dir = path.resolve(state, entry.name);
      if (entry.isDirectory() && dir !== active) add(dir, entry.name);
    }
    // Legacy private layout: applications at the root, auxiliary files in state/.
    dirs.add(path.resolve(state));
  }
  return { dirs, stateDocs: [...files.values()].filter(item => item.doc) };
}

function portalHealth(dirs) {
  const health = new Map();
  for (const dir of dirs) {
    const doc = readJson(path.join(dir, 'saude_portais.json'), null);
    for (const [key, item] of Object.entries(asObj(doc?.portais) || {})) {
      const state = item?.state ?? item?.estado;
      if (typeof state !== 'string') continue;
      const evidence = item.evidence ?? item.evidencia ?? null;
      const rawDate = item.checkedAt ?? item.em ?? doc.atualizado;
      const checkedAt = Number.isFinite(timestamp(rawDate)) ? rawDate : null;
      if (health.has(key) && timestamp(checkedAt) <= timestamp(health.get(key).checkedAt)) continue;
      health.set(key, { state, evidence, checkedAt, reason: item.reason ?? item.motivo ?? null });
    }
  }
  return Object.fromEntries(health);
}

function discovery(dirs) {
  const jobs = new Map();
  const totals = new Map();
  let newest = null;
  for (const dir of dirs) {
    const queue = asObj(readJson(path.join(dir, 'vagas_fila.json'), null));
    if (!queue) continue;
    const collectedAt = timestamp(queue.ultima_coleta);
    if (!newest || collectedAt > timestamp(newest.ultima_coleta)) newest = queue;
    for (const [key, job] of Object.entries(asObj(queue.vagas) || {})) {
      if (!asObj(job)) continue;
      const seenAt = Math.max(timestamp(job.visto_em), timestamp(job.atualizado_em));
      const at = Number.isFinite(seenAt) ? seenAt : collectedAt;
      if (!jobs.has(key) || at > jobs.get(key).at) jobs.set(key, { job, at });
    }
    for (const [key, count] of Object.entries(asObj(queue.totais) || {})) {
      if (Number.isSafeInteger(count) && count >= 0) totals.set(key, (totals.get(key) || 0) + count);
    }
  }
  if (!newest) return null;
  const values = [...jobs.values()].map(({ job }) => job);
  const counts = new Map();
  for (const job of values) {
    const key = job.status || '?';
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  return {
    ultimaColeta: newest.ultima_coleta || null,
    porStatus: Object.fromEntries(counts),
    filtradasTotal: Object.fromEntries(totals),
    ultima: asObj(newest.stats),
    proximas: INCLUDE_DETAILS
      ? values.filter(v => v.status === 'nova')
        .sort((a, b) => (b.score || 0) - (a.score || 0) || (a.ofertas || 0) - (b.ofertas || 0))
        .slice(0, 8)
        .map(v => ({ empresa: v.empresa, titulo: v.titulo, fonte: v.fonte, url: v.url, score: v.score, publicada: v.publicada }))
      : undefined
  };
}

const duracoes = (sourceEvents) => {
  const out = [];
  let inicio = null;
  for (const e of sourceEvents) {
    if (e.kind === 'rodada') inicio = e.at;
    else if (inicio && (e.kind === 'ok' || e.kind === 'falha' || e.kind === 'quota')) {
      const min = (new Date(e.at).getTime() - new Date(inicio).getTime()) / 60000;
      if (min >= 0 && min < 24 * 60) out.push(min);
      inicio = null;
    }
  }
  const ultimas = out.slice(-20);
  return {
    ultimaMin: out.length ? Math.round(out[out.length - 1] * 10) / 10 : null,
    mediaMin: ultimas.length ? Math.round((ultimas.reduce((a, b) => a + b, 0) / ultimas.length) * 10) / 10 : null,
    amostras: out.length
  };
};

const STATUS_LINE = /^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.*)$/;
const classify = (text) => {
  const t = text.toLowerCase();
  if (/no limite, cascateando/.test(t)) return { kind: 'cascata', severity: 'warn' };
  if (/rodada usou o modelo/.test(t)) return { kind: 'modelo', severity: 'info' };
  if (/quota\/limite do modelo|quota esgotada|todos os \d+ modelos/.test(t)) return { kind: 'quota', severity: 'warn' };
  if (/falhas consecutivas/.test(t)) return { kind: 'alerta', severity: 'error' };
  if (/rodada iniciada|rodada diaria iniciada/.test(t)) return { kind: 'rodada', severity: 'info' };
  if (/rodada ok/.test(t)) return { kind: 'ok', severity: 'ok' };
  if (/terminou com erro|estourou|indisponivel|invalida|travado/.test(t)) return { kind: 'falha', severity: 'error' };
  if (/lock|ja esta ativo|ocupado/.test(t)) return { kind: 'lock', severity: 'warn' };
  if (/rotacionado/.test(t)) return { kind: 'sistema', severity: 'muted' };
  return { kind: 'evento', severity: 'muted' };
};

const PORTAIS = [
  ['gupy', /\bgupy\b/i],
  ['remotar', /\bremotar\b/i],
  ['inhire', /\binhire\b/i],
  ['linkedin', /\blinkedin\b/i],
  ['indeed', /\bindeed\b/i],
  ['email', /\be-?mail\b|@/i]
];
const parseFonte = (como) => {
  const t = como || '';
  let fonte = 'outro';
  for (const [nome, re] of PORTAIS) { if (re.test(t)) { fonte = nome; break; } }
  const via = (/\bvia\s+(remotar|inhire)\b/i.exec(t) || [])[1]?.toLowerCase() || null;
  return { fonte, via: via && via !== fonte ? via : null };
};

// Job link for the dashboard (the title becomes clickable). Order of trust:
// 1) an explicit field the robot saved, 2) a full job URL cited in the text,
// 3) an id in a verified URL format (LinkedIn jobs/view, Indeed viewjob).
// Never guesses formats not seen working (e.g. Gupy by bare id gave 404).
const CAMPOS_URL = ['url', 'url_vaga', 'link', 'link_vaga', 'url_formulario'];
const URL_RUIM = /linkedin\.com\/(in|feed|search)|\/jobs\/search|instagram\.com|facebook\.com|secure\.indeed\.com|applystart|\/auth\b|\/login|\/signin|job-search|accounts\.google|mail\.google/i;
const URL_ATS = /^(?:[\w-]+\.)+(?:gupy\.io|inhire\.app|greenhouse\.io|ashbyhq\.com|lever\.co|recrutei\.com\.br|recruitee\.com|factorialhr\.com\.br|rippling\.com|solides\.jobs|programathor\.com\.br|remotar\.com\.br|infojobs\.com\.br|catho\.com\.br|vagas\.com\.br|geekhunter\.com\.br|join\.com)\/\S{6,}/i;
const limpaUrl = (u) => String(u).replace(/[)\]}>.,;'"]+$/, '');
export function linkDaVaga(o, chave = '') {
  for (const k of CAMPOS_URL) {
    const v = o?.[k];
    if (typeof v === 'string' && /^https?:\/\//.test(v) && !URL_RUIM.test(v)) return limpaUrl(v);
  }
  const t = `${chave} ${o?.motivo || ''} ${o?.como || ''} ${o?.vaga || ''} ${o?.detalhe || ''}`;
  for (const m of t.matchAll(/https?:\/\/[^\s"'<>]+/g)) if (!URL_RUIM.test(m[0])) return limpaUrl(m[0]);
  for (const m of t.matchAll(/(?<![\w@/.])(?:[\w-]+\.)+[a-z]{2,}(?:\.br)?\/[^\s"'<>]+/gi)) {
    if (URL_ATS.test(m[0]) && !URL_RUIM.test(m[0])) return `https://${limpaUrl(m[0])}`;
  }
  const li = /linkedin[^0-9]{0,20}?(\d{10})(?!\d)/i.exec(t);
  if (li) return `https://www.linkedin.com/jobs/view/${li[1]}/`;
  const jk = /\bjk=([0-9a-f]{16})\b/i.exec(t);
  if (jk) return `https://br.indeed.com/viewjob?jk=${jk[1]}`;
  return null;
}

// Personal data never leaves the machine: the robot writes contact data inside free-text
// reasons ("account created (<e-mail>...)"). Only formatted patterns — bare digit runs
// are job ids (LinkedIn has 10 digits) and must stay.
const PII = [
  [/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, '[e-mail]'],
  [/\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g, '[cpf]'],
  [/(?:\+55\s?)?\(?\b\d{2}\)?\s?9?\d{4}-\d{4}\b/g, '[telefone]'],
  // Bare BR mobile (DDD + 9 + 8 digits = 11, optional 55). Job ids never match: LinkedIn 10 digits, Gupy 7-9.
  [/\b(?:55)?\d{2}9\d{8}\b/g, '[telefone]'],
];
export const semPII = (v) => {
  if (typeof v === 'string') return PII.reduce((t, [re, sub]) => t.replace(re, sub), v);
  if (Array.isArray(v)) return v.map(semPII);
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, semPII(x)]));
  return v;
};

const CAMPOS_CADASTRO = [
  ['RG', /\brg\b/],
  ['Facebook', /facebook/],
  ['CPF', /\bcpf\b/],
  ['nome da mãe', /nome (?:completo )?da m[ãa]e/],
  ['CR (coeficiente)', /coeficiente|\bcr\b/],
  ['grade horária', /grade hor[áa]ria/],
  ['PIS', /\bpis\b/],
  ['data de nascimento', /data de nascimento/]
];
const faltantesDe = (texto) => {
  const t = (texto || '').toLowerCase();
  const mFalta = /falta(?:\s+somente)?\s+([^|.;]+)/.exec(t);
  if (mFalta) return CAMPOS_CADASTRO.filter(([, re]) => re.test(mFalta[1])).map(([r]) => r);
  if (/j[áa]\s+(?:consta|constam|existe|existem)/.test(t)) return [];
  if (/(n[ãa]o consta|obrigat[óo]ri|n[ãa]o inventar|ausente)/.test(t)) {
    return CAMPOS_CADASTRO.filter(([, re]) => re.test(t)).map(([r]) => r);
  }
  return [];
};

const eventsFrom = (files, source) => {
  const out = [];
  for (const file of files) {
    for (const line of readLines(file, EVENT_LOG_BYTES)) {
      const m = STATUS_LINE.exec(line);
      if (!m) continue;
      const [, stamp, text] = m;
      const at = new Date(stamp.replace(' ', 'T'));
      if (Number.isFinite(at.getTime())) out.push({ at: at.toISOString(), source, text, ...classify(text) });
    }
  }
  return out.sort((a, b) => a.at.localeCompare(b.at));
};

const waitSeconds = (text) => {
  const s = /em (\d+)s/.exec(text);
  if (s) return Number(s[1]);
  const min = /dormindo (\d+)min/.exec(text);
  if (min) return Number(min) * 60;
  return null;
};
const stateOf = (last, maxRunMin) => {
  if (!last) return { state: 'desconhecido', message: 'Nenhum evento registrado ainda.', proximaEm: null };
  const ageMin = (Date.now() - new Date(last.at).getTime()) / 60000;
  const espera = waitSeconds(last.text);
  const proximaEm = espera ? new Date(new Date(last.at).getTime() + espera * 1000).toISOString() : null;
  if (last.kind === 'alerta') return { state: 'quebrado', message: last.text, proximaEm };
  if (last.kind === 'quota') return { state: 'quota', message: last.text, proximaEm };
  if (last.kind === 'falha') return { state: 'retentando', message: last.text, proximaEm };
  if (last.kind === 'rodada') return ageMin > maxRunMin ? { state: 'interrompido', message: `Rodada iniciada há ${Math.round(ageMin)}min e nunca concluiu.`, proximaEm: null } : { state: 'rodando', message: 'Rodada em execução.', proximaEm: null };
  if (last.kind === 'ok') return ageMin > (espera ? espera / 60 + 5 : 60) ? { state: 'parado', message: 'Última rodada terminou, mas a próxima não começou.', proximaEm } : { state: 'dormindo', message: last.text, proximaEm };
  return { state: 'ocioso', message: last.text, proximaEm };
};

const nomeModelo = (txt) => (/((?:[\w.:-]+\/)+[\w.:-]+)/.exec(txt) || [])[1] || null;

const ESCADA = [
  'openrouter/nex-agi/nex-n2.5-pro:free', 'opencode/muse-spark-1.3-contributor-free',
  'opencode/nemotron-3-ultra-free', 'opencode/nemotron-3.5-lightning-free', 'opencode/mimo-v2.5-free',
  'opencode/muse-spark-1.2-contributor-free', 'opencode/ling-3.0-flash-fin-free',
  'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free', 'openrouter/nvidia/nemotron-3-super-120b-a12b:free',
  'openrouter/z-ai/glm-5.2:free', 'openrouter/poolside/laguna-s-2.1:free',
  'openrouter/thinkingmachines/inkling:free', 'openrouter/cohere/north-mini-code:free',
  'openrouter/dots-studio/dots-3-note-preview:free', 'openrouter/nvidia/nemotron-3.5-lightning:free',
  'nvidia/nvidia/nemotron-3-super-120b-a12b', 'groq/openai/gpt-oss-120b', 'groq/qwen/qwen3.8-27b',
  'groq/openai/gpt-oss-20b', 'groq/meta-llama/llama-3.3-70b-versatile', 'cerebras/gpt-oss-120b',
  'cerebras/qwen-3.8-27b', 'huggingface/deepseek-ai/DeepSeek-V4-Pro', 'huggingface/deepseek-ai/DeepSeek-V3.2',
  'huggingface/google/gemma-3-27b-it'
];

// Every input is read inside buildSnapshot(): publish-status.mjs is a long-lived
// daemon that calls it repeatedly, so module-level reads would freeze the data
// at process start while updatedAt kept advancing.
export function buildSnapshot() {
  const now = new Date();
  const { dirs, stateDocs } = stateLocations();
  const allAppliedRaw = stateDocs.flatMap(item => Array.isArray(item.doc.aplicadas) ? item.doc.aplicadas.map(a => ({ ...a, perfil: item.profile })) : []);
  const allBlockedRaw = stateDocs.flatMap(item => {
    const blocked = item.doc.bloqueados || {};
    return Object.entries(blocked).map(([chave, value]) => ({ chave, perfil: item.profile, value }));
  });

  const hojeLocal = localDate.format(now);
  const events = eventsFrom([path.join(ROOT, 'loop.log.1'), path.join(ROOT, 'loop.log')], 'candidaturas');
  const doDia = events.filter(e => localDate.format(new Date(e.at)) === hojeLocal);
  const ultimoModelo = [...doDia].reverse().find(e => e.kind === 'modelo');
  const doTetoDia = doDia.filter(e => e.kind === 'cascata');
  const tetoPorModelo = {};
  for (const e of doTetoDia) {
    const m = nomeModelo(e.text);
    if (m) tetoPorModelo[m] = (tetoPorModelo[m] || 0) + 1;
  }
  const quotaCache = readJson(path.join(ROOT, 'quota-cache.json'), null);
  const openrouterQuota = quotaCache?.openrouter || null;

  const escada = ESCADA.map(id => ({ id, tier: id.split('/')[0], tetoHoje: tetoPorModelo[id] || 0 }));
  const candLast = events.filter(e => e.source === 'candidaturas').at(-1) || null;
  const applied = allAppliedRaw.map(a => {
    const { fonte, via } = parseFonte(a.como);
    return { ...a, quando: a.enviada_em || a.enviada_em_aprox || null, data: a.data || null, exato: Boolean(a.enviada_em), fonte, via, url: linkDaVaga(a, a.chave), status: a.status || 'enviada', respondida_em: a.respondida_em || null, desfecho: a.desfecho || null };
  });
  const porFonte = {};
  for (const a of applied) porFonte[a.fonte] = (porFonte[a.fonte] || 0) + 1;
  // Per-day counts are aggregate (no company/job text): safe in both modes, feed the hero chart.
  const porDia = {};
  for (const a of applied) {
    const k = a.data || (Number.isFinite(timestamp(a.quando)) ? localDate.format(new Date(a.quando)) : null);
    if (k) porDia[k] = (porDia[k] || 0) + 1;
  }
  const blocked = allBlockedRaw.map(item => {
    const o = typeof item.value === 'object' && item.value ? item.value : { motivo: String(item.value) };
    return { chave: item.chave, perfil: item.perfil, ...o, url: linkDaVaga(o, item.chave), em: o.bloqueado_em || o.em || o.criadoEm || o.criado_em || o.at || null };
  });
  // Compatible jobs held only by an expired login; the robot sends them once the channel logs in again.
  const aguardandoLogin = stateDocs.flatMap(item => {
    const checagens = item.doc.login_checagens || {};
    return Object.entries(item.doc.aguardando_login || {}).map(([chave, v]) => {
      const o = typeof v === 'object' && v ? v : {};
      const canal = String(o.canal || '?');
      return {
        chave, perfil: item.profile, canal,
        empresa: o.empresa || null, vaga: o.vaga || null,
        url: linkDaVaga(o, chave), score: o.score ?? null,
        motivo: String(o.motivo || o.motivo_original || '').slice(0, 600),
        em: o.bloqueado_em || o.data || null,
        checagem: checagens[canal] || null
      };
    });
  });
  // Optional state files written by the side scripts (absent on a fresh install: every read is defensive).
  // descoberta = deterministic discovery queue; gmailStatus = Gmail reply reader summary.
  const descoberta = discovery(dirs);
  const gmailDoc = asObj(readJson(path.join(ROOT, 'state', 'gmail_status.json'), null));
  const gmailStatus = gmailDoc
    ? { atualizado: gmailDoc.atualizado || null, lidas: gmailDoc.linhas_lidas ?? null, achados: Array.isArray(gmailDoc.achados) ? gmailDoc.achados.length : 0 }
    : null;
  const contadorFalta = {};
  for (const b of blocked) for (const campo of faltantesDe(`${b.chave || ''} ${b.motivo || b.detalhe || ''}`)) contadorFalta[campo] = (contadorFalta[campo] || 0) + 1;
  const dadosFaltantes = Object.entries(contadorFalta).map(([campo, vagas]) => ({ campo, vagas })).sort((a, b) => b.vagas - a.vagas);
  const rodadasHoje = doDia.filter(e => e.kind === 'rodada').length;
  const evCand = events.filter(e => e.source === 'candidaturas');
  const sizeOf = (f) => { try { return fs.statSync(f).size; } catch { return 0; } };
  const loopLog = path.join(ROOT, 'loop.log');
  const loopLog1 = path.join(ROOT, 'loop.log.1');
  // Sends whose outcome is unknown (estado.py intencao without add-aplicada): a count only, safe in aggregate mode.
  const enviosPendentes = stateDocs.reduce((sum, item) => sum + (item.doc.envios_pendentes && typeof item.doc.envios_pendentes === 'object' ? Object.keys(item.doc.envios_pendentes).length : 0), 0);
  const nextSite = stateDocs[0]?.doc.rodizio?.proximo;
  const saudePortais = portalHealth(dirs);
  const portais = Object.fromEntries(Object.entries(saudePortais).map(([key, value]) => [key, value.state]));
  const descarteTotal = stateDocs.reduce((sum, item) => sum + (Number(item.doc.descartes_listagem_total) || 0), 0);
  const rodizioPorPerfil = Object.fromEntries(stateDocs.map(item => [item.profile, item.doc.rodizio || null]));
  const perfis = stateDocs.map(item => ({ nome: item.profile, aplicadas: Array.isArray(item.doc.aplicadas) ? item.doc.aplicadas.length : 0, bloqueados: item.doc.bloqueados && typeof item.doc.bloqueados === 'object' ? Object.keys(item.doc.bloqueados).length : 0 }));
  const eventCounts = {};
  for (const e of events) eventCounts[e.kind] = (eventCounts[e.kind] || 0) + 1;
  const statusCounts = {};
  for (const a of applied) statusCounts[a.status] = (statusCounts[a.status] || 0) + 1;

  const telemetry = {
    version: 1,
    mode: TELEMETRY_MODE,
    includeDetails: INCLUDE_DETAILS,
    perfis,
    totals: {
      aplicadas: applied.length,
      bloqueios: blocked.length,
      descartes: descarteTotal,
      enviosPendentes,
      rodadasHoje,
      eventos: events.length
    },
    porFonte,
    porStatus: statusCounts,
    rodadas: duracoes(evCand),
    modelos: { emUso: ultimoModelo ? nomeModelo(ultimoModelo.text) : null, noTetoHoje: [...new Set(doTetoDia.map(e => nomeModelo(e.text)).filter(Boolean))], openrouterQuota },
    ultimoEvento: candLast?.at || null
  };
  return semPII({
    updatedAtLocal: now.toLocaleString('pt-BR', { timeZone: TZ }),
    builtAt: now.toISOString(),
    publisher: { mode: 'aggregate', version: '1.0.0' },
    logSizes: INCLUDE_DETAILS ? { loopLog: sizeOf(loopLog), loopLog1: sizeOf(loopLog1) } : undefined,
    tz: TZ,
    hoje: hojeLocal,
    modelos: {
      emUso: ultimoModelo ? nomeModelo(ultimoModelo.text) : null,
      desde: ultimoModelo?.at || null,
      noTetoHoje: [...new Set(doTetoDia.map(e => nomeModelo(e.text)).filter(Boolean))],
      escada,
      openrouterQuota,
      quotaMotivo: openrouterQuota ? null : (quotaCache?.motivo || 'quota-cache.json ausente — quota-daemon nao rodou')
    },
    loops: { candidaturas: {
      ...stateOf(candLast, 21), ultimoEvento: candLast?.at || null, rodadasHoje,
      nextSite: typeof nextSite === 'string' ? nextSite : undefined, duracao: duracoes(evCand)
    } },
    applied: INCLUDE_DETAILS ? applied : undefined,
    porFonte,
    porDia,
    blocked: INCLUDE_DETAILS ? blocked : undefined,
    aguardandoLogin: INCLUDE_DETAILS ? aguardandoLogin : undefined,
    descoberta,
    gmailStatus,
    portais,
    saudePortais,
    dadosFaltantes,
    descartes: INCLUDE_DETAILS ? Object.fromEntries(stateDocs.map(item => [item.profile, item.doc.descartes_listagem || null])) : { total: descarteTotal },
    pularTipos: INCLUDE_DETAILS ? Object.fromEntries(stateDocs.map(item => [item.profile, item.doc.pular_tipos || []])) : undefined,
    rodizio: INCLUDE_DETAILS ? rodizioPorPerfil : Object.keys(rodizioPorPerfil),
    agenda: { candidaturas: 'Loop contínuo — rodada a cada ~20min quando ocioso, backoff quando vazio' },
    contasCriadas: INCLUDE_DETAILS ? Object.fromEntries(stateDocs.map(item => [item.profile, item.doc.contas_criadas || {}])) : undefined,
    events: INCLUDE_DETAILS ? events.slice(-400).reverse() : undefined,
    eventCounts: INCLUDE_DETAILS ? undefined : eventCounts,
    logTail: INCLUDE_DETAILS ? { candidaturas: tailOf([loopLog1, loopLog], 80) } : undefined,
    totals: { candidaturas: applied.length, bloqueios: blocked.length, eventos: events.length },
    telemetry
  });
}
