// Pure helpers: importing this module never connects to Chrome or reads credentials.
export function parseHostname(input) {
  // Accept DNS labels (including ASCII IDN/punycode) and canonical IPv4 only.
  // Reject URL syntax, whitespace, trailing dots and URL parser shorthand.
  if (typeof input !== 'string' || input.length > 253 ||
      !input.split('.').every(label => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label))) {
    throw new Error('erro: informe somente um hostname valido, sem URL ou porta');
  }
  const hostname = input.toLowerCase();
  if (new URL(`https://${hostname}`).hostname !== hostname) {
    throw new Error('erro: hostname ambiguo');
  }
  return hostname;
}

// Self-contained so the exact same predicate can run inside the attached page.
export function matchesHostname(url, hostname) {
  try {
    if (typeof url !== 'string' || /[\s\\]/.test(url)) return false;
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && parsed.hostname === hostname &&
      parsed.port === '' && parsed.username === '' && parsed.password === '';
  } catch {
    return false;
  }
}

export function selectPasswordTarget(targets, input) {
  const hostname = parseHostname(input);
  if (!Array.isArray(targets)) throw new Error('erro: lista de abas invalida');
  const pages = targets.filter(target => target?.type === 'page' && matchesHostname(target.url, hostname));
  if (pages.length !== 1) throw new Error('erro: esperada exatamente uma aba HTTPS com o hostname solicitado');
  return pages[0];
}

export function buildFillExpression(hostname, selector, password) {
  const escaped = hostname.replace(/\./g, '\\.');
  const hrefPattern = `^https:\\/\\/${escaped}(?::443)?(?:[/?#]|$)`;
  return `(() => {
    // Use native Location properties when present (never call page-global URL, which a page can override).
    const safe = () => {
      if (typeof location.origin === 'string') {
        return location.protocol === 'https:'
          && location.hostname === ${JSON.stringify(hostname)}
          && location.origin === ${JSON.stringify(`https://${hostname}`)};
      }
      return typeof location.href === 'string' && !/[\\s\\\\]/.test(location.href)
        && new RegExp(${JSON.stringify(hrefPattern)}, 'i').test(location.href);
    };
    if (!safe()) return 0;
    const els = [...document.querySelectorAll(${JSON.stringify(selector)})].filter(e => e.offsetParent !== null);
    if (!els.length || !safe()) return 0;
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    for (const e of els) {
      e.focus();
      if (!safe()) return 0;
      set.call(e, ${JSON.stringify(password)});
      e.dispatchEvent(new Event('input', { bubbles: true }));
      e.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return safe() && els.every(e => e.value === ${JSON.stringify(password)}) ? els.length : 0;
  })()`;
}
