'use client';

import { useMemo, useState } from 'react';
import { Inbox, Download } from 'lucide-react';
import VagaLink from './VagaLink';
import { Seg, Chips, Busca, Pager, paginar } from './ui';
import { baixarCSV, dataHora, dia, horaSeg, rotuloStatus } from '@/lib/dashboard';

const PAG = 10;
// Status -> triage group (who acts next) and card tone.
const GRUPO = { entrevista: 'etapa', etapa_teste: 'etapa', proxima_etapa: 'etapa', respondida: 'etapa', encerrada: 'fim' };
const grupoDe = (a) => GRUPO[(a.status || 'enviada').toLowerCase()] || 'aberto';
const tomDe = (a) => ({ entrevista: 'ok', etapa_teste: 'ok', proxima_etapa: 'ok', respondida: 'ok', encerrada: 'mute', em_analise: 'info' }[(a.status || '').toLowerCase()] || 'ink');

export default function ApplicationsPanel({ aplicadas }) {
  const [busca, setBusca] = useState('');
  const [grupo, setGrupo] = useState('todas');
  const [fonte, setFonte] = useState(null);
  const [pagina, setPagina] = useState(1);
  const [abertos, setAbertos] = useState(() => new Set());

  const contas = useMemo(() => {
    const c = { todas: aplicadas.length, aberto: 0, etapa: 0, fim: 0 };
    for (const a of aplicadas) c[grupoDe(a)] += 1;
    return c;
  }, [aplicadas]);
  const doGrupo = grupo === 'todas' ? aplicadas : aplicadas.filter(a => grupoDe(a) === grupo);
  const fontes = useMemo(() => {
    const m = new Map();
    for (const a of doGrupo) m.set(a.fonte || 'outro', (m.get(a.fonte || 'outro') || 0) + 1);
    return [...m.entries()].sort((x, y) => y[1] - x[1]);
  }, [doGrupo]);

  const buscaL = busca.trim().toLowerCase();
  const filtradas = doGrupo.filter(a =>
    (!fonte || (a.fonte || 'outro') === fonte) &&
    (!buscaL || `${a.empresa || ''} ${a.vaga || ''} ${a.fonte || ''} ${a.como || ''} ${a.status || ''}`.toLowerCase().includes(buscaL))
  );
  const pag = paginar(filtradas, pagina, PAG);
  const reset = (fn) => (v) => { fn(v); setPagina(1); };
  const alternar = (k) => setAbertos(s => { const n = new Set(s); if (n.has(k)) n.delete(k); else n.add(k); return n; });

  const exportar = () => baixarCSV('candidaturas.csv',
    ['data', 'hora', 'empresa', 'vaga', 'fonte', 'via', 'remota', 'status', 'como', 'url'],
    filtradas.map(a => [a.data || '', a.exato ? horaSeg(a.quando) : '', a.empresa || '', a.vaga || '', a.fonte || '', a.via || '',
      a.remota ? 'sim' : 'não', a.status || 'enviada', a.como || '', a.url || '']));

  return (
    <section className="panel apps">
      <div className="panel-head">
        <h2>Candidaturas enviadas</h2>
        <span>{filtradas.length}/{aplicadas.length}</span>
        <button type="button" className="btn-ghost" onClick={exportar} disabled={!filtradas.length}>
          <Download className="ico" aria-hidden="true" /> CSV
        </button>
      </div>

      <Seg rotulo="Status" valor={grupo} onChange={(g) => { setGrupo(g); setFonte(null); setPagina(1); }} opcoes={[
        { id: 'todas', rotulo: 'Todas', conta: contas.todas },
        { id: 'aberto', rotulo: 'Em aberto', conta: contas.aberto },
        { id: 'etapa', rotulo: 'Próxima etapa', conta: contas.etapa, tom: 'ok' },
        { id: 'fim', rotulo: 'Encerradas', conta: contas.fim },
      ]} />
      <Chips rotulo="Filtrar por fonte" itens={fontes} ativo={fonte} onChange={reset(setFonte)} />
      <Busca valor={busca} onChange={reset(setBusca)} placeholder="buscar empresa, vaga, fonte…" nome="busca-apl" />

      <div className="list cards-list">
        {pag.itens.length ? pag.itens.map((a, i) => {
          const k = a.chave || String(i);
          const ult = (a.historico_status || []).slice(-1)[0];
          const longo = (a.como || '').length > 140;
          return (
            <article className={`app-card t-${tomDe(a)}`} key={k}>
              <div className="app-when">
                {a.quando
                  ? <strong title={dataHora(a.quando)}>{dia(a.quando)}</strong>
                  : <strong className="no-time">{a.data ? `${a.data.slice(8)}/${a.data.slice(5, 7)}` : '--/--'}</strong>}
                <small>{a.quando ? horaSeg(a.quando).slice(0, 5) : '--:--'}{a.quando && !a.exato && <em title="Hora aproximada, reconstruída do CV gerado">~</em>}</small>
              </div>
              <div className="app-body">
                <div className="app-title">
                  <VagaLink url={a.url}><b>{a.empresa || '—'}</b></VagaLink>
                  <span>{a.vaga}</span>
                </div>
                <div className="block-tags">
                  <span className={`tag st-${tomDe(a)}`}>{rotuloStatus(a.status)}</span>
                  {a.fonte && <span className="tag muted" title={a.via ? `via ${a.via}` : 'portal de origem'}>{a.fonte}{a.via ? ` · ${a.via}` : ''}</span>}
                  {a.manual && <span className="tag muted">manual</span>}
                  {a.conflito_data && <span className="tag muted" title="Data registrada divergia do CV">data revisada</span>}
                  {/* email_data = date of the e-mail itself; `em` is only when the robot noticed it. */}
                  {ult && <span className="tag muted" title={`robô detectou em ${dataHora(ult.em)}`}>
                    {rotuloStatus(ult.para)} · {ult.email_data ? `e-mail de ${ult.email_data.slice(8)}/${ult.email_data.slice(5, 7)}` : `detectado ${dia(ult.em)}`}
                  </span>}
                </div>
                {a.como && <p className={`block-text${abertos.has(k) || !longo ? '' : ' is-clamped'}`}>{a.como}</p>}
                {longo && (
                  <button type="button" className="link-btn" onClick={() => alternar(k)} aria-expanded={abertos.has(k)}>
                    {abertos.has(k) ? 'ver menos' : 'ver detalhes'}
                  </button>
                )}
              </div>
            </article>
          );
        }) : <p className="empty"><Inbox className="ico" aria-hidden="true" />{busca || fonte ? 'Nenhuma candidatura para este filtro.' : 'Nenhuma candidatura registrada.'}</p>}
      </div>
      <Pager pagina={pag.atual} total={pag.total} onChange={setPagina} />
      {aplicadas.some(a => a.quando && !a.exato) && (
        <p className="footnote">~ hora aproximada, reconstruída do CV gerado para a vaga. Candidaturas novas gravam o horário exato com fuso.</p>
      )}
    </section>
  );
}
