'use client';

// Tab bar for the detail area. Panel content is rendered by the parent
// (only the active tab), so hidden tabs cost nothing.
export default function DetailTabs({ abas, ativa, onChange }) {
  const mover = (e, i) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const j = (i + (e.key === 'ArrowRight' ? 1 : -1) + abas.length) % abas.length;
    onChange(abas[j].id);
    document.getElementById(`tab-${abas[j].id}`)?.focus();
  };
  return (
    <div className="tabs" role="tablist" aria-label="Detalhes">
      {abas.map((a, i) => (
        <button key={a.id} id={`tab-${a.id}`} role="tab" type="button"
                aria-selected={ativa === a.id} tabIndex={ativa === a.id ? 0 : -1}
                className={`tab ${ativa === a.id ? 'on' : ''}`}
                onClick={() => onChange(a.id)} onKeyDown={(e) => mover(e, i)}>
          {a.rotulo}{a.conta != null && <em>{a.conta}</em>}
          {a.alerta && <span className="tab-dot" aria-label="tem pendência" />}
        </button>
      ))}
    </div>
  );
}
