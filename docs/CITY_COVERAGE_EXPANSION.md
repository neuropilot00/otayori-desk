# Musashino guardian source expansion — verified 2026-10-01

Research handoff only. This task owns **only this document**. No edits to `sources.json`, collector code, caches, notifications, deployment, or Git history were made. Existing coverage was compared with [SOURCE_COVERAGE.md](SOURCE_COVERAGE.md) and the live registry. Concurrent implementation changes belong to the main task.

## Recommended additions and evidence

These are public, unauthenticated, explicitly selected official roots. Counts below are **distinct URLs discovered on the first page using the proposed regexes and the repository's `CatalogService._scoped_links`**, not counts of current events or successfully decoded PDFs. All roots returned direct HTTP **200** locally on 2026-10-01. HTML requests were limited to selected roots and their reviewed direct details, four concurrent requests, 2 MB per HTML response; no recursive archive crawl, login, form submission, image/video request, or PDF-body download was performed. Seven selected attachments were checked with HEAD only.

The main task reports adding body-scoped, allowed-host PDF/image/Word/Excel attachment links with an original-only note. The recommendations below use that approach; a linked attachment is not proof its contents were extracted. This research does not revalidate Railway/GitHub execution. Railway's reported 403 must remain a separate runtime status from these successful local HTTP checks.

