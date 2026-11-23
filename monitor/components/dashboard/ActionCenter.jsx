'use client';

import { CheckCircle2, Check, OctagonAlert, TriangleAlert, Info, UserRound, RefreshCw } from 'lucide-react';
import { desde } from '@/lib/dashboard';
import { StaleBadge } from './ui';

// Severity groups, most urgent first. Only the first three need a human and count toward "Precisa de você".
export const GRUPOS = {
  critico: { ordem: 0, rotulo: 'Crítico', icone: OctagonAlert, humano: true },
  voce: { ordem: 1, rotulo: 'Precisa de você', icone: TriangleAlert, humano: true },
  dados: { ordem: 2, rotulo: 'Dado do candidato', icone: UserRound, humano: true },
  retry: { ordem: 3, rotulo: 'Robô tenta de novo', icone: RefreshCw, humano: false },
  info: { ordem: 4, rotulo: 'Informativo', icone: Info, humano: false },
};
export const precisaHumano = (it) => Boolean(GRUPOS[it.grupo]?.humano);

function Item({ it, abrirAba, onFeito }) {
  const g = GRUPOS[it.grupo] || GRUPOS.info;
  const Ico = g.icone;
  return (
    <li className={`todo todo-${it.grupo}`}>
      <span className="sev"><Ico className="ico" aria-hidden="true" /><span>{g.rotulo}</span></span>
      <div className="todo-txt">
        <b>{it.titulo}</b>
        {it.porque && <p><span className="todo-k">Por que importa:</span> {it.porque}</p>}
        {it.proximo && <p><span className="todo-k">Próximo passo:</span> {it.proximo}</p>}
        {it.feitos?.length > 0 && onFeito && (
          <span className="feitos">{it.feitos.map(f => (
            <button key={f.chave} type="button" className="btn-ghost btn-feito" onClick={() => onFeito(f.chave)}>
              <Check className="ico" aria-hidden="true" />Marcar {f.empresa} como feito
            </button>
          ))}</span>
        )}
      </div>
      {it.acao && <button type="button" className="btn-ghost" onClick={() => abrirAba(it.acao.aba)}>{it.acao.rotulo}</button>}
    </li>
  );
}

// "Precisa de você": what happened / why it matters / next step, grouped by severity.
// Each item: { id, grupo: keyof GRUPOS, titulo, porque?, proximo?, acao?: { rotulo, aba } }.
export default function ActionCenter({ itens, abrirAba, resolvidos = [], agora = Date.now(), onFeito, obsoleto }) {
  const ordenados = itens.map((it, i) => [it, i])
    .sort((a, b) => (GRUPOS[a[0].grupo]?.ordem ?? 9) - (GRUPOS[b[0].grupo]?.ordem ?? 9) || a[1] - b[1])
    .map(([it]) => it);
  const humanos = ordenados.filter(precisaHumano);
  const sozinho = ordenados.filter(it => !precisaHumano(it));
  const criticos = humanos.filter(it => it.grupo === 'critico').length;
  return (
    <section className="card action-center" aria-labelledby="action-title">
      <div className="card-head">
        <h2 id="action-title">
          Precisa de você
          <span className={`count${criticos ? ' is-alert' : ''}`}>
            {humanos.length}<span className="sr-only"> {humanos.length === 1 ? 'item' : 'itens'}{criticos ? `, ${criticos} crítico(s)` : ''}</span>
          </span>
        </h2>
        {obsoleto && <StaleBadge tipo={obsoleto} />}
      </div>
      {humanos.length ? (
        <ul className="todo-list">{humanos.map(it => <Item key={it.id} it={it} abrirAba={abrirAba} onFeito={onFeito} />)}</ul>
      ) : (
        <div className="all-ok">
          <CheckCircle2 className="ico" aria-hidden="true" />
          <b>Nada depende de você agora</b>
          <small>Logins pendentes, dados faltantes e respostas de empresas aparecem aqui.</small>
        </div>
      )}
      {sozinho.length > 0 && (
        <details className="todo-more">
          <summary>O robô resolve sozinho · {sozinho.length}</summary>
          <ul className="todo-list">{sozinho.map(it => <Item key={it.id} it={it} abrirAba={abrirAba} onFeito={onFeito} />)}</ul>
        </details>
      )}
      {resolvidos.length > 0 && (
        <>
          <p className="resolved-label">Resolvido nas últimas 24h · {resolvidos.length}</p>
          <ul className="todo-list">
            {resolvidos.map(r => (
              <li key={r.id} className="todo todo-ok">
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
