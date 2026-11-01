const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '../app/static/index.html'), 'utf8');
const logic = html.match(/<script id="review-logic">([\s\S]*?)<\/script>/)?.[1] || '';
const context = vm.createContext({});
vm.runInContext(logic, context);
function classify(status, body) {
  assert.equal(typeof context.classifyResponse, 'function', 'Response classification is missing');
  return JSON.parse(JSON.stringify(context.classifyResponse(status, body)));
}
function success(count = 3) {
  return {summary: 'Сводка <b>текст</b>', risks: Array.from({length: count}, (_, i) => ({
    file: `file-${i}`, line: i + 1, evidence: '  строка\n    продолжение', risk: `Риск ${i}`,
  })), checks: ['Первая', 'Вторая'], request_id: 'not-a-uuid'};
}

test('US1: accepts complete results in order, with 1–3 risks and extra fields', () => {
  for (const count of [1, 2, 3]) {
    const payload = {...success(count), extra: 'ignored'};
    assert.deepEqual(classify(200, JSON.stringify(payload)).result, payload);
  }
});

test('US1: rejects missing fields and wrong types without partial success', () => {
  const variants = [null, [], 1, 'text', {}, {...success(), risks: Array(4).fill(success().risks[0])}];
  for (const field of ['summary', 'risks', 'checks', 'request_id']) {
    const missing = success(); delete missing[field]; variants.push(missing);
    for (const value of [null, 1, {}, true]) variants.push({...success(), [field]: value});
  }
  for (const risk of [null, [], {}, ...[0, -1, 1.5, '1', true].map(line => ({...success().risks[0], line}))]) {
    variants.push({...success(), risks: [risk]});
  }
  for (const field of ['file', 'line', 'evidence', 'risk']) {
    const missing = {...success().risks[0]}; delete missing[field];
    variants.push({...success(), risks: [missing]});
    if (field !== 'line') variants.push({...success(), risks: [{...success().risks[0], [field]: 1}]});
  }
  variants.push({...success(), checks: [1]}, {...success(), checks: 'text'}, {...success(), risks: {}});
  for (const payload of variants) {
    const response = classify(200, JSON.stringify(payload));
    assert.equal(response.message, 'Некорректный ответ сервиса', JSON.stringify(payload));
    assert.equal(response.result, undefined);
    assert.equal(response.request_id, typeof payload?.request_id === 'string' ? payload.request_id : undefined);
  }
});

