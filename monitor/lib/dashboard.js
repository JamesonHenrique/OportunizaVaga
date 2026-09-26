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
// Simple heuristics over the text/key, no personal data exposed.
export function causaRaiz(b) {
  const t = `${b.chave || ''} ${(b.motivo || b.detalhe || '')}`.toLowerCase();
  if (/presencial|h[ií]brido|somente remoto|regra 1/.test(t)) return 'regra 1 · não-remoto';
  if (/pleno|senior|s[eê]nior|nível|nivel|regra 3|somente jr/.test(t)) return 'regra 3 · nível';
  if (/evid[eê]ncia|inventar|regra 4|sem evidencia|experi[eê]ncia/.test(t)) return 'regra 4 · skill sem evidência';
  if (/cpf|rg|facebook|instagram|estado civil|nome.*m[aã]e|coeficiente|cr\b|grade hor[aá]ria|obrigat[oó]rio|n[aã]o consta/.test(t)) return 'dado ausente (não inventar)';
  if (/404|encerrad|expirad|p[aá]gina.*home|zero resultados/.test(t)) return 'vaga encerrada';
  if (/pcd|exclusiva/.test(t)) return 'exclusiva PCD';
  if (/ingl[eê]s|superior completo|cursando/.test(t)) return 'requisito (idioma/formação)';
  if (/cadastro|oauth|redirect_uri|allowlist|google quebrado/.test(t)) return 'cadastro quebrado';
  if (/spam|paywall|premium/.test(t)) return 'fonte com spam/paywall';
  if (/linkedin|nota|convite|limite/.test(t)) return 'linkedin/quota';
  return 'outros';
}

// Escapes one CSV cell: duplicated quotes + wraps if it has comma/quote/newline.
const csvCell = (v) => {
  const s = v == null ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};

export function rotuloStatus(s) {
  const v = (s || 'enviada').toLowerCase();
  if (v === 'enviada') return 'ENVIADA';
  if (v === 'entrevista') return 'ENTREVISTA';
  if (v === 'respondida') return 'RESPONDIDA';
  if (v === 'followup' || v === 'follow-up') return 'FOLLOW-UP';
  if (v === 'quase_la' || v === 'quase-la') return 'QUASE LÁ';
  return v.toUpperCase();
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
