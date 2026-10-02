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
    innerHTML: "", _textContent: "", hidden: false, open: false, value: "all",
    get textContent() { return this.innerHTML ? this.innerHTML.replace(/<[^>]+>/g, "") : this._textContent; },
    set textContent(value) { this.innerHTML = ""; this._textContent = value; },
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
  vm.runInContext(`${script}\nthis.frontend = { state, I18N, t, noticeSections, noticeDateText, renderNoticeCard, detailMarkup, translationParts, translationMarkup, renderNotices, renderCoverage, renderAfterSchoolScope, coverageStatus, selectNotice, officialLink, japanToday, formatScanTime, loadNotices, queryString, setLoading };`, context);
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
  assert.match(html, /参考資料（入会・制度・施設案内）/);
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

const afterSchoolScope = (daily_notice_status = "not_collected", source_ids = []) => ({
  daily_notice_status, source_ids,
  scope_note: "予定・持ち物・保護者向け連絡は未収集。入会案内・あそべえだよりとは別です。",
});
const afterSchoolNotice = (kind, fields = {}) => notice(kind, {
  source_id: kind, source_group: "after_school", source_group_label: "学童・あそべえ", kind, ...fields,
});

test("admissions and guides are references while Asobee letters and supplied daily notices remain distinct", () => {
  const app = frontend();
  const references = ["gakudo_admissions", "gakudo_facility", "asobee_reference"];
  for (const coverage_kind of ["reference", undefined]) {
    app.renderNotices({ notices: references.map((kind) => afterSchoolNotice(kind, { coverage_kind })), notice_count: 3, after_school_scope: afterSchoolScope() });
    assert.equal(app.get("metric-notices").textContent, 0);
    assert.equal(app.state.selectedId, null);
    assert.match(app.get("notice-list").innerHTML, /参考資料（入会・制度・施設案内）/);
    assert.match(app.get("notice-list").innerHTML, /新着通知の対象ではありません/);
    assert.doesNotMatch(app.get("notice-list").innerHTML, /latest-section|<details[^>]*\bopen\b/);
  }
  const mixed = [...references.map((kind) => afterSchoolNotice(kind, { coverage_kind: "reference" })), afterSchoolNotice("asobee_letter"), afterSchoolNotice("gakudo_daily")];
  const sections = app.noticeSections(mixed);
  assert.deepEqual(ids(sections.references), references);
  assert.deepEqual(ids(sections.active[0].items).sort(), ["asobee_letter", "gakudo_daily"]);
  app.renderNotices({ notices: mixed, notice_count: 5 });
  assert.equal(app.get("metric-notices").textContent, 2);
  assert.match(app.get("notice-list").innerHTML, /あそべえだより/);
  assert.match(app.get("notice-list").innerHTML, /学童の生活連絡/);
});

test("typed card and detail badges, original-only state and official links survive all four locales", () => {
  const app = frontend();
  const kinds = ["gakudo_admissions", "gakudo_facility", "asobee_reference", "asobee_letter", "gakudo_daily"];
  for (const language of ["ja", "ko", "en", "zh"]) {
    app.state.language = language;
    for (const kind of kinds) {
      // The machine-readable kind must win over a legacy generic label.
      const item = afterSchoolNotice(kind, { kind_label: "学童クラブ", title: "日本語の資料", text: "原文をご確認ください。", extraction_status: "original_only" });
      for (const html of [app.renderNoticeCard(item), app.detailMarkup(item)]) {
        assert.ok(html.includes(app.t(`kind.${kind}`).replaceAll("&", "&amp;")), `${language}: ${kind}`);
        assert.ok(html.includes(app.t("groups.afterSchool").replaceAll("&", "&amp;")));
        assert.ok(html.includes(app.t("extraction.unverified")));
        assert.match(html, /日本語の資料/);
        assert.ok(html.includes(`href="https://school.example/${kind}"`));
      }
      if (["gakudo_admissions", "gakudo_facility", "asobee_reference"].includes(kind)) {
        assert.ok(app.detailMarkup(item).includes(app.t("reference.note")));
      }
      const labelOnly = { ...item, kind: undefined, kind_label: app.I18N.ja[`kind.${kind}`] };
      assert.ok(app.renderNoticeCard(labelOnly).includes(app.t(`kind.${kind}`).replaceAll("&", "&amp;")));
    }
  }
});

