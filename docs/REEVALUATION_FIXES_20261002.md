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

Deployment and real mobile refresh verification must be recorded after the release. Do not treat unit-test results as deployed acceptance.

## Boundaries

The private daily Gakudo notices remain uncollected. The low-confidence Asobee PDF remains original-only, not guessed text. Actual physical-device push delivery is not established by this release. GitHub scheduling is not a precise interval guarantee; even an enabled fallback cannot remove GitHub-wide queue/outage risk. No account-wide GitHub credential was transferred to Railway.
