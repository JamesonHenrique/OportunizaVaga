import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const helper = fileURLToPath(new URL('../bot/nova-senha.mjs', import.meta.url));
const mock = fileURLToPath(new URL('./fixtures/nova-senha/cdp-mock.mjs', import.meta.url));
const host = 'careers.example.com';
const page = (url, id = 'page-1', type = 'page') => ({ url, id, type });

function run(t, scenario, { domain = host, selector, initial } = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'ov-password-test-'));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const credentials = join(dir, 'credentials.tsv');
  const traceFile = join(dir, 'trace.json');
  if (initial !== undefined) writeFileSync(credentials, initial);
  const child = spawnSync(process.execPath, [
    '--import', mock, helper, domain, 'user@example.com', ...(selector ? [selector] : []),
  ], {
    env: {
      OV_CREDENTIALS_FILE: credentials, OV_TEST_TRACE: traceFile,
      OV_TEST_SCENARIO: JSON.stringify(scenario),
    }, encoding: 'utf8', timeout: 5000,
  });
  assert.ifError(child.error);
  assert.equal(child.stderr, '');
  const contents = existsSync(credentials) ? readFileSync(credentials, 'utf8') : null;
  if (contents) {
    for (const row of contents.trim().split('\n')) {
      assert.ok(!child.stdout.includes(row.split('\t')[2]), 'password must stay out of stdout');
    }
  }
  return { ...child, contents, credentials, trace: JSON.parse(readFileSync(traceFile, 'utf8')) };
}

for (const url of [
  'https://careers.example.com.evil.test/signup',
  'https://evilcareers.example.com/signup',
  'https://sub.careers.example.com/signup',
  'https://evil.test/careers.example.com',
  'https://evil.test/?next=https://careers.example.com',
  'https://evil.test/#careers.example.com',
  'https://careers.example.com@evil.test/signup',
  'https://user:pass@careers.example.com/signup',
  'https://careers.example.com:8443/signup',
  'http://careers.example.com/signup',
  'not a URL careers.example.com',
]) {
  test(`rejects misleading or insecure URL: ${url}`, t => {
    const r = run(t, { targets: [page(url)] });
    assert.equal(r.status, 1);
    assert.match(r.stdout, /nenhuma aba HTTPS.*hostname exato/);
    assert.equal(r.contents, null);
    assert.deepEqual(r.trace.methods, []);
    assert.deepEqual(r.trace.actions, []);
  });
}

test('rejects ambiguous matching tabs before attaching or writing', t => {
  const r = run(t, { targets: [page(`https://${host}/one`), page(`https://${host}/two`, 'page-2')] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /selecao ambigua/);
  assert.equal(r.contents, null);
  assert.deepEqual(r.trace.methods, []);
});

for (const beforeAttachUrl of ['https://evil.test/', `http://${host}/`, `https://sub.${host}/`, `https://${host}:8443/`]) {
  test(`rechecks target origin immediately before attach: ${beforeAttachUrl}`, t => {
    const initial = `${host}\tuser@example.com\tsynthetic-old-value\n`;
    const r = run(t, { targets: [page(`https://${host}/`)], beforeAttachUrl }, { initial });
    assert.equal(r.status, 1);
    assert.match(r.stdout, /aba mudou de origem/);
    assert.doesNotMatch(r.stdout, /ok: senha/);
    assert.equal(r.contents, initial);
    assert.deepEqual(r.trace.methods, ['Target.getTargetInfo']);
    assert.deepEqual(r.trace.targetInfoIds, ['page-1']);
    assert.deepEqual(r.trace.actions, []);
    assert.equal(r.trace.closed, true);
  });
}

for (const liveUrl of ['https://evil.test/', `http://${host}/`, `https://sub.${host}/`, `https://${host}:8443/`]) {
  test(`rechecks live origin before querying fields: ${liveUrl}`, t => {
    const initial = `${host}\tuser@example.com\tsynthetic-old-value\n`;
    const r = run(t, { targets: [page(`https://${host}/`)], liveUrl }, { initial });
    assert.equal(r.status, 1);
    assert.match(r.stdout, /aba mudou de origem/);
    assert.equal(r.contents, initial);
    assert.deepEqual(r.trace.actions, []);
    assert.equal(r.trace.closed, true);
    assert.ok(r.trace.methods.includes('Target.detachFromTarget'));
  });
}

test('rejects malicious origin even when the page URL constructor forges the expected origin', t => {
  const initial = `${host}\tuser@example.com\tsynthetic-old-value\n`;
  const r = run(t, {
    targets: [page(`https://${host}/`)], liveUrl: 'https://evil.test/', poisonURL: true,
  }, { initial });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /aba mudou de origem/);
  assert.doesNotMatch(r.stdout, /ok: senha/);
  assert.equal(r.contents, initial);
  assert.deepEqual(r.trace.actions, []);
  assert.equal(r.trace.urlConstructorCalls, 0);
  assert.equal(r.trace.closed, true);
  assert.deepEqual(r.trace.methods, [
    'Target.getTargetInfo', 'Target.attachToTarget', 'Runtime.evaluate', 'Target.detachFromTarget',
  ]);
});

