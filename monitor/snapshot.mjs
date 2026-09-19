// Monta o retrato da operacao a partir dos arquivos locais.
// A maquina local e a fonte de verdade. O monitor publica agregados por padrao;
// detalhes brutos so entram quando MONITOR_INCLUDE_DETAILS=1 e explicitamente opt-in.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TZ = process.env.BOT_TZ || 'America/Sao_Paulo';
process.env.TZ = TZ;
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.CANDIDATURAS_ROOT || path.join(HERE, '..', 'bot');
const INCLUDE_DETAILS = ['1', 'true', 'True', 'sim', 'Sim'].includes(process.env.MONITOR_INCLUDE_DETAILS || '');
const TELEMETRY_MODE = process.env.MONITOR_TELEMETRY_MODE || 'aggregate';

const readJson = (file, fallback) => {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
};
const readLines = (file) => {
  try { return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean); } catch { return []; }
};

const tailOf = (files, n) => {
  const all = [];
  for (const file of files) all.push(...readLines(file));
  return all.slice(-n).map(l => (l.length > 300 ? l.slice(0, 300) + '…' : l));
};

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

const toIso = (stamp) => new Date(stamp.replace(' ', 'T')).toISOString();
const eventsFrom = (files, source) => {
  const out = [];
  for (const file of files) {
    for (const line of readLines(file)) {
      const m = STATUS_LINE.exec(line);
      if (!m) continue;
      const [, stamp, text] = m;
      out.push({ at: toIso(stamp), source, text, ...classify(text) });
    }
  }
  return out.sort((a, b) => a.at.localeCompare(b.at));
};

const stateFile = (file, profile) => ({ file, profile, doc: readJson(file, null) });
const stateFiles = [stateFile(path.join(ROOT, 'aplicadas.json'), 'default')];
const stateDir = path.join(ROOT, 'state');
if (fs.existsSync(stateDir)) {
  for (const entry of fs.readdirSync(stateDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    stateFiles.push(stateFile(path.join(stateDir, entry.name, 'aplicadas.json'), entry.name));
  }
}
const stateDocs = stateFiles.filter(item => item.doc && typeof item.doc === 'object');
const aplicadas = stateDocs.find(item => item.profile === 'default')?.doc || stateDocs[0]?.doc || {};
const allAppliedRaw = stateDocs.flatMap(item => Array.isArray(item.doc.aplicadas) ? item.doc.aplicadas.map(a => ({ ...a, perfil: item.profile })) : []);
const allBlockedRaw = stateDocs.flatMap(item => {
  const blocked = item.doc.bloqueados || {};
  return Object.entries(blocked).map(([chave, value]) => ({ chave, perfil: item.profile, value }));
});

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

const nomeModelo = (txt) => (/([\w.-]+\/[\w.:-]+)/.exec(txt) || [])[1] || null;
const hojeLocal = new Date().toLocaleDateString('en-CA', { timeZone: TZ });
const events = eventsFrom([path.join(ROOT, 'loop.log.1'), path.join(ROOT, 'loop.log')], 'candidaturas');
const doDia = events.filter(e => e.at.startsWith(hojeLocal) || new Date(e.at).toLocaleDateString('en-CA', { timeZone: TZ }) === hojeLocal);
const ultimoModelo = [...doDia].reverse().find(e => e.kind === 'modelo');
const doTetoDia = doDia.filter(e => e.kind === 'cascata');
const tetoPorModelo = {};
for (const e of doTetoDia) {
  const m = nomeModelo(e.text);
  if (m) tetoPorModelo[m] = (tetoPorModelo[m] || 0) + 1;
}
const quotaCache = readJson(path.join(ROOT, 'quota-cache.json'), null);
const openrouterQuota = quotaCache?.openrouter || null;
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
const escada = ESCADA.map(id => ({ id, tier: id.split('/')[0], tetoHoje: tetoPorModelo[id] || 0 }));
const candLast = events.filter(e => e.source === 'candidaturas').at(-1) || null;
const applied = allAppliedRaw.map(a => {
  const { fonte, via } = parseFonte(a.como);
  return { ...a, quando: a.enviada_em || a.enviada_em_aprox || null, data: a.data || null, exato: Boolean(a.enviada_em), fonte, via, status: a.status || 'enviada', respondida_em: a.respondida_em || null, desfecho: a.desfecho || null };
});
const porFonte = {};
for (const a of applied) porFonte[a.fonte] = (porFonte[a.fonte] || 0) + 1;
const blocked = allBlockedRaw.map(item => {
  const o = typeof item.value === 'object' && item.value ? item.value : { motivo: String(item.value) };
  return { chave: item.chave, perfil: item.perfil, ...o, em: o.bloqueado_em || o.em || o.criadoEm || o.criado_em || o.at || null };
});
const contadorFalta = {};
for (const b of blocked) for (const campo of faltantesDe(`${b.chave || ''} ${b.motivo || b.detalhe || ''}`)) contadorFalta[campo] = (contadorFalta[campo] || 0) + 1;
const dadosFaltantes = Object.entries(contadorFalta).map(([campo, vagas]) => ({ campo, vagas })).sort((a, b) => b.vagas - a.vagas);
const rodadasHoje = events.filter(e => e.kind === 'rodada' && e.at.startsWith(hojeLocal)).length;
const evCand = events.filter(e => e.source === 'candidaturas');
const sizeOf = (f) => { try { return fs.statSync(f).size; } catch { return 0; } };
const loopLog = path.join(ROOT, 'loop.log');
const loopLog1 = path.join(ROOT, 'loop.log.1');
const descarteTotal = stateDocs.reduce((sum, item) => sum + (Number(item.doc.descartes_listagem_total) || 0), 0);
const rodizioPorPerfil = Object.fromEntries(stateDocs.map(item => [item.profile, item.doc.rodizio || null]));
const perfis = stateDocs.map(item => ({ nome: item.profile, aplicadas: Array.isArray(item.doc.aplicadas) ? item.doc.aplicadas.length : 0, bloqueados: item.doc.bloqueados && typeof item.doc.bloqueados === 'object' ? Object.keys(item.doc.bloqueados).length : 0 }));
const eventCounts = {};
for (const e of events) eventCounts[e.kind] = (eventCounts[e.kind] || 0) + 1;
const statusCounts = {};
for (const a of applied) statusCounts[a.status] = (statusCounts[a.status] || 0) + 1;

export function buildSnapshot() {
  const telemetry = {
    version: 1,
    mode: TELEMETRY_MODE,
    includeDetails: INCLUDE_DETAILS,
    perfis,
    totals: {
      aplicadas: applied.length,
      bloqueios: blocked.length,
      descartes: descarteTotal,
      rodadasHoje,
      eventos: events.length
    },
    porFonte,
    porStatus: statusCounts,
    rodadas: duracoes(evCand),
    modelos: { emUso: ultimoModelo ? nomeModelo(ultimoModelo.text) : null, noTetoHoje: [...new Set(doTetoDia.map(e => nomeModelo(e.text)).filter(Boolean))], openrouterQuota },
    ultimoEvento: candLast?.at || null
  };
  return {
    updatedAtLocal: new Date().toLocaleString('pt-BR', { timeZone: TZ }),
    builtAt: new Date().toISOString(),
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
    loops: { candidaturas: { ...stateOf(candLast, 21), ultimoEvento: candLast?.at || null, rodadasHoje, duracao: duracoes(evCand) } },
    applied: INCLUDE_DETAILS ? applied : undefined,
    porFonte,
    blocked: INCLUDE_DETAILS ? blocked : undefined,
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
  };
}