// Only the DOM boundary is simulated; all validation, rendering and handlers run
// from the shipped HTML. This does not simulate layout or assistive technology.
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.listeners = {};
    this.hidden = false; this.disabled = false; this.value = ''; this.text = '';
  }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return this.text + this.children.map(child => child.textContent).join(''); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.text = ''; this.children = children; }
  addEventListener(event, callback) { this.listeners[event] = callback; }
  setAttribute(name, value) { this[name] = value; }
  focus() { this.focused = true; }
  fire(event) { return this.listeners[event]?.({preventDefault() {}}); }
}
function page(fetch) {
  const elements = {};
  for (const match of html.matchAll(/<(\w+)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    elements[match[2]] = new Element(match[1]);
    elements[match[2]].hidden = /\bhidden\b/.test(match[0]);
  }
  const timers = new Map(); let clock = 0; let nextTimer = 0;
  const sandbox = vm.createContext({
    document: {
      getElementById: id => elements[id],
      createElement: tag => new Element(tag),
      createDocumentFragment: () => new Element('fragment'),
    },
    fetch, AbortController, performance: {now: () => clock},
    setTimeout: callback => { timers.set(++nextTimer, callback); return nextTimer; },
    clearTimeout: id => timers.delete(id),
  });
  for (const script of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) vm.runInContext(script[1], sandbox);
  return {elements, timers, advance(ms) { clock += ms; },
    expire() { clock = 15000; for (const callback of [...timers.values()]) callback(); },
    submit(value) {
      assert.ok(elements['review-form'], 'Review form is missing');
      if (value !== undefined) elements.diff.value = value;
      return elements['review-form'].fire('submit');
    }};
}
function response(payload = success(), status = 200) {
  return {status, text: async () => JSON.stringify(payload)};
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return {promise, resolve, reject};
}

test('US1: sends original input once, locks form, renders text safely and hides stale success', async () => {
  const pending = deferred(); const calls = [];
  const ui = page((...args) => { calls.push(args); return pending.promise; });
  const diff = '  исходный\n diff 😀  ';
  const done = ui.submit(diff);
  ui.submit();
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/api/reviews');
  assert.equal(calls[0][1].method, 'POST');
  assert.equal(calls[0][1].headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(calls[0][1].body), {diff});
  const e = ui.elements;
  assert.equal(e.diff.disabled, true);
  assert.equal(e.submit.disabled, true);
  assert.equal(e.submit.textContent, 'Проверяем…');
  assert.equal(e.status.textContent, 'Проверяем изменения…');
  pending.resolve(response()); await done;
  assert.equal(e.diff.disabled, false); assert.equal(e.submit.disabled, false);
  assert.equal(e.diff.value, diff); assert.equal(e.result.hidden, false);
  assert.equal(e.error.textContent, '');
  assert.match(e.result.textContent, /СводкаСводка <b>текст<\/b>Риски/);
  assert.match(e.result.textContent, /Файлfile-0Строка1Фрагмент  строка\n    продолжениеРискРиск 0/);
  assert.match(e.result.textContent, /ПроверкиПерваяВторая/);
  assert.equal(e.status.textContent, 'Проверка завершена');
  assert.equal(ui.timers.size, 0);
  const walk = node => [node, ...node.children.flatMap(walk)];
  assert.ok(walk(e.result).some(node => node.tagName === 'pre'));
  assert.ok(!walk(e.result).some(node => node.tagName === 'b'));
  e.diff.fire('input');
  assert.equal(e.result.hidden, true); assert.equal(e.status.textContent, '');
});

test('US2: empty lists and empty strings are valid success, with explicit empty states', async () => {
  for (const [risks, checks] of [[[], ['check']], [success(1).risks, []], [[], []]]) {
    const payload = {summary: '', risks, checks, request_id: ''};
    assert.deepEqual(classify(200, JSON.stringify(payload)), {result: payload});
    const ui = page(async () => response(payload));
    await ui.submit('diff');
    assert.equal(ui.elements.result.hidden, false);
    assert.equal(ui.elements.error.textContent, '');
    if (!risks.length) assert.match(ui.elements.result.textContent, /Риски не найдены/);
    if (!checks.length) assert.match(ui.elements.result.textContent, /Список проверок пуст/);
  }
  const payload = {summary: '', risks: [{file: '', line: 1, evidence: '', risk: ''}], checks: [''], request_id: ''};
  assert.deepEqual(classify(200, JSON.stringify(payload)), {result: payload});
});

const apiErrors = [
  [422, 'invalid_request', 'Не удалось проверить diff. Проверьте введённые изменения и повторите попытку'],
  [413, 'diff_too_large', 'Diff слишком большой. Максимум — 20 000 символов. Уменьшите diff и повторите попытку'],
  [504, 'llm_timeout', 'Проверка заняла слишком много времени. Повторите попытку'],
  [502, 'llm_failed', 'Не удалось выполнить проверку. Повторите попытку позже'],
];
test('US3: only exact HTTP/code pairs select special errors, preserving string request_id', () => {
  for (const [status, code, message] of apiErrors) {
    assert.deepEqual(classify(status, JSON.stringify({error: {code}, request_id: '<id>'})), {message, request_id: '<id>'});
    for (const other of [200, 201, 400, 500, ...apiErrors.map(row => row[0]).filter(s => s !== status)]) {
      assert.deepEqual(classify(other, JSON.stringify({error: {code}, request_id: ''})), {
        message: other === 200 ? 'Некорректный ответ сервиса' : 'Сервис недоступен', request_id: '',
      });
    }
  }
  for (const error of [null, [], 'text', {}, {code: 502}, {code: 'unknown'}]) {
    assert.deepEqual(classify(502, JSON.stringify({error, request_id: 'id'})), {message: 'Сервис недоступен', request_id: 'id'});
  }
  for (const body of ['<html>failure</html>', '', '{']) {
    for (const status of [200, 502]) assert.deepEqual(classify(status, body), {message: 'Сервис недоступен'});
  }
  for (const payload of [null, [], false, {error: {code: 'llm_failed'}, request_id: 123}]) {
    assert.equal(classify(502, JSON.stringify(payload)).request_id, undefined);
  }
});

test('US3: whitespace never fetches and returns focus; errors survive edits but clear on retry', async () => {
  let calls = 0;
  const pending = deferred();
  const ui = page(() => { calls++; return pending.promise; });
  for (const blank of ['', ' \n\t\r ', '\u00a0']) {
    await ui.submit(blank);
    assert.equal(calls, 0); assert.equal(ui.elements.diff.focused, true);
    assert.equal(ui.elements.error.textContent, 'Вставьте diff для проверки');
    ui.elements.diff.fire('input');
    assert.equal(ui.elements.error.textContent, 'Вставьте diff для проверки');
  }
  const done = ui.submit('исправленный diff');
  assert.equal(ui.elements.error.textContent, '');
  pending.resolve(response({error: {code: 'llm_failed'}, request_id: '<img src=x>'}, 502));
  await done;
  assert.equal(ui.elements.error.textContent, apiErrors[3][2] + 'request_id: <img src=x>');
  assert.equal(ui.elements.diff.disabled, false);
  assert.equal(ui.elements.diff.value, 'исправленный diff');
  ui.elements.diff.fire('input');
  assert.match(ui.elements.error.textContent, /request_id: <img src=x>/);
});

test('US3: network, non-JSON and malformed success unlock the form without raw errors', async () => {
  for (const fetch of [
    async () => { throw new Error('private detail'); },
    async () => ({status: 200, text: async () => 'private detail'}),
    async () => ({status: 502, text: async () => { throw new Error('body failed'); }}),
    async () => response({summary: 'partial', request_id: 'trace'}),
  ]) {
    const ui = page(fetch); await ui.submit('diff');
    assert.equal(ui.elements.diff.disabled, false); assert.equal(ui.elements.submit.disabled, false);
    assert.equal(ui.elements.result.hidden, true);
    assert.match(ui.elements.error.textContent, /Сервис недоступен|Некорректный ответ сервиса/);
    assert.doesNotMatch(ui.elements.error.textContent, /private detail|body failed|partial/);
    assert.equal(ui.timers.size, 0);
  }
});

test('US3: timeout covers headers and body; late resolves/rejections cannot touch a newer attempt', async () => {
  for (const phase of ['headers', 'body', 'reject']) {
    const old = deferred(); const fresh = deferred(); let calls = 0; let signal;
    const ui = page((url, options) => {
      calls++; signal = options.signal;
      if (calls > 1) return fresh.promise;
      return phase === 'body' ? Promise.resolve({status: 200, text: () => old.promise}) : old.promise;
    });
    const first = ui.submit('old');
    await Promise.resolve();
    assert.equal(ui.timers.size, 1);
    ui.expire();
    assert.equal(ui.elements.error.textContent, 'Сервис не ответил вовремя');
    assert.equal(signal.aborted, true);
    assert.equal(ui.elements.diff.disabled, false); assert.equal(ui.timers.size, 0);
    const second = ui.submit('new');
    if (phase === 'reject') old.reject(new Error('late failure'));
    else old.resolve(phase === 'body' ? JSON.stringify(success()) : response());
    await first;
    assert.equal(ui.elements.diff.disabled, true);
    assert.equal(ui.elements.status.textContent, 'Проверяем изменения…');
    assert.equal(ui.elements.error.textContent, '');
    const payload = {...success(1), summary: 'Новая сводка'};
    fresh.resolve(response(payload)); await second;
    assert.match(ui.elements.result.textContent, /Новая сводка/);
    assert.equal(ui.elements.error.textContent, ''); assert.equal(ui.timers.size, 0);
  }
});

test('US3: absolute deadline wins even when the timer callback is delayed', async () => {
  for (const phase of ['headers', 'body', 'parse', 'render']) {
    let ui;
    ui = page(async () => {
      if (phase === 'headers') ui.advance(15000);
      return {status: 200, text: async () => {
        if (phase === 'body') ui.advance(15000);
        return JSON.stringify(success());
      }};
    });
    if (phase === 'parse' || phase === 'render') {
      // Advance the monotonic clock during synchronous work, without firing timers.
      if (phase === 'render') {
        const original = Element.prototype.append;
        Element.prototype.append = function (...children) { ui.advance(15000); return original.apply(this, children); };
        try { await ui.submit('diff'); } finally { Element.prototype.append = original; }
      } else {
        // Body coercion is part of JSON.parse, so this crosses the deadline inside parsing.
        ui = page(async () => ({status: 200, text: async () => ({toString() {
          ui.advance(15000); return JSON.stringify(success());
        }})}));
        await ui.submit('diff');
      }
    } else await ui.submit('diff');
    assert.equal(ui.elements.error.textContent.startsWith('Сервис не ответил вовремя'), true, phase);
    assert.equal(ui.elements.result.hidden, true);
    assert.equal(ui.elements.diff.disabled, false); assert.equal(ui.timers.size, 0);
  }
});

test('US3: just-before-deadline succeeds and late old completion preserves new success', async () => {
  const old = deferred(); let calls = 0;
  const ui = page(async () => ++calls === 1 ? old.promise : response({...success(0), summary: 'Новое'}));
  const first = ui.submit('old'); ui.expire();
  await ui.submit('new');
  old.resolve(response({...success(), request_id: 'late-id'})); await first;
  assert.match(ui.elements.result.textContent, /Новое/);
  assert.equal(ui.elements.error.textContent, ''); assert.equal(ui.elements.diff.disabled, false);
  const near = page(async () => { near.advance(14999); return response(); });
  await near.submit('diff');
  assert.equal(near.elements.result.hidden, false); assert.equal(near.timers.size, 0);
});
