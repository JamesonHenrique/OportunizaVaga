'use client';

import { House, Send, ShieldAlert, Bot, Users, MessageCircle } from 'lucide-react';
import { Mark, Wordmark } from '@/components/brand/Brand';

const ICONE = { inicio: House, candidaturas: Send, bloqueios: ShieldAlert, robo: Bot, linkedin: Users, telegram: MessageCircle };

// One navigation for every width (CSS only switches the layout):
// ≥1200px vertical rail with labels · 1024–1199px icon rail · <1024px fixed bottom tab bar
// with equal-width cells and short labels, so no item is ever clipped or scrolled away.
// itens: [{ id, rotulo, curto?, conta?, alerta? }]; `ativo` = the visible workspace.
export default function Sidebar({ itens, ativo, onSelect, rodape }) {
  return (
    <aside className="sidebar" style={{ '--nav-n': itens.length }}>
      <a className="side-brand" href="#topo" onClick={(e) => { e.preventDefault(); onSelect('inicio'); }} aria-label="OportunizaVaga — Início">
        <Mark size={30} />
        <Wordmark />
      </a>
      <nav className="side-nav" aria-label="Seções do monitor">
        {itens.map(it => {
          const Ico = ICONE[it.id];
          const on = ativo === it.id;
          return (
            <button key={it.id} type="button" className={`side-item${on ? ' is-on' : ''}`}
                    aria-current={on ? 'page' : undefined} title={it.rotulo} onClick={() => onSelect(it.id)}>
              {Ico && <Ico className="ico" aria-hidden="true" />}
              <span className="side-lbl">{it.rotulo}</span>
              <span className="side-short">{it.curto || it.rotulo}</span>
              {it.conta != null && <em className="side-count"><span className="sr-only">, </span>{it.conta}</em>}
              {it.alerta && <span className="side-dot"><span className="sr-only">, tem pendência</span></span>}
            </button>
          );
        })}
      </nav>
      {rodape && <div className="side-foot">{rodape}</div>}
    </aside>
  );
}
