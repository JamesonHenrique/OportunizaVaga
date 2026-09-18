// Monta o retrato completo da operacao a partir dos arquivos locais.
// A maquina local e a fonte de verdade: aplicadas.json e os logs.
// O Vercel so exibe o que recebe daqui — por isso nada aqui depende de banco (custo zero).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const TZ = process.env.BOT_TZ || 'America/Sao_Paulo';   // ajuste ao seu fuso (mesmo TZ dos scripts .sh).
// Fixa o fuso DESTE processo antes de qualquer Date: assim os carimbos sem offset
// dos logs sao lidos no mesmo fuso em que os loops os escreveram, sem offset chutado.
process.env.TZ = TZ;
// Raiz dos dados: bot/aplicadas.json + bot/*.log. Via env no cron; fallback = bot/ do repo.
const ROOT = process.env.CANDIDATURAS_ROOT
  || path.resolve(path.dirname(new URL(import.meta.url).pathname), '..', 'bot');

const readJson = (file, fallback) => {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
};
const readLines = (file) => {
  try { return fs.readFileSync(file, 'utf8').split('\n').filter(Boolean); } catch { return []; }
};

// Espelho cru do terminal: últimas N linhas verbatim (com carimbo original).
// É o que alimenta o painel "Terminal ao vivo" — prova visual de que o PC
// está escrevendo AGORA. Truncado por linha e por quantidade para o POST
// continuar leve. Mesma fonte dos eventos: nada novo vaza além dos logs.
const tailOf = (files, n) => {
  const all = [];
  for (const file of files) all.push(...readLines(file));
  return all.slice(-n).map(l => (l.length > 300 ? l.slice(0, 300) + '…' : l));
};

// Duração das rodadas: pareia "rodada iniciada" com o próximo evento terminal
// (ok/falha/quota). Sem isso o painel não distingue rodada de 2min de travada.
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

// "[2026-09-14 18:11:18] texto" -> evento. Os logs ja estao em horario de Natal.
const STATUS_LINE = /^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+(.*)$/;

const classify = (text) => {
  const t = text.toLowerCase();
  if (/no limite, cascateando/.test(t))                 return { kind: 'cascata', severity: 'warn' };
  if (/rodada usou o modelo/.test(t))                   return { kind: 'modelo', severity: 'info' };
  if (/quota\/limite do modelo|quota esgotada|todos os \d+ modelos/.test(t)) return { kind: 'quota', severity: 'warn' };
  if (/falhas consecutivas/.test(t))                    return { kind: 'alerta', severity: 'error' };
  if (/rodada iniciada|rodada diaria iniciada/.test(t)) return { kind: 'rodada', severity: 'info' };
  if (/rodada ok/.test(t))                              return { kind: 'ok', severity: 'ok' };
  if (/terminou com erro|estourou|indisponivel|invalida|travado/.test(t)) return { kind: 'falha', severity: 'error' };
  if (/lock|ja esta ativo|ocupado/.test(t))             return { kind: 'lock', severity: 'warn' };
  if (/rotacionado/.test(t))                            return { kind: 'sistema', severity: 'muted' };
  return { kind: 'evento', severity: 'muted' };
};

// Deriva a FONTE (portal onde a candidatura entrou) do texto livre `como`.
// Retroativo: lê os registros que já existem, nenhum campo novo precisa ser
// gravado pelo robô. `via` guarda o intermediário quando há ("Gupy ... via
// Remotar" = portal gupy, alcançado via remotar). gmail/google são cliente de
// e-mail/conta, não portal — por isso não entram em `via`.
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

