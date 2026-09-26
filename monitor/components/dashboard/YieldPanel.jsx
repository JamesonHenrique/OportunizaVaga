'use client';

import Collapsible from './Collapsible';
import { Barras } from './Charts';

// Rounds vs. applications in the last 7 days — how many rounds it takes, on
// average, to land one application. Aggregates only.
export default function YieldPanel({ rendimento: r }) {
  const temAplicadas = (r?.aplicadas7d ?? 0) > 0;
  return (
    <Collapsible title="Rendimento (7 dias)" meta={`${r?.rodadas7d ?? 0} rodadas · ${r?.aplicadas7d ?? 0} envios`} defaultOpen>
      <div className="panel-body">
        <div className="bars-block">
          <span className="bars-title">últimos 7 dias</span>
          <Barras
            itens={[
              ['rodadas', r?.rodadas7d ?? 0],
              ['candidaturas enviadas', r?.aplicadas7d ?? 0]
            ]}
            tom="info"
          />
        </div>
        <p className="line-note">
          {temAplicadas
            ? <>Média de <b>{r.rodadasPorCandidatura}</b> rodada(s) por candidatura enviada na janela.</>
            : 'Sem candidaturas enviadas nos últimos 7 dias — sem base para calcular a média.'}
        </p>
      </div>
    </Collapsible>
  );
}
