from __future__ import annotations

import copy
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .extractor import (
    ExtractionError,
    extract_document_text,
    normalize_grade,
    select_relevant_text,
    sha256_bytes,
    sha256_text,
)
from .fetcher import FetchError, HttpFetcher, LinkCandidate
from .formatter import MessageDocument, format_notification
from .line_client import LineClient
from .state import age_in_hours, load_state, save_state, utc_now


class PipelineError(RuntimeError):
    """Raised when a safe polling or delivery transition is not possible."""


@dataclass(frozen=True)
class PrepareResult:
    status: str
    grade: str
    candidate_count: int
    message: str | None
    notification_id: str | None
    state_changed: bool


@dataclass(frozen=True)
class DeliverResult:
    status: str
    notification_id: str | None
    request_id: str | None
    accepted_via_retry: bool = False


def build_notification_id(grade: str, documents: list[MessageDocument]) -> str:
    payload = {
        "grade": normalize_grade(grade),
        "documents": [
            {
                "url": document.url,
                "title": document.title,
                "kind": document.kind,
                "reason": document.reason,
                "content_sha256": sha256_text(document.text),
            }
            for document in sorted(documents, key=lambda item: (item.url, item.title))
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_retry_key(notification_id: str) -> str:
    # The same notification gets the same key if the runner has to recover
    # after LINE accepted the request but before the final state commit.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sakurano-line-notifier:{notification_id}"))


def _document_reason(previous: dict[str, Any] | None, link: LinkCandidate, content_hash: str) -> str | None:
    if previous is None:
        return "new_link"
    if previous.get("content_sha256") != content_hash:
        return "content_changed"
    if previous.get("title") != link.title or previous.get("kind") != link.kind:
        return "title_changed"
    return None


class SchoolNotifier:
    def __init__(self, settings: Settings, fetcher: HttpFetcher | None = None) -> None:
        self.settings = settings
        self.fetcher = fetcher or HttpFetcher(
            timeout_seconds=settings.request_timeout_seconds,
            max_document_bytes=settings.max_document_bytes,
            user_agent=settings.user_agent,
            allowed_hosts={urlparse(settings.page_url).hostname},
        )

    def prepare(self, dry_run: bool = False) -> PrepareResult:
        state = load_state(self.settings.state_path)
        grade = normalize_grade(self.settings.grade)
        pending = state.get("pending")
        if pending:
            message = str(pending.get("message") or "")
            if dry_run and message:
                print(message)
            return PrepareResult(
                status="pending_exists",
                grade=grade,
                candidate_count=len(pending.get("documents", [])),
                message=message or None,
                notification_id=pending.get("notification_id"),
                state_changed=False,
            )

        try:
            page_html = self.fetcher.fetch_page(self.settings.page_url)
            links = self._parse_links(page_html)
        except (FetchError, PipelineError):
            raise
        if not links:
            raise PipelineError("no school-news PDF/link was found; state was not changed")

        baseline_needed = grade not in state["baseline_grades"]
        observations: list[MessageDocument] = []
        state_dirty = False
        now = utc_now()
        for link in links:
            previous = state["documents"].get(link.url)
            title_changed = previous is not None and (
                previous.get("title") != link.title or previous.get("kind") != link.kind
            )
            force_download = previous is None or baseline_needed or title_changed or not previous.get("content_sha256")
            conditional_headers: dict[str, str] = {}
            if not force_download and previous:
                if previous.get("etag"):
                    conditional_headers["If-None-Match"] = str(previous["etag"])
                if previous.get("last_modified"):
                    conditional_headers["If-Modified-Since"] = str(previous["last_modified"])

            fetched = self.fetcher.fetch_document(link.url, conditional_headers=conditional_headers or None)
            if fetched.not_modified:
                if force_download or previous is None or not previous.get("content_sha256"):
                    raise PipelineError(f"server returned 304 without a usable cached document: {link.url}")
                entry = copy.deepcopy(previous)
                reason = None
                relevant_text = None
                content_hash = str(previous["content_sha256"])
            else:
                if fetched.content is None:
                    raise PipelineError(f"document response had no content: {link.url}")
                try:
                    raw_text = extract_document_text(fetched.content, fetched.content_type, link.url)
                    relevant_text = select_relevant_text(raw_text, link.kind, grade)
                except ExtractionError as exc:
                    raise PipelineError(str(exc)) from exc
                content_hash = sha256_bytes(fetched.content)
                reason = _document_reason(previous, link, content_hash)
                entry = {
                    "url": link.url,
                    "title": link.title,
                    "kind": link.kind,
                    "content_sha256": content_hash,
                    "etag": fetched.etag or (previous or {}).get("etag"),
                    "last_modified": fetched.last_modified or (previous or {}).get("last_modified"),
                    "first_seen_at": (previous or {}).get("first_seen_at", now),
                }

            if previous != entry:
                state["documents"][link.url] = entry
                state_dirty = True

            if relevant_text is None:
                continue
            if not relevant_text.strip():
                raise PipelineError(f"target section is empty: {link.url}")
            if baseline_needed and reason is None:
                reason = "existing_baseline"
            if reason is not None or baseline_needed:
                observations.append(
                    MessageDocument(
                        title=link.title,
                        kind=link.kind,
                        url=link.url,
                        reason=reason or "existing_baseline",
                        text=relevant_text,
                    )
                )

        if baseline_needed:
            state["baseline_grades"].append(grade)
            state_dirty = True

        should_notify_existing = self.settings.notify_existing_on_first_run or dry_run
        if observations and (not baseline_needed or should_notify_existing):
            notification_id = build_notification_id(grade, observations)
            previous_notification = state["notifications"].get(notification_id)
            if previous_notification and previous_notification.get("status") in {"sent", "baseline"}:
                notification_id = None
                message = None
            else:
                message = format_notification(grade, observations, max_chars=self.settings.line_max_chars)
                pending = {
                    "notification_id": notification_id,
                    "retry_key": build_retry_key(notification_id),
                    "grade": grade,
                    "prepared_at": now,
                    "message": message,
                    "documents": [
                        {
                            "url": document.url,
                            "title": document.title,
                            "kind": document.kind,
                            "reason": document.reason,
                            "content_sha256": sha256_text(document.text),
                        }
                        for document in observations
                    ],
                }
                state["pending"] = pending
                state["notifications"][notification_id] = {
                    "status": "pending",
                    "grade": grade,
                    "documents": [document.url for document in observations],
                    "prepared_at": now,
                }
                state_dirty = True
        else:
            notification_id = None
            message = None
            if baseline_needed and observations:
                baseline_id = build_notification_id(grade, observations)
                state["notifications"][baseline_id] = {
                    "status": "baseline",
                    "grade": grade,
                    "documents": [document.url for document in observations],
                    "baselined_at": now,
                }
                state_dirty = True

        if state_dirty:
            state["last_checked_at"] = now
            if not dry_run:
                save_state(self.settings.state_path, state)

        if message and dry_run:
            print(message)
        return PrepareResult(
            status="prepared" if message else ("baselined" if baseline_needed else "unchanged"),
            grade=grade,
            candidate_count=len(observations),
            message=message,
            notification_id=notification_id,
            state_changed=state_dirty and not dry_run,
        )

    def deliver(self, dry_run: bool = False) -> DeliverResult:
        state = load_state(self.settings.state_path)
        pending = state.get("pending")
        if not pending:
            return DeliverResult(status="nothing_to_send", notification_id=None, request_id=None)

        notification_id = str(pending.get("notification_id") or "")
        retry_key = str(pending.get("retry_key") or "")
        message = str(pending.get("message") or "")
        prepared_at = str(pending.get("prepared_at") or "")
        if not notification_id or not retry_key or not message or not prepared_at:
            raise PipelineError("pending notification is incomplete; state was not changed")
        try:
            if age_in_hours(prepared_at) > self.settings.pending_retry_max_hours:
                raise PipelineError(
                    "pending notification is older than the safe LINE retry-key window; "
                    "inspect state before manually re-arming it"
                )
        except ValueError as exc:
            raise PipelineError("pending notification has an invalid prepared_at timestamp") from exc

        if dry_run:
            print(message)
            return DeliverResult(status="dry_run", notification_id=notification_id, request_id=None)
        if not self.settings.line_channel_access_token or not self.settings.line_to:
            raise PipelineError("LINE_CHANNEL_ACCESS_TOKEN and LINE_TO are required for delivery")

        client = LineClient(
            channel_access_token=self.settings.line_channel_access_token,
            recipient=self.settings.line_to,
            timeout_seconds=self.settings.request_timeout_seconds,
        )
        result = client.push_text(message, retry_key=retry_key)
        sent_at = utc_now()
        notification = state["notifications"].setdefault(notification_id, {})
        notification.update(
            {
                "status": "sent",
                "grade": pending.get("grade", normalize_grade(self.settings.grade)),
                "documents": [item.get("url") for item in pending.get("documents", [])],
                "prepared_at": prepared_at,
                "sent_at": sent_at,
                "request_id": result.request_id,
                "accepted_via_retry": result.accepted_via_retry,
            }
        )
        state["pending"] = None
        state["last_sent_at"] = sent_at
        save_state(self.settings.state_path, state)
        return DeliverResult(
            status="sent",
            notification_id=notification_id,
            request_id=result.request_id,
            accepted_via_retry=result.accepted_via_retry,
        )

    def run(self, dry_run: bool = False) -> tuple[PrepareResult, DeliverResult | None]:
        prepared = self.prepare(dry_run=dry_run)
        if dry_run:
            return prepared, None
        delivered = self.deliver(dry_run=False)
        return prepared, delivered

    def _parse_links(self, page_html: str) -> list[LinkCandidate]:
        from .fetcher import parse_relevant_links

        return parse_relevant_links(page_html, self.settings.page_url)
