'use client';

import { hora } from '@/lib/dashboard';

// Fallback ladder as rows with a state pill: in use / hit the limit today / available.
// Only OpenRouter exposes a real quota; the others show the limit counter from loop.log.
export default function ModelsPanel({ modelos: m }) {
  const escada = m?.escada || [];
  const tiers = [...new Set(escada.map(x => x.tier || x.id.split('/')[0]))];
  const q = m?.openrouterQuota;
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Uso dos modelos</h2>
        <span>{escada.length} na cascata · {m?.noTetoHoje?.length || 0} no teto</span>
      </div>
      <div className="panel-body">
        <div className="model-now">
          <span className="card-label">em uso agora</span>
          {m?.emUso
            ? <><code>{m.emUso}</code><small>desde {hora(m.desde)}</small></>
            : <em>nenhuma rodada concluiu ainda</em>}
        </div>

        {q ? (
          <div className="bars-block">
            <span className="bars-title">OpenRouter :free · {q.used}/{q.limit} requisições hoje ({q.remaining} restam)</span>
            <div className="bar-row">
              <span className="bar-track"><span className={`bar-fill ${q.percent >= 90 ? 'warn' : 'ok'}`} style={{ width: `${Math.min(100, q.percent)}%` }} /></span>
              <span className="bar-num">{Math.round(q.percent)}%</span>
            </div>
          </div>
        ) : <p className="line-note">OpenRouter: {m?.quotaMotivo || 'sem dados de cota'}</p>}

        {tiers.map(t => (
          <div className="bars-block" key={t}>
            <span className="bars-title">{t}</span>
            <ul className="ladder">
              {escada.filter(x => (x.tier || x.id.split('/')[0]) === t).map(mod => {
                const pos = escada.indexOf(mod) + 1;
                const emUso = mod.id === m?.emUso;
                const estado = emUso ? 'em-uso' : (mod.tetoHoje > 0 ? 'teto' : 'livre');
                return (
                  <li key={mod.id} className={`ladder-row s-${estado}`} title={mod.id}>
                    <span className="ladder-pos">{pos}</span>
                    <span className="ladder-name">{mod.id.split('/').slice(1).join('/') || mod.id}</span>
                    <span className={`pill ${emUso ? 'pill-ok' : (mod.tetoHoje > 0 ? 'pill-warn' : 'pill-mute')}`}>
                      {emUso ? 'em uso' : (mod.tetoHoje > 0 ? `teto ×${mod.tetoHoje}` : 'livre')}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
        <p className="line-note">"teto ×n" = quantas vezes bateu no limite hoje (contador do loop.log).</p>
      </div>
    </section>
  );
}
