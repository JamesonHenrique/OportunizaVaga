'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CACHE_KEY, FIRST_SEEN_KEY, TZ, POLL_MS, POLL_BG_MS, FETCH_TIMEOUT_MS,
  desde, fmtDur, horaSeg, causaRaiz, classificar, refBloq, statusLoop, serieDias, diaDoSnapshot, resumoRespostas,
  podeCachear, modoAcesso, frescor, rotuloAtualizacao, estadoOperacional, rodadasDoLoop, listaPortais
} from '@/lib/dashboard';
import StatusStrip from '@/components/dashboard/StatusStrip';
import CommandHeader from '@/components/dashboard/CommandHeader';
import ActionCenter, { precisaHumano } from '@/components/dashboard/ActionCenter';
import TodayHero from '@/components/dashboard/TodayHero';
import KpiRow from '@/components/dashboard/KpiRow';
import Sidebar from '@/components/dashboard/Sidebar';
import AutomationMonitor from '@/components/dashboard/AutomationMonitor';
import { Mark } from '@/components/brand/Brand';
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
import TelegramPanel from '@/components/dashboard/TelegramPanel';
import YieldPanel from '@/components/dashboard/YieldPanel';
import RotationHealthPanel from '@/components/dashboard/RotationHealthPanel';

// v2: the overview is now a real tab ("inicio"), so v1 values (default "candidaturas") are not reused.
const ABA_KEY = 'monitor:aba:v2';

// Only public/demo snapshots are persisted. A private snapshot found there (written by an
// older build) is removed instead of being shown.
function lerLocal() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw);
    if (!j || !j.updatedAt) return null;
    if (!podeCachear(j)) { localStorage.removeItem(CACHE_KEY); return null; }
    return j;
  } catch { return null; }
}

const contaDia = (a) => a.data || (a.quando || a.enviada_em || a.enviada_em_aprox || '').slice(0, 10);

