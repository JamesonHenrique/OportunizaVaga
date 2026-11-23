'use client';

import { DailyChart } from './Charts';
import { StaleBadge } from './ui';

// Daily activity card (overview). The "today" number itself lives in the KPI row;
// this card only adds the 14-day context. `serie`: [[YYYY-MM-DD, n]] zero-filled, last = today.
export default function TodayHero({ hojeLabel, serie, rodadasHoje, obsoleto }) {
  const anteriores = serie.slice(0, -1).map(([, n]) => n);
  const hoje = serie[serie.length - 1]?.[1] ?? 0;
  const media = anteriores.length ? anteriores.reduce((a, b) => a + b, 0) / anteriores.length : 0;
  const nota = hoje === 0 ? 'nenhum envio hoje ainda'
    : anteriores.length && hoje >= Math.max(...anteriores) ? 'hoje é o melhor dia do período'
      : hoje > media ? 'hoje acima da média' : 'hoje abaixo da média';
  return (
    <section className="card activity" aria-labelledby="activity-title">
      <div className="card-head">
        <h2 id="activity-title">Atividade diária</h2>
        <span className="card-meta">
          {obsoleto && <StaleBadge tipo={obsoleto} />}
          {hojeLabel}
        </span>
      </div>
      <p className="activity-note">
        {nota} · média {media.toFixed(1).replace('.', ',')}/dia nos {anteriores.length} dias anteriores · {rodadasHoje ?? '—'} rodadas hoje
      </p>
      <DailyChart serie={serie} />
    </section>
  );
}
