const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

const web = path.join(__dirname, "../web");
const script = readFileSync(path.join(web, "app.js"), "utf8");
const notice = (id, fields = {}) => ({
  id, source_id: "school", source_name: "桜野小学校", title: id,
  ward: "武蔵野市", level: "小学校", grade: "1年生", kind_label: "学校だより",
  url: `https://school.example/${id}`, feed_group: "notices", date_kind: "published",
  date_label: "2026/10/01", published_label: "2026/10/01", ...fields,
});
const event = (id, date, fields = {}) => notice(id, {
  feed_group: "events", date_kind: "event", date_label: date, event_date: date, published_label: "", ...fields,
});

function frontend({ api, timers } = {}) {
  const elements = new Map();
  const element = () => ({
    innerHTML: "", textContent: "", hidden: false, value: "all",
    attributes: {}, querySelector: () => null, querySelectorAll: () => [],
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren() { this.innerHTML = ""; },
  });
  const document = {
    addEventListener() {}, querySelectorAll: () => [],
    getElementById(id) { if (!elements.has(id)) elements.set(id, element()); return elements.get(id); },
  };
  class FixedDate extends Date {
    constructor(...args) { super(...(args.length ? args : ["2026-09-30T15:30:00Z"])); }
  }
  const context = vm.createContext({
    document, localStorage: { getItem: () => null }, URL, URLSearchParams, Date: FixedDate, AbortController, DOMException,
    setTimeout: timers?.setTimeout || setTimeout, clearTimeout: timers?.clearTimeout || clearTimeout,
    pilotApi: api || (async () => notice("detail", { text: "日本語の本文" })),
  });
  vm.runInContext(`${script}\nthis.frontend = { state, I18N, t, noticeSections, noticeDateText, renderNoticeCard, detailMarkup, renderNotices, renderCoverage, coverageStatus, selectNotice, officialLink, japanToday, formatScanTime, loadNotices };`, context);
  return { ...context.frontend, document, get: (id) => document.getElementById(id) };
}
const ids = (items) => Array.from(items, (item) => item.id);
const flush = () => new Promise(setImmediate);

function fakeTimers() {
  let now = 0;
  let nextId = 0;
  const pending = new Map();
  return {
    setTimeout(callback, delay) { const id = ++nextId; pending.set(id, { callback, due: now + delay }); return id; },
    clearTimeout(id) { pending.delete(id); },
    get size() { return pending.size; },
    async advance(milliseconds) {
      const target = now + milliseconds;
      for (;;) {
        const next = [...pending].sort((a, b) => a[1].due - b[1].due)[0];
        if (!next || next[1].due > target) break;
        now = next[1].due;
        pending.delete(next[0]);
        next[1].callback();
        await flush();
      }
      now = target;
      await flush();
    },
  };
}

function pollingFrontend(respond) {
  const timers = fakeTimers();
  const calls = [];
  let detailCalls = 0;
  const app = frontend({ timers, api: (url, options = {}) => {
    if (url.startsWith("/api/notices/")) { detailCalls++; return Promise.resolve(notice("detail")); }
    calls.push({ url, options });
    return respond(calls.length, url, options);
  } });
  return { ...app, timers, calls, get detailCalls() { return detailCalls; } };
}

test("events keep October before November, include today, and archive only elapsed dates", () => {
  const app = frontend();
  assert.equal(app.japanToday(), "2026-10-01");
  const sections = app.noticeSections([
    event("november", "2026/11/03"), event("october", "2026/10/12"),
    event("past", "2026/09/30"), event("today", "2026/10/01"),
    event("closed-registration", "2026/10/08", { deadline_date: "2026/09/25" }),
    event("next-year", "2027/01/10"),
    event("deadline-only", "", { deadline_date: "2026/10/05" }),
    event("publication-only", "", { date_kind: "published", date_label: "2026/09/01", published_label: "2026/09/01" }),
  ], "events");
  assert.deepEqual(ids(sections.active[0].items), ["today", "deadline-only", "closed-registration", "october", "november", "next-year"]);
  assert.deepEqual(ids(sections.archive[0].items), ["past"]);
  assert.deepEqual(ids(sections.undated), ["publication-only"]);
});

