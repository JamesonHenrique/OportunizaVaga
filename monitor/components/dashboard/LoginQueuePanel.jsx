'use client';

import { KeyRound } from 'lucide-react';
import VagaLink from './VagaLink';
import { dataHora, desde } from '@/lib/dashboard';

// Compatible jobs held only by an expired login (aplicadas.json -> aguardando_login).
// Grouped by canal: logging into that site in the Chrome 9222 releases the whole group,
// and the robot sends them at the start of its next round.
export default function LoginQueuePanel({ itens, agora }) {
  if (!itens.length) return null;
  const grupos = new Map();
  for (const it of itens) {
    if (!grupos.has(it.canal)) grupos.set(it.canal, []);
    grupos.get(it.canal).push(it);
  }
  return (
    <section className="panel login-queue">
      <div className="panel-head">
        <h2><KeyRound className="ico" aria-hidden="true" /> Esperando login</h2>
        <span>{itens.length} vaga(s) compatível(is)</span>
      </div>
      <p className="line-note">
        Não se perdem: faça login no site no navegador do robô e ele envia na próxima rodada.
      </p>
      <div className="lq-groups">
        {[...grupos.entries()].map(([canal, vagas]) => {
          const chk = vagas[0].checagem;
          const logado = chk?.logado === 'sim';
          return (
            <div className="lq-group" key={canal}>
              <div className="lq-head">
                <b>{canal}</b>
                <span className={`pill ${logado ? 'pill-ok' : 'pill-warn'}`}>
                  {chk ? (logado ? 'logado — enviando' : 'deslogado') : 'ainda não checado'}
                </span>
                {chk?.em && <small title={dataHora(chk.em)}>checado {desde(chk.em, agora)}</small>}
              </div>
              <ul>
                {vagas.map(v => (
                  <li key={v.chave}>
                    <VagaLink url={v.url} className="lq-title">
                      <b>{v.empresa || v.chave}</b>{v.vaga ? ` — ${v.vaga}` : ''}
                    </VagaLink>
                    <small title={v.motivo || ''}>
                      esperando {desde(v.em, agora).replace('há ', '')}
                      {v.score != null ? ` · score ${v.score}` : ''}
                    </small>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </section>
  );
}