| Priority / proposed ID | Exact reviewed `page_urls` root | Detected | Freshness / guardian value |
| --- | --- | ---: | --- |
| P0 `musashino_food_family_events` | [食育の取り組み](https://www.city.musashino.lg.jp/kenko_fukushi/kenko_hoken/syokuiku/torikumi/index.html) | **2** | Festival updated **2026-10-01**, cooking application updated **2026-09-29**; event **2026-10-31**. |
| P0 `musashino_family_sports_events` | [イベント(スポーツ)](https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/index.html) | **4** | Festival updated **2026-09-28**, event **2026-10-12**. Two other entries have already ended. |
| P0 `musashino_asobee_reference` | [子育て支援施設](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/index.html) | **1** | あそべえ city guidance updated **2026-07-02**: registration, eligibility, hours, closures; reference, not a new monthly notice. |
| P0 per-school Asobee letters | [子ども協会・今月のおたより](https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html) | **12** across schools; **1** for 桜野 | Current HTML table says **9月号**, linked filenames say **202609**. No October issue was observed. |
| P1 `musashino_school_lunch_parent` | [学校給食](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/index.html) | **5** | Newest reviewed article: 食物アレルギー対応, **2026-08-24**. Includes current forms/support and older safety references. |
| P1 `musashino_school_health_parent` | [学校保健](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/index.html) | **3** | Latest displayed update among these is **2023-05-10**; standing guidance, not three new notices. Named `gakkou_kansen.html` must be included. |
| P1 `musashino_school_safety_parent` | [小・中学校に関する取り組み](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/torikumi/index.html) | **2** | 通学路点検 **2026-07-15** and 非常変災時の臨時休業 **2026-06-02**. No recruitment, tenders, or general city news. |

The existing `musashino_education_notices` already covers admission/transfer and school assistance; `musashino_gakudo_notices` already covers club applications. Do not add duplicate sources for those. Asobee is distinct from 学童クラブ, and school-specific letters must follow the selected school/collection rather than being shared with every guardian in the ward.

## Proposed registry records

These are reviewable proposals, **not applied**. The six city records may be shared within 武蔵野市; the 桜野 letter example must remain school-specific. Other schools should use their existing collection IDs plus the row-to-file mapping below. Common patterns use regex search against **title + space + absolute URL**, matching the current collector. JSON below contains correctly escaped backslashes. `discovery_depth: 0` deliberately discovers only links on the listed roots; linked PDFs/images belong on detail cards rather than becoming another discovery frontier.

```json
[
  {
    "name": "武蔵野市・食育フェスタ",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "municipality",
    "content_kind": "city_info",
    "id": "musashino_food_family_events",
    "page_urls": [
      "https://www.city.musashino.lg.jp/kenko_fukushi/kenko_hoken/syokuiku/torikumi/index.html"
    ],
    "link_patterns": [
      "(?s)食育フェスタ.*https://www\\.city\\.musashino\\.lg\\.jp/kenko_fukushi/kenko_hoken/syokuiku/torikumi/[0-9]+\\.html$"
    ],
    "max_documents": 12,
    "feed_group": "events",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "武蔵野市・親子スポーツイベント",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "municipality",
    "content_kind": "city_info",
    "id": "musashino_family_sports_events",
    "page_urls": [
      "https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/index.html"
    ],
    "link_patterns": [
      "(?s)(?:市民スポーツフェスティバル|ファミリースポーツフェア|市民スポーツデー|ボールゲームフェスタ|親子|小学生).*https://www\\.city\\.musashino\\.lg\\.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/[0-9]+\\.html$"
    ],
    "max_documents": 12,
    "feed_group": "events",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "武蔵野市・あそべえ利用案内",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "after_school",
    "content_kind": "after_school",
    "id": "musashino_asobee_reference",
    "page_urls": [
      "https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/index.html"
    ],
    "link_patterns": [
      "(?s)あそべえ.*https://www\\.city\\.musashino\\.lg\\.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/[0-9]+\\.html$"
    ],
    "max_documents": 4,
    "feed_group": "notices",
    "coverage_kind": "reference",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "武蔵野市・学校給食の保護者案内",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "municipality",
    "content_kind": "city_info",
    "id": "musashino_school_lunch_parent",
    "page_urls": [
      "https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/index.html"
    ],
    "link_patterns": [
      "(?s)(?:アレルギー|スマイル給食|産地偽装|放射性物質|武蔵野市の学校給食について).*https://www\\.city\\.musashino\\.lg\\.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/[0-9]+\\.html$"
    ],
    "max_documents": 15,
    "feed_group": "notices",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "武蔵野市・学校保健",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "municipality",
    "content_kind": "city_info",
    "id": "musashino_school_health_parent",
    "page_urls": [
      "https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/index.html"
    ],
    "link_patterns": [
      "https://www\\.city\\.musashino\\.lg\\.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/(?:[0-9]+|gakkou_kansen)\\.html$"
    ],
    "max_documents": 10,
    "feed_group": "notices",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "武蔵野市・通学と休業の安全案内",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "www.city.musashino.lg.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": true,
    "source_group": "municipality",
    "content_kind": "city_info",
    "id": "musashino_school_safety_parent",
    "page_urls": [
      "https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/torikumi/index.html"
    ],
    "link_patterns": [
      "(?s)(?:臨時休業|通学路).*https://www\\.city\\.musashino\\.lg\\.jp/shussan_kodomo_kyoiku/sho_chugakko/torikumi/[0-9]+\\.html$"
    ],
    "max_documents": 10,
    "feed_group": "notices",
    "coverage_note": "市・公式運営団体の公開情報。掲載日・更新日と開催日・対象年度は区別します。"
  },
  {
    "name": "桜野あそべえ・公開のおたより",
    "ward": "武蔵野市",
    "level": "小学校",
    "mode": "link_index",
    "allowed_hosts": [
      "mu-kodomo.kids.coocan.jp"
    ],
    "discovery_depth": 0,
    "default_grade": "全学年",
    "grades": [
      "全学年"
    ],
    "collection_id": "sakurano",
    "collection_root": false,
    "shared_with_ward": false,
    "source_group": "after_school",
    "content_kind": "after_school",
    "id": "sakurano_asobee_public_letters",
    "page_urls": [
      "https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html"
    ],
    "link_patterns": [
      "https://mu-kodomo\\.kids\\.coocan\\.jp/kodomokan/20[0-9]{2}(?:0[1-9]|1[0-2])-12\\.pdf$"
    ],
    "max_documents": 4,
    "feed_group": "notices",
    "coverage_note": "子ども協会の公開一覧にある桜野あそべえのおたより。公開月号を表示し、非公開連絡や当月号の存在を推測しません。"
  }
]
```

The final food pattern is intentionally narrower than the initial exploratory check: **2**, excluding the third matched item 食育講習会「お弁当、ここが足りてなかった!?給食に学ぶ弁当設計術」. That article was updated 2026-02-17 and explicitly says its January/February events ended. A broader title filter would reintroduce it.

## Food festival: corrected URL, actual dates, application links

- The supplied [`/area/shokuiku/index.html`](https://www.city.musashino.lg.jp/area/shokuiku/index.html) returned **404**, without a redirect.
- The official live campaign page is [`/area/syokuiku/`](https://www.city.musashino.lg.jp/area/syokuiku/), **200**. Its HTML explicitly says 第６回 and **2026年10月31日（土）**. It contains many videos, food initiatives and historical links; use the narrow city index above for discovery.
- The [festival article, 1055016](https://www.city.musashino.lg.jp/kenko_fukushi/kenko_hoken/syokuiku/torikumi/1055016.html) returned **200**, updated **2026-10-01**, held **2026-10-31 10:00–15:00**, at 武蔵野市立保健センター. Preserve event, update, application opening and deadline as separate dates.
- [Vegetable sandwich/soup application, 1048625](https://www.city.musashino.lg.jp/kenko_fukushi/kenko_hoken/syokuiku/torikumi/1048625.html) returned **200**, updated **2026-09-29**; application **October 1–15**. It targets city residents in grade 3+ who can use a knife; grade 2 and younger can attend with a guardian. The main article and this page disagree on October 1's weekday: the application page prints 水曜日. Retain numeric dates and the source inconsistency; do not silently copy the wrong weekday.
- Lunch tasting and daikon cooking applications now link to the city's contracted [給食・食育振興財団 `/education2/`](https://www.musashinoshi-kyusyoku.jp/education2/), **200**. Its latest section is dated **2026-09-29**, with deadline **2026-10-09** and an email application procedure. Treat this as a reviewed outbound action link. It is HTML on another host, so the city's same-host attachment feature will not expose it automatically. Do not add the entire foundation host to the city's discovery allowlist.
- That foundation page also contains 2025, 2019, 2018 and 2017 sections in the same body. Do not ingest the whole page as one new 2026 event; if a dedicated source is later needed, isolate the newest dated section and exact `www.musashinoshi-kyusyoku.jp` host.
- The current city index exposes the festival and sandwich/soup application, **not** the two older application URLs returned by search (`1048622.html`, `1048623.html`). Those search results are not validated current index discoveries and are not proposed here. The external application form on `logoform.jp` was observed as a link only, not opened or submitted.

## Sports: current original differs from search cache

[市民スポーツフェスティバル, 1039803](https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/1039803.html) returned **200**, updated **2026-09-28**. The original says **令和8年度 第39回**, held **2026-10-12 10:00–15:30** at the 総合体育館 and 陸上競技場. No advance application, free, bring indoor sports shoes; outdoor activities are cancelled in rain. Search had surfaced the same URL with the previous year's 第38回/2025-10-13 content, so the direct current response is the evidence used here.

The other three matches are:

| Article | Displayed update | Event / status |
| --- | --- | --- |
| [SOMPOボールゲームフェスタ](https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/1051276.html) | 2026-09-04 | 2026-09-13; explicitly ended; grades 1–2 with a parent / grades 3–6. |
| [令和8年度市民スポーツデー](https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/1024850.html) | 2026-06-17 | Multiple dates; next after review is 2026-10-18 at 第一・第二・千川, **not 桜野**. Preserve the date-to-school table. |
| [ファミリースポーツフェア2026](https://www.city.musashino.lg.jp/heiwa_bunka_sports/sports_taikengakushu/event_sports/1024690.html) | 2026-04-15 | 2026-04-26; historical by this review date. |

The fifth sports-index link, 市民スポーツ大会・市民スポーツ祭, is excluded by the proposed title filter. Four discoveries must not be advertised as four upcoming activities.

## Asobee: official provenance, school mapping and extraction limit

The [city Asobee article](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/1006778.html) states that operations are entrusted to 公益財団法人武蔵野市子ども協会 and links its website. The operator's [地域子ども館 home](https://mu-kodomo.kids.coocan.jp/kodomokan/) links the reviewed [おしらせ index](https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html). HTTPS works even though the city link uses HTTP. Exact additional host: **`mu-kodomo.kids.coocan.jp`**.

The index is Shift_JIS/CP932 HTML. All 12 anchors say only **PDFダウンロード**; the school name is in the table row and month is in its header. The current generic link parser loses that context. Keep source names school-specific or join row/header text when implementing; do not present 12 indistinguishable citywide cards. PDF body extraction was not tested and no publication day was inferred from a filename.

Observed rows, not a guessed numbering sequence:

| School | Exact current PDF | Per-school filename suffix |
| --- | --- | --- |
| 一小 | [202609-1.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-1.pdf) | `-1.pdf` |
| 二小 | [202609-2.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-2.pdf) | `-2.pdf` |
| 三小 | [202609-3.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-3.pdf) | `-3.pdf` |
| 四小 | [202609-4.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-4.pdf) | `-4.pdf` |
| 五小 | [202609-5.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-5.pdf) | `-5.pdf` |
| 大野田 | [202609-6.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-6.pdf) | `-6.pdf` |
| 境南 | [202609-7.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-7.pdf) | `-7.pdf` |
| 本宿 | [202609-8.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-8.pdf) | `-8.pdf` |
| 千川 | [202609-9.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-9.pdf) | `-9.pdf` |
| 井之頭 | [202609-10.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-10.pdf) | `-10.pdf` |
| 関前南 | [202609-11.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-11.pdf) | `-11.pdf` |
| 桜野 | [202609-12.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-12.pdf) | `-12.pdf` |

Audit-only all-school pattern: `https://mu-kodomo\.kids\.coocan\.jp/kodomokan/20[0-9]{2}(?:0[1-9]|1[0-2])-(?:[1-9]|1[0-2])\.pdf$` gives **12**; the proposed 桜野 pattern gives **1**. Never guess a future month's URL or crawl `katsudou.html` for activity photographs. There are no per-school private club communications in this evidence.

## Education, support and safety: exact article samples

The reviewed [city education-committee root](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kyoikuiinkai/index.html) is a navigation index, and the [school-portal education page](https://www.musashino-city.ed.jp/modules/hp_jpage10/) is guidance (updated 2023-03-20). Neither established a single current public feed literally titled 市教育委員会のお知らせ. For that product category, use the bounded topic roots above plus the already registered admission/assistance roots. Do not claim coverage of school-app/private board messages.

| Topic / live article | Displayed date | Parent relevance / attached material |
| --- | --- | --- |
| [食物アレルギー対応](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/1007036.html) | Updated 2026-08-24 | Consult school, required management/application documents; no PDF linked in inspected body. Preserve medical/school instructions as official guidance. |
| [スマイル給食](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/1050648.html) | Updated 2026-03-26 | Support for enrolled children who find school attendance difficult. Parent notice and invitation PDFs. |
| [武蔵野市の学校給食について](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/1007035.html) | Updated 2026-03-26 | Provision schedule and current fiscal-year plans; elementary milk/meal withdrawal and restart form. Three PDFs. |
| [産地偽装報道について](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/1045640.html) | Published 2023-11-06 | Historical safety notice, one PDF; must not appear as a newly occurring incident. |
| [給食の放射性物質測定](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/kyushoku/1007037.html) | Updated 2018-04-01 | Body mentions a February 2025 operational change despite old displayed metadata. One process PDF, outbound result link; do not invent an update date. |
| [非常変災時の臨時休業等](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/torikumi/1051213.html) | Updated 2026-06-02 | Typhoon/earthquake/heat-alert school closure criteria; essential rules are in the linked PDF. A successful HTML summary alone does not establish full coverage. |
| [通学路合同安全点検](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/torikumi/1020365.html) | Updated 2026-07-15 | Guardian route-safety actions; FY2024 and FY2025 reports. Two PDFs; no historical recursion needed. |
| [感染症による出席停止](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/gakkou_kansen.html) | Updated 2016-07-29 | Return-to-school certificate linked. Body includes newer disease content despite old metadata; reference with provenance, not a 2026 notice. |
| [災害共済給付制度](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/1007031.html) | Updated 2022-04-01 | Seven claim/form PDFs; reference, preserve original date. |
| [コロナによる学級閉鎖等の基準](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/hoken/1033795.html) | Updated 2023-05-10 | Standing closure criteria; no linked PDF. Not evidence that a class is presently closed. |

Optional bounded calendar root already reviewed: [`gaiyo_nittei/index.html`](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/gaiyo_nittei/index.html), HTTP 200. Pattern `(?s)始業式・終業式.*https://www\.city\.musashino\.lg\.jp/shussan_kodomo_kyoiku/sho_chugakko/gaiyo_nittei/[0-9]+\.html$` on host `www.city.musashino.lg.jp` gives **2**. Current FY2026 [1034938](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/gaiyo_nittei/1034938.html) is updated **2025-11-10**, while FY2025 [1030839](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/gaiyo_nittei/1030839.html) is updated **2024-11-13**. Keep the older year collapsed; do not infer publication year from fiscal year.

## Body-container and attachment pitfalls

- **No literal `bodycontainer` selector was observed** in the checked city sports article, school topic indexes, or operator index. Current city HTML uses `main[role=main] > article#content`; the food index uses `article#content3` inside `main`. Requiring only `#bodycontainer` or only `article#content` would lose valid content. The existing main parser returned nonempty bodies for all 19 proposed/optional city detail candidates.
- The operator's notice list uses **`div#contents`**, with no `main` or `article#content`. The current main-text parser returned **0 characters** there. Use the reviewed PDF link index; do not add it as `html_page` or claim the current body attachment extractor can read that container.
- ICtea school/portal pages use `div#hp_jpageN_read`. The school-portal homepage is not a city notice feed: it mostly exposes school diaries and directory links. No diary detail, photo, protected parent page or login was accessed.
- Full-page link discovery includes navigation, so path/host/title restrictions remain necessary even when body attachment extraction is scoped. Index dates belong to the index: the food root shows 2023-10-17 while its current festival article shows 2026-10-01.
- The new attachment feature can retain same-host original links without reading them. Keep its original-only note for PDF/image/Word/Excel and unreadable files. Do not infer page count, readability, an attachment publication date, or equivalence of different URLs from a filename or byte length.
- Image links may be stock illustrations or event photographs, not documents. Record only links needed by the product; do not download or classify photographs as guardian action documents. Current festival body labels several images as illustrative.
- External action links are distinct from attachments. The festival's foundation application page and external form must remain visible through the original article or an explicitly reviewed action-link presentation; do not silently widen discovery.

### Important attachment URLs

All are observed links in the reviewed original HTML. **HEAD 200/PDF** means headers only; all other rows are **linked, body not fetched**.

| Source / attachment | Exact original link | Evidence |
| --- | --- | --- |
| 食育フェスタ flyer | [20290925_02.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/055/016/20290925_02.pdf) | HEAD 200/PDF, 2,355,765 bytes. Filename is not a publication date. |
| Special-page flyer | [festa_2026.pdf](https://www.city.musashino.lg.jp/area/syokuiku/img/festa_2026.pdf) | HEAD 200/PDF, 2,355,765 bytes; same length does not prove identical content. |
| Sports festival flyer | [39sfes.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/039/803/39sfes.pdf) | HEAD 200/PDF, 361,247 bytes. |
| Sports venue map | [39annai.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/039/803/39annai.pdf) | HEAD 200/PDF, 1,768,411 bytes. |
| 桜野 Asobee September letter | [202609-12.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-12.pdf) | HEAD 200/PDF, 1,221,250 bytes; monthly label established by HTML table. |
| Emergency closure criteria | [hensai20262.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/051/213/hensai20262.pdf) | HEAD 200/PDF, 425,002 bytes. |
| Smile lunch parent notice | [R8oshirase.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/050/648/R8oshirase.pdf) | HEAD 200/PDF, 643,280 bytes. |
| Smile lunch invitation | [invitation_smile.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/050/648/invitation_smile.pdf) | Linked, body not fetched. |
| Elementary milk/meal withdrawal/restart | [R8jitai_p.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/007/035/R8jitai_p.pdf) | Linked, body not fetched. |
| Return-to-school certificate | [toukoukyokasyoumei.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/007/030/toukoukyokasyoumei.pdf) | Linked, body not fetched. |
| School-route safety FY2025 report | [0714.pdf](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/020/365/0714.pdf) | Linked, body not fetched; FY2024 sibling `R6result.pdf` also linked. |

## Avoid broad education archives

The [教育委員会資料 index](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kyoikuiinkai/shiryo/index.html), HTTP 200, exposes **16 numeric detail links**: surveys, annual reports, history, newsletters and a committee report. Do **not** use a generic `kyoikuiinkai/.*` pattern as a guardian-news source.

- [きょういく武蔵野 令和元年度～8年度](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kyoikuiinkai/shiryo/1025688.html), updated **2026-09-24**, has **22 distinct PDF links**, issues 139–160. Latest issue is **160号, 2026-07-31**, not a September issue. This is a mixed multi-year archive, not 22 fresh notices.
- [令和8年度武蔵野市の教育](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kyoikuiinkai/shiryo/1054968.html), published **2026-09-01**, links **11 PDFs**, including a **7.2 MB** full report plus overlapping chapter files. [Full report link](https://www.city.musashino.lg.jp/_res/projects/default_project/_page_/001/054/968/00zentai.pdf) was recorded only; page count and body were not fetched. Do not download/summarize the full report and all chapters during a normal parent-feed refresh.
- Keep any future education-newsletter addition separate and bound it by actual issue label/date. The existing candidate sort uses filenames/numeric IDs and title, so merely setting `max_documents: 1` does **not** guarantee the latest issue.
- Safety guidance's two report PDFs and health guidance's seven form PDFs are manageable **detail attachments**, not seven or two new parent alerts. Public URL reachability does not establish a new publication.

## Verification outcome and implementation handoff

Validated against the repository's parser and live HTML: final food **2**, sports **4**, city Asobee **1**, lunch **5**, health **3**, safety **2**, optional calendar **2**, operator all-school audit **12**, 桜野-only **1**. All 19 city detail URLs from these final/optional patterns were HTTP 200 with nonempty main-body extraction. Operator HTML body extraction remains unsupported by the current main parser; its direct PDF discovery works. Seven priority attachment HEAD checks were 200/application/pdf; PDF content, OCR and image rendering were deliberately not tested.

Before reporting this expansion as delivered, the main task should validate its updated detail attachments and final parent UI on the selected school, with food deadlines, 2026 sports dates, September Asobee labeling, old health/reference dates and the external festival application route intact. This report supplies bounded source specs and original-link evidence; it makes no deployment or delivery claim.

