// monitor/snapshot.test.mjs — node:test nativo para o retrato agregado.
// Cria um diretorio de estado temporario (sem dado real) e valida:
// 1) modo aggregate (padrao): nenhum detalhe bruto sai;
// 2) modo details (opt-in): aplicadas/bloqueadas/eventos aparecem;
// 3) perfis isolados somam sem vazar conteudo entre si.
import { execFileSync } from 'node:child_process';
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

function makeRoot() {
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
  return root;
}

const runSnapshot = (root, includeDetails) => {
  const env = {
    ...process.env,
    CANDIDATURAS_ROOT: root,
    MONITOR_INCLUDE_DETAILS: includeDetails ? '1' : '0',
    MONITOR_TELEMETRY_MODE: 'aggregate',
    BOT_TZ: 'America/Sao_Paulo'
  };
  const code = [
    "import { buildSnapshot } from './monitor/snapshot.mjs';",
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
    assert.equal(s.telemetry.totals.bloqueios, 2);
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
