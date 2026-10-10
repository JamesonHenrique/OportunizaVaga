'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CACHE_KEY, FIRST_SEEN_KEY, TZ, desde, fmtDur, horaSeg, causaRaiz, classificar, refBloq, statusLoop, serieDias } from '@/lib/dashboard';
import StatusStrip from '@/components/dashboard/StatusStrip';
import ActionCenter from '@/components/dashboard/ActionCenter';
import TodayHero from '@/components/dashboard/TodayHero';
import KpiRow from '@/components/dashboard/KpiRow';
import DetailTabs from '@/components/dashboard/DetailTabs';
import ApplicationsPanel from '@/components/dashboard/ApplicationsPanel';
import TerminalPanel from '@/components/dashboard/TerminalPanel';
import TimelinePanel from '@/components/dashboard/TimelinePanel';
import DiagnosisPanel from '@/components/dashboard/DiagnosisPanel';
import ModelsPanel from '@/components/dashboard/ModelsPanel';
import CadencePanel from '@/components/dashboard/CadencePanel';
import InvitesPanel from '@/components/dashboard/InvitesPanel';
import BlocksPanel from '@/components/dashboard/BlocksPanel';
import LoginQueuePanel from '@/components/dashboard/LoginQueuePanel';
import DiscoveryPanel from '@/components/dashboard/DiscoveryPanel';
import { CalendarDays, Send, RefreshCw, MessageSquareReply, UserPlus, Filter } from 'lucide-react';
import TelegramPanel from '@/components/dashboard/TelegramPanel';
import YieldPanel from '@/components/dashboard/YieldPanel';
import RotationHealthPanel from '@/components/dashboard/RotationHealthPanel';

const ABA_KEY = 'monitor:aba:v1';

function lerLocal() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw);
    return j && j.updatedAt ? j : null;
  } catch { return null; }
}

