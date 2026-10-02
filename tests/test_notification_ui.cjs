const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const web = path.join(__dirname, "../web");

function appFixture({ result = { provider_accepted: true, delivery_confirmed: false }, subscription = { endpoint: "https://fcm.googleapis.com/mock" }, failure = false, workerSupport = true } = {}) {
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, { textContent: "", value: "all", dataset: {}, querySelector: () => null });
    return elements.get(id);
  };
  const calls = [], statuses = [];
  class FakeChannel {
    constructor() {
      this.port1 = { close() {}, onmessage: null };
      this.port2 = { close() {}, postMessage: (data) => this.port1.onmessage({ data }) };
    }
  }
  const context = vm.createContext({
    document: { addEventListener() {}, getElementById: get, querySelectorAll: () => [] },
    localStorage: { getItem: () => null }, URL, URLSearchParams, setTimeout, clearTimeout, MessageChannel: FakeChannel,
    location: { origin: "https://test.example" }, navigator: { serviceWorker: {} },
    pilotText: (key) => key, pilotStatus: (id, key) => statuses.push(key),
    pilotApi: async (url, options) => { calls.push({ url, options }); if (failure) throw new Error("failure"); return result; },
  });
  vm.runInContext(readFileSync(path.join(web, "app.js"), "utf8") + "\nthis.app = { state, testPushNotification, updatePushControls };", context);
  const app = context.app;
  Object.assign(app.state.push, { ready: true, subscribed: true, scopesKnown: true, registration: {
    active: { scriptURL: "https://test.example/sw.js", state: "activated", postMessage: (data, ports) => ports[0].postMessage({ test_notification: workerSupport }) }, pushManager: { getSubscription: async () => subscription },
  } });
  app.state.config = { sources: [] };
  return { ...app, calls, statuses, get };
}

test("self-test only posts the current endpoint and does not claim actual arrival", async () => {
  const app = appFixture();
  await app.testPushNotification();
  assert.equal(app.calls.length, 1);
  assert.equal(app.calls[0].url, "/api/push/test");
  assert.deepEqual(JSON.parse(app.calls[0].options.body), { endpoint: "https://fcm.googleapis.com/mock" });
  assert.deepEqual(app.statuses, ["testSending", "testAccepted"]);
  assert.equal(app.state.push.busy, false);
});

test("self-test is unavailable without existing consented subscription and enabled delivery", async () => {
  for (const field of ["ready", "subscribed"]) {
    const app = appFixture();
    app.state.push[field] = false;
    app.updatePushControls();
    assert.equal(app.get("notification-test").disabled, true);
    await app.testPushNotification();
    assert.equal(app.calls.length, 0);
  }
});

test("self-test failures, missing subscription and false acceptance show no success", async () => {
  for (const options of [{ failure: true }, { subscription: null }, { result: { provider_accepted: false } }, { workerSupport: false }]) {
    const app = appFixture(options);
    await app.testPushNotification();
    assert.equal(app.statuses.at(-1), "testError");
    assert.equal(app.state.push.busy, false);
    assert.equal(app.state.push.subscribed, true);
    if (options.workerSupport === false) assert.equal(app.calls.length, 0);
  }
});

test("service worker uses a distinct generic test notification and safe destination", async () => {
  const handlers = {}, shown = [];
  const context = vm.createContext({ URL, self: {
    location: { origin: "https://test.example" },
    addEventListener: (name, handler) => { handlers[name] = handler; },
    registration: { showNotification: async (title, options) => shown.push({ title, options }) },
  } });
  vm.runInContext(readFileSync(path.join(web, "sw.js"), "utf8"), context);
  let capabilities;
  handlers.message({ data: { type: "otayori-push-capabilities" }, ports: [{ postMessage: (value) => { capabilities = value; } }] });
  assert.equal(capabilities.test_notification, true);
  for (const type of ["test", "update"]) {
    let complete;
    handlers.push({ data: { json: () => ({ type, body: "PRIVATE", url: "https://evil.example" }) }, waitUntil: (promise) => { complete = promise; } });
    await complete;
  }
  assert.equal(shown[0].options.tag, "otayori-desk-test");
  assert.match(shown[0].options.body, /テスト通知/);
  assert.equal(shown[1].options.tag, "otayori-desk-update");
  assert.doesNotMatch(shown[1].options.body, /PRIVATE/);
  assert.equal(shown[0].options.data.url, "https://test.example/");
});
