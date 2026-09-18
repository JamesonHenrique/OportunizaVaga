// Envio unico do retrato atual (chamado pelo loop a cada mudanca de estado).
import { buildSnapshot } from './snapshot.mjs';

const endpoint = process.env.MONITOR_URL;
if (!endpoint) throw new Error('MONITOR_URL ausente');

const response = await fetch(`${endpoint.replace(/\/$/, '')}/api/status`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(buildSnapshot())
});
if (!response.ok) throw new Error(`monitor HTTP ${response.status}`);
console.log('publicado');
