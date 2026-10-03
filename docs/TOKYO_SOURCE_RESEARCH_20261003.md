# Tokyo source provenance research — おたより desk

Research date: **2026-10-03 (Asia/Tokyo)**. Research-only sidecar; no registry or application changes, commit, deployment, or guardian-message access.

## Findings

All **12 Musashino municipal elementary schools** are matched to existing registry IDs and official directory links. Their configured primary school indexes returned HTTP 200 in direct checks. This establishes identity and index access, not complete guardian-notice or PDF coverage.

The broader Tokyo sample is deliberately bounded to **six existing registry schools**: four elementary, one middle, and one metropolitan high school, across 港区・文京区・世田谷区・渋谷区. These are purposive examples, not a representative statistical sample, demographic weights, an all-Tokyo inventory, or nationwide collection.

School, Gakudo, and Asobee are distinct publishing/ownership contexts. The provider's public Asobee index exposes 12 September PDF links. Only their labels and links were checked. City Gakudo facility pages and admission instructions do not establish access to enrolled-family notices.

Identity, endpoint reachability, HTML readability, linked-document readability, and audience coverage are recorded independently in the companion JSON. It contains all **75 actual registry source IDs/fingerprints**, with **45 identity-verified source records**, **34 reachable registry endpoints**, and **50 unverified registry endpoints**. Endpoint counts include multiple configured URLs per source and repeat the shared Asobee index per source; they are not counts of distinct pages, schools, or readable PDFs.

## Method and bounded questions

The explicitly requested deep-research workflow was applied to five questions:

1. Which official directory establishes a school's name, municipality, type, and official host?
2. What public notice channel is actually available, and what authenticated guardian boundary is documented?
3. Is grade-specific information observed in an index, in a sampled document, or merely claimed by configuration?
4. Who operates and publishes school, Gakudo, and Asobee information?
5. Which official code schemes can support future stable identity joins?

Official Japanese government, school, and provider pages were used. Current registry entries were read without alteration. Browsing used selected pages and bounded direct HTTPS GETs; no recursive crawl, broad PDF download, login, or private student data collection occurred. Student names, credentials, individual submissions and private messages are not included.

All citation access dates below are actual research-day observations. Publication/update dates are separate and remain unknown when not established. Search-tool crawl metadata was not used as publication time. Direct requests exposed newer school content than cached browser-search extracts; the direct observations take precedence. A tool-specific 403 followed by a successful direct public GET is not an authenticated-content finding.

## Official directory provenance and identity

