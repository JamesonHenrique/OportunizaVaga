'use client';

import { Sun, Moon, CloudOff, EyeOff, Activity, WifiOff, FlaskConical } from 'lucide-react';
import { dataHora } from '@/lib/dashboard';
import { Mark } from '@/components/brand/Brand';

function alternarTema() {
  const raiz = document.documentElement;
  const novo = raiz.dataset.theme === 'light' ? 'dark' : 'light';
  raiz.dataset.theme = novo;
  try { localStorage.setItem('monitor:tema', novo); } catch {}
}

// The one sticky header, on every tab and width: where am I · is the data fresh · theme.
// Below 1024px it also carries the brand mark (the sidebar turns into the bottom tab bar).
// Cache / demo / public notices are spelled out in text, never tooltip-only.
export default function StatusStrip({ secao, contexto, fr, idadeSinal, avisoCache, modo, onInicio }) {
  return (
    <header className="topbar">
      <div className="topbar-row">
        <a className="topbar-brand" href="#topo" onClick={(e) => { e.preventDefault(); onInicio?.(); }} aria-label="OportunizaVaga — Início">
          <Mark size={26} />
        </a>
        <p className="topbar-ctx">{secao}{contexto && <span> · {contexto}</span>}</p>
        <div className="topbar-side">
          {modo.id === 'demo' && (
            <span className="topbar-tag is-demo"><FlaskConical className="ico" aria-hidden="true" /><span>{modo.rotulo}</span></span>
          )}
          {modo.id === 'publico' && (
            <span className="topbar-tag" title="Textos, terminal e dados pessoais ficam ocultos nesta visão.">
              <EyeOff className="ico" aria-hidden="true" /><span>{modo.rotulo}</span>
            </span>
          )}
          <span className={`freshness${fr.semSinal ? ' is-stale' : ''}`} role="status"
                title={`Último sinal do robô: ${fr.ref ? dataHora(fr.ref) : 'nenhum'}`}>
            {fr.semSinal ? <WifiOff className="ico" aria-hidden="true" /> : <Activity className="ico" aria-hidden="true" />}
            <span>{fr.ref ? (
              <><span className={fr.semSinal ? undefined : 'freshness-prefix'}>{fr.semSinal ? 'Sem sinal · ' : 'Última atualização '}</span>{idadeSinal}</>
            ) : (
              <><span className="freshness-prefix">Nenhuma atualização recebida</span><span className="freshness-compact">Sem sinal</span></>
            )}</span>
          </span>
          <button type="button" className="theme-toggle" onClick={alternarTema} aria-label="Alternar tema claro/escuro" title="Alternar tema claro/escuro">
            <Sun className="ico ico-sun" aria-hidden="true" />
            <Moon className="ico ico-moon" aria-hidden="true" />
          </button>
        </div>
      </div>
      {avisoCache && (
        <p className="topbar-warn" role="status"><CloudOff className="ico" aria-hidden="true" /><span><b>Em cache.</b> {avisoCache}</span></p>
      )}
    </header>
  );
}
