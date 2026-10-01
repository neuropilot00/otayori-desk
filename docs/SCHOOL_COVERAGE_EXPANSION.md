# Musashino school public-source coverage expansion

Verified from official sites on **2026-10-01 (Asia/Tokyo)**. This work owns only `sources.json` school records and this report. No deployment, notification delivery, commit, subscription enrollment, or production-cache write was performed.

## Final bounded scope and handoff

- Registry at handoff: **55 sources**, up from 36: **19 new sibling source IDs**, preserving all existing IDs, default grades, grade lists, and the **12 Musashino elementary-school collections**.
- The new siblings contain **26 roots: 22 newly registered roots and 4 roots moved out of Sakurano's original source**. Sakurano's old common-page root was removed from PDF discovery because it has no PDF links or current announcements.
- Scope/limit changes to the existing `sakurano`, `musashino_dai1_es`, `musashino_dai2_es`, and `musashino_dai4_es` records carry **`notification_revision: coverage-20261001b`**. New IDs use the application's first-discovery baseline behavior. This audit does not exercise or send push notifications.
- Every new sibling has its existing school's `collection_id`, `collection_root: false`, `source_group: school`, `feed_group: notices`, and `discovery_depth: 0`. Existing school/grade IDs are unchanged. No municipality records were edited; the parent task may now add its city roots.
- This is verified coverage of selected public school materials, **not all school pages or all parent communications**.

## Exact registered additions and live extraction sample

The table records the **live current-material sample audited before the final removal of year filters**: discovered / successfully extracted by the real uncached collector, with the default grade. A readable HTML body counts as one item for `mixed`/`html_page`; remaining items are PDFs. Failed PDF extraction leaves an explicit `original_only` record and is not counted as successful extraction. All 19 sources have at least one substantive, successfully extracted item. The final registry also admits older and future-year filenames, with the same independent caps; final discovery and limit results are below. Do not treat this sample as the final full audit.

