'use client';

import { Inbox } from 'lucide-react';
import Collapsible from './Collapsible';
import { dataHora, desde } from '@/lib/dashboard';

// Per-site rotation health as a grid of site tiles: active / next / paused (with until when),
// plus the last validate-rodada.log run. Counters only.
// `portais`: normalized list from listaPortais(d) (API saudePortais || legacy portais); hidden when empty.
function PortaisSaude({ portais, agora }) {
  if (!portais?.length) return null;
  const ruins = portais.filter(p => p.tom === 'bad' || p.tom === 'warn').length;
  return (
    <div className="bars-block">
      <span className="bars-title">saúde por portal · {ruins ? `${ruins} com problema` : 'nenhum problema registrado'}</span>
      <ul className="portal-list">
        {portais.map(p => (
          <li key={p.nome}>
            <b>{p.nome}</b>
            <span className={`pill pill-${p.tom}`}><i aria-hidden="true" />{p.rotulo}</span>
            <small>{p.checkedAt ? `verificado ${desde(p.checkedAt, agora)}` : 'sem horário de verificação'}</small>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function RotationHealthPanel({ rodizioSaude: r, proximo, portais = [] }) {
  const sites = Object.entries(r?.sites || {});
  const agora = Date.now();
  const v = r?.validacao || { ok: null, falha: null };
  const validOk = v.ok === true;
  const pausados = sites.filter(([, s]) => s?.pausado_ate && new Date(s.pausado_ate).getTime() > agora).length;
  const validMeta = v.ok === null ? 'sem validação' : (validOk ? 'validação OK' : 'validação FALHOU');
  return (
    <Collapsible title="Saúde dos portais e do rodízio"
                 meta={sites.length ? `${sites.length - pausados}/${sites.length} ativos · ${validMeta}` : `${portais.length} portal(is)`}
                 defaultOpen={!validOk || pausados > 0 || portais.some(p => p.tom === 'bad')}>
      <div className="panel-body">
        <PortaisSaude portais={portais} agora={agora} />
        {sites.length ? (
          <div className="site-grid">
            {sites.map(([nome, s]) => {
              const pausado = s?.pausado_ate && new Date(s.pausado_ate).getTime() > agora;
              const prox = nome === proximo;
              return (
                <div key={nome} className={`site-tile${pausado ? ' is-paused' : ''}${prox ? ' is-next' : ''}`}>
                  <div className="site-head">
                    <b>{nome}</b>
                    {prox ? <span className="pill pill-ok">próximo</span>
                      : pausado ? <span className="pill pill-warn">pausado</span>
                        : <span className="pill pill-mute">ativo</span>}
                  </div>
                  <div className="site-nums">
                    <span><b>{s?.aplicadas ?? 0}</b> envios</span>
                    <span><b>{s?.rodadas ?? 0}</b> rodadas</span>
                    <span><b>{s?.vazias_seguidas ?? 0}</b> secas</span>
                  </div>
                  {pausado && <small>volta {dataHora(s.pausado_ate)}</small>}
                </div>
              );
            })}
          </div>
        ) : !portais.length && (
          <p className="empty"><Inbox className="ico" aria-hidden="true" />Sem dados de saúde do rodízio ainda.</p>
        )}
        {(sites.length > 0 || v.ok !== null) && <p className={`verdict ${validOk ? 'v-ok' : (v.ok === false ? 'v-bad' : 'v-mute')}`}>
          {v.ok === null && 'Sem execução registrada de validate-rodada.'}
          {validOk && 'Última validação do aplicadas.json: OK.'}
          {v.ok === false && <>Validação FALHOU: <code>{v.falha || 'motivo não registrado'}</code></>}
        </p>}
        {r?.atualizado && <p className="line-note">Atualizado {dataHora(r.atualizado)} · site seco = 4 rodadas sem nenhuma vaga nova → pausa de 12h a 48h</p>}
      </div>
    </Collapsible>
  );
}
