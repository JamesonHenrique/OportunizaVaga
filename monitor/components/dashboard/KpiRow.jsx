'use client';

import { ArrowRight } from 'lucide-react';

// itens: [{ rotulo, valor, sub?, dica?, icone? (lucide), ponto? ('lime'|'cobalt'|'coral'), destaque?, ir? () => void }]
// `destaque` cards form the large first row; the rest render as a compact secondary row.
function Kpi({ k }) {
  const Ico = k.icone;
  const corpo = (
    <>
      <div className="kpi-top">
        {k.ponto && <i className={`kpi-dot is-${k.ponto}`} aria-hidden="true" />}
        <span className="card-label">{k.rotulo}</span>
        {!k.ponto && Ico && <Ico className="ico" aria-hidden="true" />}
      </div>
      <strong>{k.valor}</strong>
      <div className="kpi-foot">
        {k.sub && <small>{k.sub}</small>}
        {k.ir && <ArrowRight className="ico kpi-go" aria-hidden="true" />}
      </div>
    </>
  );
  const cls = `kpi${k.destaque ? ' kpi-main' : ''}`;
  return k.ir
    ? <button type="button" className={`${cls} is-link`} title={k.dica || ''} onClick={k.ir}>{corpo}</button>
    : <article className={cls} title={k.dica || ''}>{corpo}</article>;
}

export default function KpiRow({ itens }) {
  const main = itens.filter(k => k.destaque);
  const resto = itens.filter(k => !k.destaque);
  return (
    <section className="kpis" aria-label="Indicadores">
      {main.length > 0 && <div className="kpis-main">{main.map(k => <Kpi key={k.rotulo} k={k} />)}</div>}
      {resto.length > 0 && <div className="kpis-sub">{resto.map(k => <Kpi key={k.rotulo} k={k} />)}</div>}
    </section>
  );
}
