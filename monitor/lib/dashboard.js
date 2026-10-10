// Pure helpers for the dashboard: formatting, block analysis, CSV export.
// No React here — imported by both the page and the panel components.

// Robot timezone; the snapshot also carries it (d.tz). Override with NEXT_PUBLIC_BOT_TZ.
export const TZ = process.env.NEXT_PUBLIC_BOT_TZ || 'America/Sao_Paulo';
export const CACHE_KEY = 'monitor:lastGood:v2';
export const FIRST_SEEN_KEY = 'monitor:firstSeen:v1';

export const hora = (iso) => iso
  ? new Date(iso).toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' })
  : '--:--';
export const horaSeg = (iso) => iso
  ? new Date(iso).toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  : '--:--:--';
export const dia = (iso) => iso
  ? new Date(iso).toLocaleDateString('pt-BR', { timeZone: TZ, day: '2-digit', month: '2-digit' })
  : '--/--';

export const desde = (iso, agora) => {
  if (!iso) return 'nunca';
  const s = Math.max(0, Math.round((agora - new Date(iso).getTime()) / 1000));
  if (s < 60) return `há ${s}s`;
  if (s < 3600) return `há ${Math.round(s / 60)}min`;
  if (s < 86400) return `há ${Math.round(s / 3600)}h`;
  return `há ${Math.round(s / 86400)}d`;
};

export const faltam = (iso, agora) => {
  if (!iso) return null;
  const s = Math.round((new Date(iso).getTime() - agora) / 1000);
  if (s <= 0) return 'a qualquer momento';
  const m = Math.floor(s / 60);
  return m >= 1 ? `em ${m}min ${String(s % 60).padStart(2, '0')}s` : `em ${s}s`;
};

export const dataHora = (iso) => iso ? `${dia(iso)} ${horaSeg(iso)}` : 'sem registro';

export const fmtDur = (m) => m == null ? '—' : (m < 1 ? `${Math.max(1, Math.round(m * 60))}s` : `${m.toFixed(1)}min`);

// Date cited in the block text ("publ. 14/09", "atualiz. 15/09", "2026-09-14").
// firstSeen stamped everything at first access — the date inside the text is the
// only real clue about the past. Returns YYYY-MM-DD or null. Ignores values
// (R$5,5k), app ids (756908301) and shifts (12x36): the pattern demands DD/MM
// or YYYY-MM-DD.
export function dataCitada(b) {
  const t = `${b.chave || ''} ${b.motivo || b.detalhe || ''}`;
  let best = null;
  const push = (y, mo, dd) => {
    if (mo < 1 || mo > 12 || dd < 1 || dd > 31) return;
    const iso = `${y}-${String(mo).padStart(2, '0')}-${String(dd).padStart(2, '0')}`;
    if (!best || iso > best) best = iso;
  };
  for (const m of t.matchAll(/(\d{4})[\/\-](\d{2})[\/\-](\d{2})/g)) push(+m[1], +m[2], +m[3]);
  for (const m of t.matchAll(/(?<!\d)(\d{2})\/(\d{2})(?:\/(\d{4}|\d{2}))?/g)) {
    // "ate 30/09" is the job deadline, not the mention date — otherwise an old
    // block with a future deadline would sort as the newest one.
    const antes = t.slice(Math.max(0, m.index - 8), m.index);
    if (/at[eé]\s*$/i.test(antes)) continue;
    let y = m[3] ? +m[3] : 2026;
    if (y < 100) y += 2000;
    push(y, +m[2], +m[1]);
  }
  return best;
}

export const diaCurto = (ymd) => {
  if (!ymd || ymd.length < 10) return '--/--';
  const ano = ymd.slice(0, 4);
  return `${ymd.slice(8, 10)}/${ymd.slice(5, 7)}${ano === '2026' ? '' : '/' + ano.slice(2)}`;
};

// Block timeline line, by confidence order:
// 1) `em` sent by the PC (bloqueado em) 2) date cited in the text (mencionado em)
// 3) local firstSeen (detectado aqui em — only valid for new blocks).
export function refBloq(b, vistos) {
  if (b.em) return { txt: `bloqueado em ${dataHora(b.em)}`, key: b.em.slice(0, 10) };
  const c = dataCitada(b);
  if (c) return { txt: `mencionado em ${diaCurto(c)}`, key: c };
  const v = vistos[b.chave];
  if (v) return { txt: `detectado aqui em ${dataHora(v)}`, key: v.slice(0, 10) };
  return { txt: 'horário não registrado', key: '' };
}