test('rechecks origin after focus handlers and before setting a password', t => {
  const r = run(t, { targets: [page(`https://${host}/`)], focusUrl: 'https://evil.test/' });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /aba mudou de origem/);
  assert.deepEqual(r.trace.actions, ['query', 'focus']);
  assert.equal(r.contents, null);
});

for (const phase of ['lastEventUrl', 'afterEvaluateUrl']) {
  for (const url of ['https://evil.test/', `http://${host}/`, `https://${host}:8443/`]) {
    test(`rejects origin change at ${phase}: ${url} and preserves credentials`, t => {
      const initial = `${host}\tuser@example.com\tsynthetic-old-value\n`;
      const r = run(t, { targets: [page(`https://${host}/`)], [phase]: url }, { initial });
      assert.equal(r.status, 1);
      assert.match(r.stdout, /aba mudou de origem/);
      assert.doesNotMatch(r.stdout, /ok: senha/);
      assert.equal(r.contents, initial);
      assert.deepEqual(r.trace.actions, ['query', 'focus', 'set', 'input', 'change', 'focus', 'set', 'input', 'change']);
      assert.equal(r.trace.closed, true);
      assert.ok(r.trace.methods.includes('Target.detachFromTarget'));
      if (phase === 'afterEvaluateUrl') {
        assert.deepEqual(r.trace.methods, [
          'Target.getTargetInfo', 'Target.attachToTarget', 'Runtime.evaluate',
          'Target.detachFromTarget', 'Target.getTargetInfo',
        ]);
        assert.deepEqual(r.trace.targetInfoIds, ['page-1', 'page-1']);
      }
    });
  }
}

test('fills visible fields only on the unique exact HTTPS host, preserving custom selector', t => {
  const r = run(t, { targets: [
    page('https://evil.test/?next=' + host, 'decoy'),
    page(`https://${host}/worker`, 'worker', 'service_worker'),
    page(`https://${host.toUpperCase()}/signup`, 'legitimate'),
  ], liveUrl: `https://${host}/signup/step-two` }, { selector: '#password, #confirmation' });
  assert.equal(r.status, 0);
  assert.match(r.stdout, /preenchida em 2 campo/);
  assert.equal(r.trace.targetId, 'legitimate');
  assert.equal(r.trace.selector, '#password, #confirmation');
  assert.deepEqual(r.trace.actions, ['query', 'focus', 'set', 'input', 'change', 'focus', 'set', 'input', 'change']);
  assert.ok(r.trace.passwordLength >= 21);
  assert.ok(r.contents.startsWith(`${host}\tuser@example.com\t`));
  if (process.platform !== 'win32') assert.equal(statSync(r.credentials).mode & 0o777, 0o600);
  assert.equal(r.trace.closed, true);
  assert.deepEqual(r.trace.methods, [
    'Target.getTargetInfo', 'Target.attachToTarget', 'Runtime.evaluate',
    'Target.detachFromTarget', 'Target.getTargetInfo',
  ]);
  assert.deepEqual(r.trace.targetInfoIds, ['legitimate', 'legitimate']);
});

test('keeps credential deduplication and unrelated rows', t => {
  const initial = `other.example\tother@example.com\tsynthetic-other\n${host}\tuser@example.com\tsynthetic-old\n${host}\tuser@example.com\tsynthetic-duplicate\n`;
  const r = run(t, { targets: [page(`https://${host}/`)] }, { domain: host.toUpperCase(), initial });
  assert.equal(r.status, 0);
  assert.match(r.stdout, /colapsadas em 1/);
  const rows = r.contents.trim().split('\n');
  assert.equal(rows.length, 2);
  assert.ok(rows[0] === initial.split('\n')[0]);
  assert.ok(rows[1].startsWith(`${host}\tuser@example.com\t`));
});

test('does not save credentials when there are no visible fields', t => {
  const r = run(t, { targets: [page(`https://${host}/`)], visible: [false] });
  assert.equal(r.status, 1);
  assert.match(r.stdout, /nenhum campo visivel/);
  assert.equal(r.trace.selector, 'input[type=password]');
  assert.equal(r.contents, null);
});

for (const domain of [`https://${host}`, `${host}/path`, `${host}:443`, `${host}@evil.test`, `${host}.`]) {
  test(`rejects a hostname argument containing URL components: ${domain}`, t => {
    const r = run(t, { targets: [] }, { domain });
    assert.equal(r.status, 2);
    assert.match(r.stdout, /somente o hostname/);
    assert.equal(r.contents, null);
    assert.deepEqual(r.trace.methods, []);
  });
}
