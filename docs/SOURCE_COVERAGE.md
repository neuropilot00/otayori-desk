# Public source coverage evidence — 2026-10-01

Checked on 2026-10-01 (Asia/Tokyo) using ordinary, unauthenticated HTTP GETs of the official pages below. Web search was used to locate the correct 瀬田中 site; direct HTTP then verified it. External pages were treated as data, not instructions. No private messages, account areas, application submissions, or club communications were accessed.

This change owns only `sources.json` and this report. The collector implementation is being integrated separately. Registry validation, public availability, successful link discovery, and successful body extraction are different checks; a downloadable image-only PDF is not an absent notice.

## Registry contract

- Existing source IDs and school selections are retained. There are 36 source records, including 12 distinct Musashino elementary-school collections, a library sibling, 12 facility references, and five scoped `link_index` sources. No static facility text remains.
- `mixed`: collect the registered root's article body and its PDF links. `sakurano_library` belongs to `collection_id: sakurano`, `collection_root: false`.
- `link_index`: discover article links matching `link_patterns` against title plus absolute URL; do not ingest the list itself. Patterns restrict both the public host and reviewed URL subtree; parent/child program sources also filter titles. These registered lists have direct article links, so `discovery_depth: 0` is intentional with the current collector: discover direct links without recursively scanning articles for more links. The supported depth ceiling remains two.
- `allowed_hosts` contains exact public hostnames, never wildcards. School downloads checked here stay on their root host; no CDN, authentication, or API host exception was required.
- Facility sources use live `html_page`, `coverage_kind: reference`, and an honest Japanese `coverage_note`. They do not represent monthly newsletters or private communications.
- General municipal and after-school notices use `shared_with_ward: true`. They belong to the Musashino sibling collection but should also appear for other same-ward school and club selections. Individual facility references are not shared across the whole ward.
- Limits are explicit: library 20; parent events 40; program news 20; education notices 40; children's-center events 30; shared club notices 20; each facility one. No root currently reaches its cap.

## Four schools previously returning zero

All four roots and the representative PDFs below returned HTTP 200 directly. The web search/open service returned 403 for some Schoolweb pages, so that service's response was not treated as evidence that public HTTP access was impossible.

