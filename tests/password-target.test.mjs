import assert from 'node:assert/strict';
import test from 'node:test';
import { runInNewContext } from 'node:vm';
import { buildFillExpression, matchesHostname, parseHostname, selectPasswordTarget } from '../bot/password-target.mjs';

const hostname = 'jobs.example';
const page = (url, id = '1') => ({ type: 'page', url, id });

test('normalizes case and accepts explicit subdomains and punycode', () => {
  assert.equal(parseHostname('JOBS.Example'), hostname);
  assert.equal(parseHostname('company.jobs.example'), 'company.jobs.example');
  assert.equal(parseHostname('xn--bcher-kva.example'), 'xn--bcher-kva.example');
});

for (const input of ['', undefined, 'https://jobs.example', 'jobs.example/apply',
  'jobs.example?q=1', 'jobs.example#x', 'user@jobs.example', 'jobs.example:443',
  'jobs.example:8443', ' jobs.example', 'jobs.example\n', 'jobs.example.',
  'jobs..example', '-jobs.example', 'jobs_.example', 'jobs.example\\evil',
  '%6aobs.example', '127.1', '0x7f000001', 'a'.repeat(64) + '.example']) {
  test(`rejects ambiguous or invalid hostname ${JSON.stringify(input)}`, () => {
    assert.throws(() => parseHostname(input));
  });
}

for (const url of ['https://evil.example/jobs.example', 'https://evil.example/?next=https://jobs.example',
  'https://jobs.example.evil.example', 'https://fakejobs.example', 'http://jobs.example',
  'https://company.jobs.example', 'https://jobs.example:8443', 'https://jobs.example.',
  'https://user@jobs.example', 'https://jobs.example@evil.example', 'not a URL',
  'https://jobs.example\\@evil.example', 'https://jobs.exa\nmple']) {
  test(`rejects ineligible URL ${JSON.stringify(url)}`, () => {
    assert.equal(matchesHostname(url, hostname), false);
    assert.throws(() => selectPasswordTarget([page(url)], hostname));
  });
}

test('selects exactly one HTTPS page, ignoring unrelated targets', () => {
  const selected = page('https://JOBS.example:443/apply?step=2');
  assert.equal(selectPasswordTarget([
    page('http://jobs.example'), { type: 'service_worker', url: 'https://jobs.example' }, selected,
  ], 'JOBS.EXAMPLE'), selected);
  assert.equal(selectPasswordTarget([page('https://company.jobs.example')], 'company.jobs.example').id, '1');
});

test('fails closed for zero, two, malformed lists and invalid input even with a matching URL', () => {
  for (const targets of [[], [page('https://jobs.example'), page('https://jobs.example/apply', '2')], null]) {
    assert.throws(() => selectPasswordTarget(targets, hostname));
  }
  assert.throws(() => selectPasswordTarget([page('https://jobs.example')], 'https://jobs.example'));
});

// Synthetic page only: no browser, CDP, filesystem, real helper or credentials.
function evaluateFill(url, { onFocus = () => {}, keepValue = true, visible = true } = {}) {
  let writes = 0;
  const location = { href: url };
  class Input {
    offsetParent = visible ? {} : null;
    get value() { return this.current; }
    set value(value) { writes++; if (keepValue) this.current = value; }
    focus() { onFocus(location); }
    dispatchEvent() {}
  }
  const input = new Input();
  const result = runInNewContext(buildFillExpression(hostname, 'input[type=password]', 'synthetic-value'), {
    URL, location, document: { querySelectorAll: () => [input] }, HTMLInputElement: Input, Event: class {},
  });
  return { result, writes };
}

test('confirms filling by count without returning the password', () => {
  assert.deepEqual(evaluateFill('https://jobs.example/apply'), { result: 1, writes: 1 });
  assert.deepEqual(evaluateFill('https://jobs.example', { visible: false }), { result: 0, writes: 0 });
  assert.deepEqual(evaluateFill('https://jobs.example', { keepValue: false }), { result: 0, writes: 1 });
});

test('origin changes after selection or attach prevent injection', () => {
  const selected = selectPasswordTarget([page('https://jobs.example')], hostname);
  assert.equal(matchesHostname(selected.url, hostname), true);
  for (const changed of ['http://jobs.example', 'https://evil.example', 'https://sub.jobs.example', 'https://jobs.example:8443']) {
    // Same predicate as the post-attach check, then the actual injected expression.
    assert.equal(matchesHostname(changed, hostname), false);
    assert.deepEqual(evaluateFill(changed), { result: 0, writes: 0 });
    assert.deepEqual(evaluateFill(selected.url, { onFocus: location => { location.href = changed; } }),
      { result: 0, writes: 0 });
  }
});
