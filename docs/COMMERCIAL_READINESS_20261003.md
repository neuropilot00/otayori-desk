# Commercial-readiness engineering audit — 2026-10-03

## Decision

Keep the service in free guardian beta. This change improves release controls and source isolation; it is **not commercial-launch sign-off**. Billing remains disabled. A running server, passing tests and simulated interviews do not establish complete school communication coverage.

## Implemented and locally verified

- Reject ambiguous collection roots, dangling relationships, cross-school/city/level sharing, invalid booleans/classifications, and live notices disguised as static reference material.
- Check every production school/grade/source-group/feed combination against independent expected scope rules. School-to-club relationships are explicit, not inferred from proximity.
- Audit the public API separately from HTTP/DB readiness: registry identity, complete source inventory, original URL ownership, readable-body evidence and timestamp freshness. Facility HTML requires the configured exact page, not merely the same city host.
- Snapshot imports reject another facility page and whitespace-only bodies. Readable notice counts cannot override individual unreadable records.
- Scheduled collection is described as a 30-minute reservation, with delay possible. Show a warning after 45 minutes without resetting the actual checked timestamp. Daily source audit preserves failure evidence for 14 days.
- Official-source provenance covers all 75 configured sources, including 18 verified school roots. Configuration drift requires deliberate review updates in CI. Evidence is not treated as verified merely because an ID exists.
- UI school/grade changes immediately discard the previous reader. Late old-scope success/errors cannot restore it. Elementary viewer grades remain 1–6; middle/high 1–3, independent of collector cache grades. Conflicting school/ward/level controls are reconciled before requests.
- Updated the service-worker shell version so installed web clients retrieve the new UI.

Validation: `python -m unittest discover -s tests -q`: **364 passed**; `node --test tests/*.cjs`: **71 passed**. JavaScript syntax and `git diff --check` passed. The malformed-PDF test emits its expected `EOF marker not found` diagnostic without a test failure.

Independent review identified four false-pass risks (same-host wrong facility, blank bodies, static notice freshness bypass, empty provenance evidence); all four have regression coverage and are fixed. Browser acceptance and deployment evidence will be appended after release, not assumed from these tests.

## Research and MiroFish

See [official parent research](TOKYO_PARENT_RESEARCH_20261003.md), [school-by-school provenance](TOKYO_SOURCE_RESEARCH_20261003.md), and [96 simulated guardian interviews](MIROFISH_TOKYO_96_20261003.md). Age bands are 20s/30s/40s/50s/60+, crossed with school stage, work patterns, multiple children and language. **Zero real respondents**; not representative Tokyo demographics or persona-operated UI tests. The evaluation baseline predates this release. Saved multiple-child views remain deferred; scope safety was fixed first.

## Live findings and unresolved release gates

- Scheduled city snapshots were approximately 255 minutes old. Manual [collection recovery](https://github.com/neuropilot00/otayori-desk/actions/runs/37114741899) succeeded. Subsequent strict public audit checked 75 sources with no identity/timestamp errors at that observation, but **17 sources contained unreadable bodies**. This does not mean all documents in those 17 sources failed. Originals remain accessible, with no invented extracted text or notification from unreadable bodies.
- Unresolved source extraction includes complex Asobee calendars, corrupt native PDF character maps and some school documents. Do not lower accuracy thresholds to obtain a green status.
- Provenance research confirms 18 school identities, not all Tokyo schools. 34 endpoint records were reachable and 50 remain unverified in that bounded research; endpoint access is not complete PDF or private-message coverage.
- Private Gakudo daily communications and school-only parent apps are not collected. Facility and admission pages are reference material, never presented as daily enrolled-family notices.
- Real iOS/Android push arrival, real-parent usability sessions, source permission/commercial reuse review, and operator/contact particulars remain open. Actual multi-child saved views are not implemented in this release.
- The automatic recovery credential (`CATALOG_DISPATCH_TOKEN`) is not configured. User approval was requested for a repository-only, Actions-only, 30-day credential; no broad CLI token was copied and no new token was issued.

These gaps prevent an all-clear commercial quality claim. A future launch decision must record actual device delivery, source-by-source remediation and real-parent task outcomes, not overwrite this audit with test counts alone.

## Released build and actual browser acceptance

- Application changes: `cb023be70cd79501e357da8231d28f353c4585f9`; mobile follow-up: `74f3956db78305fb06ee85fa2195a907615196b1`.
- Both [main CI](https://github.com/neuropilot00/otayori-desk/actions/runs/37115788955) and [mobile follow-up CI](https://github.com/neuropilot00/otayori-desk/actions/runs/37116075204) completed successfully, including tests and dependency audit. **435 automated tests**: 364 Python and 71 JavaScript.
- Railway deployment `e9b1a532-447f-4570-96ae-31d2250b05c9` succeeded for the main change, followed by successful `67b509dc-b141-4ac2-ba66-20e18b373c76` for the narrow-screen fix. [Public app](https://otayori-web-production.up.railway.app/).
- The served application JavaScript SHA-256 matches the checkout: `c1e810ad7f0fd03596ca2ce1b80fc7fd9a4c9599497910d7bde2d92b57174636`. The page uses `app.js?v=20261003-1` and `app.css?v=20261003-1`; service-worker shell is v17. `/api/ready` returned `ok: true`, `mode: free_beta`.
- Actual UI: Seta middle school exposes grades 1–3/all; Dai1 elementary preserves the child's first-grade filter even though its collector uses all-grade caches. Conflicting level selection visibly resets school to all; selecting Sakurano clears the incompatible middle-school filter. School switching shows a placeholder immediately instead of the previous reader.
- Actual UI: Sakurano's first-grade October letter expands, loads body text and the official PDF link, keeps its opened body during manual refresh, and collapses when pressed again. Korean mode exposes opt-in Google Translate links targeting `ko` in two lossless parts; they were inspected but not submitted to Google. Japanese/Sakurano/first-grade defaults were restored. No notification subscription, test push or geolocation request was made by this QA.
- Responsive follow-up found a genuine 352px document width at a 320px viewport caused by the school selector's intrinsic width. The fix constrains the existing field/select, without changing font size. Deployed checks now show document width **320/320** with settings open, and **390/390** with the notice list visible. Screenshots are in the sibling study output as `mobile-320-deployed.jpg` and `mobile-390-deployed.jpg`. Temporary viewport override and QA tab were removed.
- Post-main-release public-quality audit again checked all 75 sources: **17 with extraction/unreadable-body issues, zero registry errors**. This quality gate intentionally remains red; server readiness and successful deployment do not override it. The screenshot's single unreadable-source warning reflects the selected Sakurano scope, not the all-source total.
