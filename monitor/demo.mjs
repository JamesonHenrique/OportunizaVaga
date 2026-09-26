// monitor/demo.mjs — FICTIONAL snapshot for the public demo (MONITOR_DEMO=1),
// the Docker demo and the README GIF. Every company, job and log line here is
// invented. Dates are relative to `now`, so the demo never goes stale.
// Deterministic (seeded) so the same day always renders the same numbers.

const TZ = process.env.BOT_TZ || 'America/Sao_Paulo';

function rng(seed) {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

const EMPRESAS = [
  'Nimbus Tecnologia', 'Cajueiro Labs', 'Vento Sul Software', 'Pitanga Pay', 'Arvoredo Sistemas',
  'Maré Digital', 'Ipê Cloud', 'Farol Dados', 'Carnaúba Tech', 'Seriguela Apps', 'Mandacaru Soluções',
  'Jangada Fintech', 'Baobá Saúde Digital', 'Cerrado Logística', 'Aroeira Educação'
];
const VAGAS = [
  'Desenvolvedor(a) Backend Júnior', 'Desenvolvedor(a) Full Stack Júnior', 'Desenvolvedor(a) Java Júnior',
  'Desenvolvedor(a) Node.js Júnior', 'Desenvolvedor(a) Front-end Júnior (Angular)', 'Analista de Automação RPA Júnior',
  'Desenvolvedor(a) Python Júnior', 'Engenheiro(a) de Software Trainee'
];
const CANAIS = [
  ['gupy', 'Gupy via Google'], ['linkedin', 'LinkedIn Candidatura Simplificada'], ['indeed', 'Indeed Candidatura Fácil'],
  ['email', 'e-mail via Gmail'], ['remotar', 'Remotar via Inhire'], ['outro', 'site da empresa (Greenhouse)']
];
const SITES = ['gupy', 'linkedin', 'indeed', 'programathor', 'remotar', 'geekhunter', 'infojobs', 'catho'];
const MODELOS = [
  'openrouter/nex-agi/nex-n2.5-pro:free', 'opencode/muse-spark-1.3-contributor-free',
  'opencode/nemotron-3-ultra-free', 'groq/openai/gpt-oss-120b', 'cerebras/gpt-oss-120b'
];

const ymd = (ms) => new Date(ms).toLocaleDateString('sv-SE', { timeZone: TZ });
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];