// Campos de cadastro que ainda travam vagas. Lê o estado que o PRÓPRIO robô
// registrou no texto do bloqueio ("falta SOMENTE Facebook + RG"), em vez de
// adivinhar cruzando dados_candidato.json (chaves aninhadas dariam falso positivo).
// Só conta quando há marcador de pendência e o campo não foi marcado como resolvido.
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
  // 1) Cláusula "falta [somente] X" = estado atual que o robô registrou (autoritativa).
  //    Ela já exclui o que virou resolvido, então basta ler os campos dela.
  const mFalta = /falta(?:\s+somente)?\s+([^|.;]+)/.exec(t);
  if (mFalta) return CAMPOS_CADASTRO.filter(([, re]) => re.test(mFalta[1])).map(([r]) => r);
  // 2) Sem cláusula "falta": se o texto diz que os campos JÁ constam/existem, não é
  //    mais lacuna de dado (ex.: cadastro quebrado por OAuth, não por falta de campo).
  if (/j[áa]\s+(?:consta|constam|existe|existem)/.test(t)) return [];
  // 3) Pendência genuína e não resolvida: campos citados como obrigatório/não consta.
  if (/(n[ãa]o consta|obrigat[óo]ri|n[ãa]o inventar|ausente)/.test(t)) {
    return CAMPOS_CADASTRO.filter(([, re]) => re.test(t)).map(([r]) => r);
  }
  return [];
};

// "YYYY-MM-DD HH:MM:SS" sem offset -> ISO absoluto. O carimbo e lido no fuso deste
// processo (fixado acima), que e o mesmo em que os loops passaram a escrever.
// Nada de offset na mao: era isso que fazia rodada recem-iniciada parecer antiga.
const toIso = (stamp) => new Date(stamp.replace(' ', 'T')).toISOString();

const eventsFrom = (files, source) => {
  const out = [];
  for (const file of files) {
    for (const line of readLines(file)) {
      const m = STATUS_LINE.exec(line);
      if (!m) continue;                        // ignora corpo da rodada, so linhas de status
      const [, stamp, text] = m;
      out.push({ at: toIso(stamp), source, text, ...classify(text) });
    }
  }
  return out.sort((a, b) => a.at.localeCompare(b.at));
};