test("coverage content_kind supplies classification without mistaking reference guides for daily notices", () => {
  const app = frontend();
  app.state.config = { sources: [{ id: "facility", content_kind: "gakudo_facility", coverage_kind: "reference" }] };
  app.renderNotices({
    notices: [afterSchoolNotice(undefined, { id: "guide", source_id: "guide" }), afterSchoolNotice(undefined, { id: "facility", source_id: "facility" }), afterSchoolNotice(undefined, { id: "letter", source_id: "letter" })],
    coverage: [
      { source_id: "guide", content_kind: "asobee_reference", coverage_kind: "reference", status: "checked" },
      { source_id: "letter", content_kind: "asobee_letter", status: "checked" },
    ],
  });
  assert.equal(app.get("metric-notices").textContent, 1);
  assert.equal(app.state.selectedId, "letter");
  assert.match(app.get("notice-list").innerHTML, /あそべえの利用案内|学童の施設案内|あそべえだより/);
  assert.match(app.get("coverage-list").innerHTML, /class="pill soft">あそべえの利用案内/);
  assert.match(app.get("coverage-list").innerHTML, /class="pill soft">あそべえだより/);
  assert.doesNotMatch(app.get("coverage-list").innerHTML, /学童の生活連絡/);
});

test("missing scope is not treated as uncollected, and zero notices still show explicit after-school scope", () => {
  const app = frontend();
  for (const group of ["all", "after_school"]) {
    app.get("group-filter").value = group;
    for (const scope of [undefined, null]) {
      app.renderNotices({ notices: [], after_school_scope: scope });
      assert.equal(app.get("after-school-scope").hidden, true);
    }
    app.renderNotices({ notices: [], after_school_scope: afterSchoolScope(), filters: { group, feed: "notices" } });
    assert.equal(app.get("after-school-scope").hidden, false);
    assert.equal(app.get("after-school-scope-summary").textContent, "学童の生活連絡：未収集");
    assert.equal(app.get("after-school-scope-note").textContent, afterSchoolScope().scope_note);
    assert.equal(app.get("after-school-scope-sources").hidden, true);
    assert.equal(app.get("metric-notices").textContent, 0);
    assert.doesNotMatch(app.get("notice-list").innerHTML, /学童の生活連絡/);
    assert.equal(app.get("coverage-alert").hidden, true, "an unregistered scope is neutral, not a source failure");
  }
});

test("after-school scope is hidden for school-only, municipality and event filters", () => {
  const app = frontend();
  const payload = { notices: [], after_school_scope: afterSchoolScope() };
  for (const group of ["school", "municipality"]) {
    app.get("group-filter").value = group;
    app.renderNotices(payload);
    assert.equal(app.get("after-school-scope").hidden, true);
    app.get("group-filter").value = "all";
    app.renderNotices({ ...payload, filters: { group } });
    assert.equal(app.get("after-school-scope").hidden, true);
  }
  app.state.feed = "events";
  app.renderNotices(payload);
  assert.equal(app.get("after-school-scope").hidden, true);
  app.state.feed = "notices";
  app.renderNotices({ ...payload, filters: { feed: "events" } });
  assert.equal(app.get("after-school-scope").hidden, true);
});

test("registered daily scope reports actual failures or unknown coverage without claiming completeness", () => {
  const app = frontend();
  app.state.config = { sources: [{ id: "daily", name: "学童の連絡ページ", content_kind: "gakudo_daily" }] };
  const payload = { notices: [], after_school_scope: afterSchoolScope("registered", ["daily"]), coverage: [] };
  app.renderNotices(payload);
  assert.equal(app.get("after-school-scope-summary").textContent, "学童の生活連絡：収集対象に登録");
  assert.match(app.get("after-school-scope-sources").innerHTML, /学童の連絡ページ.*確認状況不明/);
  assert.equal(app.get("metric-notices").textContent, 0);
  assert.doesNotMatch(app.get("notice-list").innerHTML, /notice-card/);
  for (const issue of ["stale", "collection", "extraction", "unavailable", "refreshing"]) {
    app.renderNotices({ ...payload, coverage: [{ source_id: "daily", status: "partial", content_kind: "gakudo_daily", issue_codes: [issue] }] });
    assert.ok(app.get("after-school-scope-sources").innerHTML.includes(app.t(`coverage.${issue}`)));
    assert.equal(app.get("after-school-scope-summary").textContent, "学童の生活連絡：収集対象に登録");
  }
  app.renderNotices({ ...payload, coverage: [{ source_id: "daily", status: "checked", freshness_status: "fresh", issue_codes: [] }] });
  assert.match(app.get("after-school-scope-sources").innerHTML, /公開範囲を確認/);
  assert.match(app.get("after-school-scope-note").textContent, /すべての連絡の取得を保証するものではありません/);
  app.renderNotices({ ...payload, after_school_scope: afterSchoolScope("registered") });
  assert.match(app.get("after-school-scope-sources").innerHTML, /確認状況不明/);
});

