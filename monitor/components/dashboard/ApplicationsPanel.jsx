'use client';

import { useState } from 'react';
import { Inbox } from 'lucide-react';
import { baixarCSV, dataHora, dia, horaSeg, rotuloStatus } from '@/lib/dashboard';

export default function ApplicationsPanel({ aplicadas }) {
  const [busca, setBusca] = useState('');
  const buscaL = busca.trim().toLowerCase();
  const filtradas = aplicadas.filter(a =>
    !buscaL || `${a.empresa || ''} ${a.vaga || ''} ${a.fonte || ''} ${a.como || ''} ${a.status || ''}`.toLowerCase().includes(buscaL)
  );

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Candidaturas enviadas</h2>
        <div className="controls">
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="empresa / vaga / fonte / status…"
            className="search"
            aria-label="Buscar candidatura"
            name="busca-apl"
            autoComplete="off"
          />
          <button
            title="Baixar candidaturas em CSV"
            onClick={() => baixarCSV('candidaturas.csv',
              ['data', 'hora', 'empresa', 'vaga', 'fonte', 'via', 'remota', 'status', 'como'],
              filtradas.map(a => [a.data || '', a.exato ? horaSeg(a.quando) : '', a.empresa || '', a.vaga || '', a.fonte || '', a.via || '', a.remota ? 'sim' : 'não', a.status || 'enviada', a.como || '']))}
          >CSV</button>
          <span>{filtradas.length}/{aplicadas.length}</span>
        </div>
      </div>
      <div className="list">
        {filtradas.length ? filtradas.map((a, i) => (
          <div className="row" key={a.chave || i}>
            <div className="when">
              {a.quando
                ? <strong title={dataHora(a.quando)}>{horaSeg(a.quando)}{!a.exato && <em title="Hora aproximada, reconstruída do CV gerado">~</em>}</strong>
                : <strong className="no-time" title="Horário não registrado nesta candidatura">--:--</strong>}
              <small>{a.quando ? dia(a.quando) : (a.data ? a.data.slice(8) + '/' + a.data.slice(5, 7) : '--/--')}</small>
            </div>
            <div className="who">
              <b>{a.empresa}</b>
              <p>{a.vaga}</p>
              <small>{a.como}</small>
            </div>
            <div className="meta-col">
              <span className={`tag ${(a.status || 'enviada').toLowerCase() === 'enviada' ? 'solid' : ''}`}>{rotuloStatus(a.status)}</span>
              {a.fonte && <span className="tag" title={a.via ? `via ${a.via}` : 'portal de origem'}>{a.fonte}{a.via ? ` · ${a.via}` : ''}</span>}
              {a.conflito_data && <span className="tag muted" title="Data registrada divergia do CV — fuso da máquina">data revisada</span>}
            </div>
          </div>
        )) : <p className="empty"><Inbox className="ico" aria-hidden="true" />{busca ? 'Nenhuma candidatura para esta busca.' : 'Nenhuma candidatura registrada.'}</p>}
      </div>
      {aplicadas.some(a => !a.exato) && (
        <p className="footnote">
          ~ hora aproximada, reconstruída do CV gerado para a vaga (fuso do robô). <code>--:--</code> = horário nunca registrado.
          Candidaturas novas gravam o horário exato com fuso.
        </p>
      )}
    </section>
  );
}
