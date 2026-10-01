from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = 1


class StateError(RuntimeError):
    """Raised when the persisted state cannot be trusted."""


def empty_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "documents": {},
        "notifications": {},
        "baseline_grades": [],
        "pending": None,
        "last_checked_at": None,
        "last_sent_at": None,
    }


def _validate_state(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StateError("state must be a JSON object")
    if value.get("version") != STATE_VERSION:
        raise StateError(f"unsupported state version: {value.get('version')!r}")
    for key in ("documents", "notifications"):
        if not isinstance(value.get(key), dict):
            raise StateError(f"state.{key} must be an object")
    if not isinstance(value.get("baseline_grades"), list):
        raise StateError("state.baseline_grades must be an array")
    if value.get("pending") is not None and not isinstance(value.get("pending"), dict):
        raise StateError("state.pending must be an object or null")
    return value


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StateError(f"could not read state file: {path}") from exc
    return _validate_state(value)


def save_state(path: Path, value: dict[str, Any]) -> None:
    _validate_state(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def age_in_hours(timestamp: str) -> float:
    value = timestamp.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() / 3600)

