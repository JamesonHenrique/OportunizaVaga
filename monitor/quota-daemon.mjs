// quota-daemon.mjs — mede a cota DIARIA dos modelos :free do OpenRouter e grava
// em quota-cache.json para o snapshot.mjs incluir no modelo do painel.
//
// Apenas o OpenRouter expoe cota por API (GET /api/v1/auth/key ->
// data.free_model_daily_requests { used, limit, remaining }). Groq/Cerebras/
// HuggingFace/NVIDIA/Zen NAO expoem — para esses o painel usa o contador de
// "bateu no teto hoje" derivado do loop.log (ja presente no snapshot).
//
// Roda a cada hora. Nao falha ruido: na 1a vez sem resposta grava status 'erro'
// e o painel mostra "sem dados de cota" em vez de quebrar. Sem key, sai.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = process.env.CANDIDATURAS_ROOT || path.join(HERE, '..', 'bot');
const OUT = path.join(ROOT, 'quota-cache.json');
// Chaves fora do repo, cross-platform: Linux ~/.config/opencode/cron.env;
// Windows %USERPROFILE%\.config\opencode\cron.env ou %APPDATA%\opencode\cron.env.
const CRON_ENV_CANDIDATES = [
  process.env.CRON_ENV || null,
  path.join(os.homedir(), '.config', 'opencode', 'cron.env'),
  process.env.APPDATA ? path.join(process.env.APPDATA, 'opencode', 'cron.env') : null
].filter(Boolean);
const INTERVAL_MS = 60 * 60 * 1000; // 1h — a cota zera 1x/dia, nao muda em segundos.

const readKey = () => {
  for (const file of CRON_ENV_CANDIDATES) {
    try {
      const raw = fs.readFileSync(file, 'utf8');
      const m = /^OPENROUTER_API_KEY=(.+)$/m.exec(raw);
      if (m) return m[1].trim().replace(/^["']|["']$/g, '');
    } catch { /* tenta o proximo candidato */ }
  }
  return null;
};

const gravar = (obj) => {
  const tmp = `${OUT}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify({ atualizadoEm: new Date().toISOString(), ...obj }, null, 2));
  fs.renameSync(tmp, OUT); // rename e atomico: snapshot nunca le JSON pela metade.
};

const medir = async () => {
  const key = readKey();
  if (!key) return gravar({ openrouter: null, motivo: 'sem OPENROUTER_API_KEY no cron.env' });
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 15000);
    const r = await fetch('https://openrouter.ai/api/v1/auth/key', {
      headers: { Authorization: `Bearer ${key}` }, signal: ctrl.signal
    });
    clearTimeout(t);
    if (!r.ok) return gravar({ openrouter: null, motivo: `HTTP ${r.status}` });
    const j = await r.json();
    const d = j?.data?.free_model_daily_requests || {};
    const used = Number(d.used || 0), limit = Number(d.limit || 0);
    const remaining = Number(d.remaining ?? (limit ? limit - used : 0));
    const percent = limit > 0 ? Math.round((used / limit) * 1000) / 10 : null;
    gravar({ openrouter: { used, limit, remaining, percent } });
  } catch (e) {
    gravar({ openrouter: null, motivo: e?.name === 'AbortError' ? 'timeout 15s' : String(e?.message || e) });
  }
};

await medir();                       // 1a medida imediata ao subir.
setInterval(medir, INTERVAL_MS);     // depois, de hora em hora.
console.log(`[quota-daemon] ativo; cache em ${OUT}; intervalo ${INTERVAL_MS / 60000}min`);