export function buildSnapshot() {
  const aplicadas = readJson(path.join(ROOT, 'aplicadas.json'), {});

  const events = eventsFrom([path.join(ROOT, 'loop.log.1'), path.join(ROOT, 'loop.log')], 'candidaturas');

  const lastOf = (source) => {
    const list = events.filter(e => e.source === source);
    return list[list.length - 1] || null;
  };

  // Quanto o loop disse que ia esperar: "em 900s", "dormindo 30min".
  // Serve para o painel mostrar contagem regressiva em vez de um estado parado.
  const waitSeconds = (text) => {
    const s = /em (\d+)s/.exec(text);
    if (s) return Number(s[1]);
    const min = /dormindo (\d+)min/.exec(text);
    if (min) return Number(min[1]) * 60;
    return null;
  };

  // Estado derivado do ULTIMO evento do loop — nunca do corpo da rodada.
  // maxRunMin: uma rodada que comecou e nunca terminou nesse prazo esta interrompida,
  // nao "rodando".
  const stateOf = (last, maxRunMin) => {
    if (!last) return { state: 'desconhecido', message: 'Nenhum evento registrado ainda.', proximaEm: null };
    const ageMin = (Date.now() - new Date(last.at).getTime()) / 60000;
    const espera = waitSeconds(last.text);
    const proximaEm = espera ? new Date(new Date(last.at).getTime() + espera * 1000).toISOString() : null;

    if (last.kind === 'alerta') return { state: 'quebrado', message: last.text, proximaEm };
    if (last.kind === 'quota')  return { state: 'quota', message: last.text, proximaEm };
    if (last.kind === 'falha')  return { state: 'retentando', message: last.text, proximaEm };
    if (last.kind === 'rodada') {
      return ageMin > maxRunMin
        ? { state: 'interrompido', message: `Rodada iniciada há ${Math.round(ageMin)}min e nunca concluiu.`, proximaEm: null }
        : { state: 'rodando', message: 'Rodada em execução.', proximaEm: null };
    }
    if (last.kind === 'ok') {
      return ageMin > (espera ? espera / 60 + 5 : 60)
        ? { state: 'parado', message: 'Última rodada terminou, mas a próxima não começou.', proximaEm }
        : { state: 'dormindo', message: last.text, proximaEm };
    }
    return { state: 'ocioso', message: last.text, proximaEm };
  };

  // Qual modelo a operacao esta usando agora e quais ja bateram no teto hoje.
  const nomeModelo = (txt) => (/([\w.-]+\/[\w.:-]+)/.exec(txt) || [])[1] || null;
  const hojeStr = new Date().toLocaleDateString('en-CA', { timeZone: TZ });
  const doDia = events.filter(e => e.at.startsWith(hojeStr) ||
    new Date(e.at).toLocaleDateString('en-CA', { timeZone: TZ }) === hojeStr);
  const ultimoModelo = [...doDia].reverse().find(e => e.kind === 'modelo');

  // Contagem de teto por modelo hoje: cada evento 'cascata' no log registra que
  // um modelo bateu no limite e a escada avançou. Serve de indicador para os
  // provedores que NAO expoem cota por API (Groq/Cerebras/HuggingFace/NVIDIA/Zen).
  const doTetoDia = doDia.filter(e => e.kind === 'cascata');
  const noTeto = [...new Set(doTetoDia.map(e => nomeModelo(e.text)).filter(Boolean))];
  const tetoPorModelo = {};
  for (const e of doTetoDia) {
    const m = nomeModelo(e.text);
    if (m) tetoPorModelo[m] = (tetoPorModelo[m] || 0) + 1;
  }

  // Cota diaria REAL dos modelos :free do OpenRouter, medida pelo quota-daemon.
  // Unico provedor com endpoint de uso. Absorve o motivo de erro para o painel
  // mostrar "sem dados" em vez de esconder o card.
  const quotaCache = readJson(path.join(ROOT, 'quota-cache.json'), null);
  const openrouterQuota = quotaCache?.openrouter || null;

  // Escada declarada no loop.sh (mesma ordem de preferencia). Mantida aqui para
  // o card saber TODOS os modelos configurados, nao so os que ja apareceram no log.
  // tier: provedor (1a parte do id) — usado no painel para agrupar/rotular.
  const ESCADA = [
    'opencode/muse-spark-1.3-contributor-free', 'opencode/nemotron-3-ultra-free',
    'opencode/nemotron-3.5-lightning-free', 'opencode/mimo-v2.5-free',
    'opencode/muse-spark-1.2-contributor-free', 'opencode/ling-3.0-flash-fin-free',
    'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free', 'openrouter/nvidia/nemotron-3-super-120b-a12b:free',
    'openrouter/z-ai/glm-5.2:free', 'openrouter/poolside/laguna-s-2.1:free',
    'openrouter/thinkingmachines/inkling:free', 'openrouter/cohere/north-mini-code:free',
    'openrouter/nex-agi/nex-n2.5-pro:free', 'openrouter/dots-studio/dots-3-note-preview:free',
    'openrouter/nvidia/nemotron-3.5-lightning:free',
    'nvidia/nvidia/nemotron-3-super-120b-a12b',
    'groq/openai/gpt-oss-120b', 'groq/qwen/qwen3.8-27b', 'groq/openai/gpt-oss-20b',
    'groq/meta-llama/llama-3.3-70b-versatile',
    'cerebras/gpt-oss-120b', 'cerebras/qwen-3.8-27b',
    'huggingface/deepseek-ai/DeepSeek-V4-Pro', 'huggingface/deepseek-ai/DeepSeek-V3.2',
    'huggingface/google/gemma-3-27b-it'
  ];
  const escada = ESCADA.map(id => ({
    id,
    tier: id.split('/')[0],
    tetoHoje: tetoPorModelo[id] || 0,
    // percent so existe para openrouter (e o cache e por CONTA, nao por modelo —
    // o painel mostra a cota da conta na linha do provedor OpenRouter).
  }));

  const candLast = lastOf('candidaturas');

  const applied = (aplicadas.aplicadas || []).map(a => {
    const { fonte, via } = parseFonte(a.como);
    return {
      ...a,
      // enviada_em (exato, novo) tem prioridade sobre enviada_em_aprox (retroativo do mtime do CV).
      // Sem nenhum dos dois, quando fica null: hora desconhecida e informacao, 00:00 inventado nao e.
      quando: a.enviada_em || a.enviada_em_aprox || null,
      data: a.data || null,
      exato: Boolean(a.enviada_em),
      fonte, via,
      // Passthrough do desfecho (schema novo, NÃO-quebrante): hoje ninguém grava,
      // então status default 'enviada'. Quando o robô — ou um marcador manual —
      // gravar status/respondida_em/desfecho, o dado sobe sem tocar no publisher.
      status: a.status || 'enviada',
      respondida_em: a.respondida_em || null,
      desfecho: a.desfecho || null
    };
  });

  // Envios agrupados por portal — barato e retroativo (deriva de `como`).
  // Responde "qual fonte rende candidatura" sem depender de captura nova.
  const porFonte = {};
  for (const a of applied) porFonte[a.fonte] = (porFonte[a.fonte] || 0) + 1;

  const blocked = Object.entries(aplicadas.bloqueados || {}).map(([chave, v]) => {
    const o = typeof v === 'object' && v ? v : { motivo: String(v) };
    return {
      chave,
      ...o,
      // Horário do bloqueio quando o dado existe (qualquer campo conhecido).
      // Sem isso o painel mostra "detectado no monitor em" (firstSeen local).
      em: o.bloqueado_em || o.em || o.criadoEm || o.criado_em || o.at || null
    };
  });

  // Campos de cadastro que ainda destravam vagas (agregado dos bloqueios).
  const contadorFalta = {};
  for (const b of blocked) {
    for (const campo of faltantesDe(`${b.chave || ''} ${b.motivo || b.detalhe || ''}`)) {
      contadorFalta[campo] = (contadorFalta[campo] || 0) + 1;
    }
  }
  const dadosFaltantes = Object.entries(contadorFalta).map(([campo, vagas]) => ({ campo, vagas })).sort((a, b) => b.vagas - a.vagas);

  const hojeLocal = new Date().toLocaleDateString('en-CA', { timeZone: TZ });
  const rodadasHoje = events.filter(e => e.kind === 'rodada' && e.at.startsWith(hojeLocal)).length;
  const evCand = events.filter(e => e.source === 'candidaturas');

  // v2: metadados do publicador (aditivo — o endpoint da Vercel ignora o que não conhece).
  // Sem dado pessoal: só host/pid para saber QUAL máquina mandou o heartbeat.
  const sizeOf = (f) => { try { return fs.statSync(f).size; } catch { return 0; } };
  const loopLog = path.join(ROOT, 'loop.log');
  const loopLog1 = path.join(ROOT, 'loop.log.1');

  return {
    updatedAtLocal: new Date().toLocaleString('pt-BR', { timeZone: TZ }),
    builtAt: new Date().toISOString(),
    publisher: {
      host: os.hostname(),
      pid: process.pid,
      node: process.version,
      root: ROOT
    },
    logSizes: { loopLog: sizeOf(loopLog), loopLog1: sizeOf(loopLog1) },
    tz: TZ,
    hoje: hojeLocal,
    modelos: {
      emUso: ultimoModelo ? nomeModelo(ultimoModelo.text) : null,
      desde: ultimoModelo?.at || null,
      noTetoHoje: noTeto,
      escada,
      openrouterQuota, // { used, limit, remaining, percent } | null
      quotaMotivo: openrouterQuota ? null : (quotaCache?.motivo || 'quota-cache.json ausente — quota-daemon nao rodou')
    },
    loops: {
      candidaturas: { ...stateOf(candLast, 21), ultimoEvento: candLast?.at || null, rodadasHoje, duracao: duracoes(evCand) }
    },
    applied,
    porFonte,
    blocked,
    dadosFaltantes,
    descartes: aplicadas.descartes_listagem || null,
    pularTipos: aplicadas.pular_tipos || [],
    rodizio: aplicadas.rodizio || null,
    agenda: {
      candidaturas: 'Loop contínuo — rodada a cada ~20min quando ocioso, backoff quando vazio'
    },
    contasCriadas: aplicadas.contas_criadas || {},
    // Historico completo, do mais novo para o mais antigo (o cliente corta o que exibir)
    events: events.slice(-400).reverse(),
    // Espelho cru do terminal para o painel "Terminal ao vivo".
    logTail: {
      candidaturas: tailOf([path.join(ROOT, 'loop.log.1'), path.join(ROOT, 'loop.log')], 80)
    },
    totals: {
      candidaturas: applied.length,
      bloqueios: blocked.length,
      eventos: events.length
    }
  };
}
