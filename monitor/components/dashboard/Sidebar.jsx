'use client';

import { House, Send, ShieldAlert, Bot, Users, MessageCircle } from 'lucide-react';
import { Mark, Wordmark } from '@/components/brand/Brand';

const ICONE = { inicio: House, candidaturas: Send, bloqueios: ShieldAlert, robo: Bot, linkedin: Users, telegram: MessageCircle };

// Single navigation for every width: vertical rail on desktop, horizontal scroll strip below 1024px (CSS only).
// itens: [{ id, rotulo, conta?, alerta? }]; `ativo` is 'inicio' while the overview is on screen, else the open tab.
export default function Sidebar({ itens, ativo, onSelect, rodape }) {
  return (
    <aside className="sidebar">
      <a className="side-brand" href="#topo" onClick={(e) => { e.preventDefault(); onSelect('inicio'); }} aria-label="OportunizaVaga — voltar ao início">
        <Mark size={30} />
        <Wordmark />
      </a>
      <nav className="side-nav" aria-label="Seções do monitor">
        {itens.map(it => {
          const Ico = ICONE[it.id];
          return (
            <button key={it.id} type="button" className={`side-item${ativo === it.id ? ' is-on' : ''}`}
                    aria-current={ativo === it.id ? 'true' : undefined} title={it.rotulo} onClick={() => onSelect(it.id)}>
              {Ico && <Ico className="ico" aria-hidden="true" />}
              <span className="side-lbl">{it.rotulo}</span>
              {it.conta != null && <em className="side-count">{it.conta}</em>}
              {it.alerta && <span className="side-dot" role="img" aria-label="tem pendência" />}
            </button>
          );
        })}
      </nav>
      {rodape && <div className="side-foot">{rodape}</div>}
    </aside>
  );
}
