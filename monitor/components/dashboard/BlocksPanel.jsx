'use client';

import { useMemo, useState } from 'react';
import { Inbox, Download } from 'lucide-react';
import VagaLink from './VagaLink';
import { classificar, tituloBloq, GRUPO_ROTULO, baixarCSV } from '@/lib/dashboard';

const PAG = 10;
const GRUPOS = [
  ['todos', 'Todos'],
  ['voce', 'Depende de você'],
  ['robo', 'Robô retenta'],
  ['final', 'Descartadas'],
];

// Blocks triaged by who can act: the candidate (login, missing data, broken signup),
// the robot (retries by itself) or nobody (final verdict: level, stack, not remote).
// Cause chips filter the list; long robot texts stay collapsed until expanded.
export default function BlocksPanel({ bloqueios }) {
  const [busca, setBusca] = useState('');
  const [grupo, setGrupo] = useState('todos');
  const [causa, setCausa] = useState(null);
  const [pagina, setPagina] = useState(1);
  const [abertos, setAbertos] = useState(() => new Set());

  const itens = useMemo(() => bloqueios.map(b => {
    const c = classificar(b);
    // `retentar` is the robot's own flag: it wins over the text heuristic.
    return { ...b, _causa: c.causa, _grupo: b.retentar ? 'robo' : c.grupo, _titulo: tituloBloq(b) };
  }), [bloqueios]);

  const contaGrupo = useMemo(() => {
    const m = { todos: itens.length, voce: 0, robo: 0, final: 0 };
    for (const b of itens) m[b._grupo] += 1;
    return m;
  }, [itens]);

  const doGrupo = useMemo(
    () => (grupo === 'todos' ? itens : itens.filter(b => b._grupo === grupo)),
    [itens, grupo]
  );
  const causas = useMemo(() => {
    const m = new Map();
    for (const b of doGrupo) m.set(b._causa, (m.get(b._causa) || 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [doGrupo]);
  const maxCausa = causas[0]?.[1] || 1;

  const buscaL = busca.trim().toLowerCase();
  const filtrados = doGrupo.filter(b =>
    (!causa || b._causa === causa) &&
    (!buscaL || `${b._titulo} ${b.chave || ''} ${b.motivo || ''} ${b.origem || ''}`.toLowerCase().includes(buscaL))
  );
  const totalPag = Math.max(1, Math.ceil(filtrados.length / PAG));
  const pagAtual = Math.min(pagina, totalPag); // clamp: list shrink never leaves a blank page
  const paginaAtual = filtrados.slice((pagAtual - 1) * PAG, pagAtual * PAG);

  const trocarGrupo = (g) => { setGrupo(g); setCausa(null); setPagina(1); };
  const trocarCausa = (c) => { setCausa(atual => (atual === c ? null : c)); setPagina(1); };
  const alternar = (k) => setAbertos(s => {
    const n = new Set(s);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });
  const exportar = () => baixarCSV(
    'bloqueios.csv',
    ['titulo', 'chave', 'origem', 'causa', 'grupo', 'quando', 'motivo', 'url'],
    filtrados.map(b => [b._titulo, b.chave, b.origem, b._causa, GRUPO_ROTULO[b._grupo], b._ref?.txt, b.motivo, b.url || ''])
  );

  return (
    <section className="panel blocks">
      <div className="panel-head">
        <h2>Bloqueios</h2>
        <span>{filtrados.length}/{bloqueios.length}</span>
        <button type="button" className="btn-ghost" onClick={exportar} disabled={!filtrados.length}>
          <Download className="ico" aria-hidden="true" /> CSV
        </button>
      </div>

      <div className="seg" role="tablist" aria-label="Quem pode agir">
        {GRUPOS.map(([id, rot]) => (
          <button key={id} type="button" role="tab" aria-selected={grupo === id}
                  className={`seg-btn seg-${id}${grupo === id ? ' is-on' : ''}`} onClick={() => trocarGrupo(id)}>
            {rot} <span>{contaGrupo[id]}</span>
          </button>
        ))}
      </div>

      {causas.length > 0 && (
        <div className="cause-chips" aria-label="Filtrar por causa">
          {causas.map(([c, n]) => (
            <button key={c} type="button" aria-pressed={causa === c}
                    className={`cause-chip${causa === c ? ' is-on' : ''}`} onClick={() => trocarCausa(c)}>
              <span className="cause-bar" style={{ width: `${Math.max(6, (n / maxCausa) * 100)}%` }} aria-hidden="true" />
              <span className="cause-lbl">{c}</span>
              <b>{n}</b>
            </button>
          ))}
        </div>
      )}

      <div className="search-row">
        <input
          value={busca}
          onChange={(e) => { setBusca(e.target.value); setPagina(1); }}
          placeholder="buscar empresa, vaga, motivo…"
          aria-label="Buscar bloqueio"
          name="busca-bloqueio"
          autoComplete="off"
        />
      </div>

      <div className="list blocks-list">
        {paginaAtual.length ? paginaAtual.map((b, i) => {
          const k = `${b.origem}:${b.chave || i}`;
          const aberto = abertos.has(k);
          const longo = (b.motivo || '').length > 200;
          return (
            <article className={`block-card g-${b._grupo}`} key={k}>
              <div className="block-card-head">
                <VagaLink url={b.url} className="block-title">{b._titulo}</VagaLink>
                <span className="block-when" title={b.em || ''}>{b._ref?.txt}</span>
              </div>
              <div className="block-tags">
                <span className={`tag g-tag-${b._grupo}`}>{GRUPO_ROTULO[b._grupo]}</span>
                <span className="tag muted">{b._causa}</span>
                {b.origem === 'linkedin' && <span className="tag muted">linkedin-rh</span>}
                {b.retentar && <span className="tag">retentar: {String(b.retentar)}</span>}
              </div>
              {b.motivo && (
                <p className={`block-text${aberto || !longo ? '' : ' is-clamped'}`}>{b.motivo}</p>
              )}
              {longo && (
                <button type="button" className="link-btn" onClick={() => alternar(k)} aria-expanded={aberto}>
                  {aberto ? 'ver menos' : 'ver motivo completo'}
                </button>
              )}
            </article>
          );
        }) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Nenhum bloqueio para este filtro.</p>}
      </div>

      {totalPag > 1 && (
        <div className="pager">
          <button onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={pagAtual <= 1} aria-label="Página anterior">‹</button>
          <span>{pagAtual} / {totalPag}</span>
          <button onClick={() => setPagina(p => Math.min(totalPag, p + 1))} disabled={pagAtual >= totalPag} aria-label="Próxima página">›</button>
        </div>
      )}
    </section>
  );
}
