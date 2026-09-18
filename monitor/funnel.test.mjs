// monitor/funnel.test.mjs — teste node:test nativo (sem deps) de monitor/funnel.mjs.
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { computaFunil } from './funnel.mjs';

describe('computaFunil', () => {
  it('estado vazio zera tudo sem dividir por zero', () => {
    const r = computaFunil({ aplicadas: [], bloqueados: {}, descartes_listagem: { total: 0 } });
    assert.equal(r.vistas, 0);
    assert.equal(r.aplicadas, 0);
    assert.equal(r.respostas, 0);
    assert.equal(r.taxas.vistasParaAplicadas, 0);
    assert.equal(r.taxas.aplicadasParaRespostas, 0);
  });

  it('vistas = descartes + aplicadas + bloqueadas; taxas em %', () => {
    const r = computaFunil({
      aplicadas: [
        { chave: 'a1', status: 'enviada' },
        { chave: 'a2', status: 'enviada' },
        { chave: 'a3', status: 'entrevista' },
        { chave: 'a4', status: 'enviada', respondida_em: '2026-09-18' },
      ],
      bloqueados: { b1: {}, b2: {} },
      descartes_listagem: { nivel: 4, modelo: 3, stack: 3, total: 10 },
    });
    assert.equal(r.vistas, 16);
    assert.equal(r.aplicadas, 4);
    assert.equal(r.respostas, 2);
    assert.equal(r.taxas.vistasParaAplicadas, 25);
    assert.equal(r.taxas.aplicadasParaRespostas, 50);
  });

  it('descartes sem total soma os campos numericos', () => {
    const r = computaFunil({
      aplicadas: [{ chave: 'a1' }],
      bloqueados: {},
      descartes_listagem: { nivel: 2, modelo: 1, stack: 1 },
    });
    assert.equal(r.vistas, 5);
    assert.equal(r.aplicadas, 1);
  });

  it('enviada sem respondida_em/desfecho nao conta como resposta; desfecho conta', () => {
    const r = computaFunil({
      aplicadas: [
        { chave: 'a1', status: 'enviada' },
        { chave: 'a2', status: 'enviada', desfecho: 'entrevista' },
      ],
      bloqueados: {},
      descartes_listagem: { total: 0 },
    });
    assert.equal(r.respostas, 1);
  });
});
