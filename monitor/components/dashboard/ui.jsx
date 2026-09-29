'use client';

// Shared building blocks so every tab speaks the same visual language as Bloqueios:
// segmented filter (Seg), clickable count chips with proportional fill (Chips),
// stat tiles (Tiles) and a pager. Styling lives in globals.css (.seg, .cause-chips, .tiles).

export function Seg({ opcoes, valor, onChange, rotulo }) {
  return (
    <div className="seg" role="tablist" aria-label={rotulo}>
      {opcoes.map(({ id, rotulo: r, conta, tom }) => (
        <button key={id} type="button" role="tab" aria-selected={valor === id}
                className={`seg-btn${tom ? ` seg-${tom}` : ''}${valor === id ? ' is-on' : ''}`} onClick={() => onChange(id)}>
          {r}{conta != null && <span>{conta}</span>}
        </button>
      ))}
    </div>
  );
}

// itens: [[label, n]]; ativo: selected label or null; clicking the active chip clears it.
export function Chips({ itens, ativo, onChange, rotulo }) {
  if (!itens.length) return null;
  const max = Math.max(1, ...itens.map(([, n]) => n));
  return (
    <div className="cause-chips" aria-label={rotulo}>
      {itens.map(([c, n]) => (
        <button key={c} type="button" aria-pressed={ativo === c}
                className={`cause-chip${ativo === c ? ' is-on' : ''}`} onClick={() => onChange(ativo === c ? null : c)}>
          <span className="cause-bar" style={{ width: `${Math.max(6, (n / max) * 100)}%` }} aria-hidden="true" />
          <span className="cause-lbl">{c}</span>
          <b>{n}</b>
        </button>
      ))}
    </div>
  );
}

// itens: [{ rotulo, valor, sub?, tom? ('ok'|'warn'|'bad'|'info') }]
export function Tiles({ itens }) {
  return (
    <div className="tiles">
      {itens.map(t => (
        <div key={t.rotulo} className={`tile${t.tom ? ` tile-${t.tom}` : ''}`} title={t.dica || ''}>
          <span className="tile-lbl">{t.rotulo}</span>
          <b className="tile-val">{t.valor}</b>
          {t.sub && <small className="tile-sub">{t.sub}</small>}
        </div>
      ))}
    </div>
  );
}

export function Pager({ pagina, total, onChange }) {
  if (total <= 1) return null;
  return (
    <div className="pager">
      <button onClick={() => onChange(Math.max(1, pagina - 1))} disabled={pagina <= 1} aria-label="Página anterior">‹</button>
      <span>{pagina} / {total}</span>
      <button onClick={() => onChange(Math.min(total, pagina + 1))} disabled={pagina >= total} aria-label="Próxima página">›</button>
    </div>
  );
}

export function Busca({ valor, onChange, placeholder, nome }) {
  return (
    <div className="search-row">
      <input value={valor} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
             aria-label={placeholder} name={nome} autoComplete="off" />
    </div>
  );
}

// Paginates a list, clamping the page when the list shrinks (never a blank page).
export function paginar(lista, pagina, porPagina) {
  const total = Math.max(1, Math.ceil(lista.length / porPagina));
  const atual = Math.min(pagina, total);
  return { itens: lista.slice((atual - 1) * porPagina, atual * porPagina), atual, total };
}