test("school issue months retain the latest/archive split; undated items stay visible", () => {
  const app = frontend();
  const sections = app.noticeSections([
    notice("september", { date_label: "2026/09/18", published_label: "2026/09/18", title: "10月の行事予定" }),
    notice("october-issue", { date_kind: "issue", date_label: "2026/10月号", published_label: "2026/09/18" }),
    notice("unknown", { date_kind: "unknown", date_label: "更新資料", published_label: "" }),
    notice("stale-date", { date_kind: "unknown", date_label: "2026/08/01", published_label: "" }),
  ]);
  assert.deepEqual(ids(sections.active[0].items), ["october-issue"]);
  assert.deepEqual(ids(sections.archive[0].items), ["september"]);
  assert.deepEqual(ids(sections.undated), ["unknown", "stale-date"]);
  assert.equal(app.noticeDateText(sections.active[0].items[0]), "2026年10月号 · 掲載 2026年9月18日");
});

test("reference and static cards are collapsed, excluded from counts, and never auto-selected", () => {
  const app = frontend();
  app.state.config = { sources: [{ id: "static", mode: "static" }, { id: "reference", coverage_kind: "reference" }] };
  app.renderNotices({ notices: [
    notice("facility", { coverage_kind: "reference" }),
    notice("static-card", { source_id: "static", coverage_kind: "notices" }),
    notice("config-reference", { source_id: "reference" }),
  ], notice_count: 3, coverage: [] });
  const html = app.get("notice-list").innerHTML;
  assert.match(html, /<details class="archive-group reference-group"><summary>/);
  assert.match(html, /施設案内（連絡帳ではありません）/);
  assert.doesNotMatch(html, /latest-section|<details[^>]*\bopen\b/);
  assert.match(html, /https:\/\/school.example\/facility/);
  assert.equal(app.get("metric-notices").textContent, 0);
  assert.equal(app.state.selectedId, null);
  assert.equal(app.get("empty-state").hidden, true);
});

test("event rendering selects the nearest date and leaves undated cards outside archives", () => {
  const app = frontend();
  app.state.feed = "events";
  app.renderNotices({ notices: [event("nov", "2026/11/05"), event("oct", "2026/10/07"), event("past", "2026/09/01"), event("unknown", "", { date_kind: "unknown" })] });
  const html = app.get("notice-list").innerHTML;
  assert.ok(html.indexOf('data-notice-id="oct"') < html.indexOf('data-notice-id="nov"'));
  assert.ok(html.indexOf('data-notice-id="unknown"') < html.indexOf('<details class="archive-group">'));
  assert.match(html, /日付未確認/);
  assert.equal(app.state.selectedId, "oct");
});

test("date roles do not invent publication dates, including undated and invalid values", () => {
  const app = frontend();
  const item = event("event", "2026/10/12", { deadline_date: "2026/10/05" });
  assert.equal(app.noticeDateText(item), "開催 2026年10月12日 · 締切 2026年10月5日");
  assert.doesNotMatch(app.detailMarkup(item), /掲載/);
  assert.equal(app.noticeDateText(notice("unknown", { date_kind: "unknown", published_label: "2026/09/01" })), "日付未確認");
  assert.match(app.noticeDateText(event("invalid", "2026/02/30")), /開催 日付未確認/);
  assert.equal(app.formatScanTime("not-a-date"), "—");
});

test("mixed root pages stay undated despite preserved CMS update metadata", () => {
  const app = frontend();
  app.renderNotices({ notices: [notice("図書館だより・読書旬間", {
    date_kind: "unknown", date_label: "更新資料", published_label: "2026/07/10",
  })] });
  const html = app.get("notice-list").innerHTML;
  assert.match(html, /undated-section/);
  assert.doesNotMatch(html, /archive-group|latest-section|掲載|2026年7月/);
  assert.match(app.get("filter-summary").textContent, /日付未確認 1件/);
  assert.doesNotMatch(app.get("filter-summary").textContent, /表示できる情報がありません/);
});

