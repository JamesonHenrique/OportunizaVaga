'use client';

export default function KpiRow({ itens }) {
  return (
    <section className="kpis">
      {itens.map(k => (
        <article key={k.rotulo} className="card kpi" title={k.dica || ''}>
          <span className="card-label">{k.rotulo}</span>
          <strong>{k.valor}</strong>
          {k.sub && <small>{k.sub}</small>}
        </article>
      ))}
    </section>
  );
}
