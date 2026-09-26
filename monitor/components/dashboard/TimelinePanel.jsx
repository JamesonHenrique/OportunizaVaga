'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import { dia, horaSeg } from '@/lib/dashboard';

export default function TimelinePanel({ eventos: todos }) {
  const [filtroFonte, setFiltroFonte] = useState('tudo');
  const [filtroKind, setFiltroKind] = useState('tudo');
  const [busca, setBusca] = useState('');

  const kinds = useMemo(
    () => ['tudo', ...new Set((todos || []).map(e => e.kind).filter(Boolean))],
    [todos]
  );

  const buscaL = busca.trim().toLowerCase();
  const eventos = (todos || []).filter(e =>
    (filtroFonte === 'tudo' || e.source === filtroFonte) &&
    (filtroKind === 'tudo' || e.kind === filtroKind) &&
    (!buscaL || `${e.text || ''} ${e.kind || ''} ${e.at || ''}`.toLowerCase().includes(buscaL))
  );

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Linha do tempo</h2>
        <div className="controls">
          {['tudo', 'candidaturas', 'linkedin'].map(f => (
            <button key={f} className={filtroFonte === f ? 'on' : ''} onClick={() => setFiltroFonte(f)}>{f}</button>
          ))}
          <select value={filtroKind} onChange={(e) => setFiltroKind(e.target.value)} title="filtrar por tipo" aria-label="Filtrar eventos por tipo">
            {kinds.map(k => <option key={k} value={k}>{k}</option>)}
          </select>
          <input value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="buscar…" className="search" aria-label="Buscar na linha do tempo" name="busca-timeline" autoComplete="off" />
          <span>{eventos.length} eventos</span>
        </div>
      </div>
      <div className="timeline">
        {eventos.length ? eventos.map((e, i) => (
          <div className={`event ${e.severity}`} key={`${e.at}-${i}`}>
            <span className="ts">{dia(e.at)} {horaSeg(e.at)}</span>
            <span className="kind">{e.kind}</span>
            <span className="text">{e.text}</span>
            <span className="src">{e.source}</span>
          </div>
        )) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Sem eventos para este filtro.</p>}
      </div>
    </section>
  );
}
