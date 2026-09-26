'use client';

import { useEffect, useRef, useState } from 'react';

const ABAS = ['candidaturas', 'linkedin'];

export default function TerminalPanel({ logTail }) {
  const [aba, setAba] = useState('candidaturas');
  const [pausado, setPausado] = useState(false);
  const scrollRef = useRef(null);
  const linhas = (logTail && logTail[aba]) || [];

  // Auto-scroll the terminal (pausable so you can read at ease).
  useEffect(() => {
    if (!pausado && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logTail, aba, pausado, linhas]);

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Terminal ao vivo</h2>
        <div className="controls">
          {ABAS.map(t => (
            <button key={t} className={aba === t ? 'on' : ''} onClick={() => setAba(t)}>{t}</button>
          ))}
          <button onClick={() => setPausado(p => !p)} title="Pausar a rolagem para ler">{pausado ? 'retomar' : 'pausar'}</button>
          <span>{linhas.length} linhas</span>
        </div>
      </div>
      <div className="terminal" ref={scrollRef}>
        {linhas.length
          ? linhas.map((l, i) => <div key={`${aba}-${i}`}>{l}</div>)
          : <span className="term-empty">sem linhas recebidas ainda — o próximo heartbeat traz o espelho do log.</span>}
      </div>
      <p className="footnote">espelho das últimas 80 linhas de {aba === 'candidaturas' ? 'loop.log' : 'dia.log'} do PC, renovado a cada heartbeat — se mexeu aqui, o terminal lá está escrevendo.</p>
    </section>
  );
}
