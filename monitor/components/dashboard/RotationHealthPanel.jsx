'use client';

import { Inbox } from 'lucide-react';
import Collapsible from './Collapsible';
import { dataHora } from '@/lib/dashboard';

// Per-site rotation health (rounds/empty streak/applications/pause) as sent by
// the publisher, plus the last validate-rodada.log run. Counters only — the
// [FALHA] text is technical (schema/JSON), never personal data.
export default function RotationHealthPanel({ rodizioSaude: r }) {
  const sites = Object.entries(r?.sites || {});
  const v = r?.validacao || { ok: null, falha: null };
  const validOk = v.ok === true;
  const validMeta = v.ok === null ? 'sem dados' : (validOk ? 'validação OK' : 'validação FALHOU');
  return (
    <Collapsible title="Saúde do rodízio" meta={sites.length ? `${sites.length} site(s) · ${validMeta}` : validMeta} defaultOpen={!validOk}>
      <div className="panel-body">
        {r?.atualizado && <p className="line-note">Atualizado {dataHora(r.atualizado)}</p>}
        {sites.length ? (
          <div className="list">
            {sites.map(([nome, s]) => (
              <div className="row compact" key={nome}>
                <div className="who">
                  <b>{nome}</b>
                  <p>
                    {s?.rodadas ?? 0} rodada(s) · {s?.vazias_seguidas ?? 0} vazia(s) seguida(s) · {s?.aplicadas ?? 0} aplicada(s)
                  </p>
                </div>
                {s?.pausado_ate
                  ? <span className="tag">pausado até {dataHora(s.pausado_ate)}</span>
                  : <span className="tag muted">ativo</span>}
              </div>
            ))}
          </div>
        ) : (
          <p className="empty"><Inbox className="ico" aria-hidden="true" />Sem dados de saúde do rodízio ainda.</p>
        )}
        <div className={`lead ${validOk ? '' : (v.ok === false ? 'is-warn' : '')}`} style={{ marginTop: 8 }}>
          {v.ok === null && <em>Sem execução registrada de validate-rodada.</em>}
          {validOk && <span>Última validação: OK.</span>}
          {v.ok === false && <span>Última validação FALHOU: <code>{v.falha || 'motivo não registrado'}</code></span>}
        </div>
      </div>
    </Collapsible>
  );
}
