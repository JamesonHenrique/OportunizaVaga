'use client';

// Chart primitives. Colors come only from --chart-* tokens (globals.css).
import { useId, useRef, useState } from 'react';

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

const rot = (ymd) => `${ymd.slice(8, 10)}/${ymd.slice(5, 7)}`;
const diaSemana = (ymd) => new Date(`${ymd}T12:00:00Z`)
  .toLocaleDateString('pt-BR', { weekday: 'short', timeZone: 'UTC' }).replace('.', '');
const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

// Nice upper bound for the y axis (1, 2, 4, 5, 10, 20…), so gridlines land on integers.
function teto(max) {
  if (max <= 2) return Math.max(1, max);
  if (max <= 4) return 4;
  const p = 10 ** Math.floor(Math.log10(max));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= max && Number.isInteger((m * p) / 2)) return m * p;
  return Math.ceil(max / p) * p;
}

/**
 * Single daily-activity chart used by the overview and the Candidaturas tab.
 * serie: [[YYYY-MM-DD, n]] zero-filled, chronological; the last item is "hoje".
 * Accessibility: the plot is ONE focusable target (no 14 tiny tab stops):
 *  - Tab focuses it and selects "hoje"; ←/→ move, Home/End jump; Esc clears.
 *  - Mouse hover / click / touch pick the nearest day.
 *  - The readout is aria-live; a screen-reader summary describes the whole series.
 */
export function DailyChart({ serie, unidade = ['envio', 'envios'], titulo = 'Envios por dia', altura = 132, compacto = false }) {
  const [sel, setSel] = useState(null);
  const plotRef = useRef(null);
  const id = useId();
  if (!serie?.length) return <p className="empty-inline">Sem envios registrados no período.</p>;

  const u = serie.length - 1;
  const max = Math.max(0, ...serie.map(([, n]) => n));
  const topo = teto(max);
  const total = serie.reduce((a, [, n]) => a + n, 0);
  const melhor = serie.reduce((m, x) => (x[1] > m[1] ? x : m), serie[0]);
  const media = total / serie.length;
  const ativo = sel ?? u;
  const [dAtivo, nAtivo] = serie[ativo];
  const nomeDia = (i) => (i === u ? 'hoje' : `${diaSemana(serie[i][0])}, ${rot(serie[i][0])}`);
  const resumo = `${titulo}, últimos ${serie.length} dias: ${plural(total, ...unidade)} no total, ` +
    `média ${media.toFixed(1).replace('.', ',')} por dia` +
    (max > 0 ? `, melhor dia ${rot(melhor[0])} com ${melhor[1]}` : '') + `, hoje ${serie[u][1]}.`;

  const mover = (i) => setSel(Math.max(0, Math.min(u, i)));
  const onKeyDown = (e) => {
    const atual = sel ?? u;
    if (e.key === 'ArrowLeft') { e.preventDefault(); mover(atual - 1); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); mover(atual + 1); }
    else if (e.key === 'Home') { e.preventDefault(); mover(0); }
    else if (e.key === 'End') { e.preventDefault(); mover(u); }
    else if (e.key === 'Escape') setSel(null);
  };
  const diaNoPonto = (clientX) => {
    const r = plotRef.current?.getBoundingClientRect();
    if (!r || !r.width) return null;
    return Math.max(0, Math.min(u, Math.floor(((clientX - r.left) / r.width) * serie.length)));
  };
  const marcas = topo > 1 ? [topo, topo / 2, 0] : [topo, 0];

  return (
    <figure className={`dchart${compacto ? ' is-compact' : ''}`}>
      <figcaption className="dchart-head">
        <span className="dchart-title">{titulo} · {serie.length} dias</span>
        <span className="dchart-read" aria-live="polite">
          <b>{nomeDia(ativo)}</b> · {plural(nAtivo, ...unidade)}
        </span>
      </figcaption>
      <p id={`${id}-sum`} className="sr-only">{resumo}</p>
      <div className="dchart-body">
        <div className="dchart-y" aria-hidden="true">
          {marcas.map(m => <span key={m}>{m}</span>)}
        </div>
        <div
          ref={plotRef}
          className="dchart-plot"
          style={{ height: altura }}
          role="img"
          tabIndex={0}
          aria-label={`${titulo}. Use as setas para percorrer os dias.`}
          aria-describedby={`${id}-sum`}
          onKeyDown={onKeyDown}
          onFocus={() => setSel(s => s ?? u)}
          onBlur={() => setSel(null)}
          onMouseMove={(e) => { const i = diaNoPonto(e.clientX); if (i != null) setSel(i); }}
          onMouseLeave={() => { if (document.activeElement !== plotRef.current) setSel(null); }}
          onClick={(e) => { const i = diaNoPonto(e.clientX); if (i != null) setSel(i); }}
        >
          {marcas.map(m => (
            <i key={m} className={`dchart-grid${m === 0 ? ' is-base' : ''}`} style={{ bottom: `${(m / topo) * 100}%` }} aria-hidden="true" />
          ))}
          <div className="dchart-cols" aria-hidden="true">
            {serie.map(([d, n], i) => (
              <span key={d} className={`dchart-col${i === u ? ' is-today' : ''}${i === ativo && sel != null ? ' is-active' : ''}`}>
                <span className={`dchart-bar${n ? '' : ' is-zero'}`} style={{ height: n ? `${Math.max(3, (n / topo) * 100)}%` : undefined }} />
                {i === ativo && sel != null && (
                  <span className={`dchart-tip${i < 2 ? ' at-start' : i > u - 2 ? ' at-end' : ''}`}>
                    {plural(n, ...unidade)}<small>{nomeDia(i)}</small>
                  </span>
                )}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="dchart-x" aria-hidden="true">
        {serie.map(([d], i) => (
          <span key={d} className={`${i === u ? 'is-today' : ''}${(u - i) % 2 ? ' is-odd' : ''}${(u - i) % 4 ? ' is-alt' : ''}`}>
            {i === u ? 'hoje' : rot(d)}
          </span>
        ))}
      </div>
      {!compacto && (
        <div className="dchart-legend" aria-hidden="true">
          <span><i className="lg-today" />hoje</span>
          <span><i className="lg-past" />dias anteriores</span>
          <span><i className="lg-zero" />sem {unidade[1]}</span>
        </div>
      )}
    </figure>
  );
}
