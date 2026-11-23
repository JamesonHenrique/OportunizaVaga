// Envio unico do retrato atual (chamado pelo loop a cada mudanca de estado).
import { buildSnapshot } from './snapshot.mjs';

const endpoint = process.env.MONITOR_URL;
if (!endpoint) throw new Error('MONITOR_URL ausente');
const secret = process.env.MONITOR_SECRET || process.env.MONITOR_INGEST_SECRET;

const response = await fetch(`${endpoint.replace(/\/$/, '')}/api/status`, {
  method: 'POST',
  headers: {
    'content-type': 'application/json',
    ...(secret ? { 'x-monitor-secret': secret } : {})
  },
  body: JSON.stringify(buildSnapshot()),
  signal: AbortSignal.timeout(20000)
});
if (!response.ok) throw new Error(`monitor HTTP ${response.status}`);
console.log('publicado');
