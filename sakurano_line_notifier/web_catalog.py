from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
import unicodedata
from email.message import Message
from concurrent.futures import Future, ThreadPoolExecutor, as_completed, wait
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urldefrag, urljoin, urlparse

from .extractor import (
    ExtractionError,
    clean_text_lines,
    extract_document_text,
    html_to_text,
    normalize_grade,
    select_relevant_text,
    sha256_bytes,
    sha256_text,
)
from .fetcher import FetchError, HttpFetcher, LinkCandidate, parse_relevant_links
from .formatter import KIND_LABELS, categorize_text
from .notice_dates import activity_dates, publication_date, calendar_date
from .catalog_watchdog import CatalogDispatchWatchdog


class CatalogError(RuntimeError):
    """Raised when the source registry or a requested source is invalid."""


SOURCE_GROUP_LABELS = {
    "school": "学校",
    "municipality": "武蔵野市・教育委員会／市役所",
    "after_school": "学童",
}

FEED_GROUPS = {"notices", "events"}


@dataclass(frozen=True)
class SourceConfig:
    id: str
    name: str
    ward: str
    level: str
    page_url: str
    mode: str
    default_grade: str
    grades: tuple[str, ...]
    page_urls: tuple[str, ...]
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    max_documents: int = 12
    enabled: bool = True
    note: str = ""
    collection_id: str = ""
    collection_root: bool = True
    source_group: str = "school"
    feed_group: str = "notices"
    content_kind: str = "document"
    latitude: float | None = None
    longitude: float | None = None
    static_text: str = ""
    static_title: str = ""
    allowed_hosts: tuple[str, ...] = ()
    link_patterns: tuple[str, ...] = ()
    discovery_depth: int = 0
    coverage_kind: str = "notices"
    coverage_note: str = "登録した公開ページの直近の資料が対象です。非公開の連絡帳は含みません。"
    shared_with_ward: bool = False
    collection_driver: str = "server"
    notification_revision: str = ""
    related_collections: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "collection_driver": self.collection_driver,
            "name": self.name,
            "ward": self.ward,
            "level": self.level,
            "page_url": self.page_url,
            "page_urls": list(self.page_urls),
            "mode": self.mode,
            "default_grade": self.default_grade,
            "grades": list(self.grades),
            "include_patterns": list(self.include_patterns),
            "exclude_patterns": list(self.exclude_patterns),
            "max_documents": self.max_documents,
            "enabled": self.enabled,
            "note": self.note,
            "collection_id": self.collection_id or self.id,
            "collection_root": self.collection_root,
            "related_collections": list(self.related_collections),
            "source_group": self.source_group,
            "source_group_label": SOURCE_GROUP_LABELS.get(self.source_group, self.source_group),
            "feed_group": self.feed_group,
            "content_kind": self.content_kind,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "coverage_kind": self.coverage_kind,
            "coverage_note": self.coverage_note,
        }


@dataclass(frozen=True)
class CatalogNotice:
    id: str
    source_id: str
    source_name: str
    ward: str
    level: str
    grade: str
    title: str
    kind: str
    url: str
    text: str
    content_hash: str
    date_label: str
    published_label: str
    source_group: str
    feed_group: str
    coverage_kind: str = "notices"
    event_date: str = ""
    deadline_date: str = ""
    date_kind: str = "published"
    extraction_status: str = "ok"
    attachments: tuple[tuple[str, str], ...] = ()

    def categories(self) -> dict[str, list[str]]:
        return {key: value for key, value in categorize_text(self.text, self.kind).items() if value}

    def to_summary(self) -> dict[str, Any]:
        categories = self.categories()
        lines = clean_text_lines(self.text)
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "ward": self.ward,
            "level": self.level,
            "grade": self.grade,
            "title": self.title,
            "kind": self.kind,
            "kind_label": KIND_LABELS.get(self.kind, "関連資料"),
            "url": self.url,
            "date_label": self.date_label,
            "published_label": self.published_label,
            "source_group": self.source_group,
            "source_group_label": SOURCE_GROUP_LABELS.get(self.source_group, self.source_group),
            "feed_group": self.feed_group,
            "category_names": list(categories),
            "excerpt": " ".join(lines[:4])[:320],
            "line_count": len(lines),
            "coverage_kind": self.coverage_kind,
            "event_date": self.event_date,
            "deadline_date": self.deadline_date,
            "date_kind": self.date_kind,
            "extraction_status": self.extraction_status,
        }

    def to_detail(self) -> dict[str, Any]:
        result = self.to_summary()
        result.update({"text": self.text, "categories": self.categories(), "content_hash": self.content_hash,
                       "attachments": [{"title": title, "url": url} for title, url in self.attachments]})
        return result


@dataclass(frozen=True)
class CatalogResult:
    source: SourceConfig
    grade: str
    scanned_at: str
    notices: tuple[CatalogNotice, ...]
    warnings: tuple[str, ...] = ()
    discovered_count: int = 0
    limit_reached: bool = False
    refreshing: bool = False
    freshness_status: str = "fresh"

    def coverage(self) -> dict[str, Any]:
        freshness = self.freshness_status if self.scanned_at else ("pending" if self.refreshing or self.freshness_status == "pending" else "unknown")
        issues = []
        if freshness == "stale":
            issues.append("stale")
        if any(notice.extraction_status != "ok" for notice in self.notices):
            issues.append("extraction")
        if not self.notices and freshness not in {"pending"} and not self.refreshing:
            issues.append("unavailable")
        if self.warnings and not issues and not self.refreshing and freshness != "pending":
            issues.append("collection")
        if self.limit_reached:
            issues.append("limit")
        if self.refreshing:
            issues.append("refreshing")
        return {
            "source_id": self.source.id, "source_name": self.source.name,
            "page_url": self.source.page_url,
            "checked_at": self.scanned_at if self.source.mode != "static" else "",
            "status": ("partial" if self.notices else "unavailable") if self.warnings else (
                "reference" if self.source.coverage_kind == "reference" else "checked"),
            "coverage_kind": self.source.coverage_kind,
            "coverage_note": self.source.coverage_note + (
                " 約30分ごとに定期収集します。更新ボタンでは最新の保存データを確認します。"
                if self.source.collection_driver == "scheduled" else ""),
            "notice_count": len(self.notices),
            "readable_count": sum(notice.extraction_status == "ok" for notice in self.notices),
            "discovered_count": self.discovered_count,
            "limit_reached": self.limit_reached,
            "refreshing": self.refreshing,
            "collection_driver": self.source.collection_driver,
            "freshness_status": freshness,
            "issue_codes": issues,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "grade": self.grade,
            "scanned_at": self.scanned_at,
            "notices": [notice.to_summary() for notice in self.notices],
            "warnings": list(self.warnings),
        }