| Source | Registered root | Observed public material | Required handling |
| --- | --- | --- | --- |
| 芝浦小 | [学校だより](https://shibaura-es.minato-tky.ed.jp/gakkoudayori) | Four text-labelled PDF links: September, July, June, May. Image-alt links expose more files; the updated collector found 11 URLs on the first page. | `/file/{number}` is an extensionless PDF route. Read image `alt` when the anchor has no text. Eleven URLs are not necessarily eleven distinct issues: two winter-issue URLs have matching extracted contents. |
| 桜町小 | [配布文書](https://school.setagaya.ed.jp/sachi/document) | Four school newsletters: September, June, May, April; the home page also links the same four. | `/sachi/download/document/{number}`; all four are image-only for the tested text extractor. |
| 神南小 | [学校だより](https://shibuya.schoolweb.ne.jp/1310231/page/frm5e49ee9d22f62) | Five first-page PDFs: October school and grade editions, September school and grade editions, summer issue. October PDFs show publication on September 30. | `/1310231/download/document/{number}`; links are already in the server HTML. |
| 瀬田中 | [瀬田中だより](https://school.setagaya.ed.jp/tseta/page/school_mail) | Five first-page PDFs: September, July, June, May, April. September is published September 7. | `/tseta/download/document/{number}` and the title filter `瀬田中だより`. |

The previous 瀬田中 registry URL, `https://school.setagaya.ed.jp/tseya`, identifies **世田谷中学校**, a different school. The correct [瀬田中 homepage](https://school.setagaya.ed.jp/tseta) links to `page/school_mail`. The source ID and school name were preserved while the root and title filter were corrected. The general `/tseta/document` endpoint returned 403 in this check; the school's linked newsletter page returned 200 and is the registered root.

Representative document evidence:

| Official URL | Observed response | Body evidence |
| --- | --- | --- |
| [芝浦 R8 9月号](https://shibaura-es.minato-tky.ed.jp/file/7798) | 200, `application/pdf`, `%PDF-1.7`, 714,115 bytes, 4 pages | Text includes the school name and 令和8年度9月号. Other text-labelled IDs: 7792, 7775, 7767. |
| [桜町 学校だより9月号](https://school.setagaya.ed.jp/sachi/download/document/18538482?tm=20260903084119) | 200, `application/pdf`, `%PDF-1.4`, 709,639 bytes, 4 pages | `pypdf` returned zero characters on all pages. June ID 18293734: 4 pages; May 18275430: 5; April 18257508: 4. All 17 pages across these four PDFs returned zero characters. |
| [神南 学校だより10月号](https://shibuya.schoolweb.ne.jp/1310231/download/document/18679086?tm=20260930120011) | 200, `application/pdf`, `%PDF-1.7`, 1,027,706 bytes, 2 pages | Extractable text discusses the 青山キャンパス move. The [各学年 edition](https://shibuya.schoolweb.ne.jp/1310231/download/document/18679087) is a separate link on the same root. |
| [瀬田中だより9月号](https://school.setagaya.ed.jp/tseta/download/document/18540195?tm=20260907150938) | 200, `application/pdf`, 4 pages | Page text lengths 1,474 / 1,414 / 2,027 / 758; school name and 令和8年9月7日 are present. |

Adapter handoff: in addition to normal `.pdf` links, the observed routes require matching `r"/(?:file|download/document)/\d+/?$"` against `urlparse(url).path`, followed by bounded GET and PDF content validation. School path prefixes naturally precede this match. Existing `/plugin/attachments/`, `/file/get/`, and `/files/download/` patterns do not cover these routes. No Schoolweb JSON API, browser automation, session, or new `schoolweb` mode is necessary for the current first-page newsletters. The CMS uses JavaScript/Livewire elsewhere, but these links are server-rendered. Historical pagination was not crawled.

桜町 requires an additional extraction decision outside this registry change: preserve a clearly labelled original-PDF entry with its observed title and extraction warning, or implement OCR. Do not manufacture article text, treat OCR as already available, silently replace it with unrelated text, or report zero published newsletters. No OCR was performed in this investigation.

## Sakurano library and HTML notices

[図書館だより](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage38/) returned 200. The article container is **`div#hp_jpage38_read`**, inside `#mainColumn .sub_box`. The school home page's announcement container is **`div#hp_jpage1_read`**. The general pattern is `hp_jpage\d+_read`; selecting the whole page would include navigation and footer text.

The library article contains the literal HTML notice `読書旬間 9/25～10/9`. `本てるニュース NO.2` is text without a document link in the inspected body. There are seven linked PDFs: 桜野文庫 for grades 1–6, plus 本てるニュース No.1. For example, [grade 1](https://sakurano-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260705203758.pdf) and [No.1](https://sakurano-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260705213654.pdf). The live collector successfully read all seven PDFs and the HTML body: eight entries for 全学年.

The surrounding `p.date` says 公開日 2026-05-31 00:28:24 and 更新日 2026-07-05 21:37:03. Those page metadata do not prove the publication date or year of the reading-period notice. Do not invent a September/October publication date, assume the upload filename is a publication timestamp, or relabel the page as an October newsletter. Image-only content is not converted into text by registering `mixed`.

## Dynamic public lists and verified current articles

All list roots below returned 200. Counts are deduplicated URL candidates matching the exact new registry patterns on the inspected first page. They describe these registered lists, not all city communications. Each candidate was subsequently read by the local collector with no warnings and no limit reached.

| Source / official list root | Matched / read | Scope |
| --- | --- | --- |
| [野外活動センター イベント](https://www.musashino.or.jp/yakatsu/1001959/1001960/index.html) | 8 / 8 | Parent/child, school, teen, and astronomy program titles in this event subtree. |
| [武蔵野プレイス イベント](https://www.musashino.or.jp/place/1001585/index.html) | 7 / 7 | Parent/child, school, youth, and YA titles. Archive-index links are excluded. Together with the preceding root: 15 entries for `sakurano_musashino_events`. |
| [野外活動センター お知らせ](https://www.musashino.or.jp/yakatsu/1001959/1001961/index.html) | 2 / 2 | Recruitment/program announcements. |
| [入学・転校手続き](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/nyugaku_tenko_tetsuzuki/index.html) | 16 / 16 | School admission, transfer, health-check, and parent guidance. |
| [就学援助](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/shugakuenjo/index.html) | 4 / 4 | Education support. Together with the preceding root: 20 entries for `musashino_education_notices`. |
| [桜堤児童館 イベント](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/event_kodomokatei/event_sakurazutsumijidokan/index.html) | 17 / 17 | Public children's-center events, including preschool-age events; each article retains its target age/residency conditions. This is not a club-message feed. |
| [地域子ども館学童クラブ](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/index.html) | 9 / 9 | Public application, rules, facility overview, and related city notices. Includes older-year applications with their original years. |

Specific current evidence, fetched from the live articles:

- [令和9年度学童クラブ入会申請](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/1054987.html): 掲載日 **2026-10-01**; simultaneous admission application period **2026-10-13–2026-11-13**. The year in the title is the admission year, not the publication year. The source contains an inconsistent weekday for a later March 11 deadline; do not silently infer or repair that weekday from scraped prose.
- [学校生活 はじめの一歩 就学支援シート](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/nyugaku_tenko_tetsuzuki/1020412.html): updated **2026-09-28**, for children entering municipal elementary schools in 令和9年度; optional support handover to school/あそべえ/学童 is described.
- [新入学児童の就学時健康診断](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/nyugaku_tenko_tetsuzuki/1007009.html): updated **2026-08-17**, for April 2027 entrants. The school-by-school schedule lists 桜野小 on **2026-11-19**; the page is not published November 19.
- [児童館・今月の行事予定](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/event_kodomokatei/event_sakurazutsumijidokan/1048441.html): updated **2026-09-28**; October activities and the October PDF are linked. [じどうかんまつり](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/event_kodomokatei/event_sakurazutsumijidokan/1024873.html) has the same update date and takes place **2026-10-21**, for preschoolers with guardians, elementary pupils, and junior-high pupils.
- [10月1日募集開始のプログラム](https://www.musashino.or.jp/yakatsu/1001959/1001961/1010094.html): updated **2026-09-28**; the heading's October 1 is the recruitment start, not its publication date.
- The original three event URLs remain discoverable: [親子収穫体験](https://www.musashino.or.jp/yakatsu/1001959/1001960/1010072.html), [森林体験教室 入門編2](https://www.musashino.or.jp/yakatsu/1001959/1001960/1010071.html), and [世界を知る会ジュニア](https://www.musashino.or.jp/place/1001585/1009916.html). The last is updated **2026-09-28**, held **2026-11-21**, and targets local grades 1–3 with a guardian. The harvest event is **2026-11-22** with an **October 14** application deadline; its event date must not become a publication date.

The event title filters deliberately cover a subset relevant to families. A future family event with a different title may need a reviewed pattern extension. New numeric article IDs within the scoped public lists require no registry edit. The empty education-support-center event list and the education-support division list containing only an older 令和7年度 event were inspected but not added as supposed current content.

## Twelve live facility references

Every facility below returned 200, with its own club name, location, hours, and eligibility in the main HTML content. Each reports **2025-04-04** (更新日 for 一小, 掲載日 for the other eleven). Fetching it today does not make its content newly published. These are reference cards, not evidence of twelve club newsletter feeds.

| Club | Verified official facility URL |
| --- | --- |
| 一小 | [1000403](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000403.html) |
| 二小 | [1000404](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000404.html) |
| 三小 | [1000405](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000405.html) |
| 四小 | [1000406](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000406.html) |
| 五小 | [1000407](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000407.html) |
| 大野田 | [1000408](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000408.html) |
| 境南 | [1000409](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000409.html) |
| 本宿 | [1000410](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000410.html) |
| 千川 | [1000411](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000411.html) |
| 井之頭 | [1000412](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000412.html) |
| 関前南 | [1000413](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000413.html) |
| 桜野 | [1000414](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000414.html) |

These URLs were extracted from the city's facility navigation, not constructed by assuming a number sequence. The first, 大野田, 境南, and 関前南 records previously all pointed to a general club overview while using static text; they now point to their individual official pages. Static titles/text, including hard-coded dates, were removed for all twelve.

There are material inconsistencies between these older pages and the [city's club overview](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/1006775.html), which is updated **2026-10-01** and labels its facility table **令和8年7月2日現在**:

- 井之頭 facility page: 吉祥寺本町3-27-19, 井之頭小校舎内. Newer overview: 中町3-9-5, 一中敷地内体育館棟.
- 桜野 facility page phone: 0422-55-5546. Newer overview: 0422-53-3404.
- 境南 and 関前南 overview entries also specify an additional adjacent lot not listed on their older facility page.

The registry does not claim these conflicts are resolved. Its reference note directs users to the city overview for relocation details; that overview is also discovered by `musashino_gakudo_notices`. The new registry fetches actual source text and preserves provenance instead of maintaining a fabricated current facility card. Real-time per-club communications remain outside public coverage.

## Validation and remaining integration checks

- `load_sources(Path("sources.json"))`: 36 unique source IDs; 12 `reference` records; zero `static` records. Existing collection/school counts and known modes validate.
- `.venv/bin/python -B -m unittest tests.test_web_catalog.SourceRegistryTests -v`: **7 passed** against the concurrently integrated schema.
- `git diff --check -- sources.json`: passed after the registry edit.
- Every `link_patterns` expression was loaded from the saved JSON, checked for accidental doubled regex backslashes, and passed to `CatalogService._scoped_links` against freshly fetched real pages. Matched counts were **8+7 / 2 / 16+4 / 17 / 9**. The JSON text `\\.` decodes to the correct regex `\.`; no overescaped domain expression was present in the final file.
- Uncached, direct `CatalogService._scan_source` with `web_catalog_cache_path=None`, `全学年`, 15-second timeout and 10 MB document cap: library **8/8**, parent events **15/15**, program news **2/2**, education notices **20/20**, children's-center events **17/17**, shared club notices **9/9**; no warnings or limits reached. No production cache, notification delivery, or deployment was invoked.
- School integration check after `/file/{number}` support: 芝浦 **11 discovered / 11 read**, no catalog warnings; `pypdf` emitted rotated-text warnings for some archived files. In that same code snapshot, `/download/document/{number}` was still rejected by `_is_document_url`, so 桜町・神南・瀬田 still returned zero. The exact additional route and live evidence were handed to the collector owner. This is an adapter limitation, not zero public content.
- Remaining acceptance checks: rerun the three Schoolweb sources after the route change; show 桜町's original PDFs with explicit unreadable-body state or verified OCR; verify same-ward school/club filtering and the final UI/deployment separately. Registry research alone does not establish those product-level outcomes.
