// Display audience and reader identity must stay in the same school/grade scope.
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");
const root = path.join(__dirname, "..");
const registry = JSON.parse(readFileSync(path.join(root, "sources.json"), "utf8")).sources;
const sources = registry.filter((source) => source.collection_root !== false && source.enabled !== false);

function fixture({ api = async () => ({ notices: [] }), stored = {} } = {}) {
  const nodes = new Map(), calls = [], cards = [];
  function node() {
    const classes = new Set();
    return {
      innerHTML: "", textContent: "", value: "all", children: [], dataset: {}, hidden: false,
      classList: { contains: (key) => classes.has(key), add: (...keys) => keys.forEach((key) => classes.add(key)),
        remove: (...keys) => keys.forEach((key) => classes.delete(key)), toggle: (key, on) => on ? classes.add(key) : classes.delete(key) },
      setAttribute() {}, addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
      replaceChildren() { this.children = []; this.innerHTML = ""; },
      appendChild(child) { this.children.push(child); },
      get options() { return this.children; },
      get selectedOptions() { return this.children.filter((option) => option.value === this.value); },
    };
  }
  const get = (id) => { if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id); };
  const context = vm.createContext({
    document: { getElementById: get, createElement: node, addEventListener() {},
      querySelectorAll: (selector) => selector === ".notice-card" ? cards
        : selector === ".notice-card.expanded" ? cards.filter((card) => card.classList.contains("expanded")) : [] },
    localStorage: { getItem: (key) => stored[key] || null, setItem: (key, value) => { stored[key] = value; } },
    URL, URLSearchParams, AbortController, DOMException, setTimeout, clearTimeout,
    pilotText: (key) => key, pilotApi: (url, options) => { calls.push({ url, options }); return api(url, options); },
  });
  vm.runInContext(readFileSync(path.join(root, "web/app.js"), "utf8") +
    "\nthis.app = { state, populateConfig, updateGradeOptions, changeDisplayFilter, loadNotices, selectNotice, queryString };", context);
  const app = context.app;
  app.state.config = { sources, wards: [...new Set(sources.map((source) => source.ward))], default_source_id: "sakurano", default_grade: "1年生" };
  get("source-filter").value = "sakurano";
  get("grade-filter").value = "6年生";
  return { ...app, get, calls, stored, cards, node };
}

test("every production school offers viewer grades by level, independent of collector grades", () => {
  const app = fixture();
  for (const source of sources) {
    app.get("source-filter").value = source.id;
    app.updateGradeOptions("6年生");
    const options = app.get("grade-filter").options.map((option) => option.value);
    assert.ok(options.length, source.id);
    const maximum = ["中学校", "高等学校"].includes(source.level) ? 3 : 6;
    assert.deepEqual(options, [...Array.from({ length: maximum }, (_, index) => `${index + 1}年生`), "全学年"], source.id);
    assert.ok(options.includes(app.get("grade-filter").value), source.id);
    if (["中学校", "高等学校"].includes(source.level)) assert.ok(options.every((grade) => !/[456]年生/.test(grade)), source.id);
  }
});

test("all-grade collection still supports first-grade audience on Dai1, Shibaura and Seta", async () => {
  const app = fixture();
  for (const id of ["musashino_dai1_es", "minato_shibaura_es", "setagaya_seta_jhs"]) {
    assert.deepEqual(sources.find((source) => source.id === id).grades, ["全学年"]);
    app.get("source-filter").value = id;
    app.get("grade-filter").value = "1年生";
    await app.changeDisplayFilter("source-filter");
    assert.equal(app.get("grade-filter").value, "1年生", id);
    assert.equal(new URL(app.calls.at(-1).url, "https://example.test").searchParams.get("grade"), "1年生", id);
    if (id === "setagaya_seta_jhs") assert.deepEqual(app.get("grade-filter").options.map((option) => option.value), ["1年生", "2年生", "3年生", "全学年"]);
  }
});

test("invalid persisted elementary grade is corrected before a middle-school query", () => {
  const app = fixture({ stored: { "school-news-source": "setagaya_seta_jhs", "school-news-grade": "6年生" } });
  app.populateConfig(app.state.config);
  const query = new URLSearchParams(app.queryString());
  assert.equal(query.get("source_id"), "setagaya_seta_jhs");
  assert.ok(["1年生", "2年生", "3年生", "全学年"].includes(query.get("grade")));
});

test("school selection clears conflicting level and ward before sending its query", async () => {
  const app = fixture();
  app.get("source-filter").value = "setagaya_seta_jhs";
  app.get("level-filter").value = "小学校";
  app.get("ward-filter").value = "武蔵野市";
  const push = JSON.stringify(app.state.push);
  app.get("notification-consent").checked = true;
  await app.changeDisplayFilter("source-filter");
  const query = new URL(app.calls[0].url, "https://example.test").searchParams;
  assert.equal(query.get("source_id"), "setagaya_seta_jhs");
  assert.equal(query.get("level"), null); assert.equal(query.get("ward"), null);
  assert.notEqual(query.get("grade"), "6年生");
  assert.equal(app.get("level-filter").value, "all"); assert.equal(app.get("ward-filter").value, "all");
  assert.equal(JSON.stringify(app.state.push), push);
  assert.equal(app.get("notification-consent").checked, true);
  assert.ok(app.calls.every((call) => call.url.startsWith("/api/notices?") && !call.options.method));
});