class CatalogCacheStore:
    """Small persistent cache for public notices; no parent identity data is stored."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS catalog_results (
                    cache_key TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=5000")
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _source_fingerprint(source: SourceConfig) -> str:
        return sha256_text("collection-v2\n" + json.dumps(asdict(source), sort_keys=True, ensure_ascii=False))

    def load(self, source: SourceConfig, grade: str) -> CatalogResult | None:
        key = f"{source.id}\0{grade}"
        try:
            with self._lock, self._connect() as connection:
                row = connection.execute(
                    "SELECT payload_json FROM catalog_results WHERE cache_key = ?",
                    (key,),
                ).fetchone()
        except sqlite3.Error:
            return None
        if not row:
            return None
        try:
            payload = json.loads(row[0])
            if not isinstance(payload, dict):
                return None
            if payload.get("source_id") != source.id or payload.get("grade") != grade:
                return None
            if payload.get("source_fingerprint") != self._source_fingerprint(source):
                return None
            notices = tuple(self._notice_from_payload(item) for item in payload.get("notices", []))
            return CatalogResult(source, grade, str(payload["scanned_at"]), notices, tuple(str(item) for item in payload.get("warnings", [])), int(payload.get("discovered_count", len(notices))), bool(payload.get("limit_reached", False)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def save(self, result: CatalogResult) -> None:
        key = f"{result.source.id}\0{result.grade}"
        payload = json.dumps(
            {
                "source_id": result.source.id,
                "source_fingerprint": self._source_fingerprint(result.source),
                "grade": result.grade,
                "scanned_at": result.scanned_at,
                "warnings": list(result.warnings),
                "discovered_count": result.discovered_count,
                "limit_reached": result.limit_reached,
                "notices": [notice.to_detail() for notice in result.notices],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            with self._lock, self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO catalog_results(cache_key, source_id, grade, scanned_at, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        scanned_at = excluded.scanned_at,
                        payload_json = excluded.payload_json,
                        updated_at = excluded.updated_at
                    """,
                    (key, result.source.id, result.grade, result.scanned_at, payload, time.time()),
                )
        except sqlite3.Error:
            # Public collection remains available if the optional cache volume is unavailable.
            return

    @staticmethod
    def _notice_from_payload(payload: object) -> CatalogNotice:
        if not isinstance(payload, dict):
            raise TypeError("cached notice must be an object")
        return CatalogNotice(
            id=str(payload["id"]),
            source_id=str(payload["source_id"]),
            source_name=str(payload["source_name"]),
            ward=str(payload["ward"]),
            level=str(payload["level"]),
            grade=str(payload["grade"]),
            title=str(payload["title"]),
            kind=str(payload["kind"]),
            url=str(payload["url"]),
            text=str(payload.get("text", "")),
            content_hash=str(payload.get("content_hash", "")),
            date_label=str(payload.get("date_label", "更新資料")),
            published_label=str(payload.get("published_label", "更新資料")),
            source_group=str(payload.get("source_group", "school")),
            feed_group=str(payload.get("feed_group", "notices")),
            coverage_kind=str(payload.get("coverage_kind", "notices")),
            event_date=str(payload.get("event_date", "")),
            deadline_date=str(payload.get("deadline_date", "")),
            date_kind=str(payload.get("date_kind", "published")),
            extraction_status=str(payload.get("extraction_status", "ok")),
            attachments=tuple((str(item["title"]), str(item["url"])) for item in payload.get("attachments", [])),
        )