export function buildDemoSnapshot(now = Date.now()) {
  const hoje = ymd(now);
  const r = rng(Number(hoje.replaceAll('-', '')));
  const DAY = 86400000;

  // 14 days of applications, today included (today is always a good day in the demo).
  const applied = [];
  for (let i = 13; i >= 0; i--) {
    const n = i === 0 ? 4 : Math.floor(r() * 5);
    for (let k = 0; k < n; k++) {
      const quando = new Date(now - i * DAY - Math.floor(r() * 8) * 3600000 - k * 1500000);
      if (quando.getTime() > now) continue;
      const [fonte, via] = pick(r, CANAIS);
      const empresa = pick(r, EMPRESAS);
      applied.push({
        chave: `demo-${applied.length}`, empresa, vaga: `${pick(r, VAGAS)} (remoto)`, remota: true,
        como: via, data: ymd(quando.getTime()), quando: quando.toISOString(), exato: true,
        fonte, via: null, status: 'enviada'
      });
    }
  }
  applied.sort((a, b) => a.quando.localeCompare(b.quando));

  const em = (h) => new Date(now - h * 3600000).toISOString();
  const blocked = [
    { chave: 'farol_dados_node_jr', empresa: 'Farol Dados', motivo: 'Cadastro quebrado: ATS pede CPF antes do envio (dado ausente em dados_candidato.json).', em: em(5) },
    { chave: 'ipe_cloud_backend_jr', empresa: 'Ipê Cloud', motivo: 'Descartada: título oficial Pleno (regra 3 · nível).', em: em(9) },
    { chave: 'mare_digital_react_jr', empresa: 'Maré Digital', motivo: 'Descartada: React obrigatório sem evidência nos dados (regra 4).', em: em(20) },
    { chave: 'jangada_fintech_java_jr', empresa: 'Jangada Fintech', motivo: 'Vaga presencial em São Paulo (regra 1 · não-remoto).', em: em(30) },
    { chave: 'aroeira_python_trainee', empresa: 'Aroeira Educação', motivo: 'Formulário pede o dado "CR (coeficiente)".', em: em(44) },
    { chave: 'cerrado_rpa_jr', empresa: 'Cerrado Logística', motivo: 'Canal travado no redirecionamento; causa vencida, retomar.', em: em(52), retentar: 'retomar na próxima rodada' }
  ];

  const events = [];
  let t = now - 6 * 3600000;
  let rodadasHoje = 0;
  while (t < now - 60000) {
    const m = pick(r, MODELOS);
    events.push({ at: new Date(t).toISOString(), source: 'candidaturas', text: `rodada iniciada · modelo ${m}`, kind: 'rodada', severity: 'info' });
    if (r() < 0.25) events.push({ at: new Date(t + 40000).toISOString(), source: 'candidaturas', text: `modelo ${m} no limite, cascateando para o proximo`, kind: 'cascata', severity: 'warn' });
    events.push({ at: new Date(t + 9 * 60000).toISOString(), source: 'candidaturas', text: r() < 0.4 ? 'rodada ok, 1 candidatura enviada' : 'rodada ok, nada novo compatível', kind: 'ok', severity: 'ok' });
    if (ymd(t) === hoje) rodadasHoje++;
    t += (18 + Math.floor(r() * 10)) * 60000;
  }
  const ultimo = events.at(-1)?.at || new Date(now).toISOString();

  const hhmm = (iso) => new Date(iso).toLocaleTimeString('pt-BR', { timeZone: TZ, hour12: false });
  const logTail = events.slice(-14).map(e => `[${hhmm(e.at)}] ${e.text}`);

  const porFonte = {};
  for (const a of applied) porFonte[a.fonte] = (porFonte[a.fonte] || 0) + 1;
  const porDia = {};
  for (const a of applied) porDia[a.data] = (porDia[a.data] || 0) + 1;
  const aplicadas7d = applied.filter(a => new Date(a.quando).getTime() > now - 7 * DAY).length;
  const rodadas7d = 52 + Math.floor(r() * 12);
  const descartes = { nivel: 412, modelo: 138, stack: 96, total: 646 };
  const perfis = [{ nome: 'backend', aplicadas: applied.length, bloqueados: blocked.length, descartes: descartes.total, rodizio: 'gupy', ativo: true }];

  return {
    updatedAtLocal: new Date(now).toLocaleString('pt-BR', { timeZone: TZ }),
    builtAt: new Date(now).toISOString(),
    publisher: { mode: 'demo', version: '1.0.0' },
    tz: TZ,
    hoje,
    modelos: {
      emUso: MODELOS[1], desde: em(1),
      noTetoHoje: [MODELOS[0]],
      escada: MODELOS.map((id, i) => ({ id, tier: id.split('/')[0], tetoHoje: i === 0 ? 3 : 0 })),
      openrouterQuota: null, quotaMotivo: 'demo: sem cota real'
    },
    loops: {
      candidaturas: {
        state: 'dormindo', message: 'rodada ok, dormindo 20min',
        proximaEm: new Date(now + 14 * 60000).toISOString(), ultimoEvento: ultimo,
        rodadasHoje, duracao: { ultimaMin: 9, mediaMin: 11.5, amostras: 40 }
      }
    },
    applied,
    porFonte,
    porDia,
    porStatus: { enviada: applied.length },
    blocked,
    dadosFaltantes: [{ campo: 'CR (coeficiente)', vagas: 1 }, { campo: 'CPF', vagas: 1 }],
    descartes,
    rodizio: { ordem: SITES, proximo: 'programathor' },
    rodizioSaude: {
      sites: Object.fromEntries(SITES.map((s, i) => [s, {
        rodadas: 3 + (i % 4), vazias_seguidas: s === 'catho' ? 4 : i % 2, aplicadas: Math.max(0, 5 - i),
        pausado_ate: s === 'catho' ? new Date(now + 36 * 3600000).toISOString() : null
      }]))
    },
    rendimento: { rodadas7d, aplicadas7d, rodadasPorCandidatura: Math.round((rodadas7d / Math.max(1, aplicadas7d)) * 10) / 10 },
    agenda: { candidaturas: 'Loop contínuo — rodada a cada ~20min quando ocioso' },
    events: events.reverse(),
    logTail: { candidaturas: logTail },
    totals: { candidaturas: applied.length, bloqueios: blocked.length, eventos: events.length },
    telemetry: { version: 1, mode: 'demo', includeDetails: true, perfis, totals: { aplicadas: applied.length, bloqueios: blocked.length, descartes: descartes.total, rodadasHoje } }
  };
}
