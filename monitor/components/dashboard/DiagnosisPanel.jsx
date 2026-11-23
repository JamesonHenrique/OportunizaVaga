'use client';

import { desde, horaSeg, dia, fmtDur, ROTULO, rodadasDoLoop } from '@/lib/dashboard';
import { Barras } from './Charts';
import { Tiles } from './ui';

// "Why is it not sending?" — the answer first (one verdict line), numbers after.
function veredito({ horasSemEnviar, loops, fr }) {
  const st = loops.candidaturas?.state;
  if (!fr.ref) return { tom: 'bad', txt: 'Sem sinal do robô: o monitor ainda não recebeu nenhuma atualização.' };
  if (fr.semSinal) return { tom: 'bad', txt: 'Sem sinal recente do robô.' };
  if (st === 'quebrado' || st === 'interrompido') return { tom: 'bad', txt: `Loop ${ROTULO[st]?.toLowerCase()}: ${loops.candidaturas?.message || ''}` };
  if (st === 'quota') return { tom: 'warn', txt: 'Modelos grátis no limite — o loop espera a cota voltar.' };
  if (horasSemEnviar != null && horasSemEnviar >= 48) return { tom: 'warn', txt: `${(horasSemEnviar / 24).toFixed(1)} dias sem envio: o funil está descartando tudo (não é falha de envio).` };
  if (horasSemEnviar != null && horasSemEnviar >= 24) return { tom: 'warn', txt: `${Math.round(horasSemEnviar)}h sem envio novo.` };
  return { tom: 'ok', txt: 'Robô enviando normalmente.' };
}

export default function DiagnosisPanel({
  d, fr, loops, agora, ultimaAplicada, rodadasDesdeEnvio, horasSemEnviar, gruposBloq, totalBloqueios
}) {
  const v = veredito({ horasSemEnviar, loops, fr });
  const dur = loops.candidaturas?.duracao;
  const desc = d.descartes;
  return (
    <section className="panel diag">
      <div className="panel-head">
        <h2>Por que não está enviando?</h2>
        <span>{ultimaAplicada ? `último envio ${desde(ultimaAplicada, agora)}` : 'nenhum envio com horário'}</span>
      </div>
      <div className="panel-body">
        <p className={`verdict v-${v.tom}`}>{v.txt}</p>
        <Tiles itens={[
          { rotulo: 'Último envio', valor: ultimaAplicada ? horaSeg(ultimaAplicada).slice(0, 5) : '—', sub: ultimaAplicada ? dia(ultimaAplicada) : 'sem horário' },
          { rotulo: 'Rodadas sem envio', valor: rodadasDesdeEnvio ?? '—', sub: 'desde o último', tom: rodadasDesdeEnvio > 12 ? 'warn' : undefined },
          { rotulo: 'Rodadas hoje', valor: rodadasDoLoop(loops.candidaturas) ?? '—', sub: `média ${fmtDur(dur?.mediaMin)}` },
          { rotulo: 'Último sinal', valor: fr.ref ? desde(fr.ref, agora).replace('há ', '') : '—', sub: 'do robô', tom: fr.semSinal ? 'bad' : undefined },
        ]} />
        <div className="bars-block">
          <span className="bars-title">
            {gruposBloq ? `bloqueios por causa · ${totalBloqueios} abertos` : `bloqueios abertos · ${totalBloqueios ?? '—'}`}
          </span>
          {gruposBloq && <Barras itens={gruposBloq.slice(0, 8)} tom="warn" />}
        </div>
        {desc && desc.total > 0 && (
          <div className="bars-block">
            <span className="bars-title">descartes na listagem feitos pelo robô · {desc.total}</span>
            <Barras itens={[['nível', desc.nivel || 0], ['presencial/híbrido', desc.modelo || 0], ['stack', desc.stack || 0]]} tom="info" />
          </div>
        )}
        <p className="line-note">
          Modelo: {d.modelos?.emUso ? <code>{d.modelos.emUso}</code> : '—'}
          {d._meta ? <> · instância <code>{d._meta.instanceId}</code> ({d._meta.posts} posts)</> : null}
        </p>
      </div>
    </section>
  );
}
