'use client';

import Collapsible from './Collapsible';
import { Barras, Sparkbars } from './Charts';

export default function CadencePanel({ porDia, porFonte, porStatus, total }) {
  return (
    <Collapsible title="Cadência & fontes" meta={`${total} envios`} defaultOpen={total > 0}>
      <div className="panel-body">
        <div className="bars-block">
          <span className="bars-title">envios por dia · últimos {porDia.length}</span>
          <Sparkbars dados={porDia} />
        </div>
        <div className="bars-block">
          <span className="bars-title">por fonte (portal de origem)</span>
          <Barras itens={porFonte} tom="info" />
        </div>
        {porStatus && porStatus.length > 0 && (
          <div className="bars-block">
            <span className="bars-title">por status</span>
            <Barras itens={porStatus} tom="ok" />
          </div>
        )}
      </div>
    </Collapsible>
  );
}
