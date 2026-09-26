'use client';

import { Inbox } from 'lucide-react';
import Collapsible from './Collapsible';

export default function InvitesPanel({ convites }) {
  return (
    <Collapsible title="Convites LinkedIn" meta={String(convites.length)} defaultOpen={convites.length > 0}>
      <div className="list">
        {convites.length ? convites.map((c, i) => (
          <div className="row compact" key={c.perfil_url || i}>
            <div className="when"><strong>{c.data?.slice(8)}/{c.data?.slice(5, 7)}</strong></div>
            <div className="who">
              <b>{c.nome}</b>
              <p>{(c.headline || '').slice(0, 70)}</p>
            </div>
            <span className={`tag ${c.nota_enviada ? '' : 'muted'}`}>{c.nota_enviada ? 'COM NOTA' : 'SEM NOTA'}</span>
          </div>
        )) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Nenhum convite registrado.</p>}
      </div>
    </Collapsible>
  );
}
