'use client';

import { useMemo, useState } from 'react';
import { Inbox } from 'lucide-react';
import VagaLink from './VagaLink';
import { Sparkbars } from './Charts';
import { Seg, Tiles, Busca, Pager, paginar } from './ui';
import { serieDias } from '@/lib/dashboard';

const PAG = 12;
const iniciais = (n) => String(n || '?').trim().split(/\s+/).slice(0, 2).map(p => p[0]?.toUpperCase() || '').join('') || '?';

export default function InvitesPanel({ convites, bloqueios = [], convitesHoje = 0, limiteDiario, hoje, loop }) {
  const [filtro, setFiltro] = useState('todos');
  const [busca, setBusca] = useState('');
  const [pagina, setPagina] = useState(1);

  const comNota = convites.filter(c => c.nota_enviada).length;
  const porDia = useMemo(() => {
    const m = new Map();
    for (const c of convites) if (c.data) m.set(c.data, (m.get(c.data) || 0) + 1);
    return [...m.entries()];
  }, [convites]);
  const serie = hoje ? serieDias(porDia, hoje, 14) : porDia.slice(-14);
  const semana = serie.slice(-7).reduce((a, [, n]) => a + n, 0);

  const buscaL = busca.trim().toLowerCase();
  const filtrados = convites.filter(c =>
    (filtro === 'todos' || (filtro === 'nota' ? c.nota_enviada : !c.nota_enviada)) &&
    (!buscaL || `${c.nome || ''} ${c.headline || ''}`.toLowerCase().includes(buscaL))
  );
  const pag = paginar(filtrados, pagina, PAG);
  const bloqRecentes = bloqueios.slice().reverse().slice(0, 5);

  return (
    <div className="li-tab">
      <section className="panel">
        <div className="panel-head">
          <h2>Convites LinkedIn-RH</h2>
          <span>{loop?.message ? loop.message.slice(0, 90) : ''}</span>
        </div>
        <div className="panel-body">
          <Tiles itens={[
            { rotulo: 'Total', valor: convites.length, sub: 'recrutadores conectados' },
            { rotulo: 'Hoje', valor: `${convitesHoje}/${limiteDiario ?? 10}`, sub: 'limite diário', tom: convitesHoje ? 'ok' : undefined },
            { rotulo: 'Últimos 7 dias', valor: semana, sub: 'meta semanal 70' },
            { rotulo: 'Com nota', valor: convites.length ? `${Math.round((comNota / convites.length) * 100)}%` : '—', sub: `${comNota} convite(s)` },
          ]} />
          <div className="bars-block">
            <span className="bars-title">convites por dia · 14 dias</span>
            <Sparkbars dados={serie} />
          </div>
        </div>
      </section>

      {bloqRecentes.length > 0 && (
        <section className="panel">
          <div className="panel-head"><h2>Bloqueios do robô de convites</h2><span>{bloqueios.length}</span></div>
          <div className="list">
            {bloqRecentes.map((b, i) => (
              <article className={`block-card ${/sess/.test(b.tipo || '') ? 'g-voce' : 'g-robo'}`} key={`${b.data}-${i}`}>
                <div className="block-card-head">
                  <span className="block-title">{/sess/.test(b.tipo || '') ? 'Sessão do LinkedIn expirada' : (b.tipo || 'bloqueio').replace(/_/g, ' ')}</span>
                  <span className="block-when">{b.data}</span>
                </div>
                <p className="block-text is-clamped">{b.detalhe}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-head"><h2>Recrutadores</h2><span>{filtrados.length}/{convites.length}</span></div>
        <Seg rotulo="Nota" valor={filtro} onChange={(f) => { setFiltro(f); setPagina(1); }} opcoes={[
          { id: 'todos', rotulo: 'Todos', conta: convites.length },
          { id: 'nota', rotulo: 'Com nota', conta: comNota },
          { id: 'sem', rotulo: 'Sem nota', conta: convites.length - comNota },
        ]} />
        <Busca valor={busca} onChange={(v) => { setBusca(v); setPagina(1); }} placeholder="buscar nome ou cargo…" nome="busca-convites" />
        {pag.itens.length ? (
          <div className="person-grid">
            {pag.itens.map((c, i) => (
              <article className="person" key={c.perfil_url || i}>
                <span className="avatar" aria-hidden="true">{iniciais(c.nome)}</span>
                <div className="person-body">
                  <VagaLink url={c.perfil_url}><b>{c.nome}</b></VagaLink>
                  <p className="block-text is-clamped">{c.headline}</p>
                  <div className="block-tags">
                    <span className="tag muted">{c.data ? `${c.data.slice(8)}/${c.data.slice(5, 7)}` : '--/--'}</span>
                    <span className={`tag ${c.nota_enviada ? 'st-ok' : 'muted'}`}>{c.nota_enviada ? 'com nota' : 'sem nota'}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : <p className="empty"><Inbox className="ico" aria-hidden="true" />Nenhum convite para este filtro.</p>}
        <Pager pagina={pag.atual} total={pag.total} onChange={setPagina} />
      </section>
    </div>
  );
}
