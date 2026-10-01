# Free-pilot release check — 2026-10-01

Scope: nearby-parent testing, not a paid commercial release. Operator identity, billing and calendar integration are deferred. This is an engineering verification record, not certification or a legal opinion.

## Changes checked

- Japanese privacy/terms/source policy; optional notification consent; device-scoped export, unsubscribe and deletion; feedback template copied locally, not submitted to a third party.
- Random HttpOnly/SameSite device cookie, Secure on the configured public HTTPS origin. Cookie values are hashed for ownership, never used to reset rate limits. No global subscription counts, endpoint/key values or raw exceptions in public responses.
- Same-origin JSON POST protection; body/time/connection limits; actual-peer-IP plus global mutation limits. Forged rotating cookies and GET refresh bypasses have regression tests. Proxy/NAT clients share peer-IP limits; a trusted edge-wide limiter is still needed before broad scaling.
- Allowlisted Push providers, key validation, no outbound redirects, provider timeouts; per-recipient delivery ledgers and scanner locks; legacy consent is renewed before sending; 180-day expiry; generic lockscreen messages; enrollment cap and kill switch.
- Reviewed collection-host allowlists, public-IP checks, bounded responses and redirect validation. PDF page/text limits reduce resource use but are not a process sandbox.
- Persistent cache age survives restart, source-configuration changes invalidate cached data, single-school requests share scans, failed/partial refreshes preserve prior readable information with warnings.
- Public-catalog backup/restore CLI verifies consistency/integrity and refuses subscription data or overwrite of an existing destination. Backups are manual, not offsite disaster recovery.
- Readiness endpoint and CI unit/syntax/dependency checks, including weekly dependency audit.

## Verification

- Python offline suite: 90 tests passing after the rotating-cookie regression.
- JavaScript syntax: `node --check` for `web/app.js`, `web/policies.js`, `web/sw.js`.
- `git diff --check`.
- Fresh requirements audit initially passed, but installed-environment audit exposed vulnerable `urllib3 2.7.0` and `pip 26.1.2`. Upgraded and pinned `urllib3==2.8.0`, `pip==26.2`; the installed-environment re-audit reported no known vulnerabilities. This is not a claim that no unknown vulnerability exists.
- Local runtime: `/api/ready` passed; Sakurano grade 1 returned 41 public entries with no collection warning in the observed scan. All sources returned 194 entries and 7 warnings (including image-only PDFs without OCR); that scan was explicitly marked incomplete.
- Browser: successful manual refresh, policy navigation, consent-before-permission controls and device-settings panel. Mobile layout checked at 390×844; school-change label kept on one line. Real browser Push permission/delivery was not granted or tested in the agent browser.
- Independent code review found a rotating-cookie throttle bypass; changed throttling to actual peer IP and added a regression test before release.

## Still requires pilot evidence

Real iOS/Android notification delivery and withdrawal, feedback from actual parents, school/source coverage review, licensing and public-document privacy review, and commercial legal/identity requirements remain open. PostgreSQL locking/migration tests use mocks, not a live database. Provider acceptance is not proof of receipt, and a process crash after acceptance can still cause a retry. TimeTree/Google Calendar integration was researched but is not included in this release.