test("coverage exposes source failures, limits, counts, official links, and static scope", () => {
  const app = frontend();
  app.state.config = { sources: [{ id: "static", name: "こどもクラブ", mode: "static", page_url: "https://city.example/facility" }] };
  app.renderCoverage({ coverage: [
    { source_id: "school", source_name: "桜野小学校", page_url: "https://school.example/", status: "checked", notice_count: 4, discovered_count: 12, limit_reached: true, coverage_note: "公開PDFの一部のみ", checked_at: "2026-10-01T01:00:00Z" },
    { source_id: "city", source_name: "市のイベント", status: "unavailable", notice_count: 0 },
    { source_id: "static", status: "checked", notice_count: 1, checked_at: "" },
  ], warnings: ["市のイベント: 接続エラー"] });
  const html = app.get("coverage-list").innerHTML;
  assert.match(html, /取得 4件 · 候補 12件/);
  assert.match(html, /収集上限あり/);
  assert.match(html, /公開PDFの一部のみ/);
  assert.match(html, /https:\/\/city.example\/facility/);
  assert.match(html, /status-reference/);
  assert.match(html, /新着通知の確認対象ではありません/);
  assert.match(html, /確認日時 —/);
  assert.match(app.get("coverage-alert").textContent, /桜野小学校（/);
  assert.match(app.get("coverage-alert").textContent, /市のイベント（取得できませんでした）/);
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.match(app.get("coverage-warnings").innerHTML, /市のイベント: 接続エラー/);
  app.renderCoverage({ complete: true, coverage: [{ source_name: "学校", status: "checked" }] });
  assert.equal(app.get("coverage-alert").hidden, true);
});

test("backend text is escaped and executable URLs are omitted", () => {
  const app = frontend();
  const injection = '<img src=x onerror="alert(1)">';
  const item = notice(injection, { title: injection, source_name: injection, excerpt: injection, text: injection, categories: { [injection]: [injection] }, url: "javascript:alert(1)" });
  for (const html of [app.renderNoticeCard(item), app.detailMarkup(item)]) {
    assert.doesNotMatch(html, /<img|href="javascript:|onclick=/);
    assert.match(html, /&lt;img/);
  }
  app.renderCoverage({ coverage: [{ source_name: injection, coverage_note: injection, status: "unavailable", page_url: "data:text/html,unsafe" }], warnings: [injection] });
  assert.doesNotMatch(app.get("coverage-list").innerHTML + app.get("coverage-warnings").innerHTML, /<img|href="data:/);
  assert.equal(app.officialLink("https://name:secret@example.com/", "link"), "");
});

test("original-only notices retain their link and explanation without presenting it as extracted content", () => {
  const app = frontend();
  const explanation = '本文を読み取れませんでした。原文をご確認ください。<img src=x onerror="alert(1)">';
  const item = notice("unreadable", {
    extraction_status: "original_only", date_kind: "unknown", date_label: "更新資料", published_label: "",
    excerpt: explanation, text: explanation,
    category_names: ["抽出エラーの分類"], categories: { "抽出エラーの分類": ["本文ではありません"] },
  });
  for (const html of [app.renderNoticeCard(item), app.detailMarkup(item)]) {
    assert.match(html, /class="pill extraction-badge">本文未確認/);
    assert.match(html, /href="https:\/\/school.example\/unreadable"/);
    assert.match(html, /本文を読み取れませんでした/);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /<img|抽出エラーの分類|<h4>日本語の原文/);
  }
  assert.match(app.detailMarkup(item), /本文は確認できていません/);
  assert.match(app.detailMarkup(item), /OCR/);
  app.renderNotices({ notices: [item], coverage: [{ source_id: "school", source_name: "桜野小学校", status: "partial", notice_count: 1, readable_count: 0 }], warnings: ["桜野小学校: 本文を読み取れませんでした"] });
  assert.equal(app.get("empty-state").hidden, true);
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="unreadable"/);
  assert.match(app.get("coverage-list").innerHTML, /本文 0 \/ 資料 1/);
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.match(app.get("coverage-warnings").innerHTML, /本文を読み取れませんでした/);
});

