# Tokyo guardian research and evaluation design — 2026-10-03

## What is supported

There is direct evidence of the user's problem, but not evidence that every Tokyo parent has it or will pay for this service. A March 2026 resident submission describes excessive paper after transferring schools and a communication app available at one municipal school but not the next. Minato's May 29 response says an emergency system exists, while use of its additional functions remains school-dependent. This supports **school-specific channel inventories**, not a universal app-integration claim. [Minato: school–guardian communication](https://www.city.minato.tokyo.jp/kouchou/kuse/kocho/ikenshokai49/3758.html)

Minato's needs-survey free responses include a working parent finding a 16:00 school-contact cutoff difficult and asking for an electronic alternative. These are qualitative comments, not prevalence estimates. Asynchronous reading can reduce part of that burden; a public notice aggregator cannot send an absence report to a school or replace its contact channel. [Minato needs report, printed p.255](https://www.city.minato.tokyo.jp/documents/162195/houkokusyo.pdf)

The official October 2023 school guide describes paper notices, communication notebooks and electronic channels; its editions include Japanese, English, Chinese and Korean. It supports keeping Japanese originals and clearly labelled translations. It is an older guide, not proof of each school's present systems. The old PDF URL ending in /141890/ returned 404 during this check; the /171915/ reference below returned indexed document text. Subsequent direct requests sometimes returned 403. [Minato school guide](https://www.city.minato.tokyo.jp/documents/171915/gakkouannai_j.pdf)

## Cohorts: age is one axis, not a stereotype

The Tokyo 2026 survey explicitly separates children's stages and their guardians (grades 3/5, middle-school year 2, age 17, and guardians of 3-year-olds). Its announced random sample of 10,500 households is **not our sample** and supplies no weights for the MiroFish scenarios. [Tokyo survey announcement, 2026-05-01](https://www.koho.metro.tokyo.lg.jp/2026/05/oshirase09.html)

Musashino's sixth child plan page links separate preschool/elementary-parent, youth and single-parent research. This reinforces the need to distinguish household context and child's stage rather than predict needs from guardian age alone. The plan page was readable through indexed official content; a later live retrieval was 403. No age-distribution statistic was extracted from its large report PDFs. [Musashino sixth child plan, updated 2026-03-17](https://www.city.musashino.lg.jp/shiseijoho/shisaku_keikaku/kodomokateibu_shisaku_keikaku/1048697.html)

For this product's **synthetic** MiroFish evaluation:

| Guardian age band | Cases | Child stages |
| --- | ---: | --- |
| 20s | 12 | Elementary lower/upper |
| 30s | 24 | Elementary lower/upper, middle, high |
| 40s | 24 | Elementary lower/upper, middle, high |
| 50s | 24 | Elementary lower/upper, middle, high |
| 60+ | 12 | Elementary lower/upper; grandparent caregivers |

Each age/stage cell has six contexts: short evening check-in, children at different schools, paper-first communication, Korean/shift-work, English/recent relocation, and Chinese/shared pickup coordination. Language totals are JA 48, KO/EN/ZH 16 each. Foreign-language contexts are deliberately oversampled to expose failure modes. The design is purposive and does not measure Tokyo population proportions, age-specific demand, satisfaction or willingness to pay. Age never implies digital ability. No real parent's age, child's name, birth date or private school communication was collected.

## Engineering consequences

1. Key relationships by reviewed source/collection IDs, municipality and school type. Do not join schools just because names or grade numbers match.
2. Keep school notices, municipal guidance, Gakudo admissions/facility references, Asobee letters and private daily Gakudo communications distinct.
3. Treat public-source identity, endpoint reachability, body readability and actual notification delivery as separate claims.
4. Preserve original links and issue/publication/event date distinctions. Unreadable text must not become an invented summary.
5. School/grade switching must not silently alter previously consented notification filters. Different children's views must not share stale detail responses.
6. Follow the new source-provenance report alongside the live quality gate. Neither establishes comprehensive Tokyo coverage.

## Actual-parent pilot acceptance, still required

Recruit through the user's Musashino acquaintances first; record voluntary age *bands* only if useful and consented, never infer them. Include at least two households with children at different schools, two non-Japanese-reading guardians and caregivers who rely on paper; overlap is fine. This is a recruitment plan, not completed testing.

- Find one current grade-specific preparation/deadline in three minutes and verify it against the original.
- Switch between two schools/grades, then explain which child's material is visible and which notification conditions remain registered.
- Explain what is **not** collected, especially private Gakudo pickup/day-to-day communications.
- Identify a delayed or unreadable source without assuming there are no new notices.
- On real iOS/Android devices, consent, receive a test notification, revoke consent, and verify that no further notification arrives.
- Record actual task success, wrong-school incidents, missed deadlines, confusion, time and neutral/negative feedback. Do not substitute simulated scores.

Commercial release remains contingent on these observations, source/data-quality gaps, reliable operations/recovery, privacy/security review and the previously deferred operator/support requirements. This document is research and an engineering plan, not legal approval or a launch certificate.
