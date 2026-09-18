// Daemon de heartbeat: reenvia o retrato completo de tempos em tempos.
// O Vercel guarda so o ultimo retrato em memoria (custo zero, sem banco); se a
// funcao reiniciar a frio, o proximo heartbeat repoe tudo em poucos segundos.
import { buildSnapshot } from './snapshot.mjs';

const endpoint = process.env.MONITOR_URL;
if (!endpoint) throw new Error('Defina MONITOR_URL com a URL da Vercel.');
const secret = process.env.MONITOR_SECRET || null;

const ACTIVE_MS = 15000;   // rodada em andamento: atualiza rapido
const IDLE_MS = 60000;     // dormindo/quota: economiza requisicao (tudo no free tier)
const TIMEOUT_MS = 20000;
const MAX_BACKOFF_MS = 300000;

let timer = null;
let falhasSeguidas = 0;

async function publish() {
  const snapshot = buildSnapshot();
  const ctrl = new AbortController();
  const timeout = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${endpoint.replace(/\/$/, '')}/api/status`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        ...(secret ? { 'x-monitor-secret': secret } : {})
      },
      body: JSON.stringify(snapshot),
      signal: ctrl.signal
    });
    if (!response.ok) throw new Error(`monitor HTTP ${response.status}`);
    falhasSeguidas = 0;
    return snapshot.loops.candidaturas.state;
  } catch (error) {
    falhasSeguidas += 1;
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function tick() {
  let state = 'desconhecido';
  try {
    state = await publish();
  } catch (error) {
    // Nunca derruba o daemon: loga e tenta de novo com backoff exponencial.
    // Sem dado pessoal aqui — só o motivo do erro de rede/HTTP.
    console.error(new Date().toISOString(), `heartbeat falhou (${falhasSeguidas}x):`, error.message);
  }
  const base = state === 'rodando' ? ACTIVE_MS : IDLE_MS;
  const backoff = falhasSeguidas === 0 ? 0 : Math.min(MAX_BACKOFF_MS, 5000 * 2 ** Math.min(falhasSeguidas - 1, 5));
  timer = setTimeout(tick, base + backoff);
}

process.on('SIGTERM', () => { clearTimeout(timer); process.exit(0); });
process.on('SIGINT', () => { clearTimeout(timer); process.exit(0); });
tick();
