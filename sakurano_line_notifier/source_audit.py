"""Live, read-only source audit. Does not enroll parents or send notifications."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .config import Settings
from .web_catalog import CatalogService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--sources", type=Path, default=Path("sources.json"))
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = replace(Settings.load(args.config), web_catalog_cache_path=None)
    service = CatalogService(settings, args.sources)
    sources = [source for source in service.sources if source.enabled and (not args.only or source.id in args.only)]
    if not sources:
        parser.error("no matching enabled sources")
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        # This command audits direct upstream reachability from its own host,
        # even when the web deployment consumes scheduled snapshots.
        futures = {pool.submit(service._scan_source, source, source.default_grade): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                result = future.result()
                row = {**result.coverage(), "warnings": list(result.warnings), "samples": [
                    {"title": notice.title, "url": notice.url, "published": notice.published_label,
                     "event_date": notice.event_date, "deadline_date": notice.deadline_date}
                    for notice in result.notices[:3]
                ]}
            except Exception as exc:
                row = {"source_id": source.id, "source_name": source.name, "status": "unavailable", "notice_count": 0,
                       "warnings": [f"{type(exc).__name__}: {exc}"]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    service.close()
    failed = [row["source_id"] for row in rows if row["warnings"] or row["notice_count"] == 0]
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "sources_checked": len(rows),
              "failed_sources": failed, "scope": "Registered public sources only; not private parent communications or a completeness guarantee.",
              "sources": sorted(rows, key=lambda row: row["source_id"])}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "sources"}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