class _NewsLinkParser(HTMLParser):
    """Collect article links from the Tokyo metropolitan school news index."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"embed", "object", "iframe"}:
            attributes = dict(attrs)
            url = attributes.get("data" if tag.lower() == "object" else "src")
            if url and _is_document_url(url):
                self.anchors.append((url, attributes.get("title") or ""))
        if tag.lower() == "img" and self._href is not None and not any(part.strip() for part in self._text):
            alt = dict(attrs).get("alt") or ""
            self._text.append(re.sub(r"の\d+ページ目のサムネイル$", "", alt))
        if tag.lower() != "a" or self._href is not None:
            return
        href = dict(attrs).get("href")
        if href:
            self._href = href
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


class _ScopedNewsTextParser(HTMLParser):
    """Extract only the article body from the Tokyo metropolitan CMS."""

    BLOCK_TAGS = {"br", "div", "dt", "dd", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._depth = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = dict(attrs)
        if self._depth == 0 and lowered == "div" and "news_detail" in (attributes.get("class") or "").split():
            self._depth = 1
            return
        if self._depth == 0:
            return
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lowered in self.BLOCK_TAGS:
            self.parts.append("\n")
        if lowered not in self.VOID_TAGS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._depth == 0:
            return
        if lowered in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if lowered in self.BLOCK_TAGS:
            self.parts.append("\n")
        if lowered not in self.VOID_TAGS:
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._depth and not self._skip_depth:
            self.parts.append(data)


class _MainContentTextParser(HTMLParser):
    """Extract the main/article body from public municipal HTML pages."""

    BLOCK_TAGS = {"br", "div", "dt", "dd", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._depth = 0
        self._skip_depth = 0
        self.attachments: list[tuple[str, str]] = []
        self._link_href: str | None = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = dict(attrs)
        is_target = (lowered == "main" or (lowered == "article" and attributes.get("id") == "content")
                     or bool(re.fullmatch(r"hp_jpage\d+_read", attributes.get("id") or "")))
        if self._depth == 0 and is_target:
            self._depth = 1
            return
        if self._depth == 0:
            return
        if lowered in {"script", "style", "noscript", "nav", "header", "footer"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if lowered == "a" and attributes.get("href"):
            self._link_href, self._link_text = attributes["href"], []
        elif lowered == "img" and attributes.get("src"):
            self.attachments.append((attributes["src"], attributes.get("alt") or "画像資料"))
            if self._link_href:
                self._link_text.append(attributes.get("alt") or "")
        if lowered in self.BLOCK_TAGS:
            self.parts.append("\n")
        if lowered not in self.VOID_TAGS:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if self._depth == 0:
            return
        if lowered in {"script", "style", "noscript", "nav", "header", "footer"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if lowered == "a" and self._link_href:
            self.attachments.append((self._link_href, " ".join(self._link_text)))
            self._link_href, self._link_text = None, []
        if lowered in self.BLOCK_TAGS:
            self.parts.append("\n")
        if lowered not in self.VOID_TAGS:
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._depth and not self._skip_depth:
            self.parts.append(data)
            if self._link_href:
                self._link_text.append(data)


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _compile_patterns(patterns: Iterable[str], label: str) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise CatalogError(f"invalid {label} pattern: {pattern}") from exc
    return tuple(compiled)


def _parse_source(raw: object, index: int) -> SourceConfig:
    if not isinstance(raw, dict):
        raise CatalogError(f"sources[{index}] must be an object")
    required = ("id", "name", "ward", "level")
    missing = [key for key in required if not str(raw.get(key, "")).strip()]
    if missing:
        raise CatalogError(f"sources[{index}] is missing: {', '.join(missing)}")
    raw_page_urls = raw.get("page_urls")
    if raw_page_urls is None:
        raw_page_urls = [raw.get("page_url", "")]
    if not isinstance(raw_page_urls, list) or not raw_page_urls:
        raise CatalogError(f"sources[{index}].page_urls must be a non-empty list")
    page_urls: list[str] = []
    for page_index, raw_page_url in enumerate(raw_page_urls):
        page_url = str(raw_page_url).strip()
        parsed = urlparse(page_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CatalogError(f"sources[{index}].page_urls[{page_index}] must be an absolute HTTP(S) URL")
        if page_url not in page_urls:
            page_urls.append(page_url)
    page_url = page_urls[0]
    mode = str(raw.get("mode", "pdf")).strip().lower()
    if mode not in {"pdf", "html_news", "html_page", "static", "mixed", "link_index"}:
        raise CatalogError(f"sources[{index}].mode is not supported")
    raw_grades = raw.get("grades")
    if raw_grades is None:
        raw_grades = ["1年生", "2年生", "3年生", "4年生", "5年生", "6年生", "全学年"]
    if not isinstance(raw_grades, list) or not raw_grades:
        raise CatalogError(f"sources[{index}].grades must be a non-empty list")
    try:
        grades = tuple(normalize_grade(str(value)) for value in raw_grades)
        default_grade = normalize_grade(str(raw.get("default_grade", grades[0])))
    except ValueError as exc:
        raise CatalogError(f"sources[{index}] has an invalid grade") from exc
    try:
        max_documents = int(raw.get("max_documents", 12))
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"sources[{index}].max_documents must be an integer") from exc
    if max_documents < 1 or max_documents > 100:
        raise CatalogError(f"sources[{index}].max_documents must be between 1 and 100")
    source_group = str(raw.get("source_group", "school")).strip().lower() or "school"
    if source_group not in SOURCE_GROUP_LABELS:
        raise CatalogError(f"sources[{index}].source_group must be school, municipality, or after_school")
    feed_group = str(raw.get("feed_group", "notices")).strip().lower() or "notices"
    if feed_group not in FEED_GROUPS:
        raise CatalogError(f"sources[{index}].feed_group must be notices or events")
    content_kind = str(raw.get("content_kind", "document")).strip() or "document"
    static_text = str(raw.get("static_text", "")).strip()
    static_title = str(raw.get("static_title", "")).strip()
    if mode == "static" and not static_text:
        raise CatalogError(f"sources[{index}].static_text is required for static sources")
    latitude = _parse_coordinate(raw.get("latitude"), "latitude", index, -90.0, 90.0)
    longitude = _parse_coordinate(raw.get("longitude"), "longitude", index, -180.0, 180.0)
    if (latitude is None) != (longitude is None):
        raise CatalogError(f"sources[{index}] must define both latitude and longitude")
    include_patterns = tuple(str(value) for value in raw.get("include_patterns", []))
    exclude_patterns = tuple(str(value) for value in raw.get("exclude_patterns", []))
    _compile_patterns(include_patterns, "include")
    _compile_patterns(exclude_patterns, "exclude")
    link_patterns = tuple(str(value) for value in raw.get("link_patterns", []))
    _compile_patterns(link_patterns, "link")
    discovery_depth = int(raw.get("discovery_depth", 0))
    if not 0 <= discovery_depth <= 2:
        raise CatalogError("discovery_depth must be between 0 and 2")
    if mode == "link_index" and not link_patterns:
        raise CatalogError("link_index requires reviewed link_patterns")
    allowed_hosts = tuple(str(host).lower() for host in raw.get("allowed_hosts", []))
    if any(not re.fullmatch(r"[a-z0-9.-]+", host) for host in allowed_hosts):
        raise CatalogError("allowed_hosts must contain hostnames only")
    coverage_kind = str(raw.get("coverage_kind", "reference" if mode == "static" else "notices"))
    if coverage_kind not in {"reference", "notices"}:
        raise CatalogError("coverage_kind must be reference or notices")
    collection_driver = str(raw.get("collection_driver", "server"))
    if collection_driver not in {"server", "scheduled"}:
        raise CatalogError("collection_driver must be server or scheduled")
    notification_revision = str(raw.get("notification_revision", ""))
    if not re.fullmatch(r"[A-Za-z0-9_-]{0,64}", notification_revision):
        raise CatalogError("notification_revision must be a short registry version")
    related = raw.get("related_collections", [])
    if not isinstance(related, list) or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) for value in related):
        raise CatalogError("related_collections must contain registry collection IDs")
    return SourceConfig(
        id=str(raw["id"]).strip(),
        name=str(raw["name"]).strip(),
        ward=str(raw["ward"]).strip(),
        level=str(raw["level"]).strip(),
        page_url=page_url,
        mode=mode,
        default_grade=default_grade,
        grades=grades,
        page_urls=tuple(page_urls),
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        max_documents=max_documents,
        enabled=bool(raw.get("enabled", True)),
        note=str(raw.get("note", "")).strip(),
        collection_id=str(raw.get("collection_id", raw["id"])).strip() or str(raw["id"]).strip(),
        collection_root=bool(raw.get("collection_root", True)),
        source_group=source_group,
        feed_group=feed_group,
        content_kind=content_kind,
        latitude=latitude,
        longitude=longitude,
        static_text=static_text,
        static_title=static_title,
        allowed_hosts=allowed_hosts,
        link_patterns=link_patterns,
        discovery_depth=discovery_depth,
        coverage_kind=coverage_kind,
        coverage_note=str(raw.get("coverage_note", SourceConfig.coverage_note)),
        shared_with_ward=bool(raw.get("shared_with_ward", False)),
        collection_driver=collection_driver,
        notification_revision=notification_revision,
        related_collections=tuple(dict.fromkeys(related)),
    )


def _parse_coordinate(value: object, name: str, index: int, minimum: float, maximum: float) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"sources[{index}].{name} must be a number") from exc
    if not minimum <= parsed <= maximum:
        raise CatalogError(f"sources[{index}].{name} must be between {minimum} and {maximum}")
    return parsed


def load_sources(path: Path) -> list[SourceConfig]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"could not read source registry: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise CatalogError("sources.json must contain a sources list")
    sources = [_parse_source(raw, index) for index, raw in enumerate(payload["sources"])]
    ids = [source.id for source in sources]
    if len(set(ids)) != len(ids):
        raise CatalogError("source ids must be unique")
    collections = {source.collection_id for source in sources}
    if any(set(source.related_collections) - collections for source in sources):
        raise CatalogError("related_collections contains an unknown collection")
    return sources


def _news_date(value: str) -> str:
    labelled = publication_date("", value)
    if labelled:
        return labelled
    # A PDF's printed, standalone header date can identify publication. A
    # filename timestamp or an activity date embedded in prose cannot.
    normalized = unicodedata.normalize("NFKC", value)
    for line in normalized.splitlines():
        if re.search(r"(?:日|\d)\s*(?:発行|掲載|公開|更新)\s*$", line):
            parsed = calendar_date(line)
            if parsed:
                return parsed
        if re.fullmatch(r"\s*(?:20\d{2}\s*[年/.-]|令和\s*(?:元|\d+)\s*年)\s*\d{1,2}\s*[月/.-]\s*\d{1,2}\s*日?\s*(?:[（(][月火水木金土日](?:曜日)?[）)])?\s*", line):
            parsed = calendar_date(line)
            if parsed:
                return parsed
    return "更新資料"


def _issue_month(value: str, kind: str | None = None) -> int | None:
    """Return an issue month only when the text looks like a monthly notice."""
    patterns = (
        r"(?:学校だより|学年だより)[^\n]{0,18}?([0-9０-９]{1,2})\s*月\s*号",
        r"([0-9０-９]{1,2})\s*月\s*号",
    )
    normalized = unicodedata.normalize("NFKC", value)
    if kind == "school_news":
        # A school newsletter can mention a future issue in its article body
        # (for example, "the October issue will be published"). Only inspect
        # the document header for the school-news issue label.
        normalized = normalized[:400]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        month = int(match.group(1))
        if 1 <= month <= 12:
            return month
    return None


def _html_page_published_date(page_html: str) -> str:
    return publication_date(page_html, html_to_text(page_html.encode("utf-8"))) or "更新資料"


def _date_labels(candidate: LinkCandidate, text: str, metadata: str = "") -> tuple[str, str]:
    # HTML metadata is authoritative (including unknown); an event date in the
    # body must never become a publication date.
    published_label = metadata if metadata else _news_date(f"{candidate.title}\n{text[:400]}")
    issue_month = _issue_month(f"{candidate.title}\n{text}", candidate.kind)
    if published_label != "更新資料":
        year_match = re.match(r"(20\d{2})/", published_label)
        if year_match and issue_month:
            return f"{year_match.group(1)}/{issue_month:02d}月号", published_label
    elif issue_month and not metadata:
        header = unicodedata.normalize("NFKC", f"{candidate.title}\n{text[:400]}")
        fiscal = re.search(r"令和\s*(\d+)\s*年度", header)
        if fiscal:
            year = 2018 + int(fiscal[1]) + (1 if issue_month <= 3 else 0)
            return f"{year}/{issue_month:02d}月号", published_label
        calendar = re.search(r"(?:(20\d{2})\s*年|令和\s*(\d+)\s*年)\s*\d{1,2}\s*月", header)
        if calendar:
            year = int(calendar[1]) if calendar[1] else 2018 + int(calendar[2])
            return f"{year}/{issue_month:02d}月号", published_label
        # An explicit issue month may use the CMS upload YEAR as context, but
        # the upload timestamp is never presented as its publication date.
        upload = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?:\d{6})?(?!\d)", candidate.url)
        if upload and calendar_date(f"{upload[1]}/{upload[2]}/{upload[3]}"):
            year = int(upload[1]) + (1 if issue_month == 1 and int(upload[2]) == 12 else 0)
            return f"{year}/{issue_month:02d}月号", published_label
    return published_label, published_label


def _news_title(value: str, url: str) -> str:
    title = _clean_title(value)
    title = re.sub(r"^20\d{2}[/-]\d{1,2}[/-]\d{1,2}\s*", "", title)
    title = re.sub(r"^(お知らせ|学校からのお知らせ)\s*", "", title)
    return title or url.rsplit("/", 1)[-1] or url


def _candidate_sort_key(candidate: LinkCandidate) -> tuple[int, str, str]:
    filename = urlparse(candidate.url).path.rsplit("/", 1)[-1]
    timestamp = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?:\d{6})?(?!\d)", filename)
    file_id = re.search(r"/(?:file|download/document)/(\d+)/?$", urlparse(candidate.url).path)
    # Upload timestamps are a discovery ordering hint, never publication dates.
    # Normalize both YYYYMMDD and YYYYMMDDhhmmss to the same scale.
    numeric_date = int(timestamp.group(0).ljust(14, "0")) if timestamp else int(file_id[1]) if file_id else 0
    return numeric_date, _clean_title(candidate.title), candidate.url


def _candidate_matches_grade(candidate: LinkCandidate, grade: str) -> bool:
    if grade == "全学年":
        return True
    title = unicodedata.normalize("NFKC", candidate.title)
    if re.search(r"全学年|全校|共通", title):
        return True
    numbers = set(re.findall(r"(?<!\d)(?:第)?([1-6])(?:年生|学年)", title))
    for match in re.finditer(r"([1-6](?:\s*[・、/〜~～-]\s*[1-6])+)\s*(?:年生|学年)", title):
        values = [int(value) for value in re.findall(r"[1-6]", match[1])]
        if re.search(r"[〜~～-]", match[1]):
            values = list(range(min(values), max(values) + 1))
        numbers.update(map(str, values))
    return not numbers or grade.removesuffix("年生") in numbers


def _html_attachments(html: str, source: SourceConfig, page_url: str) -> tuple[tuple[str, str], ...]:
    # Body-scoped HTMLParser callbacks; no scripts, navigation or remote fetches.
    # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
    parser = _MainContentTextParser()
    parser.feed(html)
    parser.close()
    hosts = {urlparse(url).hostname for url in source.page_urls} | set(source.allowed_hosts)
    links = {}
    for href, title in parser.attachments:
        url = urldefrag(urljoin(page_url, href))[0]
        try:
            parsed = urlparse(url)
            safe = parsed.scheme in {"http", "https"} and parsed.hostname in hosts and not parsed.username and not parsed.password and parsed.port in {None, 80, 443}
        except ValueError:
            safe = False
        if safe and "/_template_/" not in parsed.path and (_is_document_url(url) or parsed.path.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".doc", ".docx", ".xls", ".xlsx"))):
            links.setdefault(url, _clean_title(title)[:500] or "添付資料")
    if len(links) > 80:
        raise ExtractionError("添付資料が確認上限を超えています。公式ページをご確認ください。")
    return tuple((title, url) for url, title in links.items())


def _is_document_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".pdf") or bool(re.search(r"/(?:plugin/attachments|file/get|files/download)/|/(?:file|download/document)/\d+/?$", path))


def _decode_document_html(payload: bytes, content_type: str) -> str:
    message = Message()
    message["content-type"] = content_type
    encoding = message.get_content_charset()
    if not encoding:
        declaration = re.search(rb"<meta\b[^>]*charset\s*=\s*['\"]?\s*([\w-]+)", payload[:8192], re.IGNORECASE)
        encoding = declaration[1].decode("ascii") if declaration else None
    if encoding:
        try:
            return payload.decode(encoding)
        except (LookupError, UnicodeError) as exc:
            raise ExtractionError("HTMLの文字コードを読み取れません。原文をご確認ください。") from exc
    for fallback in ("utf-8-sig", "cp932", "euc-jp"):
        try:
            return payload.decode(fallback)
        except UnicodeError:
            continue
    raise ExtractionError("HTMLの文字コードを読み取れません。原文をご確認ください。")


def _html_page_title(html: str, fallback: str, url: str) -> str:
    if re.search(r'id=[\"\']hp_jpage\d+_read[\"\']', html):
        # ICtea's h1 is the school name, not this notice/page title.
        return _clean_title(fallback)
    for pattern in (r"<h1\b[^>]*>(.*?)</h1>", r"<title\b[^>]*>(.*?)</title>"):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        title = _clean_title(unescape(re.sub(r"<[^>]+>", " ", match.group(1))))
        title = re.split(r"\s*[|｜]\s*", title, maxsplit=1)[0].strip()
        if title:
            return title
    return _clean_title(fallback) or url.rsplit("/", 1)[-1] or url


class CatalogService:
    """Read public school pages into a parent-facing, in-memory beta catalog."""

    def __init__(self, settings: Any, sources_path: Path) -> None:
        self.settings = settings
        self.sources_path = sources_path.expanduser().resolve()
        self.sources = load_sources(self.sources_path)
        self._cache: dict[tuple[str, str], tuple[float, CatalogResult]] = {}
        self._cache_ttl_seconds = max(30.0, float(getattr(settings, "web_cache_ttl_seconds", 300.0)))
        self._max_wait_seconds = min(60.0, max(1.0, float(getattr(settings, "web_catalog_max_wait_seconds", 12.0))))
        self._lock = threading.RLock()
        self._scheduled_collection = os.getenv("WEB_SCHEDULED_COLLECTION", "").lower() == "true"
        self._dispatch_watchdog = CatalogDispatchWatchdog()
        cache_path = getattr(settings, "web_catalog_cache_path", None)
        self._cache_store = CatalogCacheStore(cache_path) if cache_path else None
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="catalog-scan")
        self._inflight: dict[tuple[str, str], Future[CatalogResult]] = {}
        self._refresh_stop = threading.Event()
        self._refresh_thread: threading.Thread | None = None

    def source_options(self) -> list[dict[str, Any]]:
        return [source.to_dict() for source in self.sources if source.enabled and source.collection_root]

    @property
    def cache_ttl_seconds(self) -> int:
        return int(self._cache_ttl_seconds)

    def storage_ready(self) -> bool:
        if not any(source.enabled for source in self.sources):
            return False
        if self._cache_store:
            try:
                with self._cache_store._connect() as connection:
                    connection.execute("SELECT cache_key FROM catalog_results LIMIT 1").fetchone()
            except (OSError, sqlite3.Error):
                return False
        return True

    def start_background_refresh(self, interval_seconds: float = 900.0) -> None:
        """Keep the public catalog warm without making parents wait for upstream PDFs."""
        interval = max(60.0, float(interval_seconds))
        with self._lock:
            if self._refresh_thread is not None:
                return
            self._refresh_stop.clear()
            self._refresh_thread = threading.Thread(
                target=self._refresh_loop,
                args=(interval,),
                name="catalog-refresh",
                daemon=True,
            )
            self._refresh_thread.start()

    def stop_background_refresh(self) -> None:
        self._refresh_stop.set()
        thread = self._refresh_thread
        if thread is not None:
            thread.join(timeout=2)
        self._refresh_thread = None

    def close(self) -> None:
        self.stop_background_refresh()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _refresh_loop(self, interval_seconds: float) -> None:
        while not self._refresh_stop.is_set():
            try:
                results = self.get_many(source_id="all", refresh=True)
                if self._scheduled_collection:
                    self._dispatch_watchdog.check(results)
            except Exception as exc:
                # A single source must not stop the catalog refresh loop.
                logging.getLogger(__name__).warning("catalog_refresh_failed type=%s", type(exc).__name__)
            if self._refresh_stop.wait(interval_seconds):
                return

    def get_source(self, source_id: str, grade: str | None = None, refresh: bool = False) -> CatalogResult:
        source = self._source_by_id(source_id)
        effective_grade = self._effective_grade(source, grade)
        key = (source.id, effective_grade)
        cached = self._last_cached(source, effective_grade)
        if self._scheduled_collection and source.collection_driver == "scheduled":
            if not cached:
                return CatalogResult(source, effective_grade, "", (), ("定期収集の初回データを待っています。公式ページをご確認ください。",), freshness_status="pending")
            result = cached[1]
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(result.scanned_at)).total_seconds()
            if age > 5400:
                return replace(result, warnings=("定期収集が遅れています。前回確認した情報です。公式ページもご確認ください。",), freshness_status="stale")
            return result
        if not refresh and cached and time.monotonic() - cached[0] < self._cache_ttl_seconds:
            return cached[1]
        try:
            result = self._scan_source(source, effective_grade)
        except Exception:
            if not cached:
                raise
            result = replace(cached[1], warnings=("最新情報を確認できませんでした。前回取得した情報を表示しています。公式ページも確認してください。",), freshness_status="stale")
            with self._lock:
                self._cache[key] = (time.monotonic(), result)
            return result
        if result.warnings and cached:
            # A failed PDF must not silently erase the last readable version.
            fetched_urls = {notice.url for notice in result.notices if notice.extraction_status == "ok"}
            retained = tuple(notice for notice in cached[1].notices if notice.extraction_status == "ok" and notice.url not in fetched_urls)
            if retained:
                retained_urls = {notice.url for notice in retained}
                result = replace(result, notices=tuple(notice for notice in result.notices if notice.url not in retained_urls) + retained, warnings=result.warnings + ("一部は前回取得した情報です。原文で最新情報を確認してください。",), freshness_status="stale")
        with self._lock:
            self._cache[key] = (time.monotonic(), result)
        if self._cache_store and not result.warnings:
            self._cache_store.save(result)
        return result

    def _last_cached(self, source: SourceConfig, grade: str) -> tuple[float, CatalogResult] | None:
        key = (source.id, grade)
        with self._lock:
            cached = self._cache.get(key)
        if cached:
            return cached
        persisted = self._cache_store.load(source, grade) if self._cache_store else None
        if persisted is None:
            return None
        try:
            age = max(0, time.time() - datetime.fromisoformat(persisted.scanned_at).timestamp())
        except (TypeError, ValueError):
            age = self._cache_ttl_seconds + 1
        cached = (time.monotonic() - age, persisted)
        with self._lock:
            self._cache[key] = cached
        return cached

    def get_many(
        self,
        source_id: str | None = None,
        grade: str | None = None,
        level: str | None = None,
        ward: str | None = None,
        feed_group: str | None = None,
        source_group: str | None = None,
        refresh: bool = False,
    ) -> list[CatalogResult]:
        selected = [source for source in self.sources if source.enabled]
        if source_id and source_id not in {"all", "*"}:
            requested = next((source for source in selected if source.id == source_id), None)
            if requested and requested.collection_root:
                selected = [source for source in selected if source.collection_id == requested.collection_id
                            or requested.collection_id in source.related_collections
                            or (source.shared_with_ward and source.ward == requested.ward)]
            else:
                selected = [source for source in selected if source.id == source_id]
        if level and level not in {"all", "*"}:
            selected = [source for source in selected if source.level == level]
        if ward and ward not in {"all", "*"}:
            selected = [source for source in selected if source.ward == ward]
        if feed_group and feed_group not in {"all", "*"}:
            if feed_group not in FEED_GROUPS:
                raise CatalogError(f"invalid feed group: {feed_group}")
            selected = [source for source in selected if source.feed_group == feed_group]
        if source_group and source_group not in {"all", "*"}:
            if source_group not in SOURCE_GROUP_LABELS:
                raise CatalogError(f"invalid source group: {source_group}")
            selected = [source for source in selected if source.source_group == source_group]
        if not selected:
            raise CatalogError("no enabled source matches the requested filters")
        results: dict[str, CatalogResult] = {}
        futures = {
            source.id: self._submit_source(source, grade, refresh)
            for source in selected
            if not self._cached_result(source, grade, refresh, results)
        }
        future_sources = {future: next(source for source in selected if source.id == source_id) for source_id, future in futures.items()}
        done, not_done = wait(future_sources, timeout=self._max_wait_seconds)
        for future in done:
            source = future_sources[future]
            try:
                results[source.id] = future.result()
            except Exception as exc:
                logging.getLogger(__name__).warning("source_scan_failed source=%s type=%s", source.id, type(exc).__name__)
                fallback = results.get(source.id)
                results[source.id] = replace(fallback, warnings=("最新情報を確認できません。前回取得した情報です。",), refreshing=False, freshness_status="stale") if fallback else CatalogResult(source, self._effective_grade(source, grade), "", (), ("公開ページを確認できません。原文をご確認ください。",))
        for future in not_done:
            source = future_sources[future]
            if source.id not in results:
                results[source.id] = CatalogResult(source, self._effective_grade(source, grade), "", (), ("公開ページを確認中です。しばらくしてから再度表示してください。",), refreshing=True)
        for source in selected:
            if source.id not in results:
                results[source.id] = CatalogResult(source, self._effective_grade(source, grade), "", (), ("最新情報を確認できません。公式ページをご確認ください。",))
        # Do not cancel shared futures: another request or the background
        # refresher may be using the same scan. Completed results populate the
        # cache for the next request.
        ordered = [results[source.id] for source in selected if source.id in results]
        return ordered

    def _cached_result(
        self,
        source: SourceConfig,
        grade: str | None,
        refresh: bool,
        results: dict[str, CatalogResult],
    ) -> bool:
        if self._scheduled_collection and source.collection_driver == "scheduled":
            # Use the real check time, not the import time or five-minute TTL.
            results[source.id] = self.get_source(source.id, grade, refresh)
            return True
        effective_grade = self._effective_grade(source, grade)
        cached = self._last_cached(source, effective_grade)
        if cached:
            with self._lock:
                inflight = self._inflight.get((source.id, effective_grade))
                pending = inflight is not None and not inflight.done()
            if not refresh and time.monotonic() - cached[0] < self._cache_ttl_seconds:
                results[source.id] = replace(cached[1], refreshing=True) if pending else cached[1]
                return True
            results[source.id] = replace(cached[1], warnings=cached[1].warnings + ("更新確認中です。前回取得した情報を表示しています。",), refreshing=True)
        return False

    def _submit_source(self, source: SourceConfig, grade: str | None, refresh: bool) -> Future[CatalogResult]:
        effective_grade = self._effective_grade(source, grade)
        key = (source.id, effective_grade)
        with self._lock:
            current = self._inflight.get(key)
            if current is not None and not current.done():
                return current
            future = self._executor.submit(self.get_source, source.id, grade, refresh)
            self._inflight[key] = future
            future.add_done_callback(lambda completed, key=key: self._clear_inflight(key, completed))
            return future

    def _clear_inflight(self, key: tuple[str, str], future: Future[CatalogResult]) -> None:
        with self._lock:
            if self._inflight.get(key) is future:
                self._inflight.pop(key, None)

    def find_notice(
        self,
        notice_id: str,
        source_id: str | None = None,
        grade: str | None = None,
        level: str | None = None,
        ward: str | None = None,
        feed_group: str | None = None,
        source_group: str | None = None,
    ) -> CatalogNotice | None:
        for result in self.get_many(source_id=source_id, grade=grade, level=level, ward=ward, feed_group=feed_group, source_group=source_group):
            for notice in result.notices:
                if notice.id == notice_id:
                    return notice
        return None

    def _source_by_id(self, source_id: str) -> SourceConfig:
        for source in self.sources:
            if source.id == source_id and source.enabled:
                return source
        raise CatalogError(f"unknown source: {source_id}")

    @staticmethod
    def _effective_grade(source: SourceConfig, requested: str | None) -> str:
        if source.level == "高等学校" or source.grades == ("全学年",):
            return "全学年"
        if requested is None or not str(requested).strip():
            return source.default_grade
        try:
            normalized = normalize_grade(requested)
        except ValueError as exc:
            raise CatalogError(f"invalid grade: {requested}") from exc
        if normalized not in source.grades:
            if "全学年" in source.grades:
                return "全学年"
            raise CatalogError(f"grade {normalized} is not available for {source.name}")
        return normalized

    @staticmethod
    def _matches(source: SourceConfig, candidate: LinkCandidate) -> bool:
        haystack = f"{candidate.title} {candidate.url}"
        include = _compile_patterns(source.include_patterns, "include")
        exclude = _compile_patterns(source.exclude_patterns, "exclude")
        if include and not any(pattern.search(haystack) for pattern in include):
            return False
        return not any(pattern.search(haystack) for pattern in exclude)

    def _scan_source(self, source: SourceConfig, grade: str) -> CatalogResult:
        allowed_hosts = {urlparse(url).hostname for url in source.page_urls} | set(source.allowed_hosts)
        fetcher = HttpFetcher(
            timeout_seconds=self.settings.request_timeout_seconds,
            max_document_bytes=self.settings.max_document_bytes,
            user_agent=self.settings.user_agent,
            max_attempts=3,
            allowed_hosts=allowed_hosts,
        )
        warnings: list[str] = []
        candidates_by_url: dict[str, LinkCandidate] = {}
        page_html_by_url: dict[str, str] = {}
        successful_pages = 0
        if source.mode == "static":
            successful_pages = 1
            candidate = LinkCandidate(url=source.page_url, title=source.static_title or source.name, kind=source.content_kind)
            if self._matches(source, candidate):
                candidates_by_url[candidate.url] = candidate
        pending_pages = [(url, 0) for url in source.page_urls] if source.mode != "static" else []
        visited: set[str] = set()
        while pending_pages and len(visited) < 24:
            page_url, depth = pending_pages.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                page_html = fetcher.fetch_page(page_url)
                successful_pages += 1
                page_html_by_url[page_url] = page_html
                if source.mode == "html_news":
                    page_candidates = self._parse_news_links(page_html, source, page_url)
                elif source.mode == "html_page":
                    page_candidates = [LinkCandidate(url=page_url, title=source.name, kind=source.content_kind)]
                elif source.mode == "link_index":
                    page_candidates = self._scoped_links(page_html, source, page_url)
                else:
                    page_candidates = self._document_links(page_html, source, page_url)
                    if source.mode == "mixed":
                        page_candidates.insert(0, LinkCandidate(url=page_url, title=source.name, kind=source.content_kind))
                for candidate in page_candidates:
                    if urlparse(candidate.url).hostname not in allowed_hosts:
                        continue
                    if self._matches(source, candidate) and _candidate_matches_grade(candidate, grade):
                        candidates_by_url.setdefault(candidate.url, candidate)
                if depth < source.discovery_depth:
                    for candidate in self._scoped_links(page_html, source, page_url):
                        if not _is_document_url(candidate.url) and candidate.url not in visited:
                            pending_pages.append((candidate.url, depth + 1))
            except (FetchError, ValueError) as exc:
                warnings.append(f"{page_url}: {exc}")
        if not successful_pages:
            raise CatalogError(f"{source.name} の公開ページを確認できませんでした。")
        if pending_pages:
            warnings.append("公開ページの確認上限に達しました。すべてのリンクを確認できていません。")
        candidates = sorted(candidates_by_url.values(), key=_candidate_sort_key, reverse=True)[: source.max_documents]
        notices: list[CatalogNotice] = []
        if not candidates:
            warnings.append("関連するお知らせのリンクが見つかりませんでした。")
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(candidates)))) as executor:
            futures = {
                executor.submit(self._read_candidate, fetcher, source, candidate, grade, page_html_by_url.get(candidate.url)): candidate
                for candidate in candidates
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    notice = future.result()
                except (FetchError, ExtractionError, ValueError) as exc:
                    warnings.append(f"{candidate.title}: {exc}")
                    # Preserve the discovered original even when extraction is
                    # unavailable. An unreadable PDF is not an absent notice.
                    label, published = _date_labels(candidate, "", "更新資料" if not _is_document_url(candidate.url) else "")
                    notices.append(CatalogNotice(
                        id=sha256_text(f"{source.id}\n{grade}\n{candidate.url}\noriginal-only")[:20],
                        source_id=source.id, source_name=source.name, ward=source.ward, level=source.level,
                        grade=grade, title=self._display_title(candidate, source, grade, ""), kind=candidate.kind,
                        url=candidate.url, text="本文の自動読み取りを完了できませんでした。内容・日付・持ち物は公式の原文をご確認ください。",
                        content_hash="", date_label=label, published_label="" if published == "更新資料" else published,
                        source_group=source.source_group, feed_group=source.feed_group, coverage_kind=source.coverage_kind,
                        date_kind="unknown" if label == "更新資料" else "published", extraction_status="original_only",
                    ))
                    continue
                if notice is not None:
                    notices.append(notice)
        notices.sort(key=lambda item: (item.date_label != "更新資料", item.date_label, item.title), reverse=True)
        return CatalogResult(
            source=source,
            grade=grade,
            scanned_at=datetime.now(timezone.utc).isoformat(),
            notices=tuple(notices),
            warnings=tuple(warnings),
            discovered_count=len(candidates_by_url),
            limit_reached=len(candidates_by_url) > source.max_documents,
        )

    def _read_candidate(
        self,
        fetcher: HttpFetcher,
        source: SourceConfig,
        candidate: LinkCandidate,
        grade: str,
        page_html: str | None = None,
    ) -> CatalogNotice | None:
        is_html = False
        date_text = None
        attachments = ()
        if not _candidate_matches_grade(candidate, grade):
            return None
        if source.mode == "static":
            text = source.static_text
            content_hash = sha256_text(text)
            kind = source.content_kind
            candidate = LinkCandidate(url=candidate.url, title=source.static_title or candidate.title, kind=kind)
        else:
            document = None
            if page_html is None:
                document = fetcher.fetch_document(candidate.url)
                if document.content is None:
                    raise ExtractionError("取得した資料に本文がありません。")
                is_pdf = document.content.lstrip().startswith(b"%PDF") or "application/pdf" in document.content_type.lower()
                if not is_pdf:
                    if not any(token in document.content_type.lower() for token in ("html", "text")):
                        raise ExtractionError("未対応の資料形式です。原文をご確認ください。")
                    page_html = _decode_document_html(document.content, document.content_type)
            if page_html is None:
                raw_text = extract_document_text(document.content, document.content_type, candidate.url)
                date_text = raw_text
                text = select_relevant_text(raw_text, candidate.kind, grade)
                content_hash = sha256_bytes(document.content)
                kind = candidate.kind
            else:
                is_html = True
                text, candidate = self._html_notice(page_html, source, candidate)
                attachments = _html_attachments(page_html, source, candidate.url)
                content_hash = sha256_text(text)
                kind = candidate.kind
        text = "\n".join(clean_text_lines(text))
        if not text:
            raise ExtractionError("資料の本文を読み取れませんでした。原文をご確認ください。")
        notice_id = sha256_text(f"{source.id}\n{grade}\n{candidate.url}\n{content_hash}")[:20]
        date_label, published_label = _date_labels(candidate, date_text if date_text is not None else text, _html_page_published_date(page_html) if is_html else "")
        event_date, deadline_date = activity_dates(text)
        date_kind = "issue" if "月号" in date_label else "published"
        if source.feed_group == "events" and event_date:
            date_label, date_kind = event_date, "event"
        elif source.mode == "mixed" and candidate.url in source.page_urls:
            # A mutable index contains announcements of different ages; its CMS
            # update date is not a publication date for each announcement.
            date_label, date_kind = "更新資料", "unknown"
        elif date_label == "更新資料":
            date_kind = "unknown"
        return CatalogNotice(
            id=notice_id,
            source_id=source.id,
            source_name=source.name,
            ward=source.ward,
            level=source.level,
            grade=grade,
            title=self._display_title(candidate, source, grade, text),
            kind=kind,
            url=candidate.url,
            text=text,
            content_hash=content_hash,
            date_label=date_label,
            published_label="" if published_label == "更新資料" else published_label,
            source_group=source.source_group,
            feed_group=source.feed_group,
            coverage_kind=source.coverage_kind,
            event_date=event_date,
            deadline_date=deadline_date,
            date_kind=date_kind,
            attachments=attachments,
        )

    @staticmethod
    def _html_notice(page_html: str, source: SourceConfig, candidate: LinkCandidate) -> tuple[str, LinkCandidate]:
        parser = _ScopedNewsTextParser() if source.mode == "html_news" else _MainContentTextParser()
        parser.feed(page_html)
        parser.close()
        text = "\n".join(clean_text_lines("".join(parser.parts)))
        if not text:
            raise ExtractionError("公開ページの本文領域を確認できませんでした。")
        candidate = LinkCandidate(
            url=candidate.url,
            title=_html_page_title(page_html, candidate.title, candidate.url) if source.mode != "html_news" else candidate.title,
            kind=candidate.kind,
        )
        return text, candidate

    @staticmethod
    def _scoped_links(html: str, source: SourceConfig, page_url: str) -> list[LinkCandidate]:
        parser = _NewsLinkParser()
        parser.feed(html)
        patterns = _compile_patterns(source.link_patterns, "link")
        hosts = {urlparse(url).hostname for url in source.page_urls} | set(source.allowed_hosts)
        result = {}
        for href, title in parser.anchors:
            url = urldefrag(urljoin(page_url, href))[0]
            if url == urldefrag(page_url)[0] or urlparse(url).hostname not in hosts:
                continue
            if urlparse(url).scheme not in {"http", "https"}:
                continue
            if patterns and any(pattern.search(f"{title} {url}") for pattern in patterns):
                result[url] = LinkCandidate(url, _clean_title(title), source.content_kind)
        return list(result.values())

    @staticmethod
    def _document_links(html: str, source: SourceConfig, page_url: str) -> list[LinkCandidate]:
        candidates = {item.url: item for item in parse_relevant_links(html, page_url) if _is_document_url(item.url)}
        parser = _NewsLinkParser()
        parser.feed(html)
        for href, title in parser.anchors:
            url = urldefrag(urljoin(page_url, href))[0]
            if _is_document_url(url):
                candidates.setdefault(url, LinkCandidate(url, _clean_title(title), source.content_kind))
        return list(candidates.values())

    @staticmethod
    def _display_title(candidate: LinkCandidate, source: SourceConfig, grade: str, text: str) -> str:
        if source.mode == "html_news":
            return _news_title(candidate.title, candidate.url)
        title = re.sub(r"^\((?:表面|裏面)\)", "", _clean_title(candidate.title))
        if re.fullmatch(r"(?:PDF\s*)?ダウンロード", title, re.IGNORECASE):
            title = source.name
        issue_month = _issue_month(f"{candidate.title}\n{text}", candidate.kind)
        if issue_month and candidate.kind == "grade_news":
            return f"{grade} 学年だより・{issue_month}月号"
        if issue_month and candidate.kind == "school_news":
            return f"学校だより・{issue_month}月号"
        return title or source.name

    @staticmethod
    def _parse_news_links(html: str, source: SourceConfig, page_url: str | None = None) -> list[LinkCandidate]:
        parser = _NewsLinkParser()
        parser.feed(html)
        parser.close()
        page_url = page_url or source.page_url
        page_without_fragment = urldefrag(page_url)[0]
        result: list[LinkCandidate] = []
        seen: set[str] = set()
        for href, raw_title in parser.anchors:
            url = urldefrag(urljoin(page_url, href))[0]
            parsed = urlparse(url)
            title = _clean_title(raw_title)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if url == page_without_fragment or "/news/20" not in url or url.endswith("/index.html"):
                continue
            candidate = LinkCandidate(url=url, title=title or url.rsplit("/", 1)[-1], kind="school_news")
            if url in seen or not CatalogService._matches(source, candidate):
                continue
            seen.add(url)
            result.append(candidate)
        return result
