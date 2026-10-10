'use client';

import { Sun, Moon, CloudOff, EyeOff, Activity, WifiOff } from 'lucide-react';
import { desde, dataHora } from '@/lib/dashboard';

function alternarTema() {
  const raiz = document.documentElement;
  const novo = raiz.dataset.theme === 'light' ? 'dark' : 'light';
  raiz.dataset.theme = novo;
  try { localStorage.setItem('monitor:tema', novo); } catch {}
}

// One sticky line that answers "is it alive?": a pill per loop + heartbeat.
// Cache / public-view notices shrink to icons with a tooltip.
export default function StatusStrip({ loops, semSinal, updatedAt, agora, avisoCache, publico, demo }) {
  const hb = updatedAt ? desde(updatedAt, agora) : 'nunca';
  return (
    <header className="strip">
      <div className="strip-inner">
        <div className="strip-brand">
          <img src="/icon.svg" alt="" className="strip-mark" aria-hidden="true" />
          <div className="strip-name">
            <b>Oportuniza<span>Vaga</span></b>
            <small>Monitor do robô de candidaturas</small>
          </div>
        </div>
        <div className="strip-pills" role="group" aria-label="Estado dos robôs">
          {loops.map(l => (
            <span key={l.nome} className={`pill pill-${l.tom}${l.vivo ? ' is-live' : ''}`} title={l.detalhe || ''}>
              <i aria-hidden="true" />{l.nome} <b>· {l.frase}</b>
            </span>
          ))}
        </div>
        <div className="strip-side">
          {demo && <span className="pill pill-mute" title="Dados fictícios gerados pelo monitor (MONITOR_DEMO=1)"><i aria-hidden="true" />demo · dados fictícios</span>}
          {avisoCache && <span className="strip-ico" title={avisoCache}><CloudOff className="ico" aria-label={avisoCache} /></span>}
          {publico && <span className="strip-ico" title="Visão pública: terminal oculto. Abra com ?secret=SUA_CHAVE."><EyeOff className="ico" aria-label="Visão pública" /></span>}
          <span className={`heartbeat${semSinal ? ' is-stale' : ''}`}
                title={`Último heartbeat do PC: ${updatedAt ? dataHora(updatedAt) : 'nenhum'}`}>
            {semSinal ? <WifiOff className="ico" aria-hidden="true" /> : <Activity className="ico" aria-hidden="true" />}
            <span className="hb-label">{semSinal ? 'Sem sinal' : 'Heartbeat'}</span>
            <b>{hb}</b>
          </span>
          <button className="theme-toggle" onClick={alternarTema} title="Alternar tema claro/escuro" aria-label="Alternar tema claro/escuro">
            <Sun className="ico ico-sun" aria-hidden="true" />
            <Moon className="ico ico-moon" aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}
