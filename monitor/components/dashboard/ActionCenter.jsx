'use client';

import { CheckCircle2, Check, OctagonAlert, TriangleAlert, Info } from 'lucide-react';
import { desde } from '@/lib/dashboard';

const ORDEM = { bad: 0, warn: 1, info: 2 };
const ICONE = { bad: OctagonAlert, warn: TriangleAlert, info: Info };
const ROTULO_TOM = { bad: 'Crítico', warn: 'Atenção', info: 'Informativo' };

// "Precisa de você": only what needs a human, most severe first (stable within a tone).
// Each item: { id, tom: 'bad'|'warn'|'info', titulo, sub, acao?: { rotulo, aba } }.
export default function ActionCenter({ itens, abrirAba, resolvidos = [], agora = Date.now(), onFeito }) {
  const ordenados = itens.map((it, i) => [it, i])
    .sort((a, b) => (ORDEM[a[0].tom] ?? 3) - (ORDEM[b[0].tom] ?? 3) || a[1] - b[1])
    .map(([it]) => it);
  const criticos = itens.filter(it => it.tom === 'bad').length;
  return (
    <section className="card action-center" aria-labelledby="action-title">
      <div className="card-head">
        <h2 id="action-title">Precisa de você?</h2>
        {itens.length > 0 && (
          <span className={`count${criticos ? ' is-alert' : ''}`}
                title={criticos ? `${criticos} crítico(s) de ${itens.length}` : `${itens.length} item(ns)`}>{itens.length}</span>
        )}
      </div>
      {ordenados.length ? (
        <ul className="todo">
          {ordenados.map(it => {
            const Ico = ICONE[it.tom] || Info;
            return (
              <li key={it.id} className={`todo-${it.tom}`}>
                <span className="sev" title={ROTULO_TOM[it.tom]}>
                  <Ico className="ico" aria-hidden="true" /><span className="sr-only">{ROTULO_TOM[it.tom]}:</span>
                </span>
                <span className="todo-txt"><b>{it.titulo}</b>{it.sub && <small>{it.sub}</small>}
                  {it.feitos?.length > 0 && onFeito && (
                    <span className="feitos">{it.feitos.map(f => (
                      <button key={f.chave} type="button" className="btn-ghost btn-feito" title={`Marcar ${f.empresa} como feito`}
                        onClick={() => onFeito(f.chave)}><Check className="ico" aria-hidden="true" />{f.empresa}</button>
                    ))}</span>
                  )}
                </span>
                {it.acao && <button type="button" className="btn-ghost" onClick={() => abrirAba(it.acao.aba)}>{it.acao.rotulo}</button>}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="all-ok">
          <CheckCircle2 className="ico" aria-hidden="true" />
          <b>Nada pendente</b>
          <small>O robô segue sozinho. Bloqueios e respostas de empresas aparecem aqui.</small>
        </div>
      )}
      {resolvidos.length > 0 && (
        <>
          <p className="resolved-label">Resolvido nas últimas 24h · {resolvidos.length}</p>
          <ul className="todo">
            {resolvidos.map(r => (
              <li key={r.id} className="todo-ok">
                <CheckCircle2 className="ico" aria-hidden="true" />
                <span className="todo-txt"><b>{r.titulo}</b><small>{desde(r.em, agora)}</small></span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