| Source ID | Official registered root(s) | Mode / cap | Discovered / extracted |
| --- | --- | --- | --- |
| `sakurano_health` | [hp_jpage14/](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage14/) | pdf / 16 | 5 / 5 |
| `sakurano_meals` | [hp_jpage27/](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage27/) | pdf / 24 | 10 / 10 |
| `sakurano_new_students` | [hp_jpage28/](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage28/) | mixed / 16 | 14 / 14 |
| `sakurano_parent_contact` | [hp_jpage10/](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage10/) | mixed / 4 | 2 / 2 |
| `sakurano_home_documents` | [home](https://sakurano-e.musashino-city.ed.jp/) | pdf / 6 | 2 / 2 |
| `musashino_dai1_es_parents` | [hp_jpage27/](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage27/)<br>[hp_jpage19/](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage19/)<br>[hp_jpage33/](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage33/)<br>[home](https://dai1-e.musashino-city.ed.jp/) | pdf / 10 | 5 / 4 |
| `musashino_oonoden_es_parents` | [hp_jpage12/](https://oonoden-e.musashino-city.ed.jp/modules/hp_jpage12/) | pdf / 4 | 1 / 1 |
| `musashino_sekimaeminami_es_parents` | [hp_jpage27/](https://sekimaeminami-e.musashino-city.ed.jp/modules/hp_jpage27/) | pdf / 4 | 2 / 2 |
| `musashino_dai3_es_health` | [hp_jpage4/index.php?page_parent=1009](https://dai3-e.musashino-city.ed.jp/modules/hp_jpage4/index.php?page_parent=1009) | pdf / 16 | 5 / 4 |
| `musashino_dai3_es_parents` | [hp_jpage22/](https://dai3-e.musashino-city.ed.jp/modules/hp_jpage22/) | mixed / 8 | 6 / 4 |
| `musashino_dai4_es_parents` | [hp_jpage9/](https://dai4-e.musashino-city.ed.jp/modules/hp_jpage9/) | pdf / 6 | 3 / 3 |
| `musashino_dai5_es_parents` | [hp_jpage12/](https://dai5-e.musashino-city.ed.jp/modules/hp_jpage12/)<br>[home](https://dai5-e.musashino-city.ed.jp/) | pdf / 12 | 7 / 7 |
| `musashino_honjuku_es_meals` | [hp_jpage2/index.php?page_parent=368](https://honjuku-e.musashino-city.ed.jp/modules/hp_jpage2/index.php?page_parent=368) | pdf / 12 | 6 / 6 |
| `musashino_honjuku_es_parents` | [hp_jpage2/](https://honjuku-e.musashino-city.ed.jp/modules/hp_jpage2/) | pdf / 4 | 1 / 1 |
| `musashino_senkawa_es_health` | [hp_jpage3/index.php?page_parent=137](https://senkawa-e.musashino-city.ed.jp/modules/hp_jpage3/index.php?page_parent=137)<br>[hp_jpage3/](https://senkawa-e.musashino-city.ed.jp/modules/hp_jpage3/) | pdf / 16 | 8 / 8 |
| `musashino_senkawa_es_parents` | [hp_jpage22/](https://senkawa-e.musashino-city.ed.jp/modules/hp_jpage22/)<br>[home](https://senkawa-e.musashino-city.ed.jp/) | pdf / 10 | 6 / 6 |
| `musashino_inokashira_es_parents` | [hp_jpage13/](https://inokashira-e.musashino-city.ed.jp/modules/hp_jpage13/)<br>[home](https://inokashira-e.musashino-city.ed.jp/) | pdf / 16 | 11 / 11 |
| `musashino_inokashira_es_health` | [hp_jpage29/](https://inokashira-e.musashino-city.ed.jp/modules/hp_jpage29/) | html_page / 1 | 1 / 1 |
| `musashino_inokashira_es_new_students` | [hp_jpage30/](https://inokashira-e.musashino-city.ed.jp/modules/hp_jpage30/) | pdf / 4 | 1 / 1 |

Live sample for new IDs: **96 discovered records, 92 with extracted text, 4 original-only PDFs**. These are not 96 wholly new documents: some Sakurano documents were moved into independent budgets, and reference sources contain older documents still linked by the school. After year-filter removal, these 19 IDs discover **264 unique candidate records**, with **127 selected by their caps** on the same fetched pages. Extra historical PDFs admitted by that final policy were not all extracted in this task; the parent owns the full final audit.

The successful HTML bodies are Sakurano admission preparations and absence-contact instructions, Third School's parent guidance, and Inokashira's infection-related return-to-school instructions. They contain relevant instructions and were checked for navigation contamination. **No school homepage is registered as `html_page` or `mixed`**: homepage main-area parsers can capture diary previews or omit the announcement area. Homepage roots here discover selected PDFs only.

### Existing sources whose scope changed

| Existing source | Final change | Live sample discovery / extracted |
| --- | --- | --- |
| `sakurano` | Only [school/grade newsletters](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/) remain in the main source; original cap 40 retained, no year filter. Health, meals, admissions and homepage PDFs now have independent caps. [Absence guidance](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage10/) is newly added. | 13 / 13, grade 1 |
| `musashino_dai1_es` | [School and health newsletters](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage14/) share one page and month-only anchors. Retain one root, remove misleading health exclusion, no year filter, cap 28. | 13 / 12 |
| `musashino_dai2_es` | [Public handouts](https://dai2-e.musashino-city.ed.jp/modules/hp_jpage5/) include school/open-day/sports-day/emergency documents plus linked admission/health/app handbooks. Topic matching without a year filter; one root, cap 24. | 12 / 11 |
| `musashino_dai4_es` | [Daishi, Hanamizuki and health letters](https://dai4-e.musashino-city.ed.jp/modules/hp_jpage3/) share one page. Keep the single root, no year filter, cap 30; formerly 14 links competed for cap 12. | 14 / 9 |

First and Fourth School health PDFs were not reliably excluded previously: their anchors are month names without the health category. These changes bound and make their existing mixed pages explicit; they must not be represented as entirely new health feeds.

Across **23 changed/new sources**, the initial live sample was **148 records, 137 extracted, 11 original-only** after duplicate removal. Final year-independent discovery on the saved live pages is **381 candidate records / 232 selected**, with these honest cap limits:

| Source | Final discovered / selected | Limit reached |
| --- | --- | --- |
| `sakurano` | 39 / 39 | No |
| `musashino_dai1_es` | 37 / 28 | Yes |
| `musashino_dai2_es` | 27 / 24 | Yes |
| `musashino_dai4_es` | 14 / 14 | No |
| `sakurano_health` | 18 / 16 | Yes |
| `sakurano_meals` | 143 / 24 | Yes |
| `musashino_honjuku_es_meals` | 28 / 12 | Yes |

Other changed/new sources retain the table's discovery counts and do not reach their caps. The candidate totals are deduplicated URLs, not raw anchor counts. Limits mean older material may be outside this fetch, not that the source is empty. Previously stored history is not deleted by this registry change.

## Twelve-school review and unavailable coverage

All 12 registered official homepages were fetched, together with the 11 linked CMS sitemaps, selected relevant category pages and bounded detail follow-ups. Fourth School's sitemap was not linked from its homepage; its navigation and known CMS sitemap endpoint were checked. Sakurano's [homepage](https://sakurano-e.musashino-city.ed.jp/) and [sitemap](https://sakurano-e.musashino-city.ed.jp/modules/hp_jsitemap/) were checked first.

| School | Added/clarified coverage | Relevant gaps at inspection |
| --- | --- | --- |
| 桜野 | Separate health and meals/food education; admission preparations, absence-contact instructions, two common learning-policy PDFs. Existing library source retained. | [Common page](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage16/) has no PDFs, only 2021 video-use guidance and a diary link; removed as an empty PDF source. Grade newsletters are combined multi-grade sheets on the existing newsletter page, not separate per-grade roots. |
| 第一 | Current school/health letters; mobile-device permission, contact-app guide, school handbook, emergency pickup and entrance-lock guidance. | No separate current menu or per-grade newsletter root found in reviewed navigation/sitemap. October health letter and school handbook are image PDFs requiring OCR. |
| 第二 | Current handouts expanded to public parent guides, emergency closure criteria and special school notices. | [Health room](https://dai2-e.musashino-city.ed.jp/modules/hp_jpage25/) exposes an older R7 school-health committee document, not a current monthly feed; not added. Parent-announcement page is marked protected and was not accessed. Menu results in reviewed navigation are diary categories. |
| 第三 | Current health-letter detail and substantive public parent guidance, with handbooks/forms/manuals. | Legacy health link points to an obsolete `andteacher.jp` hostname with a trailing dot in the article ID. The modern official sitemap supplies the working numeric article URL. One health PDF and two parent PDFs cannot be fully extracted locally. |
| 第四 | Current school/health/special-support letters; emergency response, closure criteria and app guide. | All five inspected health PDFs require Japanese OCR. No separate current menu/per-grade newsletter root found. |
| 第五 | Public admission booklet, bus guide/forms, updated annual calendar, app and school rules. | Legacy health detail link is broken/obsolete; the corresponding modern article has no body/PDFs, so no health source was added. Bus timetable is explicitly distributed through the parent app and was not accessed. |
| 大野田 | Public parent-contact application manual. | [Admission page](https://oonoden-e.musashino-city.ed.jp/modules/hp_jpage38/) embeds a readable R8 booklet with `<embed>`, not an anchor. Current document discovery finds zero there, so it was not registered as working. No separate current health/menu/grade feed found. |
| 境南 | Existing school-news source preserved; **no new working source added**. | [Meal page](https://kyounan-e.musashino-city.ed.jp/modules/hp_jpage8/) links 2025 menus and old recipe/video pages, not verified current-year menus. [R8 admission page](https://kyounan-e.musashino-city.ed.jp/modules/hp_jpage16/) has two readable embedded PDFs, but current discovery finds zero anchors; not registered. No separate current health/grade newsletter root found. |
| 本宿 | Current monthly menu PDFs and public emergency travel guidance. | [Health page](https://honjuku-e.musashino-city.ed.jp/modules/hp_jpage25/) has no substantive body/PDF links. Parent page is marked protected. Daily lunch photo diaries and PTA pages were excluded. |
| 千川 | Current health letters, reusable rhythm checklist, public parent manuals, handbook, annual and open-day schedules. | School page explicitly says grade letters are incorporated into the school newsletter from R6. Under the R8 learning-plan heading, the first-grade PDF is actually titled **R7 第1学年 年間指導計画**; those six old standalone plan links were not relabeled or added as current grade newsletters. |
| 井之頭 | Public medical-claim forms, bus guide/forms, emergency closure criteria, infection-return instructions and admission booklet. | Protected parent-contact page excluded. Admission page heading says R7 while its current linked PDF explicitly gives the R8 April 7 entrance ceremony; the registry note preserves that discrepancy. No separate current health newsletter/menu/grade feed found. |
| 関前南 | Public contact-app manual and troubleshooting guide. | School newsletter already contains grade announcements. Staff/printing request form excluded; no separate public current health/menu/grade newsletter root found. |

**After-school scope:** no dedicated school-hosted `あそべえ` newsletter/list root was found in the reviewed homepages/sitemaps. References to after-school activities inside school handbooks do not establish a separately updated public feed. City/club expansion belongs to the parent task. No private app, login, staff area, PTA login, diary archive, photo gallery, or form submission was crawled.

## Extraction limitations (not claimed as complete text coverage)

These 11 PDFs remain explicit original-only links, while their source pages and other content were verified:

| Source | PDF filename / reason |
| --- | --- |
| 第一 school/health | `20260930100402.pdf`: Japanese Tesseract language data missing. |
| 第一 parents | `20260616094850.pdf`: Japanese OCR data missing. |
| 第二 handouts | `20260305230525.pdf`: PDF text extraction failed. |
| 第三 health | `20260501124822.pdf`: Japanese OCR data missing. |
| 第三 parents | `20260202161017.pdf`: 29-page image booklet exceeds the existing 1–6-page OCR limit; another attachment reports the collector's encrypted/over-50-page restriction. No decryption or limit bypass attempted. |
| 第四 school/health | `20260513141419.pdf`, `20260513141652.pdf`, `20260622150835.pdf`, `20260709090103.pdf`, `20260924130558.pdf`: Japanese OCR data missing. |

The direct embedded-PDF research downloads for 大野田 and 境南 extracted meaningful text (R8 admission handbook / preparation list), but **that is not successful registry discovery**. Adding those pages needs explicit embed-link support by the collector owner; this task did not modify collector code or manufacture a static document.

Some successfully parsed PDFs emitted `pypdf` rotated-text/cross-reference repair warnings. Extracted text is useful evidence, not proof of perfect table layout or complete image transcription. No OCR software or language data was installed.

## Bounds, duplicates, dates and grades

- New sources use depth 0 and caps **1–24**; existing changed caps are **24/28/30/40**. There is no site recursion or pagination. The collector additionally bounds page visits and document sizes.
- **No hardcoded annual filename filter remains.** Future monthly/yearly uploads and still-linked old filenames are eligible without a registry year edit. Stable latest-URL sorting and independent source caps bound retrieval; the parent owns timestamp normalization and same-URL update handling. Upload filenames are not publication dates. A same-URL PDF must not be excluded merely because its filename contains an old year; a document outside a cap is a separate, explicitly reported limitation.
- Parent references are the currently linked public manuals/forms; several are older reusable documents. They carry `coverage_kind: reference` and retain original dates. The new school year was not assigned to an old manual merely because it remains linked.
- All **39 registered Musashino school roots** were checked with the saved registry's document matching. **Zero duplicate roots, zero cross-source or within-source duplicate document URLs, and no added PDF root without a matching document.**
- Across the **148 live-sampled records**, no repeated URL or nonempty content hash remains **within a school collection**. Final discovery after year-filter removal also has zero duplicate URLs across sibling sources. First School's homepage manual `20230512091831.pdf` had exactly the same bytes as its parent-page `20230426123323.pdf`; the former is excluded as a verified duplicate, not because of its year. A later upstream replacement of either duplicate/version-specific excluded file would warrant rechecking that choice.
- Fifth School's homepage still links an older March annual calendar `20260320165157.pdf`; keep the category page's July update `20260709171336.pdf`, excluding the older calendar. This was a version choice, not a claim that their bytes are identical.
- Existing grade lists were preserved. New health/meal/forms sources are common-reference sources with `grades: ["全学年"]`; no unrelated grade-specific monthly feed was added.
- Live Sakurano school/grade extraction succeeded for **grade 1 and grade 6: 13 items each, no warnings**. Existing Sakurano library yielded **3 items each** for grades 1 and 6: the relevant grade's book list, common news PDF, and library HTML; other grades were absent. The parent task owns the pre-cap grade-filter implementation.
- Homepage announcement bodies were not accepted as generic HTML notices. The registered `mixed` and `html_page` bodies were individually verified as useful parent instructions, without global menus, diary previews, or access counters.

## Validation and release

- `load_sources(Path("sources.json"))`: **55 unique source IDs**; existing IDs/grades preserved; four existing scope changes have `notification_revision: coverage-20261001b`.
- `.venv/bin/python -B -m unittest tests.test_web_catalog.SourceRegistryTests -v`: **7 passed** after the parent updated the old single-source-root assertion to the school-collection union contract. This task did not edit tests.
- Initial live uncached `CatalogService._scan_source` sample: **23 sources / 148 records / 137 extracted / 11 original-only**. New siblings alone: **19 / 96 / 92 / 4**. Final year-independent discovery: **381 candidates / 232 selected**, including **264 / 127** for new IDs; five sources now honestly report a cap. The parent task is conducting the final full audit of the larger selected set.
- Validation used `web_catalog_cache_path=None`, 15-second request timeout and a 10 MB document cap. Research used at most four parallel page fetches; final audit used three source workers and the collector's bounded per-source extraction pool.
- `git diff --check -- sources.json docs/SCHOOL_COVERAGE_EXPANSION.md`: checked at handoff.
- The source registry was released immediately after static-year cleanup for the parent's city/あそべえ additions and full audit. This task will not edit those additions. Counts above describe the **55-source school-expansion handoff**, before those later additions. No claim of deployed UI, universal school coverage, background delivery, or real push verification is made.
