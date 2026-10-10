'use client';

// itens: [{ rotulo, valor, sub?, dica?, icone? (lucide component) }]
export default function KpiRow({ itens }) {
  return (
    <section className="kpis" aria-label="Indicadores">
      {itens.map(k => {
        const Ico = k.icone;
        return (
          <article key={k.rotulo} className="card kpi" title={k.dica || ''}>
            <div className="kpi-top">
              <span className="card-label">{k.rotulo}</span>
              {Ico && <Ico className="ico" aria-hidden="true" />}
            </div>
            <strong>{k.valor}</strong>
            {k.sub && <small>{k.sub}</small>}
          </article>
        );
      })}
    </section>
  );
}
