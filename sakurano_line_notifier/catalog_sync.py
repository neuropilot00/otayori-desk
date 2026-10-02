"""Authenticated public-source snapshots; no parent or push-subscription data."""
from __future__ import annotations

import re
import time
from dataclasses import replace
from datetime import datetime, timezone
from urllib.parse import urlparse

from .web_catalog import CatalogCacheStore, CatalogError, CatalogResult, CatalogService

MAX_SNAPSHOT_BYTES = 2_000_000


def snapshot_payload(result: CatalogResult) -> dict:
    if result.warnings or result.refreshing or any(n.extraction_status != "ok" for n in result.notices):
        raise CatalogError("incomplete source snapshot")
    return {
        "version": 1, "source_id": result.source.id, "grade": result.grade,
        "source_fingerprint": CatalogCacheStore._source_fingerprint(result.source),
        "scanned_at": result.scanned_at, "notices": [n.to_detail() for n in result.notices],
        "discovered_count": result.discovered_count, "limit_reached": result.limit_reached,
    }


def accept_snapshot(service: CatalogService, payload: dict) -> bool:
    """Validate before touching durable/in-memory caches; retries cannot regress time."""
    if type(payload.get("version")) is not int or payload["version"] != 1 or not isinstance(payload.get("source_id"), str):
        raise CatalogError("invalid snapshot version or source")
    source = service._source_by_id(payload["source_id"])
    grade = payload.get("grade")
    if source.collection_driver != "scheduled" or grade not in source.grades:
        raise CatalogError("source or grade is not configured for scheduled collection")
    if payload.get("source_fingerprint") != CatalogCacheStore._source_fingerprint(source):
        raise CatalogError("source configuration differs")
    try:
        checked = datetime.fromisoformat(payload["scanned_at"])
        if checked.tzinfo is None:
            raise ValueError("timezone required")
        age = (datetime.now(timezone.utc) - checked).total_seconds()
        if not -300 <= age <= 7200:
            raise ValueError("timestamp outside allowed window")
    except (KeyError, TypeError, ValueError) as exc:
        raise CatalogError("invalid snapshot timestamp") from exc
    count = payload.get("discovered_count")
    limit = payload.get("limit_reached")
    raw_notices = payload.get("notices")
    if type(count) is not int or not 0 <= count <= 10000 or type(limit) is not bool:
        raise CatalogError("invalid snapshot counts")
    if not isinstance(raw_notices, list) or not 1 <= len(raw_notices) <= source.max_documents or count < len(raw_notices):
        raise CatalogError("invalid snapshot documents")
    hosts = {urlparse(url).hostname for url in source.page_urls} | set(source.allowed_hosts)
    notices = []
    ids, urls = set(), set()
    for raw in raw_notices:
        if not isinstance(raw, dict) or any(not isinstance(raw.get(key), str) for key in ("id", "source_id", "grade", "title", "url", "text", "content_hash")):
            raise CatalogError("invalid snapshot document")
        try:
            url = urlparse(raw["url"])
            safe_url = url.scheme == "https" and url.hostname in hosts and not url.username and not url.password and url.port in {None, 443}
        except ValueError:
            safe_url = False
        if not safe_url or raw["source_id"] != source.id or raw["grade"] != grade:
            raise CatalogError("snapshot document outside configured source")
        if not re.fullmatch(r"[a-f0-9]{20}", raw["id"]) or not re.fullmatch(r"[a-f0-9]{64}", raw["content_hash"]):
            raise CatalogError("invalid snapshot identifiers")
        if not 1 <= len(raw["text"]) <= 200000 or len(raw["title"]) > 1000 or raw.get("extraction_status") != "ok":
            raise CatalogError("invalid snapshot extraction")
        if raw["id"] in ids or raw["url"] in urls:
            raise CatalogError("duplicate snapshot document")
        attachments = raw.get("attachments", [])
        if not isinstance(attachments, list) or len(attachments) > 80:
            raise CatalogError("invalid snapshot attachments")
        for attachment in attachments:
            if not isinstance(attachment, dict) or not isinstance(attachment.get("title"), str) or not isinstance(attachment.get("url"), str) or len(attachment["title"]) > 500:
                raise CatalogError("invalid snapshot attachment")
            try:
                link = urlparse(attachment["url"])
                safe_link = link.scheme in {"https", "http"} and link.hostname in hosts and not link.username and not link.password and link.port in {None, 80, 443}
            except ValueError:
                safe_link = False
            if not safe_link:
                raise CatalogError("snapshot attachment outside configured source")
        try:
            notice = CatalogCacheStore._notice_from_payload(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise CatalogError("invalid snapshot fields") from exc
        notice = replace(notice, source_name=source.name, ward=source.ward, level=source.level,
                         source_group=source.source_group, feed_group=source.feed_group,
                         kind=source.content_kind if source.source_group == "after_school" else notice.kind,
                         coverage_kind=source.coverage_kind)
        ids.add(notice.id)
        urls.add(notice.url)
        notices.append(notice)
    result = CatalogResult(source, grade, checked.astimezone(timezone.utc).isoformat(), tuple(notices), (), count, limit)
    if service._cache_store is None:
        raise RuntimeError("durable public cache is required")
    with service._lock:
        cached = service._last_cached(source, grade)
        if cached and datetime.fromisoformat(cached[1].scanned_at) >= checked:
            return False
        service._cache_store.save(result)
        persisted = service._cache_store.load(source, grade)
        if persisted is None or persisted.scanned_at != result.scanned_at:
            raise RuntimeError("snapshot persistence failed")
        service._cache[(source.id, grade)] = (time.monotonic(), result)
    return True