export default function Dashboard() {
  const [dados, setDados] = useState(null);
  const [erroRede, setErroRede] = useState(null);
  const [usandoCache, setUsandoCache] = useState(false);
  const [agora, setAgora] = useState(Date.now());
  const [tentativas, setTentativas] = useState(0);
  const [vistos, setVistos] = useState({});
  const [deltaLog, setDeltaLog] = useState(null);
  const [aba, setAba] = useState('inicio');
  const ultimoBom = useRef(null);
  const prevSnap = useRef(null);
  const secretUmaVez = useRef(null);
  const proximaBusca = useRef(0);
  const mainRef = useRef(null);

  const abrirAba = (id) => {
    setAba(id);
    try { localStorage.setItem(ABA_KEY, id); } catch {}
    window.scrollTo({ top: 0 });
    // move focus to the new workspace so keyboard / screen-reader users land on it
    requestAnimationFrame(() => mainRef.current?.focus({ preventScroll: true }));
  };
  const irPrecisa = () => {
    if (aba !== 'inicio') abrirAba('inicio');
    requestAnimationFrame(() => document.getElementById('precisa')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  };

  useEffect(() => {
    // Hydrate from the public/demo cache first, so a cold start never shows a blank page.
    const cached = lerLocal();
    if (cached) { ultimoBom.current = cached; setDados(cached); setUsandoCache(true); }
    try { setVistos(JSON.parse(localStorage.getItem(FIRST_SEEN_KEY) || '{}')); } catch {}
    try { const a = localStorage.getItem(ABA_KEY); if (a) setAba(a); localStorage.removeItem('monitor:aba:v1'); } catch {}
    // Live terminal requires the secret: ?secret=XXX is sent ONCE and the API answers with an
    // httpOnly cookie. The secret is never stored in the browser and leaves the URL.
    try {
      localStorage.removeItem('monitor:secret:v1'); // legacy: older builds kept it here
      const url = new URL(window.location.href);
      const qs = url.searchParams.get('secret');
      if (qs) {
        secretUmaVez.current = qs;
        url.searchParams.delete('secret');
        window.history.replaceState(null, '', url.pathname + url.search + url.hash);
      }
    } catch {}
  }, []);

  // Polling: one request in flight at a time, setTimeout chain (15s visible / 60s hidden),
  // aborted on unmount; returning to the tab refetches at once when the data is older than 15s.
  useEffect(() => {
    let vivo = true;
    let emVoo = false;
    let timer = null;
    let ctrl = null;
    let ultimaBusca = 0;

    const agendar = () => {
      clearTimeout(timer);
      const ms = document.hidden ? POLL_BG_MS : POLL_MS;
      proximaBusca.current = Date.now() + ms;
      timer = setTimeout(buscar, ms);
    };

    const aplicar = (j) => {
      ultimoBom.current = j;
      setDados(j);
      setErroRede(null);
      setUsandoCache(false);
      setTentativas(0);
      try {
        if (podeCachear(j)) localStorage.setItem(CACHE_KEY, JSON.stringify(j));
        else localStorage.removeItem(CACHE_KEY); // authenticated data stays in memory only
        // firstSeen: stamp when each block appeared on the monitor (valid from now on).
        const vs = JSON.parse(localStorage.getItem(FIRST_SEEN_KEY) || '{}');
        const agoraIso = new Date().toISOString();
        let mudou = false;
        const todos = [...(j.blocked || []), ...((j.linkedin || {}).bloqueios || []).map(b => ({ ...b, chave: b.tipo }))];
        for (const b of todos) {
          const k = b.chave || b.tipo;
          if (k && !vs[k]) { vs[k] = agoraIso; mudou = true; }
        }
        if (mudou) localStorage.setItem(FIRST_SEEN_KEY, JSON.stringify(vs));
        setVistos(vs);
      } catch {}
      // Proof of life: did the log grow since the previous update?
      const prev = prevSnap.current;
      const cur = (j.logSizes?.loopLog || 0) + (j.logSizes?.loopLog1 || 0);
      if (prev && prev.bytes > 0) {
        const dtS = Math.max(1, Math.round((Date.now() - prev.at) / 1000));
        const diff = cur - prev.bytes;
        setDeltaLog(diff > 0
          ? `loop.log +${(diff / 1024).toFixed(1)} KB em ${dtS}s — o robô está escrevendo no terminal agora`
          : `loop.log parado há ${Math.round(dtS / 60)}min — nada novo escrito no terminal`);
      }
      prevSnap.current = { at: Date.now(), bytes: cur };
    };

    const buscar = async () => {
      if (emVoo || !vivo) return;
      emVoo = true;
      ultimaBusca = Date.now();
      ctrl = new AbortController();
      let porTimeout = false;
      const to = setTimeout(() => { porTimeout = true; ctrl.abort(); }, FETCH_TIMEOUT_MS);
      try {
        const secret = secretUmaVez.current;
        const url = secret ? `/api/status?secret=${encodeURIComponent(secret)}` : '/api/status';
        const r = await fetch(url, { cache: 'no-store', signal: ctrl.signal, credentials: 'same-origin' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        secretUmaVez.current = null; // the auth cookie now carries the session
        const j = await r.json();
        if (!vivo) return;
        if (j && j.updatedAt) aplicar(j);
        else if (ultimoBom.current) {
          // Cold serverless instance: keep the last good snapshot, flagged as cache.
          setUsandoCache(true);
          setErroRede('A instância do monitor reiniciou e ainda não recebeu dados do robô.');
        } else {
          setDados(j);
          setErroRede('O monitor respondeu sem dados do robô.');
        }
      } catch (e) {
        if (!vivo || (e?.name === 'AbortError' && !porTimeout)) return;
        setTentativas((t) => t + 1);
        setErroRede(porTimeout ? `Tempo esgotado (${FETCH_TIMEOUT_MS / 1000}s) ao buscar /api/status.` : `Falha de rede: ${e?.message || e}`);
        if (ultimoBom.current) setUsandoCache(true);
      } finally {
        clearTimeout(to);
        emVoo = false;
        if (vivo) agendar();
      }
    };

    const onVisivel = () => {
      if (!document.hidden && Date.now() - ultimaBusca >= POLL_MS) buscar();
      else if (!emVoo) agendar();
    };

    buscar();
    document.addEventListener('visibilitychange', onVisivel);
    const relogio = setInterval(() => setAgora(Date.now()), 1000);
    return () => {
      vivo = false;
      clearTimeout(timer);
      ctrl?.abort();
      clearInterval(relogio);
      document.removeEventListener('visibilitychange', onVisivel);
    };
  }, []);

  const d = dados || ultimoBom.current;

  // Hooks always before any return: stable order across renders.
  // Blocks sorted newest → oldest by best available date (em > cited in text > firstSeen).
  const bloqueios = useMemo(() => {
    const base = [
      ...((d && d.blocked) || []).map(b => ({ ...b, origem: 'candidaturas' })),
      ...(((d && d.linkedin) || {}).bloqueios || []).map(b => ({ ...b, motivo: b.detalhe, chave: b.tipo, origem: 'linkedin' }))
    ];
    const comRef = base.map(b => ({ ...b, _ref: refBloq(b, vistos) }));
    return comRef.sort((x, y) => (y._ref.key || '').localeCompare(x._ref.key || ''));
  }, [d, vistos]);

  // Every day with records — feeds the 14-day series. Aggregate/public mode: per-day counts.
  const porDiaTodos = useMemo(() => {
    if (d?.porDia) return Object.entries(d.porDia);
    const m = new Map();
    for (const a of ((d && d.applied) || [])) { const k = contaDia(a); if (k) m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()];
  }, [d]);

  const porFonte = useMemo(
    () => Object.entries((d && d.porFonte) || {}).sort((a, b) => b[1] - a[1]),
    [d]
  );

  const gruposBloq = useMemo(() => {
    const m = new Map();
    for (const b of bloqueios) { const k = causaRaiz(b); m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [bloqueios]);

  // Tab title is a semaphore: you can tell it stopped without opening the page.
  useEffect(() => {
    const dd = dados || ultimoBom.current;
    document.title = !dd || frescor(dd, Date.now()).semSinal
      ? '[SEM SINAL] Monitor OportunizaVaga'
      : 'OportunizaVaga · Monitor de Candidaturas';
  }, [dados, agora]);

  if (!d) {
    const espera = Math.max(0, Math.round((proximaBusca.current - agora) / 1000));
    return (
      <div className="app">
        <aside className="sidebar"><span className="side-brand"><Mark size={30} /></span></aside>
        <main className="shell" aria-busy="true">
          <div className="skeleton" style={{ height: 140 }} />
          <div className="home-grid">
            <div className="home-main">
              <div className="skeleton" style={{ minHeight: 220 }} />
              <div className="skeleton" style={{ minHeight: 110 }} />
            </div>
            <div className="skeleton" style={{ minHeight: 300 }} />
          </div>
          <p className="loading" role="status">Conectando ao monitor…</p>
          {erroRede && (
            <div className="panel">
              <div className="panel-body">
                <p className="verdict v-bad">{erroRede} Tentativa {tentativas}. Nova tentativa automática em {espera || POLL_MS / 1000}s.</p>
                <button type="button" className="btn" onClick={() => window.location.reload()}>Recarregar agora</button>
              </div>
            </div>
          )}
        </main>
      </div>
    );
  }

  const fr = frescor(d, agora);
  const semSinal = fr.semSinal;
  const atualizacao = rotuloAtualizacao(fr, agora);
  const ultimoSinal = fr.ref ? desde(fr.ref, agora) : 'nunca';
  const modo = modoAcesso(d);
  const obsoleto = usandoCache ? 'cache' : semSinal ? 'stale' : null;
  const loops = d.loops || {};
  const rodadasHoje = rodadasDoLoop(loops.candidaturas);

  const temLista = fr.estado !== 'cold_start' && Array.isArray(d.applied);
  const aplicadas = (d.applied || []).slice().sort((a, b) => (b.quando || '').localeCompare(a.quando || ''));
  const convites = (d.linkedin?.convites || []).slice().reverse();

  // ---- "Why is it not sending?" diagnosis ----
  const ultimaAplicada = aplicadas.find(a => a.quando)?.quando || null;
  const horasSemEnviar = ultimaAplicada ? (agora - new Date(ultimaAplicada).getTime()) / 3600000 : null;
  const rodadasDesdeEnvio = d.events?.filter(e =>
    e.kind === 'rodada' && (!ultimaAplicada || (e.at || '') > ultimaAplicada)
  ).length;
  const temBloqueios = Array.isArray(d.blocked);
  const totalBloqueios = temBloqueios ? bloqueios.length : d.totals?.bloqueios;

  // Candidate-side blocks (login, missing data, broken signup), excluding what the robot retries.
  const precisaAcao = bloqueios.filter(b => classificar(b).grupo === 'voce' && !b.retentar);
  const aguardandoLogin = d.aguardandoLogin || [];
  const dadosFaltantes = d.dadosFaltantes || [];
  const espera = Math.max(0, Math.round((proximaBusca.current - agora) / 1000));

  const statusCounts = d.porStatus ?? d.telemetry?.porStatus ?? (temLista
    ? aplicadas.reduce((counts, a) => {
      const status = a.status?.toLowerCase() || 'enviada';
      counts[status] = (counts[status] ?? 0) + 1;
      return counts;
    }, Object.create(null))
    : null);
  const respostas = resumoRespostas(statusCounts);

  const hojeYmd = diaDoSnapshot(d, agora);
  const temSerie = fr.estado !== 'cold_start' && (temLista || Boolean(d.porDia));
  const serie = temSerie ? serieDias(porDiaTodos, hojeYmd) : [];
  const hojeLabel = new Date(`${hojeYmd}T12:00:00Z`).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short', timeZone: 'UTC' });

  const stCand = statusLoop(loops.candidaturas, agora);
  const stLink = statusLoop(loops.linkedin, agora, d.agenda?.proximaRodadaLinkedin);
  const vivoDe = (l) => ['rodando', 'running'].includes(l?.state);
  const pills = [
    { nome: 'Candidaturas', ...stCand, detalhe: loops.candidaturas?.message, vivo: vivoDe(loops.candidaturas) },
    ...(loops.linkedin ? [{ nome: 'LinkedIn-RH', ...stLink, detalhe: loops.linkedin?.message, vivo: vivoDe(loops.linkedin) }] : []),
  ];
  const estado = estadoOperacional(pills, fr);

  // ---- "Precisa de você": what happened / why it matters / next step ----
  const retentar = bloqueios.filter(b => b.retentar);
  const nomeBloq = (b) => b.empresa || (b.chave || '').split('_')[0].replace(/^./, c => c.toUpperCase());
  const nomes = (arr) => arr.slice(0, 3).map(nomeBloq).join(', ') + (arr.length > 3 ? '…' : '');
  const stDe = (a) => (a.status || '').toLowerCase();
  const acoes = [];
  if (semSinal) acoes.push({ id: 'sinal', grupo: 'critico',
    titulo: fr.ref ? `Sem sinal do robô ${desde(fr.ref, agora)}` : 'Nenhuma atualização recebida do robô',
    porque: 'Nada novo chega ao monitor: os números podem estar velhos e nenhum envio está sendo confirmado.',
    proximo: 'Confira se o computador do robô está ligado e com internet e se o loop e o publish-status.mjs estão rodando.' });
  for (const p of pills) {
    const loop = p.nome === 'Candidaturas' ? loops.candidaturas : loops.linkedin;
    if (p.tom === 'bad' && !semSinal) acoes.push({ id: `loop-${p.nome}`, grupo: 'critico', titulo: `${p.nome}: ${p.frase}`,
      porque: 'Enquanto o loop estiver parado ou com erro, nenhuma vaga nova é processada.',
      proximo: loop?.message ? `Veja a mensagem do robô: “${loop.message}”.` : 'Abra a automação e confira o terminal.',
      acao: { rotulo: 'Ver automação', aba: 'robo' } });
  }
  const entrevistas = aplicadas.filter(a => stDe(a) === 'entrevista');
  if (entrevistas.length) acoes.push({ id: 'entrevista', grupo: 'critico', titulo: `${entrevistas.length} e-mail(s) falando em entrevista`,
    porque: `${nomes(entrevistas)} — responder rápido aumenta a chance de avançar.`,
    proximo: 'Abra o Gmail e responda à empresa.', acao: { rotulo: 'Ver candidaturas', aba: 'candidaturas' } });
  if (aguardandoLogin.length) {
    const canais = [...new Set(aguardandoLogin.map(v => v.canal))];
    acoes.push({ id: 'login', grupo: 'critico', titulo: `${aguardandoLogin.length} vaga(s) compatível(is) esperando login`,
      porque: 'O robô encontrou vagas que combinam, mas não consegue enviar sem uma sessão ativa.',
      proximo: `Faça login no navegador do robô: ${canais.join(', ')}.`, acao: { rotulo: 'Ver vagas', aba: 'bloqueios' } });
  }
  const testes = aplicadas.filter(a => stDe(a) === 'etapa_teste');
  if (testes.length) acoes.push({ id: 'teste', grupo: 'voce', titulo: `${testes.length} etapa(s) de teste / fit cultural`,
    porque: `${nomes(testes)} — etapas de teste costumam ter prazo.`,
    proximo: 'Faça o teste na plataforma da vaga.', acao: { rotulo: 'Ver candidaturas', aba: 'candidaturas' } });
  const etapas = aplicadas.filter(a => stDe(a) === 'proxima_etapa');
  if (etapas.length) acoes.push({ id: 'etapa', grupo: 'voce', titulo: `${etapas.length} e-mail(s) de próxima etapa`,
    porque: `${nomes(etapas)} — a empresa espera um retorno seu.`,
    proximo: 'Confira o Gmail.', acao: { rotulo: 'Ver candidaturas', aba: 'candidaturas' } });
  if (precisaAcao.length) acoes.push({ id: 'cad', grupo: 'voce', titulo: `${precisaAcao.length} bloqueio(s) dependem de você`,
    porque: `${nomes(precisaAcao)} — o robô não resolve login, cadastro ou dado ausente sozinho.`,
    proximo: 'Abra Bloqueios e resolva o motivo indicado em cada vaga.', acao: { rotulo: 'Abrir bloqueios', aba: 'bloqueios' } });
  if (horasSemEnviar != null && horasSemEnviar > 24) acoes.push({ id: 'seco', grupo: 'voce', titulo: `Sem envio há ${Math.round(horasSemEnviar)}h`,
    porque: `${rodadasDesdeEnvio} rodada(s) desde o último envio — o funil pode estar descartando tudo.`,
    proximo: 'Veja o diagnóstico: bloqueios por causa, descartes e modelo em uso.', acao: { rotulo: 'Diagnóstico', aba: 'robo' } });
  for (const f of dadosFaltantes) acoes.push({ id: `falta-${f.campo}`, grupo: 'dados', titulo: `Falta o dado: ${f.campo}`,
    porque: `Destrava ${f.vagas} vaga(s) que pedem esse campo.`,
    proximo: 'Adicione o campo em dados_candidato.json.' });
  if (retentar.length) acoes.push({ id: 'ret', grupo: 'retry', titulo: `${retentar.length} vaga(s) para tentar de novo`,
    porque: nomes(retentar), proximo: 'Nada a fazer: o robô retoma sozinho.', acao: { rotulo: 'Abrir bloqueios', aba: 'bloqueios' } });
  const sitesRod = Object.values(d.rodizioSaude?.sites || {});
  const pausados = sitesRod.filter(s => s?.pausado_ate && new Date(s.pausado_ate).getTime() > agora).length;
  if (sitesRod.length && pausados === sitesRod.length) acoes.push({ id: 'pausados', grupo: 'retry', titulo: 'Todos os sites do rodízio em pausa',
    porque: 'O robô segue só com a busca por script e a fila de login.', proximo: 'Nada a fazer: as pausas expiram sozinhas.',
    acao: { rotulo: 'Ver automação', aba: 'robo' } });
  if (d.telegram?.status === 'aguardando login') acoes.push({ id: 'tg', grupo: 'info', titulo: 'Telegram aguardando login',
    porque: 'O garimpo de vagas pelo Telegram está parado.', proximo: 'Faça login quando quiser reativar.', acao: { rotulo: 'Ver Telegram', aba: 'telegram' } });

  const pendentes = acoes.filter(precisaHumano).length;
  const criticos = acoes.filter(a => a.grupo === 'critico').length;

  // ---- 4 KPIs, no duplicates; '—' when the payload does not carry the data ----
  const ult = d.descoberta?.ultima;
  const hojeN = serie.at(-1)?.[1];
  const seteDias = d.rendimento?.aplicadas7d ?? serie.slice(-7).reduce((a, [, n]) => a + n, 0);
  const kpis = [
    { id: 'enviadas', rotulo: 'Enviadas hoje', valor: temSerie ? hojeN : '—', ponto: 'cobalt', ir: () => abrirAba('candidaturas'),
      sub: temSerie ? `${seteDias} em 7 dias · ${rodadasHoje ?? '—'} rodadas hoje` : 'sem contagem diária nesta visão' },
    { id: 'precisa', rotulo: 'Precisa de você', valor: pendentes, ponto: 'coral', ir: irPrecisa, tom: criticos ? 'bad' : undefined,
      sub: pendentes ? `${criticos} crítico(s)` : 'nada pendente' },
    { id: 'respostas', rotulo: 'Respostas de empresas', valor: respostas?.total ?? '—',
      sub: respostas ? `${respostas.entrevistas} entrevista · ${respostas.etapas} teste/etapa` : 'sem contagem de respostas nesta visão' },
    { id: 'novas', rotulo: 'Novas vagas', valor: ult?.novas ?? '—', ponto: 'lime', ir: () => abrirAba('robo'),
      sub: ult ? `${ult.lidas ?? '—'} lidas na última coleta${d.descoberta?.ultimaColeta ? ` · ${desde(d.descoberta.ultimaColeta, agora)}` : ''}` : 'sem coleta registrada',
      dica: 'Vagas novas que passaram nos filtros na última coleta' },
  ];

  const abas = [
    { id: 'candidaturas', rotulo: 'Candidaturas', curto: 'Envios', conta: temLista ? aplicadas.length : undefined },
    { id: 'bloqueios', rotulo: 'Bloqueios', conta: totalBloqueios, alerta: aguardandoLogin.length > 0 || precisaAcao.length > 0 },
    { id: 'robo', rotulo: 'Automação', curto: 'Robô', alerta: pills.some(p => p.tom === 'bad') || semSinal },
    ...(d.linkedin ? [{ id: 'linkedin', rotulo: 'LinkedIn', conta: convites.length }] : []),
    ...(d.telegram ? [{ id: 'telegram', rotulo: 'Telegram' }] : []),
  ];
  const navItens = [{ id: 'inicio', rotulo: 'Início', alerta: pendentes > 0 }, ...abas];
  const abaAtiva = navItens.some(a => a.id === aba) ? aba : 'inicio';
  const abaRot = navItens.find(a => a.id === abaAtiva)?.rotulo;
  const fontesRuins = d.fontesOk ? Object.entries(d.fontesOk).filter(([, ok]) => ok === false).map(([k]) => k) : null;
  const portais = listaPortais(d);

  const avisos = [
    usandoCache && { id: 'cache', rotulo: 'Em cache', dica: 'exibindo o último retrato válido; a atualização mais recente falhou.' },
    modo.id === 'demo' && { id: 'demo', rotulo: modo.rotulo, dica: 'números gerados pelo monitor, não são candidaturas reais.' },
    modo.id === 'publico' && { id: 'publico', rotulo: modo.rotulo, dica: 'textos, terminal e dados pessoais ficam ocultos.' },
  ].filter(Boolean);

  return (
    <div className="app" id="topo">
      <Sidebar itens={navItens} ativo={abaAtiva} onSelect={abrirAba}
               rodape={<>
                 <span className={`side-hb${semSinal ? ' is-stale' : ''}`}><i aria-hidden="true" />{semSinal ? 'Sem sinal' : 'Robô conectado'}</span>
                 <small>Último sinal {ultimoSinal}</small>
                 <small>{modo.rotulo} · fuso {d.tz || TZ}</small>
               </>} />
      <main className="shell" ref={mainRef} tabIndex={-1} aria-labelledby={abaAtiva === 'inicio' ? 'command-title' : 'workspace-title'}>
        <StatusStrip secao={abaRot} contexto={hojeLabel} fr={fr} idadeSinal={ultimoSinal} modo={modo}
                     onInicio={() => abrirAba('inicio')}
                     avisoCache={erroRede && usandoCache ? `${erroRede} Exibindo o retrato de ${horaSeg(d.updatedAt)}; nova tentativa em ~${espera}s.` : null} />

        {abaAtiva === 'inicio' ? (
          <>
            <CommandHeader estado={estado} atualizacao={atualizacao} fr={fr} pendentes={pendentes} criticos={criticos}
                           avisos={avisos} onPrecisa={irPrecisa} />
            <div className="home-grid">
              <div className="home-main">
                <div id="precisa" className="anchor">
                  <ActionCenter itens={acoes} abrirAba={abrirAba} obsoleto={obsoleto} />
                </div>
                <KpiRow itens={kpis} obsoleto={obsoleto} />
                {temSerie && <TodayHero hojeLabel={hojeLabel} serie={serie} rodadasHoje={rodadasHoje} obsoleto={obsoleto} />}
              </div>
              <AutomationMonitor loops={pills} eventos={d.events || []} semSinal={semSinal} ultimoSinal={ultimoSinal}
                                 rodadasHoje={rodadasHoje} proximoSite={d.rodizio?.proximo || loops.candidaturas?.nextSite}
                                 fontesRuins={fontesRuins} onAbrir={() => abrirAba('robo')} obsoleto={obsoleto} />
            </div>
          </>
        ) : (
          <section className="workspace" aria-labelledby="workspace-title">
            <div className="detail-head">
              <h1 id="workspace-title">{abaRot}</h1>
              <span className="detail-route" aria-hidden="true" />
            </div>
            {abaAtiva === 'candidaturas' && (
              <>
                {!temLista && (
                  <p className="notice">
                    {modo.id === 'publico'
                      ? 'Visão pública: a lista de candidaturas fica oculta. Abra o monitor com o link que contém a chave para ver os detalhes.'
                      : <>Modo agregado: a lista de candidaturas fica oculta. Para ver os detalhes, rode o publisher com
                        {' '}<code>MONITOR_INCLUDE_DETAILS=1</code> e proteja o painel com <code>MONITOR_SECRET</code>.</>}
                  </p>
                )}
                <div className="layout layout-wide">
                  <ApplicationsPanel aplicadas={aplicadas} />
                  <CadencePanel serie={serie} porFonte={porFonte} porStatus={statusCounts} total={temLista ? aplicadas.length : (d.totals?.candidaturas ?? 0)} />
                </div>
              </>
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
                <div className="robo-grid">
                  <div className="robo-col robo-main">
                    <DiagnosisPanel
                      d={d} fr={fr} loops={loops} agora={agora}
                      ultimaAplicada={ultimaAplicada}
                      rodadasDesdeEnvio={rodadasDesdeEnvio}
                      horasSemEnviar={horasSemEnviar}
                      gruposBloq={temBloqueios ? gruposBloq : null}
                      totalBloqueios={totalBloqueios}
                    />
                    <TerminalPanel logTail={d.logTail} />
                    <TimelinePanel eventos={d.events || []} />
                  </div>
                  <div className="robo-col robo-side">
                    <RotationHealthPanel rodizioSaude={d.rodizioSaude} proximo={d.rodizio?.proximo} portais={portais} />
                    <DiscoveryPanel descoberta={d.descoberta} gmail={d.gmailStatus} />
                    <YieldPanel rendimento={d.rendimento} />
                    <ModelsPanel modelos={d.modelos} />
                  </div>
                </div>
              </>
            )}
            {abaAtiva === 'linkedin' && <InvitesPanel convites={convites} bloqueios={d.linkedin?.bloqueios || []} convitesHoje={loops.linkedin?.convitesHoje ?? 0} limiteDiario={d.linkedin?.limiteDiario} hoje={hojeYmd} loop={loops.linkedin} />}
            {abaAtiva === 'telegram' && <TelegramPanel telegram={d.telegram} agora={agora} />}
          </section>
        )}

        <footer className="footer">
          Horários em {d.tz || TZ} · atualiza a cada {POLL_MS / 1000}s ({POLL_BG_MS / 1000}s com a aba em segundo plano)
          {d.rodizio?.proximo ? ` · próximo site do rodízio: ${d.rodizio.proximo}` : ''}
          {d.publisher?.host && d.publisher.host !== 'redacted' ? ` · fonte ${d.publisher.host}#${d.publisher.pid}` : ''}
        </footer>
      </main>
    </div>
  );
}
