'use client';

import Collapsible from './Collapsible';
import { Barras, Sparkbars } from './Charts';
import { Tiles } from './ui';

// Funnel stages from the statuses the follow-up and gmail-status.py record.
const ETAPAS = [
  ['enviadas', () => true],
  ['com retorno', s => ['em_analise', 'etapa_teste', 'proxima_etapa', 'entrevista', 'respondida', 'encerrada'].includes(s)],
  ['próxima etapa', s => ['etapa_teste', 'proxima_etapa', 'entrevista', 'respondida'].includes(s)],
];

export default function CadencePanel({ porDia, porFonte, porStatus, total }) {
  const st = Object.fromEntries(porStatus || []);
  const lista = Object.entries(st).flatMap(([s, n]) => Array(n).fill(String(s).toLowerCase()));
  const funil = ETAPAS.map(([r, f]) => [r, lista.filter(f).length]);
  const encerradas = st.encerrada || 0;
  const melhor = porDia.reduce((m, x) => (x[1] > (m?.[1] || 0) ? x : m), null);
  const media = porDia.length ? (porDia.reduce((a, [, n]) => a + n, 0) / porDia.length) : 0;
  const respondidas = lista.filter(s => ['etapa_teste', 'proxima_etapa', 'entrevista', 'respondida', 'encerrada'].includes(s)).length;

  return (
    <Collapsible title="Cadência & funil" meta={`${total} envios`} defaultOpen={total > 0}>
      <div className="panel-body">
        <Tiles itens={[
          { rotulo: 'Média por dia ativo', valor: media.toFixed(1).replace('.', ','), sub: `${porDia.length} dias com envio` },
          { rotulo: 'Melhor dia', valor: melhor ? melhor[1] : '—', sub: melhor ? `${melhor[0].slice(8)}/${melhor[0].slice(5, 7)}` : '' },
          { rotulo: 'Taxa de resposta', valor: total ? `${Math.round((respondidas / total) * 100)}%` : '—',
            sub: `${respondidas} de ${total} (teste, entrevista ou negativa)`, tom: respondidas ? 'ok' : undefined },
        ]} />

        <div className="bars-block">
          <span className="bars-title">funil</span>
          <div className="funnel">
            {funil.map(([r, n], i) => (
              <div className="funnel-step" key={r}>
                <span className="funnel-track"><span className={`funnel-bar f-${i}`} style={{ width: `${Math.max(3, total ? (n / total) * 100 : 0)}%` }} /></span>
                <span className="funnel-lbl">{r}</span>
                <b>{n}</b>
              </div>
            ))}
          </div>
          {encerradas > 0 && <p className="line-note">{encerradas} encerrada(s) com retorno negativo</p>}
        </div>

        <div className="bars-block">
          <span className="bars-title">envios por dia · últimos {porDia.length} dias com registro</span>
          <Sparkbars dados={porDia} />
        </div>
        <div className="bars-block">
          <span className="bars-title">por fonte (portal de origem)</span>
          <Barras itens={porFonte} tom="info" />
        </div>
      </div>
    </Collapsible>
  );
}