test("scope uses native closed details, preserves manual toggles and localizes on rerender", () => {
  const app = frontend();
  const index = readFileSync(path.join(web, "index.html"), "utf8");
  assert.match(index, /<details class="coverage-details" id="after-school-scope" hidden>\s*<summary id="after-school-scope-summary">/);
  assert.equal((index.match(/data-i18n="groups.afterSchool">学童・あそべえ/g) || []).length, 2);
  const payload = { notices: [], after_school_scope: afterSchoolScope() };
  const panel = app.get("after-school-scope");
  app.renderNotices(payload);
  assert.equal(panel.open, false);
  for (const language of ["ja", "ko", "en", "zh"]) {
    app.state.language = language;
    for (const open of [true, false]) {
      panel.open = open; // Native summary activation owns this state.
      app.renderNotices(payload);
      assert.equal(panel.open, open);
      assert.equal(app.get("after-school-scope-summary").textContent, app.t("afterSchool.notCollected"));
      assert.equal(app.get("after-school-scope-note").textContent, app.t("afterSchool.notCollectedNote"));
      app.renderNotices({ ...payload, after_school_scope: afterSchoolScope("registered") });
      assert.equal(panel.open, open);
      assert.equal(app.get("after-school-scope-summary").textContent, app.t("afterSchool.registered"));
      assert.equal(app.get("after-school-scope-note").textContent, app.t("afterSchool.registeredNote"));
    }
  }
  app.setLoading(true);
  assert.equal(panel.hidden, true, "do not show a previous filter's scope while a request is loading");
});

