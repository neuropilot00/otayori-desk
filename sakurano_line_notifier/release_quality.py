"""Read-only public-catalog quality gate, separate from process/DB readiness."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urldefrag, urlparse

import requests

from .web_catalog import SourceConfig, load_sources


PUBLIC_CATALOG = "https://otayori-web-production.up.railway.app/api/notices?source_id=all"
MAX_BYTES = 8_000_000


def evaluate_catalog(payload: dict, sources: list[SourceConfig], *, now: datetime,
                     max_age_minutes: int = 45) -> dict:
    """Require explicit per-source evidence; never infer completeness from HTTP 200."""
    if not isinstance(payload, dict) or not isinstance(payload.get("coverage"), list):
        raise ValueError("expected an all-source coverage snapshot")
    if now.tzinfo is None or not 1 <= max_age_minutes <= 1440:
        raise ValueError("timezone and bounded freshness target required")
    filters = payload.get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("invalid snapshot filters")
    if any(filters.get(key) not in allowed for key, allowed in {
        "source_id": {"all", "*"}, "grade": {"default", "全学年"},
        "feed": {"all", "*"}, "group": {"all", "*"},
        "level": {"all", "*"}, "ward": {"all", "*"},
    }.items()):
        raise ValueError("quality audit requires an unfiltered all-source snapshot")
    expected = {source.id: source for source in sources if source.enabled}
    rows = payload["coverage"]
    if any(not isinstance(row, dict) or not isinstance(row.get("source_id"), str) for row in rows):
        raise ValueError("invalid coverage rows")
    counts = Counter(row["source_id"] for row in rows)
    errors = [f"unknown_source:{key}" for key in counts if key not in expected]
    errors += [f"duplicate_source:{key}" for key, count in counts.items() if count != 1]
    notices = payload.get("notices")
    if not isinstance(notices, list) or any(not isinstance(item, dict) for item in notices):
        raise ValueError("invalid notice list")
    notice_counts: Counter = Counter()
    readable_counts: Counter = Counter()
    for notice in notices:
        source_id = notice.get("source_id")
        source = expected.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            errors.append("notice_unknown_source")
            continue
        notice_counts[source.id] += 1
        if notice.get("extraction_status") == "ok":
            if (isinstance(notice.get("excerpt"), str) and notice["excerpt"].strip()
                    and type(notice.get("line_count")) is int and notice["line_count"] > 0):
                readable_counts[source.id] += 1
            else:
                errors.append(f"empty_readable_notice:{source.id}")
        elif notice.get("extraction_status") != "original_only":
            errors.append(f"invalid_extraction_status:{source.id}")
        identity = {
            "source_name": source.name, "ward": source.ward, "level": source.level,
            "source_group": source.source_group, "feed_group": source.feed_group,
            "coverage_kind": source.coverage_kind,
        }
        if (any(notice.get(key) != value for key, value in identity.items())
                or notice.get("grade") not in source.grades
                or (source.source_group == "after_school" and notice.get("kind") != source.content_kind)):
            errors.append(f"notice_identity_mismatch:{source.id}")
        try:
            url = urlparse(notice.get("url", ""))
            hosts = {urlparse(page).hostname for page in source.page_urls} | set(source.allowed_hosts)
            safe = url.scheme in {"http", "https"} and url.hostname in hosts and not url.username and not url.password and url.port in {None, 80, 443}
            if safe and source.mode in {"html_page", "static"}:
                safe = urldefrag(url.geturl())[0] in {urldefrag(page)[0] for page in source.page_urls}
        except (ValueError, TypeError, AttributeError):
            safe = False
        if not safe:
            errors.append(f"notice_source_url_mismatch:{source.id}")
    by_id = {row["source_id"]: row for row in rows}
    report = []
    for source in expected.values():
        row = by_id.get(source.id)
        reasons = []
        notes = []
        age = None
        if row is None:
            reasons.append("missing_source")
        else:
            if any(row.get(key) != value for key, value in {
                "page_url": source.page_url, "collection_driver": source.collection_driver,
                "coverage_kind": source.coverage_kind, "content_kind": source.content_kind,
            }.items()):
                reasons.append("registry_mismatch")
            notice_count, readable = row.get("notice_count"), row.get("readable_count")
            if (type(notice_count) is not int or type(readable) is not int
                    or not 0 <= readable <= notice_count):
                reasons.append("invalid_counts")
            elif readable < notice_count:
                reasons.append("unreadable_body")
            excluded = row.get("audience_excluded_count", 0)
            if notice_count == 0 and not (type(excluded) is int and excluded > 0):
                reasons.append("empty_source_requires_review")
            if type(notice_count) is int and notice_count != notice_counts[source.id]:
                reasons.append("notice_count_mismatch")
            if type(readable) is int and readable != readable_counts[source.id]:
                reasons.append("readable_count_mismatch")
            if row.get("status") in {"unavailable", "unknown"}:
                reasons.append("source_unavailable")
            issues = row.get("issue_codes")
            if not isinstance(issues, list) or any(not isinstance(item, str) for item in issues):
                reasons.append("invalid_issue_codes")
            else:
                for issue in issues:
                    # Bounded historical collection is not a collection outage.
                    # A refresh in flight is not a failure if the saved body
                    # and timestamp still satisfy the checks below.
                    (notes if issue in {"limit", "refreshing"} else reasons).append(issue)
            if source.mode == "static" and source.coverage_kind != "reference":
                reasons.append("static_source_cannot_be_live_notices")
            if source.mode == "static" and source.coverage_kind == "reference":
                notes.append("static_reference_not_live")
            else:
                try:
                    checked = datetime.fromisoformat(row["checked_at"])
                    if checked.tzinfo is None:
                        raise ValueError("timezone required")
                    age = (now - checked).total_seconds() / 60
                    if age < -5:
                        reasons.append("future_timestamp")
                    elif age >= max_age_minutes:
                        reasons.append("over_freshness_target")
                except (KeyError, TypeError, ValueError):
                    reasons.append("unknown_check_time")
                if row.get("freshness_status") not in {"fresh", "stale", "pending", "unknown"}:
                    reasons.append("invalid_freshness")
                elif row["freshness_status"] != "fresh":
                    reasons.append(row["freshness_status"])
        report.append({
            "source_id": source.id, "collection_id": source.collection_id,
            "source_group": source.source_group, "coverage_kind": source.coverage_kind,
            "checked_at": row.get("checked_at", "") if row else "",
            "age_minutes": round(age, 1) if age is not None else None,
            "issues": sorted(set(reasons)), "notes": sorted(set(notes)),
        })
    return {
        "schema_version": 1, "audited_at": now.isoformat(),
        "ok": not errors and all(not row["issues"] for row in report),
        "freshness_target_minutes": max_age_minutes,
        "scope": "Registered public endpoints only; not proof of complete school communications or push receipt.",
        "registry_errors": sorted(set(errors)),
        "sources_checked": len(report),
        "sources_with_issues": sum(bool(row["issues"]) for row in report),
        "sources": report,
    }


def fetch_public_snapshot() -> dict:
    # Fixed public destination, no credentials, redirects, or ambient proxy auth.
    with requests.Session() as session:
        session.trust_env = False
        with session.get(PUBLIC_CATALOG, timeout=(5, 45), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f"public catalog HTTP {response.status_code}")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("catalog snapshot exceeds size limit")
    return json.loads(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    parser.add_argument("--snapshot", type=Path, help="Audit an existing public API snapshot offline")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-age-minutes", type=int, default=45)
    args = parser.parse_args()
    try:
        if args.snapshot and args.snapshot.stat().st_size > MAX_BYTES:
            raise ValueError("catalog snapshot exceeds size limit")
        payload = json.loads(args.snapshot.read_bytes()) if args.snapshot else fetch_public_snapshot()
        report = evaluate_catalog(payload, load_sources(args.sources), now=datetime.now(timezone.utc),
                                  max_age_minutes=args.max_age_minutes)
    except (ValueError, OSError, requests.RequestException) as exc:
        # No response bodies, credentials, filesystem paths or exception strings in logs.
        report = {"ok": False, "audit_failed": type(exc).__name__}
        exit_code = 2
    else:
        exit_code = 0 if report["ok"] else 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
