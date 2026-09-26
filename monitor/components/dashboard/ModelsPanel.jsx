'use client';

import { hora } from '@/lib/dashboard';

export default function ModelsPanel({ modelos: m }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Uso dos modelos</h2>
        <span>{m?.escada?.length || 0} na cascata · {m?.noTetoHoje?.length || 0} no teto</span>
      </div>
      <div className="panel-body">
        <p className="lead">
          {m?.emUso
            ? <><code>{m.emUso}</code> <small>desde {hora(m.desde)}</small></>
            : <em>nenhuma rodada concluiu ainda — o modelo aparece quando a primeira terminar</em>}
        </p>

        {/* OpenRouter REAL quota: the only provider exposing usage via API.
            Quota is per ACCOUNT (shared by :free models), not per model. */}
        {m?.openrouterQuota && (
          <div className="bars-block">
            <span className="bars-title">
              OpenRouter · {m.openrouterQuota.used}/{m.openrouterQuota.limit} req diárias ({m.openrouterQuota.remaining} restam)
            </span>
            <div className="bar-row">
              <span className="bar-track">
                <span
                  className={`bar-fill ${m.openrouterQuota.percent >= 90 ? 'warn' : 'ok'}`}
                  style={{ width: `${Math.min(100, m.openrouterQuota.percent)}%` }}
                />
              </span>
              <span className="bar-num">{Math.round(m.openrouterQuota.percent)}%</span>
            </div>
          </div>
        )}
        {!m?.openrouterQuota && (
          <p className="line-note">OpenRouter: {m?.quotaMotivo || 'sem dados de cota'}</p>
        )}

        {/* Full ladder in preference order. tetoHoje = times the model hit the
            limit today (from loop.log). Providers without a quota API
            (Groq/Cerebras/HF/NVIDIA/Zen) show only this counter. */}
        <div className="bars-block">
          <span className="bars-title">escada de fallback (ordem de preferência)</span>
          <div className="models-ladder">
            {(m?.escada || []).map((mod, i) => (
              <div className="bar-row" key={mod.id} title={mod.id}>
                <span className="bar-label">{i + 1} · {mod.id.split('/').slice(1).join('/') || mod.id}</span>
                <span className="bar-track">
                  <span
                    className={`bar-fill ${mod.tetoHoje > 0 ? 'warn' : 'ok'} ${mod.id === m?.emUso ? 'em-uso' : ''}`}
                    style={{ width: mod.tetoHoje > 0 ? '100%' : (mod.id === m?.emUso ? '4%' : '0%') }}
                  />
                </span>
                <span className="bar-num">{mod.tetoHoje > 0 ? `teto ×${mod.tetoHoje}` : (mod.id === m?.emUso ? 'em uso' : '—')}</span>
              </div>
            ))}
          </div>
        </div>
        <p className="line-note">
          Sem cota % para Groq/Cerebras/HuggingFace/NVIDIA/Zen — só o OpenRouter expõe.
          Barra hachurada = bateu no teto hoje (contador do log); vazia = ainda disponível.
        </p>
      </div>
    </section>
  );
}
