from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Raised when the application configuration is invalid."""


DEFAULT_PAGE_URL = "https://sakurano-e.musashino-city.ed.jp/modules/hp_jpage34/"


def _parse_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean value")


def _parse_positive_number(value: object, name: str, minimum: float = 0.1) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a number") from exc
    if parsed < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return parsed


def _parse_positive_int(value: object, name: str, minimum: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if parsed < minimum:
        raise ConfigurationError(f"{name} must be at least {minimum}")
    return parsed


def _resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


@dataclass(frozen=True)
class Settings:
    config_path: Path
    page_url: str
    grade: str
    state_path: Path
    notify_existing_on_first_run: bool
    request_timeout_seconds: float
    max_document_bytes: int
    line_max_chars: int
    pending_retry_max_hours: float
    line_channel_access_token: str | None
    line_to: str | None
    user_agent: str
    web_cache_ttl_seconds: float = 300.0
    web_push_state_path: Path | None = None
    web_push_database_path: Path | None = None
    web_push_database_url: str | None = None
    web_push_public_key: str | None = None
    web_push_private_key: str | None = None
    web_push_contact: str | None = None
    web_push_scan_interval_seconds: float = 900.0

    @classmethod
    def load(cls, config_path: Path, grade_override: str | None = None) -> "Settings":
        config_path = config_path.expanduser().resolve()
        if not config_path.is_file():
            raise ConfigurationError(f"config file not found: {config_path}")
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigurationError(f"could not read config file: {config_path}") from exc
        if not isinstance(raw, dict):
            raise ConfigurationError("config.json must contain a JSON object")

        page_url = str(os.getenv("SCHOOL_PAGE_URL") or raw.get("page_url") or DEFAULT_PAGE_URL).strip()
        parsed_url = urlparse(page_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError("page_url must be an absolute HTTP(S) URL")

        grade = str(grade_override or os.getenv("SCHOOL_GRADE") or raw.get("grade") or "1年生").strip()
        if not grade:
            raise ConfigurationError("grade must not be empty")

        root = config_path.parent
        state_value = str(os.getenv("STATE_PATH") or raw.get("state_path") or "state/state.json")
        notify_value = os.getenv("NOTIFY_EXISTING_ON_FIRST_RUN")
        notify_existing = (
            _parse_bool(notify_value, "NOTIFY_EXISTING_ON_FIRST_RUN")
            if notify_value is not None
            else _parse_bool(raw.get("notify_existing_on_first_run", False), "notify_existing_on_first_run")
        )

        timeout_value = os.getenv("REQUEST_TIMEOUT_SECONDS") or raw.get("request_timeout_seconds", 30)
        max_bytes_value = os.getenv("MAX_DOCUMENT_BYTES") or raw.get("max_document_bytes", 10_000_000)
        line_chars_value = os.getenv("LINE_MAX_CHARS") or raw.get("line_max_chars", 4_800)
        pending_hours_value = os.getenv("PENDING_RETRY_MAX_HOURS") or raw.get("pending_retry_max_hours", 23)
        web_cache_ttl_value = os.getenv("WEB_CACHE_TTL_SECONDS") or raw.get("web_cache_ttl_seconds", 300)
        web_push_state_value = str(os.getenv("WEB_PUSH_STATE_PATH") or raw.get("web_push_state_path") or "state/push_subscriptions.json")
        web_push_database_raw = os.getenv("WEB_PUSH_DATABASE_PATH") or raw.get("web_push_database_path")
        web_push_database_url = (os.getenv("WEB_PUSH_DATABASE_URL") or os.getenv("DATABASE_URL") or raw.get("web_push_database_url") or "").strip() or None
        web_push_scan_interval_value = os.getenv("WEB_PUSH_SCAN_INTERVAL_SECONDS") or raw.get("web_push_scan_interval_seconds", 900)

        line_max_chars = _parse_positive_int(line_chars_value, "line_max_chars", minimum=100)
        if line_max_chars > 5_000:
            raise ConfigurationError("line_max_chars cannot exceed LINE's 5,000-character text limit")
        pending_retry_max_hours = _parse_positive_number(pending_hours_value, "pending_retry_max_hours")
        if pending_retry_max_hours >= 24:
            raise ConfigurationError("pending_retry_max_hours must be less than LINE's 24-hour retry-key window")

        return cls(
            config_path=config_path,
            page_url=page_url,
            grade=grade,
            state_path=_resolve_path(root, state_value),
            notify_existing_on_first_run=notify_existing,
            request_timeout_seconds=_parse_positive_number(timeout_value, "request_timeout_seconds"),
            max_document_bytes=_parse_positive_int(max_bytes_value, "max_document_bytes", minimum=1_024),
            line_max_chars=line_max_chars,
            pending_retry_max_hours=pending_retry_max_hours,
            line_channel_access_token=(os.getenv("LINE_CHANNEL_ACCESS_TOKEN") or "").strip() or None,
            line_to=(os.getenv("LINE_TO") or "").strip() or None,
            user_agent="sakurano-line-notifier/1.0 (+GitHub Actions)",
            web_cache_ttl_seconds=_parse_positive_number(web_cache_ttl_value, "web_cache_ttl_seconds", minimum=30),
            web_push_state_path=_resolve_path(root, web_push_state_value),
            web_push_database_path=_resolve_path(root, str(web_push_database_raw)) if web_push_database_raw else None,
            web_push_database_url=web_push_database_url,
            web_push_public_key=(os.getenv("WEB_PUSH_PUBLIC_KEY") or "").strip() or None,
            web_push_private_key=(os.getenv("WEB_PUSH_PRIVATE_KEY") or "").strip() or None,
            web_push_contact=(os.getenv("WEB_PUSH_CONTACT") or "").strip() or None,
            web_push_scan_interval_seconds=_parse_positive_number(web_push_scan_interval_value, "web_push_scan_interval_seconds", minimum=60),
        )