test("changing the source group retains the chosen school and never broadens its request", async () => {
  const app = pollingFrontend(async () => ({ notices: [], after_school_scope: null }));
  app.get("source-filter").value = "sakurano";
  for (const group of ["all", "after_school", "municipality", "school", "all"]) {
    app.get("group-filter").value = group;
    await app.loadNotices();
    const query = new URL(app.calls.at(-1).url, "https://example.test").searchParams;
    assert.equal(query.get("source_id"), "sakurano");
    assert.equal(query.get("group"), group === "all" ? null : group);
    assert.equal(app.get("source-filter").value, "sakurano");
  }
  app.get("source-filter").value = "all";
  assert.equal(new URLSearchParams(app.queryString()).get("source_id"), "all");
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
  assert.match(html, /日々の連絡・新着通知の対象ではありません/);
  assert.match(html, /確認日時 —/);
  assert.doesNotMatch(app.get("coverage-alert").textContent, /桜野小学校|市のイベント|収集上限/);
  assert.match(app.get("coverage-alert").textContent, /取得できませんでした 1/);
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

test("archive caps are neutral detail-only information in new and legacy payloads", () => {
  const app = frontend();
  const source = { source_name: "学校", notice_count: 4, readable_count: 4, discovered_count: 25, limit_reached: true };
  for (const fields of [
    { status: "checked", freshness_status: "fresh", issue_codes: ["limit"] },
    { status: "checked" },
    { status: "partial" },
  ]) {
    app.renderCoverage({ complete: false, coverage: [{ ...source, ...fields }], warnings: ["学校: 収集上限あり"] });
    assert.equal(app.get("coverage-alert").hidden, true);
    assert.equal(app.get("coverage-details").open, false);
    assert.match(app.get("coverage-list").innerHTML, /収集上限あり|一部の過去資料/);
    assert.doesNotMatch(app.get("coverage-list").innerHTML + app.get("coverage-warnings").innerHTML, /status-(?:partial|unavailable|unknown)|本文未確認|取得できません/);
  }
});

test("stale snapshots keep a neutral freshness reason without claiming extraction failure", () => {
  const app = frontend();
  app.renderCoverage({ complete: false, coverage: [{
    source_name: "学校", status: "partial", freshness_status: "stale", issue_codes: ["stale"],
    notice_count: 4, readable_count: 4, checked_at: "2026-09-01T01:00:00Z",
  }], warnings: ["学校: 保存データの更新が遅れています"] });
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.equal(app.get("coverage-alert").textContent, "更新遅れ 1 詳細");
  assert.doesNotMatch(app.get("coverage-alert").className, /coverage-alert/);
  const details = app.get("coverage-list").innerHTML + app.get("coverage-warnings").innerHTML;
  assert.match(details, /前回取得した情報/);
  assert.match(details, /取得 4件/);
  assert.match(details, /2026\/09\/01/);
  assert.doesNotMatch(details, /本文未確認|読み取れ|status-(?:partial|unavailable|unknown)/);
});

test("mixed stale and OCR sources produce bounded counts rather than a wall of source names", () => {
  const app = frontend();
  const coverage = Array.from({ length: 12 }, (_, i) => ({
    source_name: `とても長い公開資料の発信元 ${i}`, status: "partial", notice_count: 5,
    readable_count: i < 10 ? 5 : 3, freshness_status: "stale",
    issue_codes: i < 10 ? ["stale", "limit"] : ["stale", "extraction", "extraction"],
  }));
  app.renderCoverage({ complete: false, coverage });
  assert.equal(app.get("coverage-alert").textContent, "更新遅れ 12 · 本文未確認 2 詳細");
  assert.doesNotMatch(app.get("coverage-alert").textContent, /発信元|収集上限/);
  assert.equal((app.get("coverage-list").innerHTML.match(/class="coverage-source"/g) || []).length, 12);
  assert.equal(app.get("coverage-details").open, false);
  assert.match(app.get("coverage-list").innerHTML, /本文 3 \/ 資料 5/);
  assert.match(app.get("coverage-list").innerHTML, /本文を読み取れない資料/);
});

test("collection failures and unavailable sources are not mislabeled as unreadable text", () => {
  const app = frontend();
  for (const issue of ["collection", "unavailable"]) {
    app.renderCoverage({ coverage: [{ source_name: "学校", status: issue === "unavailable" ? "unavailable" : "partial", freshness_status: "stale", issue_codes: [issue, "stale"], notice_count: 3, readable_count: 3 }] });
    assert.match(app.get("coverage-alert").textContent, new RegExp(`${app.t(`coverage.${issue}`)} 1`));
    assert.match(app.get("coverage-alert").innerHTML, /status-unavailable/);
    assert.match(app.get("coverage-list").innerHTML, /取得できませんでした/);
    assert.doesNotMatch(app.get("coverage-alert").textContent + app.get("coverage-list").innerHTML, /本文未確認|本文を読み取れない/);
  }
});

test("pending and refreshing do not imply failure, while unknown never claims success", () => {
  const app = frontend();
  app.renderCoverage({ complete: false, coverage: [{ source_name: "学校", status: "unavailable", freshness_status: "pending", issue_codes: ["refreshing"], notice_count: 0, readable_count: 0 }] });
  assert.match(app.get("coverage-alert").textContent, /初回確認待ち 1/);
  assert.match(app.get("coverage-alert").textContent, /更新確認中 1/);
  assert.doesNotMatch(app.get("coverage-list").innerHTML, /status-unavailable|status-partial|本文未確認|取得できません/);
  app.renderCoverage({ coverage: [{ source_name: "学校", status: "checked", freshness_status: "unknown", issue_codes: [] }] });
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.match(app.get("coverage-list").innerHTML, /確認状況不明/);
  assert.doesNotMatch(app.get("coverage-list").innerHTML, /公開範囲を確認/);
});

test("a real scheduled first-run payload remains pending despite its legacy unavailable status and warning", async () => {
  const payload = {
    scanned_at: "", source_count: 1, notice_count: 0, reference_count: 0, notices: [],
    complete: false, refreshing: false,
    warnings: ["市のイベント: 定期収集の初回データを待っています。公式ページをご確認ください。"],
    coverage: [{
      source_id: "city-events", source_name: "市のイベント", page_url: "https://city.example/events/",
      checked_at: "", status: "unavailable", coverage_kind: "notices", coverage_note: "公開ページの資料が対象です。",
      notice_count: 0, readable_count: 0, discovered_count: 0, limit_reached: false,
      refreshing: false, collection_driver: "scheduled", freshness_status: "pending", issue_codes: [],
    }],
  };
  const app = pollingFrontend(async () => payload);
  await app.loadNotices();
  await app.timers.advance(120000);
  assert.equal(app.get("coverage-alert").textContent, "初回確認待ち 1 詳細");
  assert.match(app.get("coverage-list").innerHTML, /初回の取得結果を待っています/);
  assert.match(app.get("coverage-warnings").innerHTML, /定期収集の初回データを待っています/);
  assert.doesNotMatch(app.get("coverage-alert").innerHTML + app.get("coverage-list").innerHTML + app.get("coverage-warnings").innerHTML, /status-(?:unavailable|partial|unknown)|収集の問題|本文未確認|取得できません/);
  assert.equal(app.get("coverage-details").open, false);
  assert.equal(app.calls.length, 1);
  assert.equal(app.timers.size, 0);
  assert.deepEqual(payload.coverage[0].issue_codes, [], "rendering must not mutate the backend payload");
});

test("legacy partial statuses and unexplained errors stay visible even alongside a cap", () => {
  const app = frontend();
  for (const payload of [
    { coverage: [{ source_name: "学校", status: "partial" }] },
    { coverage: [{ source_name: "学校", status: "partial", limit_reached: true }] },
    { coverage: [{ source_name: "学校", status: "checked", limit_reached: true }], warnings: ["学校: 接続エラー"] },
    { coverage: [{ source_name: "学校", status: "checked", issue_codes: ["limit"] }], errors: [{ source_name: "学校", message: "接続エラー" }] },
    { coverage: [{ source_name: "学校", status: "checked", issue_codes: [] }], warnings: ["学校: 接続エラー"] },
    { coverage: [{ source_name: "学校", status: "checked", issue_codes: ["limit"] }], warnings: ["別の資料: 接続エラー"] },
  ]) {
    app.renderCoverage(payload);
    assert.equal(app.get("coverage-alert").hidden, false);
    assert.match(app.get("coverage-alert").textContent, /収集の問題 1/);
    assert.doesNotMatch(app.get("coverage-alert").textContent, /本文未確認/);
  }
  app.renderCoverage({ coverage: [{ source_name: "学校", status: "checked", issue_codes: ["future-issue"] }] });
  assert.equal(app.get("coverage-alert").hidden, false);
  assert.match(app.get("coverage-alert").textContent, /確認状況不明/);
});

test("legacy refreshing warnings stay neutral, and readable deficits still expose extraction failures", () => {
  const app = frontend();
  const source = { source_name: "学校", status: "partial", notice_count: 2, readable_count: 2, refreshing: true };
  const warnings = ["学校: 更新確認中です。前回取得した情報を表示しています。"];
  app.renderCoverage({ coverage: [source], warnings });
  assert.equal(app.get("coverage-alert").textContent, "更新確認中 1 詳細");
  assert.doesNotMatch(app.get("coverage-list").innerHTML + app.get("coverage-warnings").innerHTML, /status-unavailable|status-partial|本文未確認/);
  app.renderCoverage({ coverage: [{ ...source, readable_count: 0 }], warnings });
  assert.match(app.get("coverage-alert").textContent, /本文未確認 1/);
  assert.match(app.get("coverage-list").innerHTML, /本文 0 \/ 資料 2/);
});

test("coverage link toggles details, follows native summary changes, and preserves open state on rerender", () => {
  const app = frontend();
  const alert = app.get("coverage-alert");
  const details = app.get("coverage-details");
  const link = app.get("coverage-toggle");
  alert.querySelector = (selector) => selector === "#coverage-toggle" ? link : null;
  const payload = { coverage: [{ source_name: "学校", status: "partial", issue_codes: ["stale"] }] };
  app.renderCoverage(payload);
  assert.equal(details.open, false);
  assert.match(alert.innerHTML, /href="#coverage-details" aria-controls="coverage-details" aria-expanded="false"/);
  let prevented = false;
  link.onclick({ preventDefault() { prevented = true; } });
  details.ontoggle();
  assert.equal(prevented, true);
  assert.equal(details.open, true);
  assert.equal(link.attributes["aria-expanded"], "true");
  assert.equal(link.textContent, "閉じる");
  app.renderCoverage(payload);
  assert.equal(details.open, true);
  assert.match(alert.innerHTML, /aria-expanded="true"/);
  link.onclick({ preventDefault() {} });
  details.ontoggle();
  assert.equal(details.open, false);
  assert.equal(link.attributes["aria-expanded"], "false");
  // Simulate opening via the native summary, then a locale change.
  details.open = true;
  details.ontoggle();
  assert.equal(link.attributes["aria-expanded"], "true");
  app.state.language = "ko";
  app.renderCoverage(payload);
  assert.equal(details.open, true);
  assert.match(alert.innerHTML, /접기/);
});

test("coverage summaries and each reason are localized in JA, KO, EN and ZH", () => {
  const app = frontend();
  for (const language of ["ja", "ko", "en", "zh"]) {
    app.state.language = language;
    for (const issue of ["stale", "extraction", "collection", "unavailable", "refreshing", "pending", "unknown", "limit"]) {
      app.renderCoverage({ coverage: [{ source_name: "日本語の発信元", status: "checked", freshness_status: "fresh", issue_codes: [issue] }] });
      assert.ok(app.get("coverage-list").innerHTML.includes(app.I18N[language][`coverage.reason.${issue}`]), `${language}: ${issue}`);
      assert.match(app.get("coverage-list").innerHTML, /日本語の発信元/);
      if (issue !== "limit") {
        assert.ok(app.get("coverage-alert").textContent.includes(`${app.I18N[language][`coverage.${issue}`]} 1`));
        assert.ok(app.get("coverage-alert").textContent.includes(app.I18N[language]["coverage.details"]));
      } else assert.equal(app.get("coverage-alert").hidden, true);
    }
  }
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
  assert.ok(app.detailMarkup(item).includes(app.t("extraction.missing")));
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
  assert.match(app.get("coverage-alert").textContent, /本文未確認 1/);
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

test("readable and legacy details include the localized extraction note without an unverified badge", () => {
  const app = frontend();
  for (const extraction_status of ["ok", undefined]) {
    const item = notice("readable", { extraction_status, text: "持ち物：水筒" });
    const html = app.detailMarkup(item);
    assert.ok(html.includes(app.t("extraction.note")));
    assert.match(html, /lang="ja">持ち物：水筒/);
    assert.doesNotMatch(html, /extraction-badge|本文は確認できていません/);
  }
});

test("key labels exist in JA/KO/EN/ZH while notice titles and bodies stay Japanese", () => {
  const app = frontend();
  const keys = Object.keys(app.I18N.ja).filter((key) => /^(coverage\.|events\.|reference\.|extraction\.|afterSchool\.|kind\.|groups\.|common\.(event|deadline)$)/.test(key));
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
  assert.match(app.get("coverage-alert").textContent, /更新確認中/);
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

test("status-only poll changes preserve the reader without refetching detail", async () => {
  const items = [notice("same")];
  const pending = { notices: items, refreshing: true, scanned_at: "2026-10-01T03:00:00Z", coverage: [] };
  const complete = { ...pending, refreshing: false, scanned_at: "2026-10-01T03:01:00Z" };
  const app = pollingFrontend((number) => Promise.resolve(number === 1 ? pending : complete));
  const loading = app.loadNotices();
  await flush();
  app.get("notice-list").innerHTML += "reader-preserved-marker";
  const detailCalls = app.detailCalls;
  await app.timers.advance(2000);
  await loading;
  assert.equal(app.state.payload, complete);
  assert.equal(app.detailCalls, detailCalls);
  assert.match(app.get("notice-list").innerHTML, /reader-preserved-marker/);
  assert.equal(app.get("metric-scanned").textContent, app.formatScanTime(complete.scanned_at));
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

test("the new refreshing issue polls, but pending or stale snapshots alone do not", async () => {
  const app = pollingFrontend(async (number) => ({ notices: [], coverage: [{ source_id: "school", status: "checked", freshness_status: number === 1 ? "pending" : "fresh", issue_codes: number === 1 ? ["refreshing"] : [] }] }));
  const loading = app.loadNotices();
  await flush();
  assert.match(app.get("coverage-alert").textContent, /更新確認中 1/);
  await app.timers.advance(2000);
  await loading;
  assert.equal(app.calls.length, 2);
  assert.equal(app.get("coverage-alert").hidden, true);
  assert.equal(app.timers.size, 0);
  for (const freshness_status of ["pending", "stale", "unknown"]) {
    const idle = pollingFrontend(async () => ({ notices: [], coverage: [{ source_id: "school", status: "partial", freshness_status, issue_codes: [] }] }));
    await idle.loadNotices();
    await idle.timers.advance(120000);
    assert.equal(idle.calls.length, 1);
    assert.equal(idle.timers.size, 0);
    assert.equal(idle.get("coverage-alert").hidden, false);
  }
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
  assert.match(app.get("coverage-alert").textContent, /確認が遅れています/);
  assert.match(app.get("coverage-warnings").innerHTML, /しばらくしてから更新/);
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
  assert.match(app.get("coverage-alert").textContent, /再確認に失敗/);
  assert.match(app.get("coverage-warnings").innerHTML, /最新情報の再確認に失敗/);
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

test("categories keep every complete block including optional conditions after item eight", () => {
  const app = frontend();
  const blocks = Array.from({ length: 9 }, (_, i) => `準備${i}`);
  blocks.push("長ぐつ\n(はきたい人だけ、学校で長ぐつにはきかえます。)");
  const html = app.detailMarkup(notice("supplies", { text: blocks.join("\n"), categories: { "持ち物・準備": blocks } }));
  assert.match(html, /category-section" open/);
  assert.equal((html.match(/<li lang="ja">/g) || []).length, 10);
  assert.match(html, /<li lang="ja">長ぐつ\n\(はきたい人だけ、学校で長ぐつにはきかえます。\)<\/li>/);
});

test("external translation is opt-in, lossless, language-specific and never for unreadable text", () => {
  const app = frontend({ api: () => { throw new Error("no automatic requests"); } });
  const item = notice('公開<タイトル>', { text: "持ち物：長ぐつ\n（希望者のみ）\n<img onerror=x>" });
  assert.equal(app.translationMarkup(item), "");
  for (const [language, target] of [["ko", "ko"], ["en", "en"], ["zh", "zh-CN"]]) {
    app.state.language = language;
    const html = app.translationMarkup(item);
    assert.match(html, /target="_blank" rel="noopener noreferrer"/);
    const url = new URL(html.match(/href="([^"]+)"/)[1].replaceAll("&amp;", "&"));
    assert.equal(url.origin, "https://translate.google.com");
    assert.equal(url.searchParams.get("tl"), target);
    assert.equal(url.searchParams.get("sl"), "ja");
    assert.equal(url.searchParams.get("text"), `${item.title}\n\n${item.text}`);
    assert.doesNotMatch(html, /<img|<iframe/);
    assert.equal(app.translationMarkup({ ...item, extraction_status: "original_only" }), "");
    assert.equal(app.translationMarkup({ ...item, text: "  \n" }), "");
  }
});

test("long translation parts retain every codepoint and whitespace within URL and text limits", () => {
  const app = frontend();
  const text = (`見出し\n${"長ぐつ（希望者のみ）。🌸 ".repeat(100)}\n\n`).repeat(8);
  const parts = app.translationParts(text);
  assert.ok(parts.length > 1);
  assert.equal(parts.join(""), text);
  for (const part of parts) {
    assert.ok(Array.from(part).length <= 4500);
    assert.ok(encodeURIComponent(part).length <= 6000);
    assert.ok(part.length > 0);
  }
  assert.deepEqual(Array.from(app.translationParts("")), []);
  assert.equal(app.translationParts("x".repeat(20000)).join(""), "x".repeat(20000));
  app.state.language = "ko";
  const item = notice("long", { text });
  const html = app.translationMarkup(item);
  const urls = [...html.matchAll(/href="([^"]+)"/g)].map((match) => new URL(match[1].replaceAll("&amp;", "&")));
  assert.equal(urls.map((url) => url.searchParams.get("text")).join(""), `${item.title}\n\n${text}`);
  assert.match(html, new RegExp(`${urls.length}/${urls.length}`));
  for (const url of urls) assert.ok(url.href.length <= 6100);
  for (const text of ["'()!~🌸".repeat(2000), "'".repeat(10000)]) {
    const punctuation = app.translationMarkup(notice("punctuation", { text }));
    const restored = [];
    for (const match of punctuation.matchAll(/href="([^"]+)"/g)) {
      const url = new URL(match[1].replaceAll("&amp;", "&").replaceAll("&#039;", "'"));
      assert.ok(url.href.length <= 6100);
      restored.push(url.searchParams.get("text"));
    }
    assert.equal(restored.join(""), `punctuation\n\n${text}`);
  }
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
