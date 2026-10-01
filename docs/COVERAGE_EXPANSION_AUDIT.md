# Public-source coverage expansion — 2026-10-02 JST

## Scope and implementation

Registry expanded from 36 to **75 source records**: 21 school-category siblings (including two embedded-PDF admission pages), six city lists, and 12 school-specific public Asobee newsletters. This does not mean 75 schools or complete private-message coverage. Existing 12 Musashino school collections and grade IDs remain unchanged.

Research evidence: [school review](SCHOOL_COVERAGE_EXPANSION.md), [city/operator review](CITY_COVERAGE_EXPANSION.md), [page-level PDF repair](PDF_COVERAGE_EXPANSION.md). The school research report describes an intermediate 55-source snapshot. Its two embedded-PDF gaps at Oonoden and Kyonan were subsequently fixed and registered; all three discovered PDFs were read successfully.

Collection fixes: filter explicit non-target grades before document caps; numeric CMS IDs and normalized upload timestamps for discovery order only; discover embedded PDFs; separate category budgets; preserve allowed-host body attachment links; reject unread PDF pages instead of accepting a partial body. Multi-session sports listings keep their original schedule and no single event date, avoiding false past-event archiving/calendar export. Generic PDF download labels use their own source name.

New Asobee records follow only their mapped school and corresponding club collection. City sources are shared within the ward, not presented as school announcements. The six new city sources use the existing authenticated GitHub Actions sync because Railway receives 403 from that city host. Total scheduled city records: **21**, every hour at minutes 7 and 37; server-driven sources retain the configured background interval.

## Live source audit

Read-only direct official-source checks, no parent enrollment or push sends:

```sh
python -m sakurano_line_notifier.source_audit --output state/coverage-expansion-all.json
python -m sakurano_line_notifier.source_audit --only musashino_oonoden_es_new_students --only musashino_kyounan_es_new_students --only musashino_family_sports_events --output state/coverage-expansion-extra.json
```

Local verification used installed Poppler/Tesseract and Japanese language data. First run: 73 sources. Second run adds the two embedded-PDF sources and rechecks recurring sports dates after the fix. Combined: **75 sources; 478 retained records; 460 readable; 18 original-only; zero sources with no retained records**. Counts are source-record counts (some originals may appear in more than one category), not unique new notices. Checks finished at 2026-10-02 00:00–00:01 JST.

The full audit correctly exited **1**, not green: 11 sources include unreadable documents. The targeted follow-up passed. Unreadable totals:

| Source | Retained / readable |
| --- | ---: |
| 第一小 保護者案内 | 5 / 4 |
| 第二小 配布資料 | 24 / 23 |
| 第三小 保護者案内 | 6 / 4 |
| 第四小 学校・保健だより | 14 / 9 |
| 桜町小 学校だより | 4 / 1 |
| 一小・三小・五小・本宿・関前南・桜野 あそべえ | each 1 / 0 |

Remaining six Asobee newsletters read successfully. Unreadable records preserve the official link and explicit warning; their bodies are not summarized or counted as readable. Causes include low OCR confidence, encrypted/invalid text, and long image booklets beyond resource limits. Quality thresholds were not weakened. Original-only and failed source results are excluded from normal new-content push eligibility.

Thirteen sources reach their bounded document cap; this is shown as a coverage limit, not an assertion that older archives were exhausted. No fixed 2026/2027 filename gate is used. The reviewed Asobee index still advertises September; no October document was invented. PDF/HTML publication dates, issue months and event dates remain separate. Two current food articles and four sports articles were read; only the actual future dates (for example October 31 food festival and October 12 sports festival) belong in upcoming events.

## Security and notification checks

Attachment links are body-scoped, escaped in UI, host-allowlisted, and reject script URLs, credentials and nonstandard ports. No externally hosted attachments are automatically downloaded. HTML attachment content is explicitly unverified. Existing sync bearer authentication, payload bounds, fingerprint validation, replay protection and durable write checks remain in place.

Existing expanded sources carry `notification_revision: coverage-20261001b`. Their newly discovered historical records are baselined without a flood of pushes; already pending retries are preserved. Regression tests exercise both. Actual device notification delivery is not tested in this change.

## Release verification

Local Python/Node results and GitHub/Railway acceptance evidence are appended after release. Source audits alone are not deployment proof. No claim of complete collection of private parent apps, school mail, paper handouts or every official archive is made.
