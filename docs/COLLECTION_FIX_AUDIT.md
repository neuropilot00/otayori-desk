# Collection repair audit — 2026-10-01

Scope: registered unauthenticated public sources. This is not a claim to aggregate private parent-app messages, every school webpage, or every historic document.

## Repairs

- Corrected four school roots/download adapters, including 瀬田中's previously wrong-school URL. Image-alt and extensionless PDF links are discovered.
- Added 桜野's library HTML body and grade-specific library PDFs; unrelated grade-only files are excluded.
- Replaced three fixed city articles with five scoped public article lists. Newly linked articles within reviewed patterns are discovered automatically.
- Twelve live club facility pages are reference material, excluded from new-notice counts and pushes. Public club admission notices remain in the main feed.
- Separated publication/issue/event/deadline dates. URL timestamps do not become publication dates; printed issue months are retained before grade-section extraction. Unknown dates remain explicitly unknown. A CMS upload year can provide context for an explicitly printed issue month, not a publication date.
- Added bounded offline Japanese OCR. Low-confidence/incomplete extraction retains an original-only entry and visible warning, not invented or silently absent content.
- Exposed per-source status, counts, scope, limits and original links. Background refresh responses are polled for up to 60 seconds; filter changes cancel/ignore old responses. An in-flight forced scan stays marked refreshing even when a recent cache exists.
- Notification ledgers isolate failed sources, ignore references, quietly baseline newly covered sources, and preserve already pending IDs on migration.

## Direct public-source audit

Command: `python -m sakurano_line_notifier.source_audit --output state/source-audit-verified.json`, with local Japanese Tesseract data installed outside the repository. Completed 2026-10-01 12:21 UTC.

- 36 registered source records checked; 290 entries retained, including 12 facility references.
- 284 entry bodies extracted; 6 originals retained with extraction warnings.
- 四小: 12 retained, 9 readable. Three low-quality scanned PDFs remain original-only.
- 桜町: 4 retained, 1 readable. Three PDFs failed whole-document OCR confidence checks.
- 芝浦: 11 URLs read; these are not necessarily 11 distinct issues. 神南: 5 read. 瀬田中: 5 read. No zero-result school remains in this run.
- Twelve sources hit their configured recent-document cap; this is exposed separately from retrieval failure. Discovery counts include older archives and, for grade filtering, unrelated-grade links. No full-history coverage is claimed.
- The audit exits nonzero for the two partial OCR sources. The daily GitHub check intentionally retains this failure signal instead of calling the run fully successful.

OCR alternative comparison tested 24 combinations on all six affected 四小 pages (PSM 6, higher resolution, Japanese+English). Best mean confidence was 61.7 versus the unchanged 70 threshold, with excessive uncertain text. No threshold was lowered merely to make the audit green.

## UI checks

Local 390px browser: October grade notice and October 1 city/club notices visible; original link retained; repeat click collapses the opened body. Events show October before November and keep event/deadline/publication roles distinct. Facility references are collapsed separately. Shared municipal records do not assert the registry's elementary-school level as their actual target audience.

## Remaining boundaries

- Six current scanned originals still require human reading. OCR/text extraction and heuristic categorization are not a correctness guarantee.
- Some PDF headers are images even when body text is extractable, so their publication dates remain unknown.
- Municipal event lists include several age groups; original eligibility conditions must be checked. Private 学童 newsletters/保護者連絡帳 are not covered.
- Public site redesigns and differently named event links can require a reviewed adapter/pattern update. Scheduled checks detect registered-source failures, not all possible missing information.
- New mobile push delivery was not sent to a real parent device during this repair.

## Automated checks before deployment

- `python -m unittest discover -s tests -q`: 139 passed, including OCR resource bounds, source/date regressions, refresh concurrency, and notification migration/isolation.
- `node --test tests/test_frontend.cjs`: 24 passed, including polling timeouts/cancellation, disclosure toggling, escaped source text, references and date presentation.
- JavaScript syntax and `git diff --check`: passed.
- Installed-environment `pip-audit`: no known vulnerabilities at check time.

Deployment results are appended after live verification.
