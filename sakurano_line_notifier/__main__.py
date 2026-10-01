from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import ConfigurationError, Settings
from .pipeline import PipelineError, SchoolNotifier
from .state import StateError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="학교 공지를 LINE으로 보내거나 보호자용 웹 베타로 보여줍니다")
    parser.add_argument("--config", type=Path, default=Path("config.json"), help="configuration JSON path")
    subparsers = parser.add_subparsers(dest="command")
    for command in ("run", "prepare", "deliver"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--grade", help="target grade, e.g. 1年生, 2, or 全学年")
        subparser.add_argument("--dry-run", action="store_true", help="do not send LINE or write state")
    web_parser = subparsers.add_parser("web", help="start the parent-facing multi-school beta")
    web_parser.add_argument("--sources", type=Path, help="source registry JSON path (default: sources.json next to config)")
    web_parser.add_argument("--host", default="127.0.0.1", help="HTTP bind host")
    web_parser.add_argument("--port", type=int, default=8765, help="HTTP port")
    return parser


def _log(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    command = args.command or "run"
    try:
        settings = Settings.load(args.config, grade_override=getattr(args, "grade", None))
        if command == "web":
            from .web_catalog import CatalogService
            from .web_server import run_server

            sources_path = args.sources or settings.config_path.parent / "sources.json"
            run_server(CatalogService(settings, sources_path), host=args.host, port=args.port, settings=settings)
            return 0
        notifier = SchoolNotifier(settings)
        dry_run = bool(getattr(args, "dry_run", False))
        if command == "prepare":
            result = notifier.prepare(dry_run=dry_run)
            _log(
                "prepare_complete",
                status=result.status,
                grade=result.grade,
                candidate_count=result.candidate_count,
                notification_id=result.notification_id,
                state_changed=result.state_changed,
            )
        elif command == "deliver":
            result = notifier.deliver(dry_run=dry_run)
            _log(
                "deliver_complete",
                status=result.status,
                notification_id=result.notification_id,
                request_id=result.request_id,
                accepted_via_retry=result.accepted_via_retry,
            )
        else:
            prepared, delivered = notifier.run(dry_run=dry_run)
            _log(
                "run_complete",
                prepare_status=prepared.status,
                grade=prepared.grade,
                candidate_count=prepared.candidate_count,
                deliver_status=delivered.status if delivered else "dry_run",
            )
        return 0
    except (ConfigurationError, PipelineError, StateError) as exc:
        _log("run_failed", error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
