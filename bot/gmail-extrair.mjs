// gmail-extrair.mjs "<gmail search query>" [account email] — prints JSON [{texto}] with the text of the result
// rows of a Gmail search, read from the robot's Chrome (CDP 9222, Gmail already logged in).
// Raw CDP over Node's built-in WebSocket: no dependency to install or break.
// Opens its OWN tab and closes only that tab (never the browser: it is shared).
// Run it under the shared browser lock (gmail-status.py does).
const QUERY = process.argv[2] || 'newer_than:30d';
// Pick the mailbox by address, not by slot (/u/0 is whichever account logged in first).
const ACCOUNT = process.argv[3] || '';
const MAX_ROWS = 60;
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const version = await (await fetch('http://127.0.0.1:9222/json/version')).json();
const ws = new WebSocket(version.webSocketDebuggerUrl);
await new Promise((ok, err) => { ws.onopen = ok; ws.onerror = err; });
let seq = 0;
const pending = new Map();
ws.onmessage = (m) => {
  const r = JSON.parse(m.data);
  if (r.id && pending.has(r.id)) { pending.get(r.id)(r); pending.delete(r.id); }
};
const send = (method, params = {}, sessionId) => new Promise((ok) => {
  const id = ++seq;
  pending.set(id, ok);
  ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
});

const url = ACCOUNT
  ? `https://mail.google.com/mail/?authuser=${encodeURIComponent(ACCOUNT)}#search/${encodeURIComponent(QUERY)}`
  : `https://mail.google.com/mail/u/0/#search/${encodeURIComponent(QUERY)}`;
const { result: { targetId } } = await send('Target.createTarget', { url, background: true });
let out = { ok: false, linhas: [] };
try {
  const { result: { sessionId } } = await send('Target.attachToTarget', { targetId, flatten: true });
  const evalJs = async (expr) => (await send('Runtime.evaluate', { expression: expr, returnByValue: true }, sessionId)).result?.result?.value;
  // Gmail is a heavy SPA: poll until result rows (or the "no results" text / a login page) show up.
  for (let i = 0; i < 40; i++) {
    await sleep(1500);
    const st = await evalJs(`(() => {
      if (/accounts\\.google\\.com/.test(location.href)) return 'login';
      const rows = document.querySelectorAll('div[role="main"] tr[role="row"], div[role="main"] tr.zA');
      if (${JSON.stringify(ACCOUNT)} && /@/.test(document.title) && !document.title.toLowerCase().includes(${JSON.stringify(ACCOUNT.toLowerCase())})) return 'outra_conta';
      if (rows.length) return 'rows';
      if (/nenhuma mensagem|no messages matched|n[aã]o h[aá] mensagens/i.test(document.body?.innerText || '')) return 'vazio';
      return 'esperando';
    })()`);
    if (st === 'outra_conta') { out = { ok: false, erro: `conta ${ACCOUNT} nao logada no Chrome`, linhas: [] }; break; }
    if (st === 'login') { out = { ok: false, erro: 'gmail deslogado', linhas: [] }; break; }
    if (st === 'vazio') { out = { ok: true, linhas: [] }; break; }
    if (st === 'rows') {
      await sleep(1500); // let the list settle
      const linhas = await evalJs(`[...document.querySelectorAll('div[role="main"] tr[role="row"], div[role="main"] tr.zA')]
        .slice(0, ${MAX_ROWS}).map(r => (r.textContent || '').replace(/\\s+/g, ' ').trim()).filter(Boolean)`);
      out = { ok: true, linhas: [...new Set(linhas || [])] };
      break;
    }
  }
  if (!out.ok && !out.erro) out.erro = 'timeout esperando o Gmail';
} finally {
  await send('Target.closeTarget', { targetId });
  ws.close();
}
console.log(JSON.stringify(out));
