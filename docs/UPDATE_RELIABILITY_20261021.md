# Automatic collection repair — 2026-10-21

Status: **implemented and locally tested; not deployed or verified in production**. The production source remains the October 3 release until deployment access is restored. This report does not supersede the unresolved commercial-launch gates in [the previous audit](COMMERCIAL_READINESS_20261003.md).

## Reproduced operational problem

The [latest observed successful external collection](https://github.com/neuropilot00/otayori-desk/actions/runs/39461192735) completed on October 21 at approximately 01:52 JST: all 21 external sources uploaded successfully. Recent scheduled starts were hours apart despite a 30-minute cron. The [latest observed quality audit](https://github.com/neuropilot00/otayori-desk/actions/runs/39347525088), October 20 at 09:28 JST, reported 38 of 75 sources with issues: 16 had extraction/unreadable-body issues, and 23 had stale markers (categories overlap). There were no registry errors in that report.

The Chrome production UI showed Sakurano's first-grade November letter, its official PDF link, and seven overdue sources in that family's selected scope. This confirms new school material is being discovered; it does not establish stable timing or complete coverage.

## Repairs

- External-source recovery now runs in a separate one-minute timer. School PDF/OCR tasks and the fifteen-minute school refresh loop cannot delay it. Sources become eligible for a recovery request after twenty minutes, ahead of the existing forty-five-minute stale warning.
- The manual refresh endpoint queues the same external workflow for the selected scope. The timer and button share a thread-safe fifteen-minute reservation. Authentication failures retain the existing six-hour backoff; network failures, redirects and tokens remain redacted and bounded.
- A manual force arriving during an automatic dispatch is covered by that accepted job. A later cooldown must not erase its pending state. Repeated clicks coalesce.
- Stop/restart retains any worker still finishing a bounded network call and does not clear its cancellation signal until it exits. A failed automatic dispatch also absorbs an overlapping manual request and preserves the real failure instead of changing it to a cooldown.
- Queued/accepted external work is indicated for at most 120 seconds; the browser's existing sixty-second poll limit remains. An acknowledgement never advances `checked_at`. Only a validated, persisted snapshot can replace it.
- `refresh_requested`, `external_refresh_status` and `refreshed` distinguish an attempt, request outcome and completed refresh. Cached snapshot `complete` remains a separate coverage measure. Disabled, unavailable or failed external refreshes show recheck failure; cooldown shows waiting in Japanese/Korean/English/Chinese. A rejection cannot advance the UI's refreshed marker or disappear when independent school polling finishes.
- `/api/collection/status` checks actual saved source ages, recovery-thread liveness and redacted request outcomes. Missing credentials, a stopped recovery thread, late data and recovery failures return 503 independently of server/DB readiness.
- Corrupted PDF native text now requests whole-page OCR. Required text pages cannot be accepted as blank; missing page selections and malformed text remain failures.
- Low-quality full-page OCR gets one alternate layout attempt, under the same time/size/confidence limits. The alternative must preserve recognized character count and confident tokens, including repetitions and qualifiers. Poppler rendering errors fail closed rather than accepting incomplete images.
- Added `poppler-data` and `fonts-noto-cjk` to the Railway runtime and daily source-audit dependencies. [Debian documents](https://packages.debian.org/trixie/poppler-data) that the CMap package supports CJK PDFs with non-embedded fonts; the [font package](https://packages.debian.org/trixie/fonts-noto-cjk) supplies Japanese glyphs. Actual Linux rendering still requires deployment verification.

## Verification

- Python offline suite: **376 passed** in the final recorded run. **13 socket-binding integration cases could not run** because this execution sandbox rejects binding localhost ports (`Operation not permitted`). The committed tests are not weakened or marked skipped; the exclusion was only in the local execution command.
- Frontend suite: **74 passed**, including failed/cooldown external requests in all four languages, accepted-job polling, rejection retention and existing reader preservation.
- Syntax/compilation and `git diff --check` passed.
- Actual PDF samples: October Sakurano Asobee produced 3,600 characters. October Oonoden remained blocked by local missing Japanese CMap data. October Dai4 and September Sakurano remained below OCR quality requirements in both layouts. Their originals remain available and failed OCR is not cached as success. **The sixteen-source failure set has not been verified resolved.**
- The official [tessdata_best Japanese model](https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/main/jpn.traineddata) was also compared locally. Both difficult documents still failed under unchanged thresholds; no new model dependency was added. Measured model size: 14,330,109 bytes; SHA-256 `36bdf9ac823f5911e624c30d0553e890b8abc7c31a65b3ef14da943658c40b79`. The temporary comparison report and four source-PDF fixtures are preserved in the sibling `outputs/otayori-update-fix-20261021/` directory, outside the public source repository.
- Four independent-review findings (the timer/manual pending-state race, false refresh success on rejected requests, a stop/restart worker race, and loss of an overlapping request's actual failure) were reproduced and have regression tests. The final bounded source/regression review reported no further substantive findings; it does not substitute for live deployment verification.

## Deployment access and remaining acceptance

The GitHub connector rejected creating the source tree with `MCP tool call requires approval, but approval policy is never`. CLI requests to GitHub/Railway also encountered DNS/network restrictions. No remote branch, new access key or deployment was created by this repair. Chrome's Railway sign-in led to an unauthenticated GitHub login page; that tab was preserved for the user. A scoped key approval request remains pending.

After restoring authorized deployment access: run the complete suite and dependency checks in GitHub, deploy the checked commit, configure the repository-only Actions recovery credential in Railway, verify `/api/collection/status`, observe actual source timestamps advance through a delayed-schedule recovery, and rerun live source quality with the Linux CMap/font dependencies. Real-device push delivery and private Gakudo communications remain separate unverified acceptance items. Do not describe this local patch as a deployed or commercially complete service.
