import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import * as dashboard from './lib/dashboard.js';

const endpoint = 'http://localhost/api/status';
const secret = 'synthetic-ingest';
const before = Object.fromEntries(['MONITOR_SECRET', 'MONITOR_INGEST_SECRET', 'MONITOR_LOCAL', 'MONITOR_DEMO']
  .map(key => [key, process.env[key]]));
let instance = 0;

afterEach(() => {
  for (const [key, value] of Object.entries(before)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
});

async function route({ demo = false, readSecret, ingestSecret } = {}) {
  for (const key of Object.keys(before)) delete process.env[key];
  process.env.MONITOR_LOCAL = '0';
  if (demo) process.env.MONITOR_DEMO = '1';
  if (readSecret) process.env.MONITOR_SECRET = readSecret;
  if (ingestSecret) process.env.MONITOR_INGEST_SECRET = ingestSecret;
  return import(`./app/api/status/route.js?instance=${++instance}`);
}

const snapshot = (extra = {}) => ({
  builtAt: new Date().toISOString(), tz: 'America/Sao_Paulo',
  totals: { candidaturas: 2, bloqueios: 1, eventos: 5 }, loops: {},
  ...extra
});

function post(payload, auth, headers = {}) {
  return new Request(endpoint, {
    method: 'POST',
    headers: { ...(auth ? { 'x-monitor-secret': auth } : {}), ...headers },
    body: typeof payload === 'object' && !(payload instanceof ReadableStream) ? JSON.stringify(payload) : payload,
    duplex: 'half'
  });
}

test('write auth fails closed and supports an ingest-only secret', async () => {
  let api = await route();
  assert.equal((await api.POST(post(snapshot()))).status, 503);
  api = await route({ ingestSecret: secret });
  assert.equal((await api.POST(post(snapshot()))).status, 401);
  assert.equal((await api.POST(post(snapshot(), 'wrong'))).status, 401);
  assert.equal((await api.POST(post(snapshot(), secret))).status, 200);
  assert.equal((await (await api.GET(new Request(endpoint))).json()).publicMode, true);
});

test('demo is read-only and server owns the demo flag', async () => {
  let api = await route({ demo: true, readSecret: secret });
  assert.equal((await api.POST(post(snapshot(), secret))).status, 403);
  assert.equal((await (await api.GET(new Request(endpoint))).json())._demo, true);
  api = await route({ readSecret: secret });
  assert.equal((await api.POST(post(snapshot({ _demo: true }), secret))).status, 200);
  const privateGet = await api.GET(new Request(endpoint, { headers: { 'x-monitor-secret': secret } }));
  assert.equal((await privateGet.json())._demo, undefined);
});

test('public response reconstructs safe fields and rejects PII in dynamic keys and enum values', async () => {
  const api = await route({ readSecret: secret });
  const pii = 'Synthetic Example Person';
  const evidence = new Date().toISOString();
  const data = snapshot({
    totals: { candidaturas: 2, bloqueios: 1, eventos: 5, extra: 99 },
    porFonte: { gupy: 2, [pii]: 3 },
    saudePortais: { gupy: { state: 'funcionando', checkedAt: evidence, reason: pii, evidence: pii }, [pii]: { state: 'funcionando' } },
    loops: {
      candidaturas: { state: 'rodando', phase: 'applying', nextSite: 'gupy', rodadasHoje: 2, message: pii, meta: { company: pii } },
      linkedin: { state: pii, phase: pii, nextSite: pii },
      [pii]: { state: 'rodando' }
    },
    descoberta: { porStatus: { nova: 2 }, ultimaColeta: evidence, ultima: { novas: 4, lidas: 8, company: pii }, proximas: [{ title: pii }] },
    telemetry: { porStatus: { entrevista: 1, respondida: 1, encerrada: 1, [pii]: 1 } },
    applied: [{ company: pii, title: pii, url: 'https://example.invalid/job/1' }],
    blocked: [{ company: pii }], blocks: [{ company: pii }], events: [{ text: pii }], terminal: [pii],
    unseen: { company: pii }
  });
  assert.equal((await api.POST(post(data, secret))).status, 200);
  const response = await api.GET(new Request(endpoint));
  const body = await response.json();
  assert.equal(body.publicMode, true);
  assert.equal(body.builtAt, data.builtAt);
  assert.equal(body.updatedAt, body.receivedAt);
  assert.deepEqual(body.totals, { candidaturas: 2, bloqueios: 1, eventos: 5 });
  assert.deepEqual(body.porFonte, { gupy: 2 });
  assert.deepEqual(body.saudePortais, { gupy: { state: 'funcionando', checkedAt: evidence } });
  assert.deepEqual(body.loops, { candidaturas: { state: 'rodando', phase: 'applying', nextSite: 'gupy', roundsToday: 2 } });
  assert.deepEqual(body.descoberta, { porStatus: { nova: 2 }, ultimaColeta: evidence, ultima: { novas: 4, lidas: 8 } });
  assert.equal(body.porDia, undefined);
  assert.deepEqual(dashboard.resumoRespostas(body.telemetry.porStatus), { total: 3, entrevistas: 1, etapas: 0 });
  for (const key of ['applied', 'blocked', 'blocks', 'events', 'terminal', 'unseen', '_meta']) assert.equal(body[key], undefined);
  assert.ok(!JSON.stringify(body).includes(pii));

  const signed = await api.GET(new Request(`${endpoint}?secret=${secret}`));
  assert.equal((await signed.json()).applied[0].company, pii);
  const cookie = signed.headers.get('set-cookie');
  assert.match(cookie, /; HttpOnly; Secure; SameSite=Strict$/);
  const session = await api.GET(new Request(endpoint, { headers: { cookie: cookie.split(';', 1)[0] } }));
  assert.equal((await session.json()).applied[0].company, pii);
});

test('public calendar and freshness follow the snapshot timezone and generation time', async () => {
  const api = await route({ ingestSecret: secret });
  const builtAt = '2026-11-21T23:51:00.000Z';
  assert.equal((await api.POST(post(snapshot({ builtAt, tz: 'Asia/Tokyo', porDia: {} }), secret))).status, 200);
  const body = await (await api.GET(new Request(endpoint))).json();
  assert.deepEqual(body.porDia, {});
  const fr = dashboard.frescor({ ...body, freshness: { ...body.freshness, state: 'live' } }, Date.parse(builtAt) + 420000);
  assert.equal(fr.estado, 'stale');
  assert.equal(fr.ref, builtAt);
  assert.equal(fr.idadeMs, 420000);
  assert.equal(dashboard.diaDoSnapshot(body, Date.parse('2026-11-23T00:00:00Z')), '2026-11-22');
});

test('byte limit applies to streamed UTF-8 even without an honest Content-Length', async () => {
  const api = await route({ readSecret: secret });
  const encoder = new TextEncoder();
  const large = JSON.stringify(snapshot({ extension: 'é'.repeat(750000) }));
  const chunks = [large.slice(0, 400000), large.slice(400000)];
  for (const headers of [{}, { 'content-length': '1' }]) {
    let index = 0;
    const stream = new ReadableStream({
      pull(controller) {
        const chunk = chunks[index++];
        if (chunk) controller.enqueue(encoder.encode(chunk));
        else controller.close();
      }
    });
    assert.equal((await api.POST(post(stream, secret, headers))).status, 413);
  }
  assert.equal((await (await api.GET(new Request(endpoint))).json()).freshness.state, 'cold_start');
});

test('malformed, invalid and out-of-order writes leave the last accepted snapshot intact', async () => {
  const api = await route({ readSecret: secret });
  const builtAt = new Date().toISOString();
  assert.equal((await api.POST(post(snapshot({ builtAt }), secret))).status, 200);
  for (const payload of ['{', snapshot({ builtAt: 'yesterday' }), snapshot({ tz: 'unrecognized' }), snapshot({ loops: [] }), snapshot({ totals: { candidaturas: '2' } }), snapshot({ applied: [false] })]) {
    assert.equal((await api.POST(post(payload, secret))).status, 400);
  }
  const older = new Date(Date.parse(builtAt) - 1000).toISOString();
  assert.equal((await api.POST(post(snapshot({ builtAt: older }), secret))).status, 409);
  assert.equal((await (await api.GET(new Request(endpoint))).json()).builtAt, builtAt);
});

test('freshness clocks distinguish cold start, live and stale', async t => {
  const api = await route({ readSecret: secret });
  let now = Date.now();
  t.mock.method(Date, 'now', () => now);
  const get = async () => (await api.GET(new Request(endpoint))).json();
  assert.deepEqual((await get()).freshness, { state: 'cold_start', ageMs: null, thresholdMs: 420000 });
  const builtAt = new Date(now - 5000).toISOString();
  assert.equal((await api.POST(post(snapshot({ builtAt }), secret))).status, 200);
  const live = await get();
  assert.equal(live.receivedAt, new Date(now).toISOString());
  assert.deepEqual(live.freshness, { state: 'live', ageMs: 5000, thresholdMs: 420000 });
  now += 415000;
  assert.deepEqual((await get()).freshness, { state: 'stale', ageMs: 420000, thresholdMs: 420000 });
  const ping = await (await api.GET(new Request(`${endpoint}?ping=1`))).json();
  assert.equal(ping.updatedAt, live.receivedAt);
  assert.deepEqual(ping.freshness, (await get()).freshness);
});

test('a slow request cannot overwrite a newer snapshot accepted while its body is pending', async () => {
  const api = await route({ readSecret: secret });
  const now = Date.now();
  const older = snapshot({ builtAt: new Date(now - 1000).toISOString() });
  const newer = snapshot({ builtAt: new Date(now).toISOString() });
  let body;
  const stream = new ReadableStream({ start: controller => { body = controller; } });
  const pending = api.POST(post(stream, secret));
  const response = await api.POST(post(newer, secret));
  body.enqueue(new TextEncoder().encode(JSON.stringify(older)));
  body.close();
  assert.equal(response.status, 200);
  assert.equal((await pending).status, 409);
  assert.equal((await (await api.GET(new Request(endpoint))).json()).builtAt, newer.builtAt);
});
