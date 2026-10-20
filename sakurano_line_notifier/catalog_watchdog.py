"""Bounded recovery for delayed GitHub schedules; never collects or sends push."""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Iterable, Any

import requests


class CatalogDispatchWatchdog:
    # Fixed destination: a secret must never follow configurable URLs/redirects.
    dispatch_url = "https://api.github.com/repos/neuropilot00/otayori-desk/actions/workflows/catalog-sync.yml/dispatches"
    stale_after_seconds = 45 * 60
    dispatch_after_seconds = 20 * 60
    cooldown_seconds = 15 * 60

    def __init__(self) -> None:
        token = os.getenv("CATALOG_DISPATCH_TOKEN", "")
        self._token = token if 32 <= len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token) else ""
        self._next_attempt = 0.0
        self._lock = threading.Lock()
        self._last_result = "idle" if self.enabled else "disabled"
        self._last_attempt_at: str | None = None
        self._last_accepted_at: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    def status(self) -> dict:
        with self._lock:
            return {"enabled": self.enabled, "last_result": self._last_result,
                    "last_attempt_at": self._last_attempt_at, "last_accepted_at": self._last_accepted_at,
                    "retry_after_seconds": max(0, int(self._next_attempt - time.monotonic())),
                    "refresh_after_seconds": self.dispatch_after_seconds}

    def check(self, results: Iterable[Any], *, force: bool = False) -> str:
        if not self.enabled:
            return "disabled"
        now = datetime.now(timezone.utc)
        scheduled = [result for result in results if result.source.collection_driver == "scheduled"]
        delayed = bool(force and scheduled)
        for result in scheduled:
            try:
                delayed = delayed or (now - datetime.fromisoformat(result.scanned_at)).total_seconds() >= self.dispatch_after_seconds
            except (TypeError, ValueError):
                delayed = True
            if delayed:
                break
        if not delayed:
            return "fresh"
        clock = time.monotonic()
        with self._lock:
            if clock < self._next_attempt:
                return "cooldown"
            # A button click and the independent timer share this reservation.
            self._next_attempt = clock + self.cooldown_seconds
            self._last_attempt_at = now.isoformat()
            self._last_result = "requesting"
        logger = logging.getLogger(__name__)
        try:
            with requests.Session() as session:
                session.trust_env = False
                response = session.post(
                    self.dispatch_url,
                    json={"ref": "main"},
                    headers={"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"},
                    timeout=(5, 15),
                    allow_redirects=False,
                )
                try:
                    status = response.status_code
                finally:
                    response.close()
        except requests.RequestException:
            logger.warning("catalog_watchdog_failed kind=network")
            with self._lock:
                self._last_result = "network_failed"
            return "failed"
        if status not in {200, 204}:
            with self._lock:
                self._last_result = "authentication_failed" if status in {401, 403} else "http_failed"
                if status in {401, 403}:
                    self._next_attempt = clock + 6 * 60 * 60
            logger.warning("catalog_watchdog_failed status=%s", status)
            return "failed"
        logger.info("catalog_watchdog_dispatched")
        with self._lock:
            self._last_result = "accepted"
            self._last_accepted_at = datetime.now(timezone.utc).isoformat()
        # Accepted dispatch is not proof of a completed collection. Only a valid
        # snapshot import may advance the source's original checked_at timestamp.
        return "dispatched"
