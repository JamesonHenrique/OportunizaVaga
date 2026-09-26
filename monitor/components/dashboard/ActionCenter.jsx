'use client';

import { CheckCircle2 } from 'lucide-react';

// "Precisa de você": only what needs a human, most severe first.
// Each item: { id, tom: 'bad'|'warn'|'info', titulo, sub, acao?: { rotulo, aba } }.
export default function ActionCenter({ itens, abrirAba }) {
  return (
    <section className="card action-center" aria-label="Precisa de você">
      <p className="card-label">Precisa de você{itens.length ? ` · ${itens.length}` : ''}</p>
      {itens.length ? (
        <ul className="todo">
          {itens.map(it => (
            <li key={it.id} className={`todo-${it.tom}`}>
              <span className="sev" aria-hidden="true" />
              <span className="todo-txt"><b>{it.titulo}</b>{it.sub && <small>{it.sub}</small>}</span>
              {it.acao && <button type="button" className="btn-ghost" onClick={() => abrirAba(it.acao.aba)}>{it.acao.rotulo}</button>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="all-ok"><CheckCircle2 className="ico" aria-hidden="true" />Nada pendente. O robô segue sozinho.</p>
      )}
    </section>
  );
}
