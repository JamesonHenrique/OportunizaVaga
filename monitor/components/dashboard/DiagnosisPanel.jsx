'use client';

import { desde, horaSeg, dia } from '@/lib/dashboard';
import { Barras } from './Charts';

export default function DiagnosisPanel({
  d, loops, agora, ultimaAplicada, rodadasDesdeEnvio, horasSemEnviar, gruposBloq, totalBloqueios
}) {
  const meta = d._meta || null;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Por que não está enviando?</h2>
        <span>{ultimaAplicada ? `último envio ${desde(ultimaAplicada, agora)}` : 'nenhum envio com horário'}</span>
      </div>
      <div className="panel-body">
        <p className="lead">
          {ultimaAplicada ? (
            <>Última candidatura <code>{horaSeg(ultimaAplicada)}</code> ({dia(ultimaAplicada)}) ·{' '}
            <strong>{rodadasDesdeEnvio}</strong> rodadas desde então sem envio novo
            {horasSemEnviar != null && <> · <strong>{horasSemEnviar.toFixed(1)}h</strong> sem enviar</>}.</>
          ) : (
            <em>Nenhuma candidatura com horário exato ainda.</em>
          )}
        </p>
        {horasSemEnviar != null && horasSemEnviar >= 48 && (
          <p className="lead" style={{ color: 'var(--warn, #f59e0b)' }}>
            <strong>SECO:</strong> {(horasSemEnviar / 24).toFixed(1)} dias sem envio novo
            ({rodadasDesdeEnvio} rodadas no período) — funil descartando tudo, não falha de POST.
          </p>
        )}
        <div className="bars-block">
          <span className="bars-title">bloqueios por causa · {totalBloqueios} abertos</span>
          <Barras itens={gruposBloq} tom="warn" />
        </div>
        <p className="line-note">
          LinkedIn: {loops.linkedin?.state ? `${loops.linkedin.state} — ${loops.linkedin.message || ''}` : 'sem dados'} ·
          Modelo: {d.modelos?.emUso ? <code>{d.modelos.emUso}</code> : '—'} ·
          Heartbeat da máquina: {d.updatedAt ? desde(d.updatedAt, agora) : 'nunca'}
          {meta ? <> · instância <code>{meta.instanceId}</code> ({meta.posts} posts)</> : null}
        </p>
        {d.descartes && d.descartes.total > 0 && (
          <p className="line-note">
            descartes na listagem (pré-filtro): <strong>{d.descartes.nivel}</strong> nível ·{' '}
            <strong>{d.descartes.modelo}</strong> modelo · <strong>{d.descartes.stack}</strong> stack ·{' '}
            {d.descartes.total} no total — vagas rejeitadas sem gastar leitura de modelo
          </p>
        )}
      </div>
    </section>
  );
}
