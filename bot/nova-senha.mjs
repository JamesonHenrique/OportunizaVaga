// nova-senha.mjs <domain> <email> [css selector] — creates a strong password for a new site account,
// appends it to ~/.config/oportunizavaga/credenciais.tsv (chmod 600; override with OV_CREDENTIALS_FILE) and types it straight into the
// password fields of the open tab whose URL contains <domain>, over CDP (9222).
// The password never reaches stdout, the LLM or the round log (fill_form logs its values; this does not).
// Default selector: input[type=password] (fills password + confirmation). Prints only a count.
// Do NOT run under the browser lock: the round that calls this already holds it.
import { randomBytes } from 'node:crypto';
import { chmodSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';

const [DOMAIN, EMAIL, SELECTOR = 'input[type=password]'] = process.argv.slice(2);
if (!DOMAIN || !EMAIL) { console.log('usage: nova-senha.mjs <dominio> <email> [seletor css]'); process.exit(2); }

const version = await (await fetch('http://127.0.0.1:9222/json/version')).json();
const targets = await (await fetch('http://127.0.0.1:9222/json/list')).json();
const page = targets.find(t => t.type === 'page' && t.url.includes(DOMAIN));
if (!page) { console.log(`erro: nenhuma aba aberta com "${DOMAIN}" na URL`); process.exit(1); }

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

// Letters+digits+symbol, always satisfies common "1 upper, 1 digit, 1 symbol" rules.
const senha = randomBytes(18).toString('base64url').replace(/[-_]/g, 'x') + 'A7!';

let n = 0;
try {
  const { result: { sessionId } } = await send('Target.attachToTarget', { targetId: page.id, flatten: true });
  const r = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(() => {
      const els = [...document.querySelectorAll(${JSON.stringify(SELECTOR)})].filter(e => e.offsetParent !== null);
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      for (const e of els) {
        e.focus(); set.call(e, ${JSON.stringify(senha)});
        e.dispatchEvent(new Event('input', { bubbles: true }));
        e.dispatchEvent(new Event('change', { bubbles: true }));
      }
      return els.length;
    })()`,
  }, sessionId);
  n = r.result?.result?.value || 0;
  await send('Target.detachFromTarget', { sessionId });
} finally {
  ws.close();
}
if (!n) { console.log(`erro: nenhum campo visivel para "${SELECTOR}" na aba ${DOMAIN}; nada gravado`); process.exit(1); }

// Kept OUTSIDE the repo by default. Best effort chmod: no-op on Windows (rely on the user profile ACL).
// 04/10 (cap 121 G3): appendFileSync had no dedupe, so the same domain appeared twice with different
// passwords — and trocar-senha.py, which reads this file to rotate, took the FIRST match and changed
// the wrong one. A credential file keyed by domain has one row per domain: update, never append.
const file = process.env.OV_CREDENTIALS_FILE || join(homedir(), '.config', 'oportunizavaga', 'credenciais.tsv');
mkdirSync(dirname(file), { recursive: true });
let linhas = [];
try { linhas = readFileSync(file, 'utf8').split('\n').filter(l => l.trim()); } catch {}
const registro = `${DOMAIN}\t${EMAIL}\t${senha}`;
const antes = linhas.filter(l => l.split('\t')[0] === DOMAIN).length;
const i = linhas.findIndex(l => l.split('\t')[0] === DOMAIN);
if (i >= 0) {
  // Collapse EVERY row for this domain, not just the first: the file on disk had programathor.com.br
  // twice with different passwords, and a lookup that takes the first match rotates the wrong one.
  // Insert back at the ORIGINAL index — after filter() the positions moved, so `linhas[i] = ...` would
  // land on whichever row happened to shift into slot i.
  const restantes = linhas.filter(l => l.split('\t')[0] !== DOMAIN);
  restantes.splice(Math.min(i, restantes.length), 0, registro);
  writeFileSync(file, restantes.join('\n') + '\n');
  console.log(antes > 1
    ? `aviso: ${DOMAIN} estava em ${antes} linhas de credenciais.tsv; colapsadas em 1 (a senha nova e a que passa a valer localmente).`
    : `aviso: ${DOMAIN} JA estava em credenciais.tsv; linha ${i + 1} ATUALIZADA (nao anexada). ` +
      `Se a senha antiga ainda estiver valendo no site, o cadastro local deixou de bater com ele.`);
} else {
  linhas.push(registro);
  writeFileSync(file, linhas.join('\n') + '\n');
}
try { chmodSync(file, 0o600); } catch {}
console.log(`ok: senha ${i >= 0 ? 'atualizada' : 'nova'} em credenciais.tsv e preenchida em ${n} campo(s) de ${DOMAIN}`);