test("readable coverage stays distinct from retained document links without upgrading failure status", () => {
  const app = frontend();
  const source = { source_name: "学校", status: "checked", notice_count: 3, readable_count: 1, discovered_count: 4 };
  app.renderCoverage({ coverage: [source] });
  assert.match(app.get("coverage-list").innerHTML, /本文 1 \/ 資料 3 · 候補 4件/);
  assert.match(app.get("coverage-alert").textContent, /学校（一部のみ確認）/);
  assert.equal(app.coverageStatus({ ...source, status: "unavailable" }), "unavailable");
  app.renderCoverage({ coverage: [{ ...source, readable_count: 3 }] });
  assert.match(app.get("coverage-list").innerHTML, /取得 3件/);
  assert.doesNotMatch(app.get("coverage-list").innerHTML, /本文 3 \/ 資料 3/);
  app.renderCoverage({ coverage: [{ ...source, readable_count: undefined }] });
  assert.doesNotMatch(app.get("coverage-list").innerHTML, /本文 undefined|本文 0/);
});

test("shared municipal records do not pretend the registry level is the article's target grade", () => {
  const app = frontend();
  const item = notice("city", { source_name: "市役所", source_group: "municipality", level: "小学校", grade: "1年生", title: "入学手続き", text: "対象条件は原文をご確認ください。" });
  assert.doesNotMatch(app.renderNoticeCard(item), /小学校/);
  assert.doesNotMatch(app.detailMarkup(item), /小学校|1年生/);
});

test("readable and legacy details include the machine-extraction/OCR note without an unverified badge", () => {
  const app = frontend();
  for (const extraction_status of ["ok", undefined]) {
    const item = notice("readable", { extraction_status, text: "持ち物：水筒" });
    const html = app.detailMarkup(item);
    assert.match(html, /class="extraction-note" lang="ja">表示本文は機械による抽出結果/);
    assert.match(html, /OCR/);
    assert.match(html, /lang="ja">持ち物：水筒/);
    assert.doesNotMatch(html, /extraction-badge|本文は確認できていません/);
  }
});

test("key labels exist in JA/KO/EN/ZH while notice titles and bodies stay Japanese", () => {
  const app = frontend();
  const keys = Object.keys(app.I18N.ja).filter((key) => /^(coverage\.|events\.|reference\.|extraction\.|common\.(event|deadline)$)/.test(key));
  for (const language of ["ja", "ko", "en", "zh"]) {
    app.state.language = language;
    for (const key of keys) assert.ok(app.I18N[language][key], `${language}: ${key}`);
    assert.match(app.detailMarkup(notice("学校だより", { text: "日本語の本文" })), /lang="ja">日本語の本文/);
    assert.match(app.renderNoticeCard(event("運動会", "2026/10/12")), /lang="ja">運動会/);
  }
});

test("cards keep click-to-expand and click-to-collapse state accessible", async () => {
  const app = frontend();
  const classes = new Set();
  const attributes = {};
  const inline = { innerHTML: "", replaceChildren() { this.innerHTML = ""; } };
  const button = { setAttribute(name, value) { attributes[name] = value; } };
  const card = {
    dataset: { noticeId: "clicked" },
    classList: {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
      toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
    },
    querySelector: (selector) => selector === "button" ? button : inline,
  };
  app.document.querySelectorAll = () => [card];
  await app.selectNotice("clicked");
  assert.equal(attributes["aria-expanded"], "true");
  assert.match(inline.innerHTML, /日本語の本文/);
  await app.selectNotice("clicked");
  assert.equal(attributes["aria-expanded"], "false");
  assert.equal(inline.innerHTML, "");
  assert.equal(app.state.selectedId, null);
});

