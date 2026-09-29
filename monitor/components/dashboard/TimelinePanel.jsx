'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import { dia, horaSeg } from '@/lib/dashboard';
import { Seg, Chips, Busca } from './ui';

const ROT_KIND = { rodada: 'rodadas', ok: 'envios/ok', falha: 'falhas', cascata: 'cascatas', modelo: 'modelos', evento: 'eventos' };
const MAX = 150;

export default function TimelinePanel({ eventos: todos }) {
  const [fonte, setFonte] = useState('tudo');
  const [kind, setKind] = useState(null);
  const [busca, setBusca] = useState('');

  const daFonte = useMemo(() => (todos || []).filter(e => fonte === 'tudo' || e.source === fonte), [todos, fonte]);
  const kinds = useMemo(() => {
    const m = new Map();
    for (const e of daFonte) { const k = ROT_KIND[e.kind] || e.kind || 'outro'; m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [daFonte]);
  const buscaL = busca.trim().toLowerCase();
  const eventos = daFonte.filter(e =>
    (!kind || (ROT_KIND[e.kind] || e.kind || 'outro') === kind) &&
    (!buscaL || `${e.text || ''} ${e.kind || ''} ${e.at || ''}`.toLowerCase().includes(buscaL))
  );
  const conta = (s) => (todos || []).filter(e => s === 'tudo' || e.source === s).length;

  // Day separators: the list is newest first.
  let diaAnt = null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Linha do tempo</h2>
        <span>{eventos.length} eventos{eventos.length > MAX ? ` (mostrando ${MAX})` : ''}</span>
      </div>
      <Seg rotulo="Origem" valor={fonte} onChange={(f) => { setFonte(f); setKind(null); }} opcoes={[
        { id: 'tudo', rotulo: 'Tudo', conta: conta('tudo') },
        { id: 'candidaturas', rotulo: 'Candidaturas', conta: conta('candidaturas') },
        { id: 'linkedin', rotulo: 'LinkedIn-RH', conta: conta('linkedin') },
      ]} />
      <Chips rotulo="Filtrar por tipo" itens={kinds} ativo={kind} onChange={setKind} />
      <Busca valor={busca} onChange={setBusca} placeholder="buscar na linha do tempo…" nome="busca-timeline" />
      <div className="timeline">
        {eventos.length ? eventos.slice(0, MAX).map((e, i) => {
          const dd = dia(e.at);
          const sep = dd !== diaAnt ? (diaAnt = dd) : null;
          return (
            <div key={`${e.at}-${i}`}>
              {sep && <div className="tl-day">{sep}</div>}
              <div className={`event ${e.severity}`}>
                <span className="ts">{horaSeg(e.at)}</span>
                <span className="kind">{e.kind}</span>
                <span className="text">{e.text}</span>
                <span className="src">{e.source === 'linkedin' ? 'li' : 'cand'}</span>
              </div>
            </div>
          );
        }) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Sem eventos para este filtro.</p>}
      </div>
    </section>
  );
}
