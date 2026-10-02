# After-school scope and school-year relevance — 2026-10-02

## Verified problems

- Production Sakurano data contained 12 after-school records: nine admissions/administrative pages, two facility/program guides and one public Asobee letter. It did not contain the club's daily guardian notices. Admissions had been classified as fresh notices.
- Selecting `group=after_school` with a school root caused the HTTP handler to broaden the selection to `all`. Other schools' records could enter the response.
- City articles were cached as `全学年`; elementary first-grade responses included middle-school admission and pre-entry procedures.
- Some Asobee PDFs contained broken native CMap text but were counted as readable. The separate OCR failure was not the only PDF quality issue.

## Corrections

- Explicit kinds: `gakudo_admissions`, `gakudo_facility`, `asobee_reference`, `asobee_letter`; future reviewed daily sources may use `gakudo_daily`. No daily source has been invented or registered.
- Admissions and facility/program guides must be `reference`; they are collapsed, excluded from current-notice counts and push delivery. Typed labels appear in cards and detail, including Korean/English/Chinese.
- A compact, native details control says `学童の生活連絡：未収集`. Its explanation distinguishes daily schedules, things to bring and guardian messages from admission documents and Asobee letters. It remains visible with an empty/failed after-school collection, and is hidden in school-only, city-only and event views.
- Each of the 12 Musashino elementary roots selects its own facility and public Asobee letter. The HTTP group filter no longer changes the chosen school.
- Shared-cache response filtering uses explicit school-stage/grade evidence in titles. Elementary 1–5 do not receive middle-school entrance procedures; sixth-graders keep transition information. Explicit pre-elementary entrance procedures are not shown as current-first-grade tasks. Shared elementary/middle safety/support information remains visible. Ambiguous audiences are not guessed. School newsletters retain their existing grade-extraction logic.
- API, detail lookup and push use the same `get_many` filtered result; the underlying public caches remain complete for other families. `audience_excluded_count` records filtering rather than misreporting an empty relevant result as a collection failure.
- Snapshot ingestion derives after-school kinds/reference status from the reviewed registry, not caller-provided display labels. Registry fingerprints invalidate outdated classification caches; scheduled city snapshots must be recollected after deployment.
- Repeated unmapped native PDF characters now fail closed to the original link instead of exposing garbled body text. No OCR gates were weakened. See [PDF evidence](PDF_OCR_RECOVERY_20261002.md).

## Verification

- Full local suites: **246 Python tests and 44 JavaScript tests passed**. JavaScript syntax and `git diff --check` passed. Expected corrupt-PDF diagnostic `EOF marker not found` does not indicate a failed test.
- Real local HTTP collection: first-grade view has no exclusive middle-school admission or explicitly tagged pre-entry procedures; sixth-grade response retains middle-school admission procedures and the parents' orientation.
- Real browser at 390×844: school and first grade remain selected after choosing after-school; references are closed by default; scope and references open/close on repeated clicks. JA/KO/EN/ZH all have document/viewport width 390, no horizontal overflow; refresh font remains 14px.
- Real Sakurano after-school response: one original-only Asobee letter and eleven reference records, with `daily_notice_status=not_collected`. Source links remain available. Browser/backend QA used an isolated public cache and no push notifier; no real notification was sent.
- CI and production deployment are separate gates; this document records pre-deployment verification, not a claim that CI or deployment has already succeeded.

## Scope limits

This release clarifies actual coverage. It does not obtain private guardian-app/club communications or guarantee complete source discovery/OCR. `registered` (when a real daily source is added later) means registration, not successful or exhaustive collection. The optional scheduling watchdog remains credential-dependent; this change does not enable it.

Official comparison sources: [city admission index](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/kodomo_kosodate/shisetsu/gakudoclub/index.html), [Asobee public letters](https://mu-kodomo.kids.coocan.jp/kodomokan/oshirase.html), [middle-school entry procedures](https://www.city.musashino.lg.jp/shussan_kodomo_kyoiku/sho_chugakko/nyugaku_tenko_tetsuzuki/1017098.html).