export const ROTULO = {
  rodando: 'Rodando', dormindo: 'Dormindo', quota: 'Limite do modelo',
  retentando: 'Retentando', quebrado: 'Quebrado', interrompido: 'Interrompido',
  parado: 'Parado', ocioso: 'Ocioso', desconhecido: 'Sem dados'
};

// Groups blocks by root cause to answer "why is it not applying?".
// Heuristics over the text the robot wrote. First match wins, so final-verdict rules
// (remote/level/language) come before channel rules; explicit "CAUSA ..." markers
// and negations ("sem ingles") are handled in classificar().
// grupo: 'voce' = needs the candidate, 'robo' = the robot retries, 'final' = discarded for good.
// [label, regex, grupo] — first match wins; grupo: voce | robo | final
export const CAUSAS = [
  ['exclusiva PCD', /\bpcd\b|exclusiva para pessoas com defici/, 'final'],
  ['não-remoto', /presencial|h[ií]brid|somente remoto|regra 1\b|modalidade=hibrido/, 'final'],
  ['nível acima de JR', /\bpleno\b|s[eê]nior|\bregra 3\b|somente jr|anos de experi[eê]ncia|\d\+? anos/, 'final'],
  ['idioma', /ingl[eê]s|english|espanhol/, 'final'],
  ['formação', /superior completo|gradua[cç][aã]o completa|formad[oa] em/, 'final'],
  ['vaga encerrada', /\b404\b|encerrad|expirad|n[aã]o (est[aá] )?mais dispon|zero resultados|vaga sumiu/, 'final'],
  ['formulário travado', /captcha|disabled|requestsubmit|bot[aã]o .*(trav|n[aã]o)|erro ao enviar|form.*(quebr|trav)|n[aã]o pode se candidatar/, 'robo'],
  ['login / sessão', /sess[aã]o|n[aã]o (est[aá] )?logad|exige login|modal de login|\/login|passport|c[oó]digo de (6|verifica)|senha google/, 'voce'],
  ['dado ausente', /\bcpf\b|\brg\b|facebook|nome.*m[aã]e|coeficiente|grade hor[aá]ria|\bpis\b|n[aã]o consta|dado ausente/, 'voce'],
  ['cadastro quebrado', /cadastro|oauth|redirect_uri|conta \w+ inexistente|exige conta|google quebrado|canal travado/, 'voce'],
  ['skill sem evidência', /evid[eê]ncia|inventar|regra 4|stack|n[aã]o possui|requisito|exige/, 'final'],
  ['fonte spam/paywall', /spam|paywall|premium|golpe/, 'final'],
  ['linkedin/quota', /linkedin|nota|convite|limite/, 'robo'],
];
// Site-wide channel problems (not a job): recognized by the key the robot chose.
const CANAL = /login|captcha|sess(ao|ion)|cloudflare|degradad|_canal|site_?wide/;
// Explicit cause markers the robot writes inside long texts ("CAUSA REAL agora: ...").
const MARCADOR = /(causa(?: real| atual| nova| do bloqueio)?(?: agora)?|causas atuais|canal (?:travado|fechado))\s*[:=-]\s*/;
// Negations that would false-match a rule ("sem anos/ingles/grad", "sem exigencia de tempo").
const NEGACAO = /\bsem (?:exig[eê]ncia (?:de )?)?[\w\/+-]+(?:\/[\w+-]+)*/g;

function porRegra(t) {
  for (const [causa, re, grupo] of CAUSAS) if (re.test(t)) return { causa, grupo };
  return null;
}

export function classificar(b) {
  const chave = String(b.chave || '').toLowerCase();
  const t = String(b.motivo || b.detalhe || '').toLowerCase();
  if (b.origem === 'linkedin') return /sess/.test(t + chave) ? { causa: 'login / sessão', grupo: 'voce' } : { causa: 'linkedin/quota', grupo: 'robo' };
  if (CANAL.test(chave)) return { causa: 'site/canal fora do ar', grupo: 'robo' };
  const m = MARCADOR.exec(t);
  if (m) {
    const r = porRegra(t.slice(m.index + m[0].length, m.index + m[0].length + 300).replace(NEGACAO, ''));
    if (r) return r;
  }
  return porRegra(`${chave} ${t.replace(NEGACAO, '')}`) || { causa: 'outros', grupo: 'final' };
}

export const causaRaiz = (b) => classificar(b).causa;

export const GRUPO_ROTULO = { voce: 'depende de você', robo: 'robô retenta', final: 'descartada' };

