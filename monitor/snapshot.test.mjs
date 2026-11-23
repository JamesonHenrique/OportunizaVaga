// monitor/snapshot.test.mjs — node:test nativo para o retrato agregado.
// Cria um diretorio de estado temporario (sem dado real) e valida:
// 1) modo aggregate (padrao): nenhum detalhe bruto sai;
// 2) modo details (opt-in): aplicadas/bloqueadas/eventos aparecem;
// 3) perfis isolados somam sem vazar conteudo entre si.
import { execFile, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import http from 'node:http';
import { promisify } from 'node:util';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const REPO = path.resolve(HERE, '..');

const aplicada = (empresa, como) => ({
  chave: `${empresa}-chave`,
  empresa,
  vaga: 'Desenvolvedor Junior Remoto',
  remota: true,
  como,
  cv: 'CV_Exemplo.pdf',
  data: '2026-09-18',
  enviada_em: '2026-09-18T10:00:00-03:00'
});

const estado = (applied, blocked) => ({
  aplicadas: applied,
  bloqueados: blocked,
  bloqueados_arquivados: {},
  pular_empresas: [],
  pular_tipos: [],
  descartes_listagem: { nivel: 2, modelo: 1, stack: 1, total: 4 },
  descartes_listagem_total: 4,
  contas_criadas: { gupy: { email: 'exemplo@example.com' } },
  rodizio: { proximo: 'indeed', ultima_rodada: '2026-09-18' }
});

function makeRoot({ extras = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ov-snapshot-'));
  const hoje = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Sao_Paulo' });
  fs.mkdirSync(path.join(root, 'state', 'frontend'), { recursive: true });
  fs.writeFileSync(path.join(root, 'aplicadas.json'), JSON.stringify(estado([aplicada('Exemplo LTDA', 'Gupy')], { exemplo: { motivo: 'falta RG' } })));
  fs.writeFileSync(path.join(root, 'state', 'frontend', 'aplicadas.json'), JSON.stringify(estado([aplicada('Exemplo Front', 'LinkedIn')], { front: { motivo: 'falta CPF' } })));
  fs.writeFileSync(path.join(root, 'loop.log'), [
    `[${hoje} 10:00:00] rodada iniciada`,
    `[${hoje} 10:01:00] rodada ok, vaga nova processada, dormindo 20min`,
    `[${hoje} 10:21:00] modelo openrouter/nex-agi/nex-n2.5-pro:free no limite, cascateando para o proximo`
  ].join('\n') + '\n');
  if (extras) {
    // New optional inputs: Gmail replies in historico_status, login queue, discovery queue, Gmail summary.
    const doc = JSON.parse(fs.readFileSync(path.join(root, 'aplicadas.json'), 'utf8'));
    doc.aplicadas[0].status = 'etapa_teste';
    doc.aplicadas[0].historico_status = [{ de: 'enviada', para: 'etapa_teste', em: '2026-09-19T09:00:00-03:00', email_data: '2026-09-18', fonte: 'gmail' }];
    doc.aplicadas[0].como = 'Gupy https://exemplo.gupy.io/jobs/1234567 contato exemplo@example.com';
    doc.bloqueados.exemplo = { motivo: 'sessao expirada, telefone 11987654321', url: 'https://jobs.example.com/vaga/9' };
    doc.aguardando_login = { 'linkedin-x': { canal: 'linkedin', empresa: 'Exemplo LTDA', vaga: 'Dev Jr', score: 7, motivo: 'exige login', bloqueado_em: '2026-09-18T08:00:00-03:00' } };
    doc.login_checagens = { linkedin: { logado: 'nao', em: '2026-09-18T09:00:00-03:00' } };
    fs.writeFileSync(path.join(root, 'aplicadas.json'), JSON.stringify(doc));
    fs.writeFileSync(path.join(root, 'state', 'vagas_fila.json'), JSON.stringify({
      ultima_coleta: '2026-09-18T07:00:00-03:00', totais: { nivel: 3 }, stats: { lidas: 10, novas: 1 },
      vagas: { a: { status: 'nova', empresa: 'Exemplo LTDA', titulo: 'Dev Jr', fonte: 'gupy', url: 'https://jobs.example.com/vaga/1', score: 5 }, b: { status: 'enviada' } }
    }));
    fs.writeFileSync(path.join(root, 'state', 'gmail_status.json'), JSON.stringify({ atualizado: '2026-09-18T10:00:00-03:00', linhas_lidas: 50, achados: [{}, {}] }));
  }
  return root;
}

const runSnapshot = (root, includeDetails, overrides = {}, now) => {
  const env = {
    ...process.env,
    CANDIDATURAS_ROOT: root,
    MONITOR_INCLUDE_DETAILS: includeDetails ? '1' : '0',
    MONITOR_TELEMETRY_MODE: 'aggregate',
    BOT_TZ: 'America/Sao_Paulo',
    STATE_DIR: '', APLICADAS_FILE: '', BOT_PERFIL: '',
    ...overrides
  };
  const code = [
    "import { buildSnapshot } from './monitor/snapshot.mjs';",
    now ? `Date = class extends Date { constructor(...args) { super(...(args.length ? args : [${now}])); } static now() { return ${now}; } };` : "",
    "const s = buildSnapshot();",
    "console.log(JSON.stringify(s));"
  ].join('\n');
  return JSON.parse(execFileSync('node', ['--input-type=module', '-e', code], { cwd: REPO, env, encoding: 'utf8' }));
};

test('aggregate: nenhum detalhe bruto sai, mas perfis somam', () => {
  const root = makeRoot();
  try {
    const s = runSnapshot(root, false);
    assert.equal(s.applied, undefined);
    assert.equal(s.blocked, undefined);
    assert.equal(s.events, undefined);
    assert.equal(s.logTail, undefined);
    assert.equal(s.contasCriadas, undefined);
    assert.equal(s.telemetry.includeDetails, false);
    assert.equal(s.telemetry.totals.aplicadas, 2);
    assert.equal(s.telemetry.totals.enviosPendentes, 0);
    assert.equal(s.telemetry.totals.bloqueios, 2);
    assert.deepEqual(s.porDia, { '2026-09-18': 2 });
    assert.equal(s.telemetry.totals.descartes, 8);
    assert.equal(s.telemetry.perfis.length, 2);
    assert.deepEqual(s.telemetry.perfis.map(p => p.nome).sort(), ['default', 'frontend']);
    assert.equal(s.telemetry.porFonte.gupy, 1);
    assert.equal(s.telemetry.porFonte.linkedin, 1);
    assert.equal(s.publisher.host, undefined);
    assert.equal(s.publisher.pid, undefined);
    assert.equal(s.publisher.root, undefined);
    assert.equal(s.telemetry.modelos.noTetoHoje.length, 1);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('details opt-in: aplicadas e eventos aparecem', () => {
  const root = makeRoot();
  try {
    const s = runSnapshot(root, true);
    assert.equal(s.applied.length, 2);
    assert.equal(s.blocked.length, 2);
    assert.ok(s.events.length > 0);
    assert.ok(s.logTail.candidaturas.length > 0);
    assert.equal(s.telemetry.includeDetails, true);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('arquivos opcionais ausentes: sem fila, sem gmail, sem login -> campos nulos/vazios', () => {
  const root = makeRoot();
  try {
    const s = runSnapshot(root, true);
    assert.equal(s.descoberta, null);
    assert.equal(s.gmailStatus, null);
    assert.deepEqual(s.aguardandoLogin, []);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('arquivos opcionais corrompidos nao derrubam o retrato', () => {
  const root = makeRoot();
  try {
    fs.writeFileSync(path.join(root, 'state', 'vagas_fila.json'), '{nao e json');
    fs.writeFileSync(path.join(root, 'state', 'gmail_status.json'), '[1,2]');
    const s = runSnapshot(root, true);
    assert.equal(s.descoberta, null);
    assert.equal(s.gmailStatus, null);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('details: etapa_teste com email_data, fila de login, descoberta, gmail, links e sem PII', () => {
  const root = makeRoot({ extras: true });
  try {
    const s = runSnapshot(root, true);
    const teste = s.applied.find(a => a.status === 'etapa_teste');
    assert.ok(teste);
    assert.equal(teste.historico_status[0].para, 'etapa_teste');
    assert.equal(teste.historico_status[0].email_data, '2026-09-18');
    assert.equal(teste.url, 'https://exemplo.gupy.io/jobs/1234567');
    assert.equal(s.telemetry.porStatus.etapa_teste, 1);
    assert.match(teste.como, /\[e-mail\]/);
    assert.equal(JSON.stringify(s).includes('exemplo@example.com'), false);
    assert.equal(JSON.stringify(s).includes('11987654321'), false);
    assert.equal(s.aguardandoLogin.length, 1);
    assert.equal(s.aguardandoLogin[0].canal, 'linkedin');
    assert.equal(s.aguardandoLogin[0].checagem.logado, 'nao');
    assert.equal(s.blocked.find(b => b.chave === 'exemplo').url, 'https://jobs.example.com/vaga/9');
    assert.equal(s.descoberta.porStatus.nova, 1);
    assert.equal(s.descoberta.proximas.length, 1);
    assert.deepEqual(s.gmailStatus, { atualizado: '2026-09-18T10:00:00-03:00', lidas: 50, achados: 2 });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('aggregate: fila de login e vagas da descoberta nao saem, so contagens', () => {
  const root = makeRoot({ extras: true });
  try {
    const s = runSnapshot(root, false);
    assert.equal(s.aguardandoLogin, undefined);
    assert.equal(s.descoberta.proximas, undefined);
    assert.equal(s.descoberta.porStatus.nova, 1);
    assert.equal(s.telemetry.porStatus.etapa_teste, 1);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('linkDaVaga: campo explicito, URL no texto, id verificado e nunca chuta', async () => {
  const { linkDaVaga } = await import('./snapshot.mjs');
  assert.equal(linkDaVaga({ url: 'https://jobs.example.com/x1' }), 'https://jobs.example.com/x1');
  assert.equal(linkDaVaga({ motivo: 'ver https://jobs.example.com/x2).' }), 'https://jobs.example.com/x2');
  assert.equal(linkDaVaga({ como: 'LinkedIn vaga 4470852208' }), 'https://www.linkedin.com/jobs/view/4470852208/');
  assert.equal(linkDaVaga({ como: 'Gupy vaga 1234567' }), null);
  assert.equal(linkDaVaga({ url: 'https://www.linkedin.com/in/alguem' }), null);
});

test('buildSnapshot relê o estado a cada chamada (daemon de longa vida)', () => {
  const root = makeRoot();
  try {
    const env = { ...process.env, CANDIDATURAS_ROOT: root, MONITOR_INCLUDE_DETAILS: '0', BOT_TZ: 'America/Sao_Paulo' };
    // Same process, two calls, state changed in between: the second must see it.
    const code = [
      "import fs from 'node:fs';",
      "import { buildSnapshot } from './monitor/snapshot.mjs';",
      "const a = buildSnapshot().telemetry.totals.aplicadas;",
      `const f = ${JSON.stringify(path.join(root, 'aplicadas.json'))};`,
      "const doc = JSON.parse(fs.readFileSync(f, 'utf8'));",
      "doc.aplicadas.push({ ...doc.aplicadas[0], chave: 'nova-chave' });",
      "fs.writeFileSync(f, JSON.stringify(doc));",
      "console.log(JSON.stringify([a, buildSnapshot().telemetry.totals.aplicadas]));"
    ].join('\n');
    const [antes, depois] = JSON.parse(execFileSync('node', ['--input-type=module', '-e', code], { cwd: REPO, env, encoding: 'utf8' }));
    assert.equal(depois, antes + 1);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('portais: legacy state map and full evidence from each profile', () => {
  const root = makeRoot();
  try {
    fs.writeFileSync(path.join(root, 'saude_portais.json'), JSON.stringify({ portais: { gupy: { estado: 'funcionando', evidencia: 'sonda ok' } } }));
    fs.writeFileSync(path.join(root, 'state', 'frontend', 'saude_portais.json'), JSON.stringify({ portais: { indeed: { estado: 'indisponivel', evidencia: 'Verify you are human' } } }));
    const s = runSnapshot(root, false);
    assert.deepEqual(s.portais, { gupy: 'funcionando', indeed: 'indisponivel' });
    assert.deepEqual(s.saudePortais.indeed, {
      state: 'indisponivel', evidence: 'Verify you are human', checkedAt: null, reason: null
    });
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('profiles: queues without application history merge and portal health keeps newer evidence', t => {
  const root = makeRoot();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const active = path.join(root, 'custom', 'active');
  fs.mkdirSync(active, { recursive: true });
  const write = (dir, file, data) => fs.writeFileSync(path.join(dir, file), JSON.stringify(data));
  write(active, 'vagas_fila.json', { ultima_coleta: '2026-09-19T10:00:00-03:00', vagas: { a: { status: 'nova' } } });
  write(path.join(root, 'state', 'frontend'), 'vagas_fila.json', {
    ultima_coleta: '2026-09-18T10:00:00-03:00', vagas: { a: { status: 'expirada' }, b: { status: 'processada' } }
  });
  write(active, 'saude_portais.json', { portais: { gupy: {
    state: 'funcionando', checkedAt: '2026-09-19T09:00:00-03:00', evidence: 'sonda ok', reason: 'sucesso'
  } } });
  write(path.join(root, 'state', 'frontend'), 'saude_portais.json', {
    atualizado: '2026-09-20T11:00:00-03:00',
    portais: { gupy: { estado: 'indisponivel', em: '2026-09-19T11:00:00Z', evidencia: 'sonda antiga' } }
  });
  const s = runSnapshot(root, false, { STATE_DIR: active });
  assert.deepEqual(s.descoberta.porStatus, { nova: 1, processada: 1 });
  assert.deepEqual(s.saudePortais.gupy, {
    state: 'funcionando', evidence: 'sonda ok', checkedAt: '2026-09-19T09:00:00-03:00', reason: 'sucesso'
  });
  assert.equal(s.portais.gupy, 'funcionando');
});

test('profile file resolves the same slug as bot and default side files are read at the root', t => {
  const root = makeRoot();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const profile = path.join(root, 'profile-fixture.json');
  fs.writeFileSync(profile, JSON.stringify({ nome_perfil: 'Perfil Ágil #42' }));
  const stateDir = path.join(root, 'state', 'perfil-gil-42');
  fs.mkdirSync(stateDir);
  fs.writeFileSync(path.join(stateDir, 'vagas_fila.json'), JSON.stringify({ vagas: { a: { status: 'nova' } } }));
  fs.writeFileSync(path.join(root, 'vagas_fila.json'), JSON.stringify({ vagas: { b: { status: 'processada' } } }));
  assert.deepEqual(runSnapshot(root, false, { BOT_PERFIL: profile }).descoberta.porStatus, { nova: 1, processada: 1 });
});

test('rounds and full model IDs follow the configured day across UTC midnight', t => {
  const root = makeRoot();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const model = 'openrouter/nex-agi/nex-n2.5-pro:free';
  fs.writeFileSync(path.join(root, 'loop.log'), [
    '[2026-09-18 23:30:00] rodada iniciada',
    `[2026-09-18 23:31:00] modelo ${model} no limite, cascateando para o proximo`,
    '[2026-09-19 00:01:00] rodada iniciada',
    `[2026-09-19 00:02:00] modelo ${model} no limite, cascateando para o proximo`,
    `[2026-09-19 00:03:00] rodada usou o modelo ${model}`,
  ].join('\n'));
  const s = runSnapshot(root, false, {}, Date.parse('2026-09-19T03:05:00Z'));
  assert.equal(s.loops.candidaturas.rodadasHoje, 1);
  assert.equal(s.modelos.emUso, model);
  assert.deepEqual(s.modelos.noTetoHoje, [model]);
  assert.equal(s.modelos.escada.find(entry => entry.id === model).tetoHoje, 1);
});

test('details reads only the tail of a log with hundreds of thousands of lines', t => {
  const root = makeRoot();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, 'loop.log'), 'irrelevant old line\n'.repeat(250000) + 'synthetic last line\n');
  const { candidaturas } = runSnapshot(root, true).logTail;
  assert.equal(candidaturas.length, 80);
  assert.equal(candidaturas.at(-1), 'synthetic last line');
});

test('the one-shot publisher authenticates and sends a valid snapshot to a local HTTP endpoint', async t => {
  const root = makeRoot();
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const requests = [];
  const server = http.createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    requests.push({
      method: request.method, url: request.url, secret: request.headers['x-monitor-secret'],
      snapshot: JSON.parse(Buffer.concat(chunks))
    });
    response.writeHead(request.headers['x-monitor-secret'] === 'synthetic-publisher' ? 200 : 401).end();
  });
  server.listen(0, '127.0.0.1');
  t.after(() => new Promise(resolve => server.close(resolve)));
  await once(server, 'listening');
  const env = {
    ...process.env,
    MONITOR_URL: `http://127.0.0.1:${server.address().port}/`,
    MONITOR_SECRET: 'synthetic-publisher',
    MONITOR_INGEST_SECRET: '',
    CANDIDATURAS_ROOT: root,
    STATE_DIR: '', APLICADAS_FILE: '', BOT_PERFIL: '',
    HTTP_PROXY: '', HTTPS_PROXY: '', ALL_PROXY: '', http_proxy: '', https_proxy: '', all_proxy: '',
    NO_PROXY: '127.0.0.1'
  };
  await promisify(execFile)(process.execPath, ['monitor/publish-once.mjs'], { cwd: REPO, env, timeout: 5000 });
  assert.equal(requests.length, 1);
  const [request] = requests;
  assert.equal(request.method, 'POST');
  assert.equal(request.url, '/api/status');
  assert.equal(request.secret, 'synthetic-publisher');
  assert.ok(Number.isFinite(Date.parse(request.snapshot.builtAt)));
  assert.equal(request.snapshot.totals.candidaturas, 2);
});
