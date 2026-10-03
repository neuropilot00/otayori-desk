# MiroFish Tokyo guardian scenarios — 2026-10-03

## Executed evaluation, not a parent survey

**96 fictional guardian interviews, 96 successful model calls, 0 real respondents.** The official MiroFish Reddit/OASIS runner was used with zero social rounds and its batch-interview IPC. This is not a social-network diffusion experiment, ReportAgent/Zep analysis, or persona-operated browser test.

- MiroFish commit: `7657031ac01184afe2cb220f5ee3545573b5e843`
- `camel-oasis 0.2.5`, `camel-ai 0.2.78`
- Actual model: `gpt-6-astra`, medium effort, through the bounded local adapter. The `gpt-4o-mini` compatibility name in the runner configuration is **not** the model used.
- Evidence version: repository `149cd9e008739353338de1bcbe7896002475d064`, application-code commit `3501af12ed39db75e6c344917c9b985d69f6291a`, plus the captured public API coverage. New changes in this work were not secretly included in that baseline.
- 18 configured school roots across elementary/middle/high; **not all Tokyo schools**. Cohort design and official parent-research evidence: [research/design](TOKYO_PARENT_RESEARCH_20261003.md).
- Each result was matched to its unique persona, exactly one OASIS interview trace, the provider answer and execution receipt. Tool execution and failed turns were rejected. Only local sign-up/interview actions occurred; no posts/messages to real people.
- The runner acknowledged `close_env` and stopped after validation. The loopback adapter was stopped too.

## Priority counts within these seeded scenarios

These are model outputs under a deliberately bounded evidence packet, **not statistical estimates or independent votes**.

| Age band | Cases | Coverage clarity | Multiple children | School identity | Freshness | Translation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 20s | 12 | 9 | 2 | 1 | 0 | 0 |
| 30s | 24 | 14 | 4 | 3 | 2 | 1 |
| 40s | 24 | 17 | 4 | 1 | 2 | 0 |
| 50s | 24 | 14 | 4 | 3 | 3 | 0 |
| 60+ | 12 | 7 | 2 | 2 | 0 | 1 |
| Total | 96 | 61 | 16 | 10 | 7 | 2 |

All 96 responses declined to label the baseline commercially ready, consistent with the seeded gaps. This is neither a rejection rate from real customers nor proof that users will/will not pay. Same-model correlation, explicit known-risk priming, small cells and fixed scenarios limit interpretation.

## Findings connected to actual engineering evidence

- **Coverage:** T001/T009/T063 could mistake readable public documents for all communications. The existing UI already marks private daily Gakudo communications uncollected and unreadable originals separately. Preserve those distinctions. The new operational quality gate checks all registered sources independently of server readiness; an ordinary historical collection limit is not counted as an outage.
- **School identity:** T011 and others requested clear official identities. Registry graph validation now prevents ambiguous roots, cross-municipality/cross-school sharing and string-to-boolean scope expansion. A separate official-source inventory records what was checked versus what remains unverified.
- **Multiple children:** T002/T014/T092 propose school/grade view switching. This is a product hypothesis, not proof of an existing feature. Implementation/verification is recorded in the release audit, not inferred from these answers.
- **Real UI follow-up:** Main browser testing reproduced a middle-school selector offering grades 4–6. It also showed previous-school desktop text briefly remaining while the new school's detail request loaded (eventually corrected on response). These are actual observed defects, distinct from the interviews' hypotheses.
- **Freshness:** A live check found scheduled city snapshots about 255 minutes old. [Recovery run 37114741899](https://github.com/neuropilot00/otayori-desk/actions/runs/37114741899) succeeded. The subsequent 75-source quality check found no source-identity mismatches or late timestamps, but **17 sources still contained unreadable bodies**. Do not convert this into an all-clear claim.

## Reproducibility

Local evidence is in sibling output directory `outputs/otayori-tokyo-commercial-study/`: `study.py`, `bridge.py`, `seed.md`, `input-version.json`, `public-coverage.json`, `results.json`, `simulation-trace.json`, `model-receipts.json`, `manifest.json`, and the runner's `run/` profiles, IPC responses and provider receipts. These are generated evidence, not production assets or real-person records.

SHA-256 checks:

- Results: `6bd4c1179c7ce23cc06031e3678fd8a7f88e49cf79b22b1872c81b41000af795`
- Trace: `3b6e392e4635d289124aaf218b12fbd0043f5b1bd41da28f23cc9240a7580ee8`
- Receipts: `7a4d0a5fb46113980cf6310c179ce3e9e376abf26e90cb389e0eca31778028f1`
- Seed: `bd7e55dd314a0a785486abc1b93ad250fd9f7f59ce7d030f289193e70f745799`

No age-based UI, inferred child identity, demographic weighting, price recommendation or commercial launch authorization was derived from this simulation. Real parent task observation, physical-device delivery, private-source access arrangements and unresolved OCR need separate evidence.