// Readable title: "Empresa — Vaga" when recorded; otherwise the head of the text
// (before the first parenthesis/colon), falling back to the humanized key.
export function tituloBloq(b) {
  if (b.empresa && b.vaga) return `${b.empresa} — ${b.vaga}`;
  if (b.empresa || b.vaga) return b.empresa || b.vaga;
  const t = String(b.motivo || '').replace(/^(descartada?|retentor|bloqueio de canal)[^:]*:\s*/i, '');
  const head = t.split(/\s\(|:\s|\.\s/)[0].trim();
  if (head && head.length >= 8 && head.length <= 90) return head;
  return String(b.chave || '—').replace(/[_-]+/g, ' ');
}

// Escapes one CSV cell: duplicated quotes + wraps if it has comma/quote/newline.
const csvCell = (v) => {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function rotuloStatus(s) {
  const v = (s || 'enviada').toLowerCase();
  if (v === 'enviada') return 'Enviada';
  if (v === 'entrevista') return 'Entrevista';
  if (v === 'etapa_teste') return 'Teste / fit cultural';
  if (v === 'proxima_etapa') return 'Próxima etapa';
  if (v === 'respondida') return 'Respondida';
  if (v === 'followup' || v === 'follow-up') return 'Follow-up';
  if (v === 'quase_la' || v === 'quase-la') return 'Quase lá';
  if (v === 'em_analise') return 'Em análise';
  if (v === 'encerrada') return 'Encerrada';
  if (v === 'sem_resposta') return 'Sem resposta';
  if (v === 'sem_retorno_verificavel') return 'Sem retorno';
  if (v.startsWith('enviada')) return 'Enviada';
  const t = v.replace(/_/g, ' ');
  return t.charAt(0).toUpperCase() + t.slice(1);
}

export function baixarCSV(nome, cabecalho, linhas) {
  const conteudo = [cabecalho, ...linhas].map(l => l.map(csvCell).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob(['\ufeff' + conteudo], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url; a.download = nome;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Human status for the status strip: tone (ok|warn|bad) + short phrase.
// Log wording ("cascateando opencode/...") stays in the Robô tab.
// `agendada`: next scheduled run (daily loops look "parado" between runs).
export function statusLoop(loop, agora, agendada) {
  if (!loop) return { tom: 'mute', frase: 'sem dados' };
  const msg = (loop.message || '').toLowerCase();
  const futuro = agendada && new Date(agendada).getTime() > agora;
  const quando = (iso) => {
    const d = new Date(iso);
    const hoje = new Date(agora).toLocaleDateString('pt-BR', { timeZone: TZ });
    const h = d.toLocaleTimeString('pt-BR', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
    return d.toLocaleDateString('pt-BR', { timeZone: TZ }) === hoje ? `hoje ${h}` : `amanhã ${h}`;
  };
  switch (loop.state) {
    case 'rodando': return { tom: 'ok', frase: 'rodando agora' };
    case 'ocioso':
      if (/limite|cascat/.test(msg)) return { tom: 'warn', frase: 'trocando de modelo' };
      return { tom: 'ok', frase: loop.proximaEm ? `próxima ${faltam(loop.proximaEm, agora)}` : 'aguardando rodada' };
    case 'dormindo': return { tom: 'ok', frase: loop.proximaEm ? `pausa, volta ${faltam(loop.proximaEm, agora)}` : 'em pausa' };
    case 'quota': return { tom: 'warn', frase: 'limite dos modelos grátis' };
    case 'retentando': return { tom: 'warn', frase: 'tentando de novo' };
    case 'quebrado': return { tom: 'bad', frase: 'com erro' };
    case 'interrompido': return { tom: 'bad', frase: 'interrompido' };
    case 'parado':
      if (futuro) return { tom: 'ok', frase: `próxima ${quando(agendada)}` };
      return { tom: 'bad', frase: `parado ${desde(loop.ultimoEvento, agora)}` };
    default: return { tom: 'mute', frase: ROTULO[loop.state] || 'sem dados' };
  }
}

// Last `n` days ending at `hoje` (YYYY-MM-DD), zero-filled: [[ymd, count]].
export function serieDias(porDia, hoje, n = 14) {
  const m = new Map(porDia);
  const fim = new Date(`${hoje}T12:00:00Z`);
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const k = new Date(fim.getTime() - i * 86400000).toISOString().slice(0, 10);
    out.push([k, m.get(k) || 0]);
  }
  return out;
}
