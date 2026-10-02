# Parent reevaluation fixes — 2026-10-02

## Confirmed defects and changes

- Manual refresh cleared the notice list and reset inline expansion before the first response. It now retains readable content during loading and failure. Unchanged data retains the actual reader DOM, category toggles and scroll; changed data keeps the selected card expanded. School/grade changes still invalidate old requests and reset expansion.
- Added click-path regressions for October grade-one notice → Korean → refresh, polling, failure, changed/removed notices, language changes, collapse during refresh and stale detail responses after filtering.
- The GitHub collection workflow was active but scheduled executions were several hours apart. Manual run [36966831156](https://github.com/neuropilot00/otayori-desk/actions/runs/36966831156) recovered all 21 scheduled source snapshots at 13:58 JST. The production Sakurano API subsequently showed fresh timestamps for its 10 scheduled sources (including events and reference material).
- The existing fallback dispatcher had no repository-scoped credential configured. Missing/invalid recovery configuration now emits one bounded startup warning, rather than silently disabling the fallback. This warning alone does not enable recovery.
- Frontend asset version is `20261002-5`, service-worker cache is `v15`.

## Local verification

- `python -m unittest discover -s tests`: 312 passed. An existing SQLite ResourceWarning and malformed-PDF fixture warning were observed; neither failed the suite.
- `node --test tests/*.cjs`: 61 passed.
- `node --check web/app.js`, `web/sw.js`, `web/policies.js`: passed.
- `git diff --check`: passed.

## Release acceptance

- App commit: `3501af12ed39db75e6c344917c9b985d69f6291a` pushed to `main`.
- [GitHub CI 36967499352](https://github.com/neuropilot00/otayori-desk/actions/runs/36967499352): both jobs passed (312 Python + 61 JavaScript tests; dependency audit found no known vulnerabilities).
- Railway deployment `f9411907-d4ac-4d67-83db-0deeccde740b`: SUCCESS. Production `/api/ready` returned 200 and `{"ok":true,"mode":"free_beta"}`.
- Production and local `app.js` SHA-256 matched: `40a6a5cfcefebffd9785851c90ca39a369742c19435c8764dee080aaad25f15a`.
- Real production browser at 390px: opened notice `94cb4a5e619c78808d99`, selected Korean, opened parent guidance and closed preparation, then clicked refresh. The card remained expanded while loading and after the response; full reader text and all three category states matched before/after. No loading panel replaced the list. The refresh button returned to enabled.
- Repeated card click collapsed it (zero expanded cards); a further click reopened it. At 320px the document width equalled the viewport width; no horizontal overflow. Browser warning/error log was empty.
- Production all-source API confirmed **21/21 scheduled sources fresh**, no issue codes, with check times `2026-10-02T04:58:06.443374+00:00`–`2026-10-02T04:58:10.946332+00:00`.
- The deployed startup log correctly reports `catalog_recovery_disabled`. A 30-day, one-repository, Actions read/write token form is prepared in the already-authenticated Chrome session; token issuance and Railway secret storage remain unperformed pending explicit approval. GitHub CLI and Chrome login are working. The Code-in-app browser has a separate logged-out session; another login is not required.

## Boundaries

The private daily Gakudo notices remain uncollected. The low-confidence Asobee PDF remains original-only, not guessed text. Actual physical-device push delivery is not established by this release. GitHub scheduling is not a precise interval guarantee; even an enabled fallback cannot remove GitHub-wide queue/outage risk. No account-wide GitHub credential was transferred to Railway.
