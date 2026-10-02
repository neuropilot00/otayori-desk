# Coverage status and delayed collection repair — 2026-10-02

## Verified causes

- The long red warning joined all source names and generic `partial` states, including benign historical document caps. A delayed saved snapshot was not distinguished from unreadable PDF text.
- GitHub's enabled 30-minute schedule actually started runs at 2026-10-02 **03:48 JST** and **08:05 JST**, hours apart. Both runs succeeded: [36909620435](https://github.com/neuropilot00/otayori-desk/actions/runs/36909620435), [36938906703](https://github.com/neuropilot00/otayori-desk/actions/runs/36938906703). The problem is not an upload-token failure. GitHub documents possible delayed/dropped schedules in its [troubleshooting guide](https://docs.github.com/en/actions/how-tos/troubleshoot-workflows).
- A fresh read-only request from the current Railway runtime to the registered municipal school-admission index still returned HTTP 403. No authentication/access barrier was bypassed or collection driver moved to that failing runtime.
- Explicit recovery [36953418415](https://github.com/neuropilot00/otayori-desk/actions/runs/36953418415) succeeded at **10:58 JST**. Municipal source check times advanced to `2026-10-02T01:58:24..28Z`. This is a successful manual recovery, not evidence that cron reliability is fixed.
- Unconfigured legacy LINE schedules were also failing on missing OCR system packages. Neither LINE Secret nor the enable variable was configured. This workflow is separate from the web-app push service.

## Changes

- Backend coverage now exposes independent `freshness_status` and `issue_codes`. Pending first collection, delayed cache, failed body extraction, retrieval failures, refresh in progress and document caps have distinct meanings.
- The Japanese-first summary shows short issue counts and a details toggle, never a wall of source names. Per-source timestamps, warnings, readable/document counts and official links remain inside the collapsed coverage section. Caps alone are neutral. Unexplained legacy failures remain visible. JA/KO/EN/ZH labels and click/keyboard open-close behavior are tested.
- Only previously readable bodies are retained after failed extraction. Retained old bodies are explicitly stale; repeated original-only failures do not masquerade as old readable content or replace a new failure reason.
- An optional server watchdog checks municipal snapshot age on the normal 15-minute refresh loop. At 45 minutes old/missing it requests the fixed GitHub collection workflow, with a 30-minute cooldown (six hours after 401/403), fixed HTTPS destination, no redirects or environment proxies and redacted failures. It does not collect municipal pages from the blocked host, modify checked times, or send notifications.
- **The watchdog is inactive until `CATALOG_DISPATCH_TOKEN` is registered securely.** It requires a fine-grained token scoped only to this repository, Actions read/write. No broad local GitHub credential was copied to Railway. Setup is in the README. Single web replica only; this is not a GitHub-outage-proof scheduler.
- LINE automation is opt-in via `LINE_NOTIFICATIONS_ENABLED=true`, validates its two Secrets before collection, installs local OCR dependencies, and defaults manual preview to dry-run. No LINE setting was enabled and no real notification was sent in this repair.
- Frontend/service-worker asset versions were bumped; source fingerprints were not changed, preserving valid persisted public snapshots.

## Verification before deployment

- `.venv/bin/python -m unittest discover -s tests`: **213 passed**. The corrupt-PDF fixture's expected `EOF marker not found` diagnostic is not a test failure.
- `node --test tests/test_frontend.cjs`: **36 passed**.
- JavaScript syntax and `git diff --check`: passed.
- UI agent: 390px fixture checks for mixed issues, four languages, keyboard/second-click toggling and error/neutral colors. Main: current-code isolated local HTTP server, real public collection, compact summary, source links and October-first/archive behavior. No local or real notification subscriptions were created.

## Remaining extraction limitation

Sakurano Asobee's two-page public PDF cannot safely be transcribed by the current local OCR. Its best tested page-2 result is 67.4 confidence and 24% uncertain characters, below unchanged gates (70 and at most 20%). Damaged time ranges/calendar associations are actionable errors, not cosmetic ones. See [bounded OCR evidence](PDF_OCR_RECOVERY_20261002.md). It remains original-only with a visible official link. This repair does not claim every registered PDF is readable, complete coverage of school communications, or private guardian-app access.

## Deployment evidence

Pending release verification; append actual commit, workflow and runtime results after deployment.
