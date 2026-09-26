'use client';

import { useState } from 'react';
import { Inbox } from 'lucide-react';
import { causaRaiz } from '@/lib/dashboard';

const PAG = 8;

export default function BlocksPanel({ bloqueios, vistos }) {
  const [busca, setBusca] = useState('');
  const [pagina, setPagina] = useState(1);

  const buscaL = busca.trim().toLowerCase();
  const filtrados = bloqueios.filter(b =>
    !buscaL || `${b.chave || ''} ${b.motivo || ''} ${b.origem || ''}`.toLowerCase().includes(buscaL)
  );
  const totalPag = Math.max(1, Math.ceil(filtrados.length / PAG));
  const pagAtual = Math.min(pagina, totalPag); // clamp: list shrink never leaves a blank page
  const paginaAtual = filtrados.slice((pagAtual - 1) * PAG, pagAtual * PAG);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Bloqueios</h2>
        <span>{filtrados.length}/{bloqueios.length}</span>
      </div>
      <div className="search-row">
        <input
          value={busca}
          onChange={(e) => { setBusca(e.target.value); setPagina(1); }}
          placeholder="buscar bloqueio…"
          aria-label="Buscar bloqueio"
          name="busca-bloqueio"
          autoComplete="off"
        />
      </div>
      <div className="list">
        {paginaAtual.length ? paginaAtual.map((b, i) => (
          <div className="block-item" key={b.chave || i}>
            <div className="block-head">
              <span className={`pip ${b.status === 'VENCIDO' ? 'done' : 'open'}`} />
              <b>{b.chave}</b>
              <small>{b.origem} · {causaRaiz(b)}</small>
            </div>
            <p>{b.motivo}</p>
            <p className="when-block" title={b.em || vistos[b.chave] || ''}>
              {b._ref.txt}
            </p>
            {b.status === 'VENCIDO' && <span className="tag">VENCIDO — será retomado</span>}
          </div>
        )) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Nenhum bloqueio para este filtro.</p>}
      </div>
      {totalPag > 1 && (
        <div className="pager">
          <button onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={pagAtual <= 1} aria-label="Página anterior">‹</button>
          <span>{pagAtual} / {totalPag}</span>
          <button onClick={() => setPagina(p => Math.min(totalPag, p + 1))} disabled={pagAtual >= totalPag} aria-label="Próxima página">›</button>
        </div>
      )}
    </section>
  );
}
