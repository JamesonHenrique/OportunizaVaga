// Offline CDP fixture: no sockets or browser processes are created.
import { writeFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const scenario = JSON.parse(process.env.OV_TEST_SCENARIO);
const trace = { methods: [], actions: [], targetInfoIds: [], urlConstructorCalls: 0, closed: false };
let evaluated = false;
let currentUrl;
const record = () => writeFileSync(process.env.OV_TEST_TRACE, JSON.stringify(trace));
record();
globalThis.fetch = async (url) => {
  if (url === 'http://127.0.0.1:9222/json/version') {
    return { json: async () => ({ webSocketDebuggerUrl: 'ws://mock.invalid' }) };
  }
  if (url === 'http://127.0.0.1:9222/json/list') {
    return { json: async () => scenario.targets };
  }
  throw new Error('Unexpected network request');
};
globalThis.WebSocket = class {
  constructor(url) {
    if (url !== 'ws://mock.invalid') throw new Error('Unexpected socket');
    queueMicrotask(() => this.onopen());
  }
  send(raw) {
    const { id, method, params, sessionId } = JSON.parse(raw);
    trace.methods.push(method);
    let result = {};
    if (method === 'Target.getTargetInfo') {
      trace.targetInfoIds.push(params.targetId);
      const target = scenario.targets.find(t => t.id === params.targetId);
      const url = evaluated ? (scenario.afterEvaluateUrl || currentUrl)
        : (scenario.beforeAttachUrl || target.url);
      result = { targetInfo: { targetId: target.id, type: target.type, url } };
    } else if (method === 'Target.attachToTarget') {
      trace.targetId = params.targetId;
      result = { sessionId: 'mock-session' };
    } else if (method === 'Runtime.evaluate') {
      if (sessionId !== 'mock-session') throw new Error('Missing session');
      const listedUrl = scenario.targets.find(t => t.id === trace.targetId).url;
      let nativeUrl = new URL(scenario.liveUrl || listedUrl);
      const location = {
        get href() { return nativeUrl.href; },
        set href(value) { nativeUrl = new URL(value); },
        get protocol() { return nativeUrl.protocol; },
        get hostname() { return nativeUrl.hostname; },
        get origin() { return nativeUrl.origin; },
      };
      const pageURL = scenario.poisonURL ? class {
        constructor() {
          trace.urlConstructorCalls++;
          return new URL(listedUrl);
        }
      } : URL;
      class Input {
        constructor(visible) { this.offsetParent = visible ? {} : null; }
        set value(value) {
          trace.actions.push('set');
          trace.passwordLength = value.length;
        }
        focus() {
          trace.actions.push('focus');
          if (scenario.focusUrl) location.href = scenario.focusUrl;
        }
        dispatchEvent(event) {
          trace.actions.push(event.type);
          if (event.type === 'change' && scenario.lastEventUrl && this === fields.filter(f => f.offsetParent !== null).at(-1)) {
            location.href = scenario.lastEventUrl;
          }
        }
      }
      const fields = (scenario.visible || [true, true, false]).map(v => new Input(v));
      try {
        const value = runInNewContext(params.expression, {
          URL: pageURL, location, HTMLInputElement: Input,
          Event: class { constructor(type) { this.type = type; } },
          document: { querySelectorAll(selector) {
            trace.actions.push('query');
            trace.selector = selector;
            return fields;
          } },
        });
        result = { result: { value } };
      } catch {
        result = { exceptionDetails: { text: 'Mock evaluation failed' } };
      }
      currentUrl = location.href;
      evaluated = true;
    } else if (method !== 'Target.detachFromTarget') {
      throw new Error('Unexpected CDP method');
    }
    record();
    queueMicrotask(() => this.onmessage({ data: JSON.stringify({ id, result }) }));
  }
  close() { trace.closed = true; record(); }
};
