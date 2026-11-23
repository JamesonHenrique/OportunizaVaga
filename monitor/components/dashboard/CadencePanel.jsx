'use client';

import Collapsible from './Collapsible';
import { Barras, DailyChart } from './Charts';
import { Tiles } from './ui';
import { resumoRespostas } from '@/lib/dashboard';

// Funnel stages from the statuses the follow-up and gmail-status.py record.
const ETAPAS = [
  ['enviadas', () => true],
  ['com retorno', s => ['em_analise', 'etapa_teste', 'proxima_etapa', 'entrevista', 'respondida', 'encerrada'].includes(s)],
  ['próxima etapa', s => ['etapa_teste', 'proxima_etapa', 'entrevista', 'respondida'].includes(s)],
];

// `serie`: the same zero-filled 14-day window the overview chart uses.
export default function CadencePanel({ serie, porFonte, porStatus, total }) {
  const counts = Object.entries(porStatus || {});
  const funil = ETAPAS.map(([rotulo, inclui]) => [rotulo, porStatus
    ? counts.reduce((sum, [status, count]) => inclui(status.toLowerCase()) ? sum + count : sum, 0)
    : null]);
  const encerradas = porStatus?.encerrada ?? 0;
  const porDia = serie.filter(([, n]) => n > 0);
  const melhor = porDia.reduce((m, x) => (x[1] > (m?.[1] || 0) ? x : m), null);
  const media = porDia.length ? (porDia.reduce((a, [, n]) => a + n, 0) / porDia.length) : 0;
  const respondidas = resumoRespostas(porStatus)?.total ?? null;

  return (
    <Collapsible title="Cadência & funil" meta={`${total} envios`} defaultOpen={total > 0}>
      <div className="panel-body">
        <Tiles itens={[
          { rotulo: 'Média por dia ativo', valor: serie.length ? media.toFixed(1).replace('.', ',') : '—', sub: serie.length ? `${porDia.length} dias com envio` : 'sem contagem diária' },
          { rotulo: 'Melhor dia', valor: melhor ? melhor[1] : '—', sub: melhor ? `${melhor[0].slice(8)}/${melhor[0].slice(5, 7)}` : '' },
          { rotulo: 'Taxa de resposta', valor: total && respondidas != null ? `${Math.round((respondidas / total) * 100)}%` : '—',
            sub: respondidas == null ? 'sem contagem de respostas' : `${respondidas} de ${total} (teste, entrevista ou negativa)`, tom: respondidas ? 'ok' : undefined },
        ]} />

        <div className="bars-block">
          <span className="bars-title">funil</span>
          <div className="funnel">
            {funil.map(([r, n], i) => (
              <div className="funnel-step" key={r}>
                <span className="funnel-track">{n != null && <span className={`funnel-bar f-${i}`} style={{ width: `${Math.max(3, total ? (n / total) * 100 : 0)}%` }} />}</span>
                <span className="funnel-lbl">{r}</span>
                <b>{n ?? '—'}</b>
              </div>
            ))}
          </div>
          {encerradas > 0 && <p className="line-note">{encerradas} encerrada(s) com retorno negativo</p>}
        </div>

        {serie.length ? <DailyChart serie={serie} compacto /> : <p className="empty-inline">Sem contagem diária nesta visão.</p>}
        <div className="bars-block">
          <span className="bars-title">por fonte (portal de origem)</span>
          <Barras itens={porFonte} tom="info" />
        </div>
      </div>
    </Collapsible>
  );
}