test("manual refresh polls ordinary GETs until fresh, without rerendering identical cached data", async () => {
  const cached = { notices: [notice("cached")], refreshing: true, complete: false, scanned_at: "2026-10-01T00:00:00Z" };
  const fresh = { notices: [notice("fresh")], refreshing: false, complete: true, scanned_at: "2026-10-01T00:00:18Z" };
  const app = pollingFrontend(async (number) => number <= 2 ? cached : fresh);
  const loading = app.loadNotices(true);
  await flush();
  assert.equal(app.calls[0].options.method, "POST");
  assert.match(app.calls[0].url, /^\/api\/refresh\?/);
  assert.equal(app.get("refresh-button").disabled, false);
  assert.match(app.get("coverage-alert").textContent, /最新の資料を確認中/);
  await app.timers.advance(2000);
  assert.equal(app.calls.length, 2);
  assert.equal(app.detailCalls, 1);
  await app.timers.advance(2000);
  await loading;
  assert.equal(app.calls.length, 3);
  for (const call of app.calls.slice(1)) {
    assert.match(call.url, /^\/api\/notices\?/);
    assert.equal(call.options.method, undefined);
    assert.equal(call.options.body, undefined);
    assert.doesNotMatch(call.url, /[?&]refresh=/);
  }
  assert.equal(app.state.payload, fresh);
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="fresh"/);
  assert.equal(app.get("coverage-alert").hidden, true);
  assert.equal(app.get("filter-summary").attributes["data-refreshed-at"], fresh.scanned_at);
  assert.equal(app.timers.size, 0);
});

test("initial GET also polls when only a source-level refreshing flag is set", async () => {
  const app = pollingFrontend(async (number) => ({ notices: [], coverage: [{ source_id: "school", status: "checked", refreshing: number === 1 }] }));
  const loading = app.loadNotices();
  await flush();
  await app.timers.advance(2000);
  await loading;
  assert.equal(app.calls.length, 2);
  assert.ok(app.calls.every((call) => call.url.startsWith("/api/notices?") && !call.options.method));
  assert.equal(app.timers.size, 0);
  assert.equal(app.state.refreshStatus, null);
});

test("partial extraction warnings alone never start a polling loop", async () => {
  const app = pollingFrontend(async () => ({ notices: [], complete: false, refreshing: false, warnings: ["本文を読み取れませんでした"] }));
  await app.loadNotices();
  await app.timers.advance(120000);
  assert.equal(app.calls.length, 1);
  assert.equal(app.timers.size, 0);
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.equal(app.get("refresh-button").disabled, false);
});

test("poll deadline aborts a slow GET, preserves cached notices and warnings, and leaves refresh enabled", async () => {
  const cached = { notices: [notice("cached")], refreshing: true, warnings: ["学校: 更新確認中"] };
  const app = pollingFrontend((number, url, options) => number === 1 ? Promise.resolve(cached) : new Promise((resolve, reject) => {
    options.signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  }));
  const loading = app.loadNotices(true);
  await flush();
  await app.timers.advance(2000);
  await app.timers.advance(18000);
  assert.equal(app.calls.length, 2, "no overlapping polls while GET is pending");
  await app.timers.advance(40000);
  await loading;
  assert.equal(app.calls[1].options.signal.aborted, true);
  assert.equal(app.state.refreshStatus, "refreshTimeout");
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="cached"/);
  assert.match(app.get("coverage-alert").textContent, /しばらくしてから更新/);
  assert.match(app.get("coverage-warnings").innerHTML, /学校: 更新確認中/);
  assert.equal(app.get("refresh-button").disabled, false);
  assert.equal(app.timers.size, 0);
  await app.timers.advance(120000);
  assert.equal(app.calls.length, 2);
});

test("repeated refreshing responses stop after 60 seconds even when GETs finish quickly", async () => {
  const app = pollingFrontend(async () => ({ notices: [notice("cached")], refreshing: true }));
  const loading = app.loadNotices();
  await flush();
  await app.timers.advance(60000);
  await loading;
  const countAtDeadline = app.calls.length;
  assert.ok(countAtDeadline > 2 && countAtDeadline <= 31);
  assert.equal(app.state.refreshStatus, "refreshTimeout");
  assert.equal(app.timers.size, 0);
  await app.timers.advance(60000);
  assert.equal(app.calls.length, countAtDeadline);
});

test("poll failure keeps cached content and reports failure without retrying forever", async () => {
  const app = pollingFrontend(async (number) => {
    if (number > 1) throw new Error("connection lost");
    return { notices: [notice("cached")], refreshing: true };
  });
  const loading = app.loadNotices();
  await flush();
  await app.timers.advance(2000);
  await loading;
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="cached"/);
  assert.match(app.get("coverage-alert").textContent, /最新情報の再確認に失敗/);
  assert.equal(app.state.refreshStatus, "refreshError");
  assert.equal(app.get("refresh-button").disabled, false);
  assert.equal(app.timers.size, 0);
});

