'use client';

import { Sun, Moon, CloudOff, EyeOff, Activity, WifiOff, FlaskConical } from 'lucide-react';
import { desde, dataHora } from '@/lib/dashboard';

function alternarTema() {
  const raiz = document.documentElement;
  const novo = raiz.dataset.theme === 'light' ? 'dark' : 'light';
  raiz.dataset.theme = novo;
  try { localStorage.setItem('monitor:tema', novo); } catch {}
}

// Top bar of the main area: context on the left, "is it alive?" on the right (heartbeat + theme).
// Loop states live in the automation monitor card; cache/public notices are spelled out, not tooltip-only.
export default function StatusStrip({ contexto, semSinal, updatedAt, agora, avisoCache, publico, demo }) {
  const hb = updatedAt ? desde(updatedAt, agora) : 'nunca';
  return (
    <header className="topbar">
      <div className="topbar-row">
        <p className="topbar-ctx">Monitor de candidaturas{contexto && <span> · {contexto}</span>}</p>
        <div className="topbar-side">
          {demo && (
            <span className="topbar-tag" title="Dados fictícios gerados pelo monitor (MONITOR_DEMO=1)">
              <FlaskConical className="ico" aria-hidden="true" /><span>Demo · dados fictícios</span>
            </span>
          )}
          {publico && (
            <span className="topbar-tag" title="Terminal e textos dos eventos ficam ocultos. Abra com ?secret=SUA_CHAVE.">
              <EyeOff className="ico" aria-hidden="true" /><span>Visão pública</span>
            </span>
          )}
          <span className={`heartbeat${semSinal ? ' is-stale' : ''}`} role="status"
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
      {avisoCache && (
        <p className="topbar-warn" role="status"><CloudOff className="ico" aria-hidden="true" />{avisoCache}</p>
      )}
    </header>
  );
}
