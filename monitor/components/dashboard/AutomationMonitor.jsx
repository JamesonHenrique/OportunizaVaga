'use client';

import { ArrowRight } from 'lucide-react';
import { horaSeg } from '@/lib/dashboard';

const PIOR = { bad: 3, warn: 2, mute: 1, ok: 0 };
const ROT_KIND = { rodada: 'rodada', ok: 'envio/ok', falha: 'falha', cascata: 'cascata', modelo: 'modelo', evento: 'evento' };
const ROT_SRC = { candidaturas: 'candidaturas', linkedin: 'linkedin-rh' };

// Overview summary of the robot (dark card). Reads the same loop pills / events / heartbeat the Robô tab uses;
// the full terminal and timeline stay in that tab. Public view: event texts arrive empty, so kind + source show.
export default function AutomationMonitor({ loops, eventos = [], semSinal, heartbeat, rodadasHoje, proximoSite, fontesRuins, onAbrir }) {
  const pior = semSinal ? 'bad' : loops.reduce((p, l) => (PIOR[l.tom] > PIOR[p] ? l.tom : p), 'ok');
  const vivo = !semSinal && loops.some(l => l.vivo);
  const estado = semSinal ? 'Sem sinal' : vivo ? 'Rodando' : { ok: 'Ativo', warn: 'Atenção', bad: 'Com erro', mute: 'Sem dados' }[pior];
  const recentes = eventos.slice(0, 7);
  const linhas = [
    { k: 'Heartbeat', v: semSinal ? `sem sinal · ${heartbeat}` : heartbeat, tom: semSinal ? 'bad' : 'ok' },
    ...loops.map(l => ({ k: l.nome, v: l.frase, tom: l.tom })),
    rodadasHoje != null && { k: 'Rodadas hoje', v: String(rodadasHoje) },
    proximoSite && { k: 'Próximo site', v: proximoSite },
    fontesRuins && { k: 'Fontes de dados', v: fontesRuins.length ? `${fontesRuins.length} ilegível(is)` : 'OK', tom: fontesRuins.length ? 'warn' : 'ok' },
  ].filter(Boolean);
  return (
    <section className="automation" aria-labelledby="automation-title">
      <div className="automation-head">
        <h2 id="automation-title"><i className={`auto-dot is-${pior}${vivo ? ' is-live' : ''}`} aria-hidden="true" />Monitor da Automação</h2>
        <span className={`auto-state is-${vivo ? 'ok' : pior}`}>{estado}</span>
      </div>
      {recentes.length ? (
        <ol className="auto-events" aria-label="Eventos recentes do robô">
          {recentes.map((e, i) => (
            <li key={`${e.at}-${i}`} className={`sev-${e.severity || 'info'}`}>
              <time dateTime={e.at}>{horaSeg(e.at).slice(0, 5)}</time>
              <span className="auto-kind">{ROT_KIND[e.kind] || e.kind || 'evento'}</span>
              <span className="auto-text">{e.text || ROT_SRC[e.source] || e.source || ''}</span>
            </li>
          ))}
        </ol>
      ) : <p className="auto-empty">Nenhum evento recebido ainda.</p>}
      <dl className="auto-sys">
        {linhas.map(l => (
          <div key={l.k} className={l.tom ? `is-${l.tom}` : undefined}><dt>{l.k}</dt><dd>{l.v}</dd></div>
        ))}
      </dl>
      <button type="button" className="auto-open" onClick={onAbrir}>
        Abrir automação <ArrowRight className="ico" aria-hidden="true" />
      </button>
    </section>
  );
}
