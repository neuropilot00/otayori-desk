from __future__ import annotations

import json
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
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
            "source_group": self.source_group,
            "source_group_label": SOURCE_GROUP_LABELS.get(self.source_group, self.source_group),
            "feed_group": self.feed_group,
            "content_kind": self.content_kind,
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
        }

    def to_detail(self) -> dict[str, Any]:
        result = self.to_summary()
        result.update({"text": self.text, "categories": self.categories(), "content_hash": self.content_hash})
        return result


@dataclass(frozen=True)
class CatalogResult:
    source: SourceConfig
    grade: str
    scanned_at: str
    notices: tuple[CatalogNotice, ...]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "grade": self.grade,
            "scanned_at": self.scanned_at,
            "notices": [notice.to_summary() for notice in self.notices],
            "warnings": list(self.warnings),
        }


class _NewsLinkParser(HTMLParser):
    """Collect article links from the Tokyo metropolitan school news index."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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

    BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr"}
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

    BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "td", "th", "tr"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._depth = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        attributes = dict(attrs)
        is_target = lowered == "main" or (lowered == "article" and attributes.get("id") == "content")
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
        if lowered in self.BLOCK_TAGS:
            self.parts.append("\n")
        if lowered not in self.VOID_TAGS:
            self._depth = max(0, self._depth - 1)

    def handle_data(self, data: str) -> None:
        if self._depth and not self._skip_depth:
            self.parts.append(data)


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
    if mode not in {"pdf", "html_news", "html_page"}:
        raise CatalogError(f"sources[{index}].mode must be pdf, html_news, or html_page")
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
    include_patterns = tuple(str(value) for value in raw.get("include_patterns", []))
    exclude_patterns = tuple(str(value) for value in raw.get("exclude_patterns", []))
    _compile_patterns(include_patterns, "include")
    _compile_patterns(exclude_patterns, "exclude")
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
    )


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
    return sources


def _news_date(value: str) -> str:
    published_hint = re.search(
        r"(?:掲載|更新|公開|発行|投稿日|配信)[^0-9０-９]{0,14}"
        r"((?:20[0-9０-９]{2})[/-][0-9０-９]{1,2}[/-][0-9０-９]{1,2}|"
        r"(?:20[0-9０-９]{2})年[0-9０-９]{1,2}月[0-9０-９]{1,2}日)",
        unicodedata.normalize("NFKC", value),
        re.IGNORECASE,
    )
    if published_hint:
        value = published_hint.group(1)
    normalized = unicodedata.normalize("NFKC", value)
    match = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", normalized)
    if match:
        return f"{match.group(1)}/{int(match.group(2)):02d}/{int(match.group(3)):02d}"
    japanese = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", normalized)
    if japanese:
        return f"{japanese.group(1)}/{int(japanese.group(2)):02d}/{int(japanese.group(3)):02d}"
    timestamp = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?:\d{6})?(?!\d)", normalized)
    if timestamp:
        return f"{timestamp.group(1)}/{timestamp.group(2)}/{timestamp.group(3)}"
    return "更新資料"


def _issue_month(value: str, kind: str | None = None) -> int | None:
    """Return an issue month only when the text looks like a monthly notice."""
    patterns = (
        r"(?:学校だより|学年だより)[^\n]{0,18}?([0-9０-９]{1,2})月号",
        r"([0-9０-９]{1,2})月号",
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
    meta = re.search(
        r"<meta\b[^>]*name=[\"'](?:modified_date|dateModified)[\"'][^>]*content=[\"']([^\"']+)",
        page_html,
        re.IGNORECASE,
    )
    if not meta:
        return "更新資料"
    return _news_date(meta.group(1))


def _date_labels(candidate: LinkCandidate, text: str, metadata: str = "") -> tuple[str, str]:
    published_label = _news_date(f"{candidate.title} {candidate.url}\n{metadata}\n{text}")
    if published_label != "更新資料":
        year_match = re.match(r"(20\d{2})/", published_label)
        issue_month = _issue_month(f"{candidate.title}\n{text}", candidate.kind)
        if year_match and issue_month:
            return f"{year_match.group(1)}/{issue_month:02d}月号", published_label
    return published_label, published_label


def _news_title(value: str, url: str) -> str:
    title = _clean_title(value)
    title = re.sub(r"^20\d{2}[/-]\d{1,2}[/-]\d{1,2}\s*", "", title)
    title = re.sub(r"^(お知らせ|学校からのお知らせ)\s*", "", title)
    return title or url.rsplit("/", 1)[-1] or url


def _candidate_sort_key(candidate: LinkCandidate) -> tuple[int, str, str]:
    filename = urlparse(candidate.url).path.rsplit("/", 1)[-1]
    timestamp = re.search(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?:\d{6})?(?!\d)", filename)
    numeric_date = int(timestamp.group(0)) if timestamp else 0
    return numeric_date, _clean_title(candidate.title), candidate.url


def _html_page_title(html: str, fallback: str, url: str) -> str:
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
        self._lock = threading.RLock()

    def source_options(self) -> list[dict[str, Any]]:
        return [source.to_dict() for source in self.sources if source.enabled and source.collection_root]

    @property
    def cache_ttl_seconds(self) -> int:
        return int(self._cache_ttl_seconds)

    def get_source(self, source_id: str, grade: str | None = None, refresh: bool = False) -> CatalogResult:
        source = self._source_by_id(source_id)
        effective_grade = self._effective_grade(source, grade)
        key = (source.id, effective_grade)
        with self._lock:
            cached = self._cache.get(key)
            if not refresh and cached and time.monotonic() - cached[0] < self._cache_ttl_seconds:
                return cached[1]
        result = self._scan_source(source, effective_grade)
        with self._lock:
            self._cache[key] = (time.monotonic(), result)
        return result

    def get_many(
        self,
        source_id: str | None = None,
        grade: str | None = None,
        level: str | None = None,
        ward: str | None = None,
        feed_group: str | None = None,
        refresh: bool = False,
    ) -> list[CatalogResult]:
        selected = [source for source in self.sources if source.enabled]
        if source_id and source_id not in {"all", "*"}:
            requested = next((source for source in selected if source.id == source_id), None)
            if requested and requested.collection_root:
                selected = [source for source in selected if source.collection_id == requested.collection_id]
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
        if not selected:
            raise CatalogError("no enabled source matches the requested filters")
        if len(selected) == 1:
            return [self.get_source(selected[0].id, grade, refresh)]

        results: dict[str, CatalogResult] = {}
        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=min(4, len(selected))) as executor:
            futures = {executor.submit(self.get_source, source.id, grade, refresh): source for source in selected}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    results[source.id] = future.result()
                except (CatalogError, FetchError, ExtractionError) as exc:
                    errors.append(f"{source.name}: {exc}")
        ordered = [results[source.id] for source in selected if source.id in results]
        if not ordered:
            raise CatalogError("すべてのソースを確認できませんでした: " + " / ".join(errors))
        if errors:
            warning_results = []
            for result in ordered:
                warning_results.extend(result.warnings)
            warning_results.extend(errors)
            # Preserve source results while making partial failure visible to the UI.
            first = ordered[0]
            ordered[0] = CatalogResult(first.source, first.grade, first.scanned_at, first.notices, tuple(warning_results))
        return ordered

    def find_notice(
        self,
        notice_id: str,
        source_id: str | None = None,
        grade: str | None = None,
        level: str | None = None,
        ward: str | None = None,
        feed_group: str | None = None,
    ) -> CatalogNotice | None:
        for result in self.get_many(source_id=source_id, grade=grade, level=level, ward=ward, feed_group=feed_group):
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
        if source.level == "高等学校":
            return "全学年"
        if requested is None or not str(requested).strip():
            return source.default_grade
        try:
            return normalize_grade(requested)
        except ValueError as exc:
            raise CatalogError(f"invalid grade: {requested}") from exc

    @staticmethod
    def _matches(source: SourceConfig, candidate: LinkCandidate) -> bool:
        haystack = f"{candidate.title} {candidate.url}"
        include = _compile_patterns(source.include_patterns, "include")
        exclude = _compile_patterns(source.exclude_patterns, "exclude")
        if include and not any(pattern.search(haystack) for pattern in include):
            return False
        return not any(pattern.search(haystack) for pattern in exclude)

    def _scan_source(self, source: SourceConfig, grade: str) -> CatalogResult:
        fetcher = HttpFetcher(
            timeout_seconds=self.settings.request_timeout_seconds,
            max_document_bytes=self.settings.max_document_bytes,
            user_agent=self.settings.user_agent,
            max_attempts=3,
        )
        warnings: list[str] = []
        candidates_by_url: dict[str, LinkCandidate] = {}
        page_html_by_url: dict[str, str] = {}
        successful_pages = 0
        for page_url in source.page_urls:
            try:
                page_html = fetcher.fetch_page(page_url)
                successful_pages += 1
                page_html_by_url[page_url] = page_html
                if source.mode == "html_news":
                    page_candidates = self._parse_news_links(page_html, source, page_url)
                elif source.mode == "html_page":
                    page_candidates = [LinkCandidate(url=page_url, title=source.name, kind=source.content_kind)]
                else:
                    page_candidates = parse_relevant_links(page_html, page_url)
                for candidate in page_candidates:
                    if source.mode == "pdf" and not urlparse(candidate.url).path.lower().endswith(".pdf"):
                        continue
                    if self._matches(source, candidate):
                        candidates_by_url.setdefault(candidate.url, candidate)
            except (FetchError, ValueError) as exc:
                warnings.append(f"{page_url}: {exc}")
        if not successful_pages:
            raise CatalogError(f"{source.name} の公開ページを確認できませんでした。")
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
        )

    def _read_candidate(
        self,
        fetcher: HttpFetcher,
        source: SourceConfig,
        candidate: LinkCandidate,
        grade: str,
        page_html: str | None = None,
    ) -> CatalogNotice | None:
        if source.mode in {"html_news", "html_page"}:
            page_html = page_html or fetcher.fetch_page(candidate.url)
            parser = _ScopedNewsTextParser() if source.mode == "html_news" else _MainContentTextParser()
            parser.feed(page_html)
            parser.close()
            text = "\n".join(clean_text_lines("".join(parser.parts)))
            if not text:
                text = html_to_text(page_html.encode("utf-8"))
            content_hash = sha256_text(text)
            kind = candidate.kind if source.mode == "html_page" else "school_news"
            candidate = LinkCandidate(
                url=candidate.url,
                title=_html_page_title(page_html, candidate.title, candidate.url) if source.mode == "html_page" else candidate.title,
                kind=kind,
            )
        else:
            document = fetcher.fetch_document(candidate.url)
            if document.content is None:
                return None
            raw_text = extract_document_text(document.content, document.content_type, candidate.url)
            text = select_relevant_text(raw_text, candidate.kind, grade)
            content_hash = sha256_bytes(document.content)
            kind = candidate.kind
        text = "\n".join(clean_text_lines(text))
        if not text:
            return None
        notice_id = sha256_text(f"{source.id}\n{grade}\n{candidate.url}\n{content_hash}")[:20]
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
            date_label=_date_labels(candidate, text, _html_page_published_date(page_html) if source.mode in {"html_news", "html_page"} else "")[0],
            published_label=_date_labels(candidate, text, _html_page_published_date(page_html) if source.mode in {"html_news", "html_page"} else "")[1],
            source_group=source.source_group,
            feed_group=source.feed_group,
        )

    @staticmethod
    def _display_title(candidate: LinkCandidate, source: SourceConfig, grade: str, text: str) -> str:
        if source.mode == "html_news":
            return _news_title(candidate.title, candidate.url)
        title = re.sub(r"^\((?:表面|裏面)\)", "", _clean_title(candidate.title))
        issue_month = _issue_month(f"{candidate.title}\n{text}", candidate.kind)
        if issue_month and candidate.kind == "grade_news":
            return f"{grade} 学年だより・{issue_month}月号"
        if issue_month and candidate.kind == "school_news":
            return f"学校だより・{issue_month}月号"
        return title or candidate.url.rsplit("/", 1)[-1] or candidate.url

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