The [Musashino school portal](https://www.musashino-city.ed.jp/) connects each of the 12 school names to its official school host. The [current city elementary-school directory](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/index.html) independently lists the same 12 names. Both were consulted on 2026-10-03. The portal's displayed directory date is 2017-10-24; it must not be relabelled as a recent publication date.

The [Tokyo Board of Education public-school CSV index](https://www.kyoiku.metro.tokyo.lg.jp/about/statistics_and_research/list_of_public_school/school_lists2025/report2025_csv), updated 2026-01-15 and accessed 2026-10-03, separates elementary, middle, high and other school categories. Its FY2025 statistical files are useful future directory baselines. Their individual rows were not joined here, and they do not establish notice availability or an exhaustive FY2026 census.

### All 12 Musashino elementary schools

Each school below is **東京都・武蔵野市・市立小学校**, operator **武蔵野市**. Every primary index was directly retrieved successfully on 2026-10-03. “City directory entry” means its link was observed in the city listing; individual facility-entry bodies were not all opened. A missing explicit registry collection_id is resolved to the existing source id according to `sakurano_line_notifier/web_catalog.py:634`; the JSON retains the original null separately.

| Existing source_id | Resolved collection_id | School / official links | Public index observation | Grade / guardian boundary | Live page update displayed |
|---|---|---|---|---|---|
| `musashino_dai1_es` | `musashino_dai1_es` | [武蔵野市立第一小学校](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage14/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000566.html) | School and health newsletters; October links observed. | not_observed_in_reviewed_index. No private guardian content reviewed. | 2026-10-01 |
| `musashino_dai2_es` | `musashino_dai2_es` | [武蔵野市立第二小学校](https://dai2-e.musashino-city.ed.jp/modules/hp_jpage5/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000567.html) | Public school letters, parent-app manual and admission guides. | not_observed_in_reviewed_index. Navigation explicitly labels guardian notices protected. | 2026-08-28 |
| `musashino_dai3_es` | `musashino_dai3_es` | [武蔵野市立第三小学校](https://dai3-e.musashino-city.ed.jp/modules/hp_jpage4/index.php?page_parent=109) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000568.html) | Public school newsletter こぶし; September link observed. | not_observed_in_reviewed_index. Guardian content not assessed. | 2026-09-16 |
| `musashino_dai4_es` | `musashino_dai4_es` | [武蔵野市立第四小学校](https://dai4-e.musashino-city.ed.jp/modules/hp_jpage3/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000569.html) | Public school, はなみずき and health newsletters; October school link observed. | not_observed_in_reviewed_index. Do not interpret a themed newsletter as a numbered grade feed. | 2026-10-01 |
| `musashino_dai5_es` | `musashino_dai5_es` | [武蔵野市立第五小学校](https://dai5-e.musashino-city.ed.jp/modules/hp_jpage12/index.php?page_parent=916) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000570.html) | Public school newsletter; August/September latest linked issue observed. | not_observed_in_reviewed_index. Guardian content not assessed. | 2026-09-02 |
| `musashino_oonoden_es` | `musashino_oonoden_es` | [武蔵野市立大野田小学校](https://oonoden-e.musashino-city.ed.jp/modules/hp_jpage4/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000571.html) | Public school newsletter; October link observed. | not_observed_in_reviewed_index. Separate public parent-app manual; app-message contents unreviewed. | 2026-09-29 |
| `musashino_kyounan_es` | `musashino_kyounan_es` | [武蔵野市立境南小学校](https://kyounan-e.musashino-city.ed.jp/modules/hp_jpage3/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000572.html) | Public school newsletter; October link observed. | not_observed_in_reviewed_index. Protected menu observed is for teachers; not evidence of a guardian channel. | 2026-09-30 |
| `musashino_honjuku_es` | `musashino_honjuku_es` | [武蔵野市立本宿小学校](https://honjuku-e.musashino-city.ed.jp/modules/hp_jpage2/index.php?page_parent=126) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000573.html) | Public school-letter index has image-only PDF anchors; PDF URLs extractable but labels/bodies not established. | unverified. Navigation explicitly labels guardian section protected. | 2026-09-30 |
| `musashino_senkawa_es` | `musashino_senkawa_es` | [武蔵野市立千川小学校](https://senkawa-e.musashino-city.ed.jp/modules/hp_jpage19/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000574.html) | Public school newsletter incorporates grade pages; explicit learning-plan links for grades 1–6. | public_links_observed (1–6). Grade plan links are under a FY2026 heading but contain 2025 filenames; body-year verification remains open. | 2026-08-26 |
| `musashino_inokashira_es` | `musashino_inokashira_es` | [武蔵野市立井之頭小学校](https://inokashira-e.musashino-city.ed.jp/modules/hp_jpage2/index.php?page_parent=103) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000575.html) | Public school newsletter; October link observed. | not_observed_in_reviewed_index. 校支援 保護者連絡帳 is explicitly marked protected. | 2026-10-01 |
| `musashino_sekimaeminami_es` | `musashino_sekimaeminami_es` | [武蔵野市立関前南小学校](https://sekimaeminami-e.musashino-city.ed.jp/modules/hp_jpage4/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000576.html) | Public school-letter index titled 学年からのお知らせ; October link observed. | unverified. Sampled August/September PDF is one school-wide page; per-grade bodies not established. Separate public app instructions exist. | 2026-09-24 |
| `sakurano` | `sakurano` | [武蔵野市立桜野小学校](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/) · [city directory entry](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/1000577.html) | School and grade newsletters; October school/grade links observed. | public_document_sample_verified (1–6). School-distributed guardian accounts documented separately; private messages not reviewed. | 2026-09-18 |

“Not observed in reviewed index” is a bounded finding, not evidence that no grade channel exists. Registry grade lists and “全学年” are not independent proof that all grades have public notices.

The [Sakurano October grade PDF](https://sakurano-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260918181117.pdf) was sampled as readable text, with six separate grade headings (1–6). The [Sekimaeminami August/September PDF](https://sekimaeminami-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260827150334.pdf), issued 2026-08-27, is a one-page school newsletter. Its index's grade-related title alone does not establish separate grade-letter coverage. Both PDFs were inspected on 2026-10-03; other school PDF bodies were not exhaustively reviewed.

### Bounded broader Tokyo sample

All six configured public indexes were readable in the research tools or direct requests on 2026-10-03; their linked PDF bodies were not reviewed. Each source's resolved collection_id equals its existing source_id because the registry omits an explicit value.

| Existing source_id | Verified institution / geographic municipality / school type / operator | Official provenance | Public channel | Grade / guardian limits |
|---|---|---|---|---|
| `minato_shibaura_es` | 港区立芝浦小学校; 港区; 小学校; operator 港区 | [directory](https://www.city.minato.tokyo.jp/gakkouuneishien/kodomo/gakko/sho/sho/); [public endpoint](https://shibaura-es.minato-tky.ed.jp/gakkoudayori) | Public school-newsletter index; FY2026 September PDF link observed. | not_observed_in_reviewed_index. Unverified; no authenticated guardian channel reviewed. |
| `bunkyo_seishi_es` | 文京区立誠之小学校; 文京区; 小学校; operator 文京区 | [directory](https://www.city.bunkyo.lg.jp/b003/p006755.html); [public endpoint](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/13,html) | Public school-newsletter index plus separate FY2026 grade-page index. | public_links_observed. Unverified; grade links do not establish complete guardian communication coverage. |
| `setagaya_sakura_machi_es` | 世田谷区立桜町小学校; 世田谷区; 小学校; operator 世田谷区 | [directory](https://www.city.setagaya.lg.jp/01022/10458.html); [public endpoint](https://school.setagaya.ed.jp/sachi/document) | Readable public document index: September newsletter and grade-letter category. Research/teaching-plan documents also present. | category_only. A public notice mentions LoiloNote distribution to pupils; guardian authentication and message coverage not verified. |
| `shibuya_jinnan_es` | 渋谷区立神南小学校; 渋谷区; 小学校; operator 渋谷区 | [directory](https://www.city.shibuya.tokyo.jp/shisetsu/kyoiku-shisetsu/kuritsu-school/shogakkou.html); [public endpoint](https://shibuya.schoolweb.ne.jp/1310231/page/frm5e49ee9d22f62) | October school newsletter and separate 各学年 PDF links, dated 2026-09-30. | public_links_observed_grades_unverified. Unverified. Site displays temporary Aoyama campus from August 2026; directory address is older. |
| `setagaya_seta_jhs` | 世田谷区立瀬田中学校; 世田谷区; 中学校; operator 世田谷区 | [directory](https://www.city.setagaya.lg.jp/01022/10458.html); [public endpoint](https://school.setagaya.ed.jp/tseta/page/school_mail) | Readable 瀬田中だより index; FY2026 September issue dated 2026-09-07. | not_observed_in_reviewed_index. Grade-one activity menu exists; this does not prove a grade-specific notice feed. Private channel unverified. |
| `shibuya_aoyama_hs` | 東京都立青山高等学校; 渋谷区; 高等学校; operator 東京都 | [directory](https://www.toritsuko.metro.tokyo.lg.jp/school/aoyama/); [public endpoint](https://www.metro.ed.jp/aoyama-h/news/news-01/index.html) | Public news combines admissions, events and staff recruitment. Metropolitan full-time general-course high school. | not_observed_in_reviewed_index. Official parent page directs absence communication to Classi and supplies PTA PDF passwords through Classi. Private content not accessed. |

Two distinctions matter for identity and audience:

- 青山高校 is **都立**, located in 渋谷区. Its geographic ward is not its establishing authority. Its [Tokyo education-board profile](https://www.toritsuko.metro.tokyo.lg.jp/school/aoyama/) establishes its full-time general-course status. Its [parent page](https://www.metro.ed.jp/aoyama-h/students.html) explicitly uses Classi for absence communication and PTA PDF passwords. Public news includes applicant and staff topics; “news” is not synonymous with enrolled-family communication. Accessed 2026-10-03.
- 神南小's [public index](https://shibuya.schoolweb.ne.jp/1310231/page/frm5e49ee9d22f62) lists October “各学年” material and displays a temporary Aoyama campus from August 2026. The [ward directory](https://www.city.shibuya.tokyo.jp/shisetsu/kyoiku-shisetsu/kuritsu-school/shogakkou.html), updated 2025-03-24, gives its older address. Keep institutional identity separate from effective-dated campus location. Accessed 2026-10-03.

The [Seishi FY2026 grade index](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/12,0,36,html) exposes links labelled 1–6. Their destination bodies were not reviewed. The Sakuramachi grade-letter category is likewise only category-level evidence.

## School versus Gakudo versus Asobee

| Context | Established publisher/operator | Public information established | Audience / unresolved boundary |
|---|---|---|---|
| School | Each municipal school; metropolitan operator for Aoyama | School indexes, selected public instructions and two sampled PDFs | Grade/institution/purpose must be established per document. Authenticated messages were not accessed. |
| Gakudo / こどもクラブ | City directory plus 公益財団法人武蔵野市子ども協会 provider description | 12 facility links; Sakurano facility body; city programme/admission policy | Normal Musashino admission grades 1–3; disability admission category through grade 6, subject to residence/care conditions. Facility reference is not an enrolled-family notice feed. |
| Asobee / 地域子ども館あそべえ | City policy entrusts operation to 公益財団法人武蔵野市子ども協会; city child/youth division with education-board cooperation | Shared provider index with 12 school-labelled September PDF links | Grades 1–6 under school/catchment selection rules. Public programme letters are distinct from Gakudo messages and school-issued letters. PDF bodies not reviewed. |

Evidence, accessed 2026-10-03: [city Asobee policy](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/1006778.html) (updated 2026-07-02); [city Gakudo policy](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/1006775.html) (updated 2026-10-01); [provider's programme description](https://mu-kodomo.kids.coocan.jp/kodomokan/about.html); [city facility directory](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/index.html); [provider letters index](https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html). City policy links the provider host, independently supporting its provenance.

### Existing after-school IDs and exact observed letter links

All links below were extracted from the provider's labelled September table, not inferred from numerical patterns. `202609` is an issue hint from the filenames; neither a publication timestamp nor a check date. Eleven non-Sakurano Gakudo endpoint bodies remain unverified even though the official city directory confirms the facility identities and URLs.

| Existing school source_id | Gakudo source_id → existing collection_id | Asobee source_id → existing collection_id | Provider PDF: link observed, body unverified |
|---|---|---|---|
| `musashino_dai1_es` | `musashino_dai1_gakudo` → `musashino_dai1_gakudo` | `musashino_dai1_es_asobee_public_letters` → `musashino_dai1_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-1.pdf) |
| `musashino_dai2_es` | `musashino_dai2_gakudo` → `musashino_dai2_gakudo` | `musashino_dai2_es_asobee_public_letters` → `musashino_dai2_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-2.pdf) |
| `musashino_dai3_es` | `musashino_dai3_gakudo` → `musashino_dai3_gakudo` | `musashino_dai3_es_asobee_public_letters` → `musashino_dai3_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-3.pdf) |
| `musashino_dai4_es` | `musashino_dai4_gakudo` → `musashino_dai4_gakudo` | `musashino_dai4_es_asobee_public_letters` → `musashino_dai4_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-4.pdf) |
| `musashino_dai5_es` | `musashino_dai5_gakudo` → `musashino_dai5_gakudo` | `musashino_dai5_es_asobee_public_letters` → `musashino_dai5_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-5.pdf) |
| `musashino_oonoden_es` | `musashino_oonoden_gakudo` → `musashino_oonoden_gakudo` | `musashino_oonoden_es_asobee_public_letters` → `musashino_oonoden_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-6.pdf) |
| `musashino_kyounan_es` | `musashino_kyounan_gakudo` → `musashino_kyounan_gakudo` | `musashino_kyounan_es_asobee_public_letters` → `musashino_kyounan_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-7.pdf) |
| `musashino_honjuku_es` | `musashino_honjuku_gakudo` → `musashino_honjuku_gakudo` | `musashino_honjuku_es_asobee_public_letters` → `musashino_honjuku_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-8.pdf) |
| `musashino_senkawa_es` | `musashino_senkawa_gakudo` → `musashino_senkawa_gakudo` | `musashino_senkawa_es_asobee_public_letters` → `musashino_senkawa_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-9.pdf) |
| `musashino_inokashira_es` | `musashino_inokashira_gakudo` → `musashino_inokashira_gakudo` | `musashino_inokashira_es_asobee_public_letters` → `musashino_inokashira_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-10.pdf) |
| `musashino_sekimaeminami_es` | `musashino_sekimaeminami_gakudo` → `musashino_sekimaeminami_gakudo` | `musashino_sekimaeminami_es_asobee_public_letters` → `musashino_sekimaeminami_es` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-11.pdf) |
| `sakurano` | `sakurano_gakudo` → `sakurano` | `sakurano_asobee_public_letters` → `sakurano` | [observed September link](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-12.pdf) |

The Sakurano Gakudo source remains in the school collection `sakurano`; the other Gakudo records have their own existing collections. Asobee records share school collections. These groupings are application associations, not proof of common publishing ownership. No collection or registry entry was changed.

## Stable identity anchors: facts and future recommendation

### MEXT school codes

[MEXT's school-code index](https://www.mext.go.jp/b_menu/toukei/mext_01087.html), accessed 2026-10-03, presents the **provisional 2026-05-01** edition, published **2026-05-29**, with Excel/CSV downloads and an officially commissioned search site. “Provisional” should remain in provenance.

The [official specification](https://www.mext.go.jp/content/20210128-mxt_chousa01-000011635_01.pdf), decided 2020-12-22 and amended 2021-01-27, defines 13 characters including a type component and check digit. Codes are normally persistent and not reused, but specified exceptions exist. Municipality is not a mandatory component. This supports a future versioned identity join; it does not justify deriving a school's code from a CMS identifier, name or URL.

**No individual MEXT code was mapped in this research.** Every source's `mext_school_code` is null and its mapping status is `not_mapped`. Recommended future work: match official name, type, operator and address to an official dataset row; retain dataset edition, exact row and ambiguity review. Do not assign school codes to an Asobee or Gakudo programme by copying a nearby school's identifier.

### Municipality codes

[J-LIS's official Tokyo table](https://www.j-lis.go.jp/spd/code-address/kantou/cms_13414181.html), accessed 2026-10-03, directly verifies these five rows:

| Municipality | Six-digit 全国地方公共団体コード |
|---|---|
| 武蔵野市 | `132039` |
| 港区 | `131032` |
| 文京区 | `131059` |
| 世田谷区 | `131121` |
| 渋谷区 | `131130` |

[J-LIS's specification](https://www.j-lis.go.jp/spd/code-address/cms_1750514.html) describes two prefecture digits, three municipality digits and one check digit. Store the namespace explicitly; five-digit regional codes and six-digit local-government codes must not be mixed. Preserve effective dates because jurisdictions/codes can change. The [download page](https://www.j-lis.go.jp/spd/code-address/jititai-code.html) describes bulk download as a service-user feature; this research used public page lookup. All accessed 2026-10-03.

## JSON contract for the source-governance gate

Companion: `research/tokyo-source-provenance-20261003.json`.

| Field | Contract |
|---|---|
| `schema_version` | `"1.0"` |
| `registry_snapshot` | Registry path, whole-file SHA-256, version, count, check date and exact fingerprint rule. |
| `sources[]` | One record per actual registry source. Keys: `source_id`, resolved `collection_id`, original `registry_collection_id`, `registry_fingerprint_sha256`, `identity`, `endpoints[]`, audience findings and recommendations. |
| `identity.status` | `verified / partially_verified / unverified`. Institutional/publisher identity only; it does not imply reachable or readable endpoints. |
| `endpoints[].reachability` | `reachable / unreachable / unverified`, actual HTTP status if known, actual check timestamp/date, method. No fabricated HTTP status for web-tool observations. |
| `endpoints[].content_readability` | `readable / partially_readable / unreadable / unverified`, with scope such as `html_index` or `facility_reference_html`. |
| `endpoints[].linked_document_review` | `sampled / not_reviewed`; `all_documents_readable` remains null. Sample evidence is document-specific. |
| `evidence` | Object keyed by evidence ID, with URL, publisher, access date, known publication/update date, method, verification status and concise finding. |
| `collections[]` | Existing collection IDs and member source IDs; no new school/collection identity invented. |
| `registry_claims` | Existing configuration values, explicitly separated from verified findings. |
| `stable_identity_anchors` | Verified official code schemes, five directly observed municipality rows; no invented MEXT mapping. |

Per-source fingerprints are SHA-256 over the **complete raw registry entry**, recursively sorting object keys, retaining array order, and serializing compact UTF-8 JSON. Derived provenance fields are excluded. The whole-file hash intentionally also detects formatting or ordering changes.

Snapshot whole-file SHA-256: `07c1d1f3a0d513ffd15d68b152bdc6bdeedea7f6f3d065e048cb5feb336d678f`.

Actual source example:

```json
{
  "source_id": "sakurano",
  "collection_id": "sakurano",
  "registry_collection_id": "sakurano",
  "registry_fingerprint_sha256": "3b7e96ede1ba448ee89945462b6adf591fbcf3bb0296dc5093708102f90421c8",
  "identity_status": "verified",
  "primary_endpoint_reachability": "reachable",
  "primary_endpoint_readability_scope": "html_index",
  "linked_document_review": "sampled"
}
```

The example is a flattened illustration; the actual nested fields follow the contract table. A gate should compare each source fingerprint before accepting its observations and independently decide which verification dimension its workflow requires. Unverified observations cannot be promoted by collection membership or an official hostname.

## Explicit gaps and recommendations — not implementation

- **No additional body crawl:** 50 configured endpoint records remain unverified. Their checks/dates remain null; they are not labelled failed. Supplementary school, municipal-event, health, meal and admission records were not comprehensively reviewed.
- **Grade availability is uneven:** Sakurano grade PDF text was sampled; Senkawa and Seishi provide grade-labelled indexes. Other grade coverage remains narrower or unknown. Senkawa's FY2026-labelled learning-plan links contain 2025 filenames: verify document-year content before inferring freshness.
- **Authenticated boundary:** public app instructions do not expose actual guardian notices. Protected menu labels are evidence of a boundary, not proof of what all grades receive. No login, password, Classi content or private student data was accessed.
- **Publication rights:** school footers, including Sakurano's, state restrictions on unauthorised reproduction. Public accessibility does not establish commercial reuse permission; permission/licence review was not performed. This is a research gap, not a legal determination.
- **Evidence types:** school-life notices, administrative guidance, admission cohorts, provider facility references and public programme letters should remain distinguishable. Recommendations in this report have not been implemented.
- **Runtime acceptance:** this work does not verify app ingestion, OCR, translation, notification delivery, production UI or deployment.

Main supplied three additional parent-research leads: Musashino sixth child plan (page identifier 1048697), a Tokyo 2026 survey described as 10,500 randomly selected households, and Minato's 2023 school guide at supplied path `/documents/171915/gakkouannai_j.pdf` (an older path reportedly returned 404). These leads were **not opened or independently verified in this sidecar**. No full URLs, check dates, findings or demographic weights were invented from them.

## Dated evidence register

Every citation below was consulted on 2026-10-03. Null/unknown source dates stay unknown. The JSON stores finer check times only where the actual network observation recorded them. Relevance score is research prioritisation, not statistical confidence.

| Evidence ID | Official source | Publisher | Displayed update / publication date, if established | Access / method / status |
|---|---|---|---|---|
| `musashino_school_directory` | [武蔵野市立小中学校ポータルサイト](https://www.musashino-city.ed.jp/) | 武蔵野市立小中学校ポータル | Not stated / not established | 2026-10-03; web_open; verified |
| `musashino_city_school_directory` | [市立小学校](https://www.city.musashino.lg.jp/shisetsu_annai/gakkou_kyoiku/shogakko/index.html) | 武蔵野市 | Not stated / not established | 2026-10-03; direct_https_get; verified |
| `musashino_gakudo_directory` | [学童クラブ](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/index.html) | 武蔵野市 | Not stated / not established | 2026-10-03; direct_https_get; verified |
| `musashino_asobee_policy` | [地域子ども館あそべえ](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/1006778.html) | 武蔵野市 | 2026-07-02 | 2026-10-03; direct_https_get; verified |
| `musashino_gakudo_policy` | [学童クラブについて](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/1006775.html) | 武蔵野市 | 2026-10-01 | 2026-10-03; direct_https_get; verified |
| `provider_about` | [地域子ども館とは](https://mu-kodomo.kids.coocan.jp/kodomokan/about.html) | 公益財団法人武蔵野市子ども協会 | Not stated / not established | 2026-10-03; direct_https_get_cp932; verified |
| `provider_letters` | [地域子ども館 お知らせ](https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html) | 公益財団法人武蔵野市子ども協会 | Not stated / not established | 2026-10-03; direct_https_get_cp932; verified |
| `sakurano_gakudo_facility` | [施設案内 桜野こどもクラブ](https://www.city.musashino.lg.jp/shisetsu_annai/kosodate/gakudo/1000414.html) | 武蔵野市 | 2025-04-04 | 2026-10-03; direct_https_get; verified |
| `minato_directory` | [小学校一覧](https://www.city.minato.tokyo.jp/gakkouuneishien/kodomo/gakko/sho/sho/) | 港区 | Not stated / not established | 2026-10-03; web_open; verified |
| `bunkyo_directory` | [小・中学校・中等教育学校（地図で施設を探す）](https://www.city.bunkyo.lg.jp/b003/p006755.html) | 文京区 | 2024-03-12 | 2026-10-03; web_open; verified |
| `setagaya_directory` | [地区の関連施設](https://www.city.setagaya.lg.jp/01022/10458.html) | 世田谷区 | 2023-07-13 | 2026-10-03; direct_https_get; verified |
| `shibuya_directory` | [区立小学校](https://www.city.shibuya.tokyo.jp/shisetsu/kyoiku-shisetsu/kuritsu-school/shogakkou.html) | 渋谷区 | 2025-03-24 | 2026-10-03; direct_https_get; verified |
| `tokyo_aoyama_directory` | [青山高等学校 学校プロフィール](https://www.toritsuko.metro.tokyo.lg.jp/school/aoyama/) | 東京都教育委員会 | Not stated / not established | 2026-10-03; web_open; verified |
| `tokyo_public_school_inventory` | [令和７年度 公立学校統計調査報告書 東京都公立学校一覧 CSV](https://www.kyoiku.metro.tokyo.lg.jp/about/statistics_and_research/list_of_public_school/school_lists2025/report2025_csv) | 東京都教育委員会 | 2026-01-15 | 2026-10-03; direct_https_get; verified |
| `sakurano_october_grade_pdf` | [R8 学年だより 10月号](https://sakurano-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260918181117.pdf) | 武蔵野市立桜野小学校 | Not stated / not established | 2026-10-03; web_pdf_text; verified |
| `sekimae_august_september_pdf` | [学校だより 令和8年度8・9月号](https://sekimaeminami-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260827150334.pdf) | 武蔵野市立関前南小学校 | 2026-08-27 | 2026-10-03; web_pdf_text; verified |
| `seishi_grade_index` | [令和8年度学年のページ](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/12,0,36,html) | 文京区立誠之小学校 | Not stated / not established | 2026-10-03; web_open; verified |
| `aoyama_guardian_boundary` | [在校生・保護者の方へ](https://www.metro.ed.jp/aoyama-h/students.html) | 東京都立青山高等学校 | Not stated / not established | 2026-10-03; web_open; verified |
| `mext_school_codes` | [文部科学省 学校コード](https://www.mext.go.jp/b_menu/toukei/mext_01087.html) | 文部科学省 | 2026-05-29 | 2026-10-03; web_open; verified |
| `mext_code_specification` | [学校コードの取り扱いについて](https://www.mext.go.jp/content/20210128-mxt_chousa01-000011635_01.pdf) | 文部科学省 | 2021-01-27 | 2026-10-03; web_pdf_text; verified |
| `jlis_code_specification` | [掲載している情報等について](https://www.j-lis.go.jp/spd/code-address/cms_1750514.html) | 地方公共団体情報システム機構 | Not stated / not established | 2026-10-03; web_open; verified |
| `jlis_tokyo_codes` | [東京都内市町村](https://www.j-lis.go.jp/spd/code-address/kantou/cms_13414181.html) | 地方公共団体情報システム機構 | Not stated / not established | 2026-10-03; web_open; verified |
| `jlis_download_scope` | [地方公共団体コード住所](https://www.j-lis.go.jp/spd/code-address/jititai-code.html) | 地方公共団体情報システム機構 | 2023-07-20 | 2026-10-03; web_open; verified |
| `endpoint_sakurano` | [桜野小学校](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/) | 桜野小学校 | 2026-09-18 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_dai1_es` | [武蔵野市立第一小学校](https://dai1-e.musashino-city.ed.jp/modules/hp_jpage14/) | 武蔵野市立第一小学校 | 2026-10-01 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_dai2_es` | [武蔵野市立第二小学校](https://dai2-e.musashino-city.ed.jp/modules/hp_jpage5/) | 武蔵野市立第二小学校 | 2026-08-28 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_dai3_es` | [武蔵野市立第三小学校](https://dai3-e.musashino-city.ed.jp/modules/hp_jpage4/index.php?page_parent=109) | 武蔵野市立第三小学校 | 2026-09-16 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_dai4_es` | [武蔵野市立第四小学校](https://dai4-e.musashino-city.ed.jp/modules/hp_jpage3/) | 武蔵野市立第四小学校 | 2026-10-01 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_dai5_es` | [武蔵野市立第五小学校](https://dai5-e.musashino-city.ed.jp/modules/hp_jpage12/index.php?page_parent=916) | 武蔵野市立第五小学校 | 2026-09-02 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_oonoden_es` | [武蔵野市立大野田小学校](https://oonoden-e.musashino-city.ed.jp/modules/hp_jpage4/) | 武蔵野市立大野田小学校 | 2026-09-29 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_kyounan_es` | [武蔵野市立境南小学校](https://kyounan-e.musashino-city.ed.jp/modules/hp_jpage3/) | 武蔵野市立境南小学校 | 2026-09-30 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_honjuku_es` | [武蔵野市立本宿小学校](https://honjuku-e.musashino-city.ed.jp/modules/hp_jpage2/index.php?page_parent=126) | 武蔵野市立本宿小学校 | 2026-09-30 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_senkawa_es` | [武蔵野市立千川小学校](https://senkawa-e.musashino-city.ed.jp/modules/hp_jpage19/) | 武蔵野市立千川小学校 | 2026-08-26 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_inokashira_es` | [武蔵野市立井之頭小学校](https://inokashira-e.musashino-city.ed.jp/modules/hp_jpage2/index.php?page_parent=103) | 武蔵野市立井之頭小学校 | 2026-10-01 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_sekimaeminami_es` | [武蔵野市立関前南小学校](https://sekimaeminami-e.musashino-city.ed.jp/modules/hp_jpage4/) | 武蔵野市立関前南小学校 | 2026-09-24 | 2026-10-03; direct_https_get; verified |
| `endpoint_setagaya_sakura_machi_es` | [桜町小学校](https://school.setagaya.ed.jp/sachi/document) | 桜町小学校 | Not stated / not established | 2026-10-03; direct_https_get; verified |
| `endpoint_shibuya_jinnan_es` | [神南小学校](https://shibuya.schoolweb.ne.jp/1310231/page/frm5e49ee9d22f62) | 神南小学校 | Not stated / not established | 2026-10-03; direct_https_get; verified |
| `endpoint_setagaya_seta_jhs` | [瀬田中学校](https://school.setagaya.ed.jp/tseta/page/school_mail) | 瀬田中学校 | Not stated / not established | 2026-10-03; direct_https_get; verified |
| `endpoint_sakurano_parent_contact` | [桜野小学校・欠席連絡の案内](https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage10/) | 桜野小学校・欠席連絡の案内 | 2024-04-05 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_oonoden_es_parents` | [大野田小学校・保護者連絡アプリ手引書](https://oonoden-e.musashino-city.ed.jp/modules/hp_jpage12/) | 大野田小学校・保護者連絡アプリ手引書 | 2026-04-02 | 2026-10-03; direct_https_get; verified |
| `endpoint_musashino_sekimaeminami_es_parents` | [関前南小学校・保護者連絡の手引き](https://sekimaeminami-e.musashino-city.ed.jp/modules/hp_jpage27/) | 関前南小学校・保護者連絡の手引き | 2025-04-07 | 2026-10-03; direct_https_get; verified |
| `endpoint_minato_shibaura_es` | [芝浦小学校](https://shibaura-es.minato-tky.ed.jp/gakkoudayori) | 芝浦小学校 | Not stated / not established | 2026-10-03; web_open; verified |
| `endpoint_bunkyo_seishi_es` | [誠之小学校](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/13,html) | 誠之小学校 | Not stated / not established | 2026-10-03; web_open; verified |
| `endpoint_shibuya_aoyama_hs` | [青山高等学校](https://www.metro.ed.jp/aoyama-h/news/news-01/index.html) | 青山高等学校 | Not stated / not established | 2026-10-03; web_open; verified |

## Delivery verification

The companion JSON is intended for exact registry-ID/fingerprint checks and evidence-link integrity validation. Validation results are reported in the delivery message. Only this Markdown file and the assigned JSON artifact are authored by this sidecar.