test("incompatible level or ward explicitly deselects the school in UI and request", async () => {
  for (const [field, value] of [["level-filter", "中学校"], ["ward-filter", "世田谷区"]]) {
    const app = fixture(); app.get(field).value = value;
    await app.changeDisplayFilter(field);
    assert.equal(app.get("source-filter").value, "all");
    assert.equal(new URL(app.calls[0].url, "https://example.test").searchParams.get("source_id"), "all");
    if (field === "level-filter") assert.ok(app.get("grade-filter").options.every((option) => !/[456]年生/.test(option.value)));
  }
});

test("compatible filters and source groups preserve the selected school", async () => {
  for (const [field, value] of [["level-filter", "小学校"], ["ward-filter", "武蔵野市"], ["group-filter", "after_school"]]) {
    const app = fixture(); app.get(field).value = value;
    await app.changeDisplayFilter(field);
    assert.equal(app.get("source-filter").value, "sakurano");
  }
});

test("filter load immediately removes the old desktop reader, including on list failure", async () => {
  for (const fail of [false, true]) {
    let resolve, reject;
    const app = fixture({ api: () => new Promise((yes, no) => { resolve = yes; reject = no; }) });
    app.get("detail-panel").innerHTML = "OLD SCHOOL BODY";
    app.state.selectedId = "old"; app.state.notices = [{ id: "old" }];
    const loading = app.loadNotices();
    assert.doesNotMatch(app.get("detail-panel").innerHTML, /OLD SCHOOL BODY/);
    assert.equal(app.state.selectedId, null); assert.equal(app.state.notices.length, 0);
    if (fail) reject(new Error("unavailable")); else resolve({ notices: [] });
    await loading;
    assert.doesNotMatch(app.get("detail-panel").innerHTML, /OLD SCHOOL BODY/);
  }
});

test("another card clears both readers immediately and late success or failure cannot restore them", async () => {
  for (const fail of [false, true]) {
    const pending = [];
    const app = fixture({ api: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) });
    const oldCard = app.node(), oldInline = app.node();
    oldCard.dataset.noticeId = "old"; oldCard.classList.add("expanded"); oldInline.innerHTML = "OLD INLINE";
    oldCard.querySelector = (selector) => selector === ".inline-detail" ? oldInline : null;
    app.cards.push(oldCard); app.state.selectedId = "old";
    app.get("detail-panel").innerHTML = "OLD SCHOOL BODY";
    const old = app.selectNotice("new", { showInline: false });
    assert.doesNotMatch(app.get("detail-panel").innerHTML, /OLD SCHOOL BODY/);
    assert.equal(oldInline.innerHTML, ""); assert.equal(oldCard.classList.contains("expanded"), false);
    const current = app.selectNotice("current", { showInline: false });
    const waiting = app.get("detail-panel").innerHTML;
    if (fail) pending[0].reject(new Error("stale-error")); else pending[0].resolve({ text: "stale-body" });
    await old;
    assert.equal(app.get("detail-panel").innerHTML, waiting);
    pending[1].reject(new Error("current-error")); await current;
    assert.match(app.get("detail-panel").innerHTML, /current-error/);
    assert.doesNotMatch(app.get("detail-panel").innerHTML, /OLD SCHOOL BODY|stale-body|stale-error/);
  }
});

test("same notice ID from a previous filter cannot render before the new list settles", async () => {
  for (const fail of [false, true]) {
    const pending = [];
    const app = fixture({ api: () => new Promise((resolve, reject) => pending.push({ resolve, reject })) });
    const detail = app.selectNotice("same", { showInline: false });
    app.get("source-filter").value = "setagaya_seta_jhs";
    const list = app.loadNotices();
    const placeholder = app.get("detail-panel").innerHTML;
    if (fail) pending[0].reject(new Error("stale-error")); else pending[0].resolve({ text: "stale-body" });
    await detail;
    assert.equal(app.get("detail-panel").innerHTML, placeholder);
    pending[1].resolve({ notices: [] }); await list;
  }
});

test("loading messages use the current JA KO EN ZH language", () => {
  for (const [language, message] of [["ja", "本文を読み込んでいます"], ["ko", "본문을 불러오는 중"], ["en", "Loading"], ["zh", "正在"]]) {
    const app = fixture({ api: () => new Promise(() => {}) });
    app.state.language = language; app.selectNotice("new", { showInline: false });
    assert.ok(app.get("detail-panel").innerHTML.includes(message), language);
  }
});
