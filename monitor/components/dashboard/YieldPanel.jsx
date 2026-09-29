'use client';

import Collapsible from './Collapsible';
import { Tiles } from './ui';

// Rounds vs. applications in the last 7 days — how many rounds it takes, on
// average, to land one application. Aggregates only.
export default function YieldPanel({ rendimento: r }) {
  const tem = (r?.aplicadas7d ?? 0) > 0;
  const rpc = r?.rodadasPorCandidatura;
  return (
    <Collapsible title="Rendimento (7 dias)" meta={`${r?.rodadas7d ?? 0} rodadas · ${r?.aplicadas7d ?? 0} envios`} defaultOpen>
      <div className="panel-body">
        <Tiles itens={[
          { rotulo: 'Rodadas', valor: r?.rodadas7d ?? 0, sub: 'últimos 7 dias' },
          { rotulo: 'Candidaturas', valor: r?.aplicadas7d ?? 0, sub: 'enviadas', tom: tem ? 'ok' : 'warn' },
          { rotulo: 'Rodadas por envio', valor: tem && rpc != null ? String(rpc).replace('.', ',') : '—',
            sub: 'quanto menor, melhor', tom: tem && rpc > 8 ? 'warn' : undefined },
        ]} />
        {!tem && <p className="line-note">Sem candidaturas nos últimos 7 dias — sem base para a média.</p>}
      </div>
    </Collapsible>
  );
}