export default function Dashboard() {
  const [dados, setDados] = useState(null);
  const [erroRede, setErroRede] = useState(null);
  const [usandoCache, setUsandoCache] = useState(false);
  const [agora, setAgora] = useState(Date.now());
  const [tentativas, setTentativas] = useState(0);
  const [vistos, setVistos] = useState({});
  const [deltaLog, setDeltaLog] = useState(null);
  const ultimoBom = useRef(null);
  const prevSnap = useRef(null);
  const secretUmaVez = useRef(null);
  const [aba, setAba] = useState('candidaturas');
  const abrirAba = (id) => {
    setAba(id);
    try { localStorage.setItem(ABA_KEY, id); } catch {}
    requestAnimationFrame(() => document.getElementById('detalhes')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  useEffect(() => {
    // Hydrate from local cache first: never show "Conectando…" again if good data was seen.
    const cached = lerLocal();
    if (cached) { ultimoBom.current = cached; setDados(cached); setUsandoCache(true); }
    try { setVistos(JSON.parse(localStorage.getItem(FIRST_SEEN_KEY) || '{}')); } catch {}
    try { const a = localStorage.getItem(ABA_KEY); if (a) setAba(a); } catch {}
    // Terminal ao vivo exige secret: ?secret=XXX é enviado UMA vez e a API devolve
    // um cookie httpOnly. O secret nunca fica salvo no navegador e sai da URL.
    // Sem isso a API devolve visão pública redigida (logTail vazio de propósito).
    try {
      localStorage.removeItem('monitor:secret:v1'); // legacy: versões antigas guardavam aqui
      const url = new URL(window.location.href);
      const qs = url.searchParams.get('secret');
      if (qs) {
        secretUmaVez.current = qs;
        url.searchParams.delete('secret');
        window.history.replaceState(null, '', url.pathname + url.search + url.hash);
      }
    } catch {}
  }, []);

  useEffect(() => {
    let ativo = true;
    const buscar = async () => {
      try {
        const ctrl = new AbortController();
        const timeout = setTimeout(() => ctrl.abort(), 15000);
        const secret = secretUmaVez.current;
        const url = secret ? `/api/status?secret=${encodeURIComponent(secret)}` : '/api/status';
        const r = await fetch(url, { cache: 'no-store', signal: ctrl.signal, credentials: 'same-origin' });
        clearTimeout(timeout);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        secretUmaVez.current = null; // the auth cookie now carries the session
        const j = await r.json();
        if (!ativo) return;
        if (j && j.updatedAt) {
          ultimoBom.current = j;
          setDados(j);
          setErroRede(null);
          setUsandoCache(false);
          setTentativas(0);
          try {
            localStorage.setItem(CACHE_KEY, JSON.stringify(j));
            // firstSeen: stamp when each block appeared on the monitor.
            // Valid from now on (the past has no recorded timestamp).
            const vistos = JSON.parse(localStorage.getItem(FIRST_SEEN_KEY) || '{}');
            const agoraIso = new Date().toISOString();
            let mudou = false;
            const todos = [...(j.blocked || []), ...((j.linkedin || {}).bloqueios || []).map(b => ({ ...b, chave: b.tipo }))];
            for (const b of todos) {
              const k = b.chave || b.tipo;
              if (k && !vistos[k]) { vistos[k] = agoraIso; mudou = true; }
            }
            if (mudou) localStorage.setItem(FIRST_SEEN_KEY, JSON.stringify(vistos));
            setVistos(vistos);
            // Proof of life: did the log grow since the last heartbeat?
            const prev = prevSnap.current;
            const cur = (j.logSizes?.loopLog || 0) + (j.logSizes?.loopLog1 || 0);
            if (prev && prev.bytes > 0) {
              const dtS = Math.max(1, Math.round((Date.now() - prev.at) / 1000));
              const diff = cur - prev.bytes;
              setDeltaLog(diff > 0
                ? `loop.log +${(diff / 1024).toFixed(1)} KB em ${dtS}s — terminal do PC escrevendo agora`
                : `loop.log parado há ${Math.round(dtS / 60)}min — nada novo escrito no terminal`);
            }
            prevSnap.current = { at: Date.now(), bytes: cur };
          } catch {}
        } else if (ultimoBom.current) {
          // Cold Vercel instance: keep the last good snapshot.
          setUsandoCache(true);
          setErroRede('Instância fria: a função respondeu vazia.');
        } else {
          setDados(j);
          setErroRede('Resposta sem updatedAt.');
        }
      } catch (e) {
        if (!ativo) return;
        setTentativas((t) => t + 1);
        setErroRede(e?.name === 'AbortError' ? 'Timeout de 15s ao buscar /api/status.' : `Falha de rede: ${e?.message || e}`);
        if (ultimoBom.current) setUsandoCache(true);
      }
    };
    buscar();
    const p = setInterval(buscar, 8000);
    const c = setInterval(() => setAgora(Date.now()), 1000);
    return () => { ativo = false; clearInterval(p); clearInterval(c); };
  }, []);

  const d = dados || ultimoBom.current;

  // Hooks always before any return: stable order across renders.
  // (useMemo after `if (!d)` broke the front with "client-side exception".)
  // Blocks sorted newest → oldest by best available date (em > cited in text
  // > firstSeen); undated ones go to the end.
  const bloqueios = useMemo(() => {
    const base = [
      ...((d && d.blocked) || []).map(b => ({ ...b, origem: 'candidaturas' })),
      ...(((d && d.linkedin) || {}).bloqueios || []).map(b => ({ ...b, motivo: b.detalhe, chave: b.tipo, origem: 'linkedin' }))
    ];
    const comRef = base.map(b => ({ ...b, _ref: refBloq(b, vistos) }));
    return comRef.sort((x, y) => (y._ref.key || '').localeCompare(x._ref.key || ''));
  }, [d, vistos]);

  // Applications per day (last 14 days with records) — straight from applied[].
  // data, durable in aplicadas.json, no dependency on log rotation. Feeds cadence.
  const porDia = useMemo(() => {
    const m = new Map();
    for (const a of ((d && d.applied) || [])) {
      const k = a.data || (a.quando || a.enviada_em || a.enviada_em_aprox || '').slice(0, 10);
      if (k) m.set(k, (m.get(k) || 0) + 1);
    }
    return [...m.entries()].sort((x, y) => x[0].localeCompare(y[0])).slice(-14);
  }, [d]);

  // Every day with records (not capped) — feeds the 14-day hero series.
  const porDiaTodos = useMemo(() => {
    const m = new Map();
    for (const a of ((d && d.applied) || [])) {
      const k = a.data || (a.quando || a.enviada_em || a.enviada_em_aprox || '').slice(0, 10);
      if (k) m.set(k, (m.get(k) || 0) + 1);
    }
    // Aggregate mode ships no applied[]: fall back to the per-day counts.
    if (!m.size && d?.porDia) return Object.entries(d.porDia);
    return [...m.entries()];
  }, [d]);

  // Sources sorted (portal with most applications first) — ready from the snapshot.
  const porFonte = useMemo(
    () => Object.entries((d && d.porFonte) || {}).sort((a, b) => b[1] - a[1]),
    [d]
  );

  const gruposBloq = useMemo(() => {
    const m = new Map();
    for (const b of bloqueios) {
      const k = causaRaiz(b);
      m.set(k, (m.get(k) || 0) + 1);
    }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [bloqueios]);

  // Tab title becomes a semaphore: you can tell it stopped without opening the page.
  useEffect(() => {
    const dd = dados || ultimoBom.current;
    const parado = !dd || !dd.updatedAt || Date.now() - new Date(dd.updatedAt).getTime() > 600000;
    document.title = parado
      ? '[SEM SINAL] Monitor OportunizaVaga'
      : 'OportunizaVaga · Monitor de Candidaturas';
  }, [dados, agora]);

  if (!d) {
    return (
      <main className="shell" aria-busy="true">
        <div className="skeleton" style={{ height: 52 }} />
        <div className="overview">
          <div className="skeleton today-hero" style={{ height: 260 }} />
          <div className="skeleton action-center" style={{ minHeight: 260 }} />
          <div className="skeleton kpis" style={{ height: 200 }} />
        </div>
        <p className="loading" role="status">Conectando ao supervisor…</p>
        {erroRede && (
          <div className="panel">
            <div className="panel-body">
              <p className="verdict v-bad">{erroRede} Tentativa {tentativas}. Nova tentativa automática em 8s.</p>
              <button className="btn" onClick={() => window.location.reload()}>Recarregar agora</button>
            </div>
          </div>
        )}
      </main>
    );
  }

  const semSinal = !d.updatedAt || agora - new Date(d.updatedAt).getTime() > 180000;
  const parado = !d.updatedAt || agora - new Date(d.updatedAt).getTime() > 600000;
  const loops = d.loops || {};

  const aplicadas = (d.applied || []).slice().sort((a, b) => (b.quando || '').localeCompare(a.quando || ''));
  const convites = (d.linkedin?.convites || []).slice().reverse();

  // ---- "Why is it not applying?" diagnosis ----
  const ultimaAplicada = aplicadas.find(a => a.quando)?.quando || null;
  const horasSemEnviar = ultimaAplicada ? (agora - new Date(ultimaAplicada).getTime()) / 3600000 : null;
  const rodadasDesdeEnvio = ultimaAplicada
    ? (d.events || []).filter(e => e.kind === 'rodada' && (e.at || '') > ultimaAplicada).length
    : (d.events || []).filter(e => e.kind === 'rodada').length;

  // Candidate-side blocks (login, missing data, broken signup), excluding what the robot retries.
  const precisaAcao = bloqueios.filter(b => classificar(b).grupo === 'voce' && !b.retentar);
  const aguardandoLogin = d.aguardandoLogin || [];
  const dadosFaltantes = d.dadosFaltantes || [];
  const proximaTentativaEm = 8 - (Math.floor(agora / 1000) % 8);

  const perfis = d.perfis || d.telemetry?.perfis || [];
  const porStatus = Object.entries(d.porStatus || d.telemetry?.porStatus || {}).sort((a, b) => b[1] - a[1]);
  const perfilAtivo = d.perfilAtivo || perfis.find(p => p.ativo)?.nome || null;

  const hojeYmd = d.hoje || new Date(agora).toLocaleDateString('sv-SE', { timeZone: TZ });
  const serie = serieDias(porDiaTodos, hojeYmd, 14);
  const hojeLabel = new Date(`${hojeYmd}T12:00:00Z`).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC' });

  const stCand = statusLoop(loops.candidaturas, agora);
  const stLink = statusLoop(loops.linkedin, agora, d.agenda?.proximaRodadaLinkedin);
  // Optional side robots (e.g. a LinkedIn recruiter loop) only show when they publish.
  const pills = [
    { nome: 'Candidaturas', ...stCand, detalhe: loops.candidaturas?.message, vivo: loops.candidaturas?.state === 'rodando' },
    ...(loops.linkedin ? [{ nome: 'LinkedIn-RH', ...stLink, detalhe: loops.linkedin?.message, vivo: loops.linkedin?.state === 'rodando' }] : []),
  ];

  // "Precisa de você" — most severe first.
  const retentar = bloqueios.filter(b => b.retentar);
  const nomeBloq = (b) => b.empresa || (b.chave || '').split('_')[0].replace(/^./, c => c.toUpperCase());
  const nomes = (arr) => arr.slice(0, 3).map(nomeBloq).join(', ') + (arr.length > 3 ? '…' : '');
  const acoes = [];
  if (parado) acoes.push({ id: 'pc', tom: 'bad', titulo: `Sem sinal do PC ${desde(d.updatedAt, agora)}`,
    sub: 'PC desligado, dormindo ou sem internet. Confira o loop e o publish-status.mjs.' });
  for (const [p, loop] of pills.map(p => [p, p.nome === 'Candidaturas' ? loops.candidaturas : loops.linkedin])) {
    if (p.tom === 'bad' && !parado) acoes.push({ id: `loop-${p.nome}`, tom: 'bad', titulo: `${p.nome} ${p.frase}`,
      sub: loop?.message, acao: { rotulo: 'Ver robô', aba: 'robo' } });
  }
  if (horasSemEnviar != null && horasSemEnviar > 24) acoes.push({ id: 'seco', tom: 'warn',
    titulo: `Sem envio há ${Math.round(horasSemEnviar)}h`, sub: `${rodadasDesdeEnvio} rodadas desde o último envio`, acao: { rotulo: 'Diagnóstico', aba: 'robo' } });
  const stDe = (a) => (a.status || '').toLowerCase();
  const entrevistas = aplicadas.filter(a => stDe(a) === 'entrevista');
  if (entrevistas.length) acoes.push({ id: 'entrevista', tom: 'bad', titulo: `${entrevistas.length} e-mail(s) falando em entrevista`,
    sub: `${nomes(entrevistas)} · confira o Gmail e responda`, acao: { rotulo: 'Ver', aba: 'candidaturas' } });
  const testes = aplicadas.filter(a => stDe(a) === 'etapa_teste');
  if (testes.length) acoes.push({ id: 'teste', tom: 'warn', titulo: `${testes.length} etapa(s) de teste / fit cultural`,
    sub: `${nomes(testes)} · faça o teste na plataforma da vaga`, acao: { rotulo: 'Ver', aba: 'candidaturas' } });
  const etapas = aplicadas.filter(a => stDe(a) === 'proxima_etapa');
  if (etapas.length) acoes.push({ id: 'etapa', tom: 'warn', titulo: `${etapas.length} e-mail(s) de próxima etapa`,
    sub: `${nomes(etapas)} · confira o Gmail`, acao: { rotulo: 'Ver', aba: 'candidaturas' } });
  const sitesRod = Object.values(d.rodizioSaude?.sites || {});
  const pausados = sitesRod.filter(s => s?.pausado_ate && new Date(s.pausado_ate).getTime() > agora).length;
  if (sitesRod.length && pausados === sitesRod.length) acoes.push({ id: 'pausados', tom: 'warn', titulo: 'Todos os sites do rodízio pausados',
    sub: 'o robô segue só com a busca por script e a fila de login', acao: { rotulo: 'Ver', aba: 'robo' } });
  if (aguardandoLogin.length) {
    const canais = [...new Set(aguardandoLogin.map(v => v.canal))];
    acoes.push({ id: 'login', tom: 'bad', titulo: `${aguardandoLogin.length} vaga(s) compatível(is) esperando login`,
      sub: `logue no navegador do robô: ${canais.join(', ')}`, acao: { rotulo: 'Ver vagas', aba: 'bloqueios' } });
  }
  if (precisaAcao.length) acoes.push({ id: 'cad', tom: 'warn', titulo: `${precisaAcao.length} bloqueio(s) dependem de você`,
    sub: nomes(precisaAcao), acao: { rotulo: 'Abrir', aba: 'bloqueios' } });
  if (retentar.length) acoes.push({ id: 'ret', tom: 'warn', titulo: `${retentar.length} vaga(s) para retentar`,
    sub: `${nomes(retentar)} · o robô retoma sozinho`, acao: { rotulo: 'Abrir', aba: 'bloqueios' } });
  for (const f of dadosFaltantes) acoes.push({ id: `falta-${f.campo}`, tom: 'warn', titulo: `Falta: ${f.campo}`,
    sub: `destrava ${f.vagas} vaga(s) · adicione em dados_candidato.json` });
  if (d.telegram?.status === 'aguardando login') acoes.push({ id: 'tg', tom: 'info',
    titulo: 'Telegram aguardando login', sub: 'garimpo de vagas parado', acao: { rotulo: 'Ver', aba: 'telegram' } });

  const kpis = [
    { rotulo: 'Últimos 7 dias', valor: d.rendimento?.aplicadas7d ?? serie.slice(-7).reduce((a, [, n]) => a + n, 0), sub: 'candidaturas', icone: CalendarDays },
    { rotulo: 'Total enviadas', valor: d.totals?.candidaturas ?? aplicadas.length, sub: `${porFonte[0]?.[0] || '—'} lidera (${porFonte[0]?.[1] ?? 0})`, icone: Send },
    { rotulo: 'Rodadas por envio', valor: d.rendimento?.rodadasPorCandidatura != null ? String(d.rendimento.rodadasPorCandidatura).replace('.', ',') : '—',
      sub: `${d.rendimento?.rodadas7d ?? '—'} rodadas em 7 dias`, dica: 'Quanto menor, mais eficiente', icone: RefreshCw },
    { rotulo: 'Respostas', valor: aplicadas.filter(a => ['etapa_teste', 'proxima_etapa', 'entrevista', 'encerrada', 'respondida'].includes(stDe(a))).length,
      sub: `${entrevistas.length} entrevista · ${testes.length + etapas.length} teste/etapa · ${aplicadas.filter(a => stDe(a) === 'em_analise').length} em análise`, icone: MessageSquareReply },
    d.linkedin
      ? { rotulo: 'Convites LinkedIn', valor: d.totals?.convites ?? convites.length, sub: `${loops.linkedin?.convitesHoje ?? 0}/${d.linkedin?.limiteDiario ?? 10} hoje`, icone: UserPlus }
      : { rotulo: 'Vagas descartadas', valor: d.descartes?.total ?? d.telemetry?.totals?.descartes ?? '—', sub: 'filtradas antes de abrir', dica: 'Nível, stack ou modelo incompatível', icone: Filter },
  ];

  const abas = [
    { id: 'candidaturas', rotulo: 'Candidaturas', conta: aplicadas.length },
    { id: 'bloqueios', rotulo: 'Bloqueios', conta: bloqueios.length, alerta: aguardandoLogin.length > 0 || precisaAcao.length > 0 || retentar.length > 0 },
    { id: 'robo', rotulo: 'Robô', alerta: pills.some(p => p.tom === 'bad') },
    ...(d.linkedin ? [{ id: 'linkedin', rotulo: 'LinkedIn', conta: convites.length }] : []),
    ...(d.telegram ? [{ id: 'telegram', rotulo: 'Telegram' }] : []),
  ];
  const abaAtiva = abas.some(a => a.id === aba) ? aba : 'candidaturas';

  return (
    <>
      <StatusStrip loops={pills} semSinal={semSinal} updatedAt={d.updatedAt} agora={agora}
                   avisoCache={(erroRede || usandoCache) ? `${erroRede || 'Instância fria na Vercel.'} Exibindo o retrato de ${horaSeg(d.updatedAt)}; nova tentativa em ~${proximaTentativaEm}s.` : null}
                   publico={!!d._redacted} demo={!!d._demo} />
      <main className="shell">
        <div className="overview">
          <TodayHero hojeLabel={hojeLabel} hoje={serie[serie.length - 1][1]} serie={serie}
                     rodadasHoje={loops.candidaturas?.rodadasHoje} />
          <ActionCenter itens={acoes} abrirAba={abrirAba} />
          <KpiRow itens={kpis} />
        </div>

        <section id="detalhes" className="detail">
          <DetailTabs abas={abas} ativa={abaAtiva} onChange={abrirAba} />
          <div className="tab-panel" role="tabpanel" aria-labelledby={`tab-${abaAtiva}`}>
            {abaAtiva === 'candidaturas' && !d.applied && (
              <p className="notice">
                Modo agregado: a lista de candidaturas fica oculta. Para ver os detalhes, rode o publisher com
                {' '}<code>MONITOR_INCLUDE_DETAILS=1</code> e proteja o painel com <code>MONITOR_SECRET</code>.
              </p>
            )}
            {abaAtiva === 'candidaturas' && (
              <div className="layout layout-wide">
                <ApplicationsPanel aplicadas={aplicadas} />
                <CadencePanel porDia={porDia} porFonte={porFonte} porStatus={porStatus} total={aplicadas.length} />
              </div>
            )}
            {abaAtiva === 'bloqueios' && (
              <div className="blocks-tab">
                <LoginQueuePanel itens={aguardandoLogin} agora={agora} />
                <BlocksPanel bloqueios={bloqueios} />
              </div>
            )}
            {abaAtiva === 'robo' && (
              <>
                {(loops.candidaturas?.duracao || loops.linkedin?.duracao) && (
                  <p className="duration-line">
                    Candidaturas: {loops.candidaturas?.message || '—'} · rodada última {fmtDur(loops.candidaturas?.duracao?.ultimaMin)}, média {fmtDur(loops.candidaturas?.duracao?.mediaMin)}
                    {' · '}LinkedIn: última {fmtDur(loops.linkedin?.duracao?.ultimaMin)}, média {fmtDur(loops.linkedin?.duracao?.mediaMin)}
                    {deltaLog ? <> · {deltaLog}</> : null}
                  </p>
                )}
                <div className="layout">
                  <DiagnosisPanel
                    d={d} loops={loops} agora={agora}
                    ultimaAplicada={ultimaAplicada}
                    rodadasDesdeEnvio={rodadasDesdeEnvio}
                    horasSemEnviar={horasSemEnviar}
                    gruposBloq={gruposBloq}
                    totalBloqueios={bloqueios.length}
                  />
                  <RotationHealthPanel rodizioSaude={d.rodizioSaude} proximo={d.rodizio?.proximo} />
                  <TerminalPanel logTail={d.logTail} />
                  <TimelinePanel eventos={d.events || []} />
                  <DiscoveryPanel descoberta={d.descoberta} gmail={d.gmailStatus} />
                  <YieldPanel rendimento={d.rendimento} />
                  <ModelsPanel modelos={d.modelos} />
                </div>
              </>
            )}
            {abaAtiva === 'linkedin' && <InvitesPanel convites={convites} bloqueios={d.linkedin?.bloqueios || []} convitesHoje={loops.linkedin?.convitesHoje ?? 0} limiteDiario={d.linkedin?.limiteDiario} hoje={hojeYmd} loop={loops.linkedin} />}
            {abaAtiva === 'telegram' && <TelegramPanel telegram={d.telegram} agora={agora} />}
          </div>
        </section>

        <footer className="footer">
          Horários em {d.tz || TZ} · atualiza sozinho a cada 8s
          {d.rodizio?.proximo ? ` · próximo site do rodízio: ${d.rodizio.proximo}` : ''}
          {d.publisher?.host ? ` · fonte ${d.publisher.host}#${d.publisher.pid}` : ''}
        </footer>
      </main>
    </>
  );
}
