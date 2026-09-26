'use client';

import { Sun, Moon, CloudOff, EyeOff } from 'lucide-react';
import { desde } from '@/lib/dashboard';

function alternarTema() {
  const raiz = document.documentElement;
  const novo = raiz.dataset.theme === 'light' ? 'dark' : 'light';
  raiz.dataset.theme = novo;
  try { localStorage.setItem('monitor:tema', novo); } catch {}
}

// One sticky line that answers "is it alive?": a pill per loop + heartbeat.
// Cache / public-view notices shrink to icons with a tooltip.
export default function StatusStrip({ loops, semSinal, updatedAt, agora, avisoCache, publico, demo }) {
  return (
    <header className="strip">
      <div className="strip-brand">
        <img src="/icon.svg" alt="" className="strip-mark" />
        <span>OportunizaVaga</span>
      </div>
      <div className="strip-pills">
        {loops.map(l => (
          <span key={l.nome} className={`pill pill-${l.tom}`} title={l.detalhe || ''}>
            <i aria-hidden="true" />{l.nome} · {l.frase}
          </span>
        ))}
      </div>
      <div className="strip-side">
        {demo && <span className="pill pill-quiet" title="Dados fictícios gerados pelo monitor (MONITOR_DEMO=1)"><i aria-hidden="true" />demo · dados fictícios</span>}
        {avisoCache && <span className="strip-ico" title={avisoCache}><CloudOff className="ico" aria-label={avisoCache} /></span>}
        {publico && <span className="strip-ico" title="Visão pública: terminal oculto. Abra com ?secret=SUA_CHAVE."><EyeOff className="ico" aria-label="Visão pública" /></span>}
        <span className={`pill ${semSinal ? 'pill-bad' : 'pill-quiet'}`} title="Último heartbeat do PC">
          <i aria-hidden="true" />{semSinal ? `sem sinal ${desde(updatedAt, agora)}` : `atualizado ${desde(updatedAt, agora)}`}
        </span>
        <button className="theme-toggle" onClick={alternarTema} title="Alternar tema claro/escuro" aria-label="Alternar tema claro/escuro">
          <Sun className="ico ico-sun" aria-hidden="true" />
          <Moon className="ico ico-moon" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
