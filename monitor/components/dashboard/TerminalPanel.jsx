'use client';

import { useEffect, useRef, useState } from 'react';
import { Seg } from './ui';

// Line tone from the loop's own wording, so errors and sends pop out of the scroll.
const tomLinha = (l) => {
  if (/FALHOU|ALERTA|erro|Error|✗|quebrou|morreu/i.test(l)) return 'bad';
  if (/limite|cascatea|resfriamento|improdutiva|pausad|timeout|estourou/i.test(l)) return 'warn';
  if (/vaga nova processada|candidatura enviada|ok add-aplicada|convite.*enviado|validate-rodada: OK/i.test(l)) return 'ok';
  if (/^\[\d{4}-\d{2}-\d{2}/.test(l)) return 'info';
  return '';
};

export default function TerminalPanel({ logTail }) {
  const [aba, setAba] = useState('candidaturas');
  const [pausado, setPausado] = useState(false);
  const [soEventos, setSoEventos] = useState(false);
  const scrollRef = useRef(null);
  const todas = (logTail && logTail[aba]) || [];
  const linhas = soEventos ? todas.filter(l => /^\[\d{4}-\d{2}-\d{2}/.test(l)) : todas;

  // Auto-scroll the terminal (pausable so you can read at ease).
  useEffect(() => {
    if (!pausado && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [logTail, aba, pausado, linhas.length]);

  return (
    <section className="panel term-panel">
      <div className="panel-head">
        <h2>Terminal ao vivo</h2>
        <span>{linhas.length} linhas</span>
        <div className="term-actions">
          <button type="button" className={`btn-ghost${soEventos ? ' is-on' : ''}`} onClick={() => setSoEventos(v => !v)} aria-pressed={soEventos}>só eventos</button>
          <button type="button" className="btn-ghost" onClick={() => setPausado(p => !p)} title="Pausar a rolagem para ler">{pausado ? 'retomar' : 'pausar'}</button>
        </div>
      </div>
      <Seg rotulo="Log" valor={aba} onChange={setAba} opcoes={[
        { id: 'candidaturas', rotulo: 'candidaturas', conta: (logTail?.candidaturas || []).length },
        { id: 'linkedin', rotulo: 'linkedin-rh', conta: (logTail?.linkedin || []).length },
      ]} />
      <div className="terminal" ref={scrollRef}>
        {linhas.length
          ? linhas.map((l, i) => <div key={`${aba}-${i}`} className={tomLinha(l) ? `tl-${tomLinha(l)}` : undefined}>{l}</div>)
          : <span className="term-empty">sem linhas recebidas ainda — o próximo heartbeat traz o espelho do log (só com o secret).</span>}
      </div>
      <p className="footnote">espelho das últimas 80 linhas de {aba === 'candidaturas' ? 'loop.log' : 'dia.log'}, renovado a cada heartbeat. Vermelho = erro · amarelo = limite/cascata · verde = envio.</p>
    </section>
  );
}