test("a new filter load cancels the pending poll timer", async () => {
  const app = pollingFrontend(async (number) => ({ notices: [notice(number === 1 ? "old" : "new")], refreshing: number === 1 }));
  app.get("source-filter").value = "old-school";
  const oldLoading = app.loadNotices(true);
  await flush();
  app.get("source-filter").value = "new-school";
  await app.loadNotices();
  await oldLoading;
  await app.timers.advance(120000);
  assert.equal(app.calls.length, 2);
  assert.equal(app.calls[0].options.signal.aborted, true);
  assert.match(app.calls[1].url, /source_id=new-school/);
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="new"/);
  assert.equal(app.timers.size, 0);
});

test("late polling responses cannot overwrite a newer filter even if cancellation is ignored", async () => {
  let resolveOldPoll;
  const fresh = { notices: [notice("new-filter")], refreshing: false };
  const app = pollingFrontend((number) => {
    if (number === 1) return Promise.resolve({ notices: [notice("old")], refreshing: true });
    if (number === 2) return new Promise((resolve) => { resolveOldPoll = resolve; });
    return Promise.resolve(fresh);
  });
  const oldLoading = app.loadNotices(true);
  await flush();
  await app.timers.advance(2000);
  app.get("grade-filter").value = "2年生";
  await app.loadNotices();
  resolveOldPoll({ notices: [notice("late-old-filter")], refreshing: false });
  await oldLoading;
  assert.equal(app.state.payload, fresh);
  assert.match(app.get("notice-list").innerHTML, /data-notice-id="new-filter"/);
  assert.doesNotMatch(app.get("notice-list").innerHTML, /late-old-filter/);
  assert.equal(app.state.refreshStatus, null);
  assert.equal(app.timers.size, 0);
});

test("late detail responses cannot overwrite the same selected ID from a newer load", async () => {
  const responses = [];
  const app = frontend({ api: () => new Promise((resolve) => responses.push(resolve)) });
  const first = app.selectNotice("same", { showInline: false });
  app.state.requestVersion++;
  const second = app.selectNotice("same", { showInline: false });
  responses[1](notice("new-detail"));
  await second;
  responses[0](notice("stale-detail"));
  await first;
  assert.match(app.get("detail-panel").innerHTML, /new-detail/);
  assert.doesNotMatch(app.get("detail-panel").innerHTML, /stale-detail/);
});

test("coverage stays closed by default and new asset versions match the service worker", () => {
  const index = readFileSync(path.join(web, "index.html"), "utf8");
  const sw = readFileSync(path.join(web, "sw.js"), "utf8");
  assert.match(index, /<details class="coverage-details" id="coverage-details" hidden>/);
  assert.match(index, /保護者専用アプリ・ログイン内のお知らせは対象外/);
  assert.doesNotMatch(index, /\sonclick=|<script>(?!\s*<\/script>)/);
  for (const asset of ["app.js", "app.css"]) {
    const version = index.match(new RegExp(`/${asset.replace(".", "\\.")}\\?v=[^"']+`))[0];
    assert.ok(sw.includes(`"${version}"`));
  }
  const policyCss = readFileSync(path.join(web, "policies.html"), "utf8").match(/\/app\.css\?v=[^"']+/)[0];
  assert.ok(sw.includes(`"${policyCss}"`));
});

test("official attachment links are compact, escaped, collapsed and never presented as read bodies", () => {
  const app = frontend();
  const html = app.detailMarkup(notice("attachments", {attachments: [
    {title: '<img src=x onerror=alert(1)>申込書', url: 'https://school.example/form.pdf'},
    {title: 'bad', url: 'javascript:alert(1)'},
  ]}));
  assert.match(html, /<details class="detail-section attachment-links">/);
  assert.match(html, /https:\/\/school.example\/form.pdf/);
  assert.match(html, /&lt;img/);
  assert.match(html, /添付本文は自動確認の対象外/);
  assert.doesNotMatch(html, /javascript:|<img src/);
});
