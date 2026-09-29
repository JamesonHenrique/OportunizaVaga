'use client';

import { Inbox } from 'lucide-react';
import Collapsible from './Collapsible';
import VagaLink from './VagaLink';
import { dataHora } from '@/lib/dashboard';

const ROTULO_FILTRO = { nivel: 'nível', modelo: 'presencial/híbrido', stack: 'stack fora', tipo: 'tipo pulado', empresa: 'empresa pulada', antiga: 'antiga (>14d)' };

// descobrir.py: listings fetched and filtered by title without an LLM; the robot only gets
// the survivors. Shows what is queued next and how much the filter saved.
export default function DiscoveryPanel({ descoberta: f, gmail }) {
  const pend = f?.porStatus?.nova || 0;
  const filtros = Object.entries(f?.filtradasTotal || {}).filter(([k]) => k !== 'novas').sort((a, b) => b[1] - a[1]);
  const economizadas = filtros.reduce((a, [, n]) => a + n, 0);
  return (
    <Collapsible title="Busca por script" meta={f ? `${pend} na fila · ${economizadas} filtradas sem IA` : 'sem dados'} defaultOpen={pend > 0}>
      <div className="panel-body">
        {f ? (
          <>
            <p className="line-note">
              Última coleta {dataHora(f.ultimaColeta)}
              {f.ultima?.lidas != null ? ` · ${f.ultima.lidas} lidas, ${f.ultima.novas} novas` : ''}
              {gmail?.atualizado ? ` · Gmail lido ${dataHora(gmail.atualizado)} (${gmail.achados} resposta(s) de empresas)` : ''}
            </p>
            {filtros.length > 0 && (
              <p className="line-note">Filtradas pelo título: {filtros.map(([k, n]) => `${ROTULO_FILTRO[k] || k} ${n}`).join(' · ')}</p>
            )}
            {f.proximas?.length ? (
              <ul className="disc-list">
                {f.proximas.map((v, i) => (
                  <li key={v.url || i}>
                    <span className="tag muted">score {v.score ?? 0}</span>
                    <VagaLink url={v.url}><b>{v.empresa || '?'}</b> — {v.titulo}</VagaLink>
                    <small>{v.fonte}{v.publicada ? ` · publ. ${v.publicada.slice(8, 10)}/${v.publicada.slice(5, 7)}` : ''}</small>
                  </li>
                ))}
              </ul>
            ) : <p className="empty"><Inbox className="ico" aria-hidden="true" />{pend > 0 ? 'Vagas da fila ocultas no modo agregado.' : 'Fila vazia: nada novo passou no filtro.'}</p>}
          </>
        ) : <p className="empty"><Inbox className="ico" aria-hidden="true" />descobrir.py ainda não rodou.</p>}
      </div>
    </Collapsible>
  );
}
