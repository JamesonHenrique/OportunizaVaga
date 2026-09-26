// Horizontal proportional bars (rankings) and daily sparkbars.

export function Barras({ itens, tom = 'warn' }) {
  const max = Math.max(1, ...itens.map(([, n]) => n));
  if (!itens.length) return <p className="empty-inline">sem dados</p>;
  return (
    <div className="bars">
      {itens.map(([rotulo, n]) => (
        <div className="bar-row" key={rotulo}>
          <span className="bar-label" title={rotulo}>{rotulo}</span>
          <span className="bar-track"><span className={`bar-fill ${tom}`} style={{ width: `${(n / max) * 100}%` }} /></span>
          <span className="bar-num">{n}</span>
        </div>
      ))}
    </div>
  );
}

// Compact inline sparkline for KPI cards — no day labels, tighter gaps.
export function SparklineMini({ dados }) {
  const max = Math.max(1, ...dados.map(([, n]) => n));
  if (!dados.length) return null;
  return (
    <div className="spark-mini" role="img" aria-label={`Envios por dia: ${dados.map(([d, n]) => `${d} ${n}`).join(', ')}`}>
      {dados.map(([dia, n]) => (
        <span key={dia} className="spark-mini-bar" style={{ height: `${Math.max(8, (n / max) * 100)}%` }} title={`${dia}: ${n}`} />
      ))}
    </div>
  );
}

// Mini vertical bars for time series (applications per day). `dados`: [[YYYY-MM-DD, n]].
export function Sparkbars({ dados }) {
  const max = Math.max(1, ...dados.map(([, n]) => n));
  if (!dados.length) return <p className="empty-inline">sem envios ainda</p>;
  return (
    <div className="spark" role="img" aria-label={`Envios por dia: ${dados.map(([d, n]) => `${d} ${n}`).join(', ')}`}>
      {dados.map(([dia, n]) => (
        <span className="spark-col" key={dia} title={`${dia.slice(8)}/${dia.slice(5, 7)}: ${n} envio${n > 1 ? 's' : ''}`}>
          <span className="spark-bar" style={{ height: `${Math.max(8, (n / max) * 100)}%` }} />
          <span className="spark-day">{dia.slice(8)}</span>
        </span>
      ))}
    </div>
  );
}
