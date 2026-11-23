'use client';

import { ArrowRight } from 'lucide-react';
import { StaleBadge } from './ui';

// Four non-redundant KPIs. itens: [{ id, rotulo, valor, sub?, dica?, ponto? ('lime'|'cobalt'|'coral'), tom?, ir? () => void }]
// `valor` may be '—' when the payload does not carry the data (aggregate / public mode): never a fake 0.
function Kpi({ k, obsoleto }) {
  const corpo = (
    <>
      <span className="kpi-top">
        {k.ponto && <i className={`kpi-dot is-${k.ponto}`} aria-hidden="true" />}
        <span className="card-label">{k.rotulo}</span>
        {obsoleto && <StaleBadge tipo={obsoleto} />}
      </span>
      <strong className={k.tom ? `is-${k.tom}` : undefined}>{k.valor}</strong>
      <span className="kpi-foot">
        {k.sub && <small>{k.sub}</small>}
        {k.ir && <ArrowRight className="ico kpi-go" aria-hidden="true" />}
      </span>
    </>
  );
  return k.ir
    ? <button type="button" className="kpi is-link" title={k.dica || undefined} onClick={k.ir}>{corpo}</button>
    : <article className="kpi" title={k.dica || undefined}>{corpo}</article>;
}

export default function KpiRow({ itens, obsoleto }) {
  return (
    <section className="kpis" aria-label="Indicadores">
      {itens.map(k => <Kpi key={k.id || k.rotulo} k={k} obsoleto={obsoleto} />)}
    </section>
  );
}
