'use client';

// Hero: today's count + 14-day area line. `serie`: [[YYYY-MM-DD, n]] zero-filled, last = today.
function Area({ serie }) {
  const W = 420, H = 84, pt = 10, pb = 18, px = 6;
  const max = Math.max(1, ...serie.map(([, n]) => n));
  const x = i => px + i * (W - 2 * px) / Math.max(1, serie.length - 1);
  const y = v => pt + (H - pt - pb) * (1 - v / max);
  const linha = serie.map(([, n], i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(n).toFixed(1)}`).join(' ');
  const area = `${linha} L${x(serie.length - 1)} ${H - pb} L${x(0)} ${H - pb} Z`;
  const u = serie.length - 1;
  const rot = (ymd) => `${ymd.slice(8)}/${ymd.slice(5, 7)}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="area" role="img"
         aria-label={`Envios por dia: ${serie.map(([d, n]) => `${rot(d)} ${n}`).join(', ')}`}>
      <defs>
        <linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, max / 2, max].map(v => <line key={v} x1="0" x2={W} y1={y(v)} y2={y(v)} className="area-grid" />)}
      <text x={W} y={y(max) - 3} className="area-lbl" textAnchor="end">{max}</text>
      <path d={area} fill="url(#areaFill)" />
      <path d={linha} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" />
      <circle cx={x(u)} cy={y(serie[u][1])} r="4" className="area-dot" />
      {serie.map(([d], i) => (i % 3 === 1 || i === u) && (
        <text key={d} x={x(i)} y={H - 4} className="area-lbl" textAnchor={i === u ? 'end' : 'middle'}>{i === u ? 'hoje' : rot(d)}</text>
      ))}
    </svg>
  );
}

export default function TodayHero({ hojeLabel, hoje, serie, rodadasHoje }) {
  const anteriores = serie.slice(0, -1).map(([, n]) => n);
  const media = anteriores.length ? anteriores.reduce((a, b) => a + b, 0) / anteriores.length : 0;
  const recorde = anteriores.length && hoje > 0 && hoje >= Math.max(...anteriores);
  const nota = recorde ? 'melhor dia dos últimos 14'
    : hoje > media ? 'acima da média' : hoje === 0 ? 'nenhum envio ainda' : 'abaixo da média';
  return (
    <section className="card today-hero">
      <p className="card-label">Enviadas hoje · {hojeLabel}</p>
      <div className="today-row">
        <strong className="big">{hoje}</strong>
        <div className="today-meta">
          <span className={`delta ${recorde || hoje > media ? 'up' : ''}`}>{nota}</span>
          <span>média {media.toFixed(1).replace('.', ',')}/dia · {rodadasHoje} rodadas hoje</span>
        </div>
      </div>
      <Area serie={serie} />
    </section>
  );
}
