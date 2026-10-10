'use client';

import { useState } from 'react';
import { TrendingUp } from 'lucide-react';

const rot = (ymd) => `${ymd.slice(8)}/${ymd.slice(5, 7)}`;
const diaSemana = (ymd) => new Date(`${ymd}T12:00:00Z`).toLocaleDateString('pt-BR', { weekday: 'short', timeZone: 'UTC' }).replace('.', '');

// Hero: today's count + 14-day area line. `serie`: [[YYYY-MM-DD, n]] zero-filled, last = today.
// Hover/focus a day for its real count; zero days get a hollow dot so "no sends" reads as data, not a gap.
function Area({ serie }) {
  const [sel, setSel] = useState(null);
  const W = 520, H = 104, pt = 12, pb = 4, px = 10;
  const max = Math.max(1, ...serie.map(([, n]) => n));
  const passo = (W - 2 * px) / Math.max(1, serie.length - 1);
  const x = i => px + i * passo;
  const y = v => pt + (H - pt - pb) * (1 - v / max);
  const linha = serie.map(([, n], i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(n).toFixed(1)}`).join(' ');
  const area = `${linha} L${x(serie.length - 1)} ${H - pb} L${x(0)} ${H - pb} Z`;
  const u = serie.length - 1;
  const ativo = sel ?? u;
  const [dAtivo, nAtivo] = serie[ativo];
  return (
    <div className="chart" onMouseLeave={() => setSel(null)}>
      <div className="chart-head">
        <span>Envios por dia · 14 dias</span>
        <span><b>{ativo === u ? 'hoje' : `${diaSemana(dAtivo)}, ${rot(dAtivo)}`}</b> · {nAtivo} envio{nAtivo === 1 ? '' : 's'}</span>
      </div>
      <div className="chart-plot">
      <span className="area-max" aria-hidden="true">{max}</span>
      <svg viewBox={`0 0 ${W} ${H}`} className="area" role="img"
           aria-label={`Envios por dia: ${serie.map(([d, n]) => `${rot(d)} ${n}`).join(', ')}`}>
        <defs>
          <linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x={x(u) - passo / 2} y={pt - 6} width={passo / 2 + px} height={H - pb - pt + 6} className="area-today" />
        <line x1={0} x2={W} y1={y(max)} y2={y(max)} className="area-grid" />
        <line x1={0} x2={W} y1={y(max / 2)} y2={y(max / 2)} className="area-grid" />
        <line x1={0} x2={W} y1={H - pb} y2={H - pb} className="area-base" />
        <path d={area} fill="url(#areaFill)" />
        <path d={linha} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {sel != null && <line x1={x(sel)} x2={x(sel)} y1={pt} y2={H - pb} className="area-guide" />}
        {serie.map(([d, n], i) => (n === 0 || i === u || i === sel) && (
          <circle key={d} cx={x(i)} cy={y(n)} r={i === u || i === sel ? 4 : 2.5} className={`area-dot${n === 0 && i !== u && i !== sel ? ' is-zero' : ''}`} />
        ))}
        {serie.map(([d, n], i) => (
          <rect key={d} x={x(i) - passo / 2} y={0} width={passo} height={H} className="area-hit"
                onMouseEnter={() => setSel(i)}>
            <title>{`${diaSemana(d)}, ${rot(d)}: ${n} envio${n === 1 ? '' : 's'}`}</title>
          </rect>
        ))}
      </svg>
      </div>
      {/* HTML axis labels: stay legible when the SVG scales down on phones */}
      <div className="area-x" aria-hidden="true">
        {serie.map(([d], i) => (i % 2 === u % 2) && (
          <span key={d} className={`${i === u ? 'is-today' : ''}${(u - i) % 4 ? ' alt' : ''}`}
                style={{ left: `${(x(i) / W) * 100}%` }}>{i === u ? 'hoje' : rot(d)}</span>
        ))}
      </div>
    </div>
  );
}

export default function TodayHero({ hojeLabel, hoje, serie, rodadasHoje }) {
  const anteriores = serie.slice(0, -1).map(([, n]) => n);
  const media = anteriores.length ? anteriores.reduce((a, b) => a + b, 0) / anteriores.length : 0;
  const recorde = anteriores.length && hoje > 0 && hoje >= Math.max(...anteriores);
  const nota = recorde ? 'melhor dia dos últimos 14'
    : hoje > media ? 'acima da média' : hoje === 0 ? 'nenhum envio ainda' : 'abaixo da média';
  const sobe = recorde || hoje > media;
  return (
    <section className="card today-hero" aria-labelledby="today-title">
      <div className="card-head">
        <h2 id="today-title">Enviadas hoje</h2>
        <span className="card-meta">{hojeLabel}</span>
      </div>
      <div className="today-row">
        <strong className="big">{hoje}</strong>
        <div className="today-meta">
          <span className={`delta${sobe ? ' up' : ''}`}>{sobe && <TrendingUp className="ico" aria-hidden="true" />}{nota}</span>
          <span>média {media.toFixed(1).replace('.', ',')}/dia · {rodadasHoje ?? '—'} rodadas hoje</span>
        </div>
      </div>
      <Area serie={serie} />
    </section>
  );
}
