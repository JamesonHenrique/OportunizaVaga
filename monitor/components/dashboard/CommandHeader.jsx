'use client';

import { Activity, CalendarClock, RefreshCw, WifiOff, OctagonAlert, CircleHelp, ArrowDown } from 'lucide-react';
import { horaSeg, dia } from '@/lib/dashboard';

const ICONE = { ativo: Activity, agendado: CalendarClock, retentando: RefreshCw, 'sem-sinal': WifiOff, erro: OctagonAlert, 'sem-dados': CircleHelp };

// Operational command header ("Instrumento de Precisão"): three immediate answers —
// is it working? · last confirmed update · how many things need you — plus the data provenance
// badges (cache / demo / public). No marketing copy here.
export default function CommandHeader({ estado, atualizacao, fr, pendentes, criticos, avisos, onPrecisa }) {
  const Ico = ICONE[estado.id] || CircleHelp;
  const titulo = estado.id === 'sem-sinal'
    ? `Sem sinal do robô${fr.ref ? ` ${atualizacao.replace(/^Sem sinal /, '')}` : ''}`
    : estado.id === 'erro' ? 'Automação com erro'
      : pendentes ? `${pendentes} ${pendentes === 1 ? 'item precisa' : 'itens precisam'} de você`
        : estado.id === 'ativo' ? 'Robô trabalhando · nada depende de você'
          : 'Nada depende de você agora';
  return (
    <section className={`command is-${estado.tom}`} aria-labelledby="command-title">
      <h1 id="command-title" className="command-title">{titulo}</h1>
      <dl className="command-grid">
        <div className="cmd-cell">
          <dt>Está funcionando?</dt>
          <dd>
            <span className={`state-chip is-${estado.tom}${estado.vivo ? ' is-live' : ''}`}><Ico className="ico" aria-hidden="true" />{estado.rotulo}</span>
            <small>{estado.frase}</small>
          </dd>
        </div>
        <div className="cmd-cell">
          <dt>Última atualização confirmada</dt>
          <dd>
            <b className={fr.semSinal ? 'is-bad' : undefined}>{atualizacao}</b>
            <small>
              {fr.ref ? `${dia(fr.ref)} ${horaSeg(fr.ref)}` : 'aguardando o primeiro envio do robô'}
              {` · sem sinal após ${Math.round(fr.limite / 60000)} min`}
            </small>
          </dd>
        </div>
        <div className="cmd-cell">
          <dt>Precisa de você</dt>
          <dd>
            <button type="button" className={`cmd-need${pendentes ? (criticos ? ' is-bad' : ' is-warn') : ' is-ok'}`} onClick={onPrecisa}>
              <b>{pendentes}</b>
              <span>{pendentes ? (criticos ? `${criticos} crítico(s)` : 'ver itens') : 'nada pendente'}</span>
              <ArrowDown className="ico" aria-hidden="true" />
            </button>
          </dd>
        </div>
      </dl>
      {avisos.length > 0 && (
        <ul className="command-flags" aria-label="Origem dos dados">
          {avisos.map(a => (
            <li key={a.id} className={`flag is-${a.id}`} title={a.dica}>
              <b>{a.rotulo}</b>{a.dica && <span> — {a.dica}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
