from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .web_catalog import CatalogError, CatalogService, SOURCE_GROUP_LABELS


class PushSubscriptionError(ValueError):
    """Raised when a browser push subscription is malformed."""


class PushSubscriptionStore:
    """Small JSON store for the beta; production can point it at a Railway volume."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"subscriptions": {}, "scopes": {}}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"subscriptions": {}, "scopes": {}}
        if not isinstance(payload, dict):
            return {"subscriptions": {}, "scopes": {}}
        subscriptions = payload.get("subscriptions") if isinstance(payload.get("subscriptions"), dict) else {}
        scopes = payload.get("scopes") if isinstance(payload.get("scopes"), dict) else {}
        return {"subscriptions": subscriptions, "scopes": scopes}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def upsert(self, subscription: dict[str, Any], scope: dict[str, str]) -> int:
        endpoint = str(subscription.get("endpoint", "")).strip()
        if not endpoint.startswith("https://") or len(endpoint) > 2_000:
            raise PushSubscriptionError("endpoint must be an HTTPS URL")
        keys = subscription.get("keys")
        if not isinstance(keys, dict) or not str(keys.get("p256dh", "")).strip() or not str(keys.get("auth", "")).strip():
            raise PushSubscriptionError("subscription keys are required")
        record = {
            "endpoint": endpoint,
            "keys": {"p256dh": str(keys["p256dh"]), "auth": str(keys["auth"])},
            "scope": scope,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            payload = self._read()
            payload["subscriptions"][endpoint] = record
            self._write(payload)
            return len(payload["subscriptions"])

    def remove(self, endpoint: str) -> None:
        with self._lock:
            payload = self._read()
            payload["subscriptions"].pop(endpoint, None)
            self._write(payload)

    def subscriptions(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._read()["subscriptions"].values())

    def scope_state(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            state = self._read()["scopes"].get(key)
            return state if isinstance(state, dict) else None

    def save_scope_state(self, key: str, state: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read()
            payload["scopes"][key] = state
            self._write(payload)


def normalize_push_scope(payload: dict[str, Any], source_ids: set[str]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise PushSubscriptionError("scope must be an object")
    source_id = str(payload.get("source_id", "all")).strip() or "all"
    if source_id not in {"all", "*"} and source_id not in source_ids:
        raise PushSubscriptionError("unknown source_id")
    grade = str(payload.get("grade", "全学年")).strip() or "全学年"
    if len(grade) > 30:
        raise PushSubscriptionError("grade is too long")
    feed = str(payload.get("feed", "notices")).strip() or "notices"
    if feed not in {"notices", "events"}:
        raise PushSubscriptionError("invalid feed")
    group = str(payload.get("group", "all")).strip() or "all"
    if group not in {"all", "*", *SOURCE_GROUP_LABELS}:
        raise PushSubscriptionError("invalid source group")
    return {"source_id": "all" if source_id == "*" else source_id, "grade": grade, "feed": feed, "group": "all" if group == "*" else group}


def scope_key(scope: dict[str, str]) -> str:
    return json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class WebPushNotifier:
    """Poll subscribed public feeds and notify browsers when a new notice appears."""

    def __init__(self, catalog: CatalogService, settings: Any) -> None:
        self.catalog = catalog
        self.settings = settings
        self.public_key = getattr(settings, "web_push_public_key", None)
        self.private_key = getattr(settings, "web_push_private_key", None)
        self.contact = getattr(settings, "web_push_contact", None)
        state_path = getattr(settings, "web_push_state_path", None)
        self.store = PushSubscriptionStore(state_path) if state_path else None
        self.interval = float(getattr(settings, "web_push_scan_interval_seconds", 900))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def browser_enabled(self) -> bool:
        return bool(self.public_key and self.store)

    @property
    def sending_enabled(self) -> bool:
        return bool(self.browser_enabled and self.private_key and self.contact)

    def config(self) -> dict[str, Any]:
        return {
            "enabled": self.browser_enabled,
            "sending_enabled": self.sending_enabled,
            "public_key": self.public_key if self.browser_enabled else None,
            "scan_interval_seconds": int(self.interval),
        }

    def subscribe(self, subscription: dict[str, Any], scope: dict[str, Any]) -> int:
        if not self.store:
            raise PushSubscriptionError("push storage is not configured")
        normalized = normalize_push_scope(scope, {source.id for source in self.catalog.sources if source.enabled})
        return self.store.upsert(subscription, normalized)

    def start(self) -> None:
        if not self.sending_enabled or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="web-push-scanner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.scan_subscriptions()
            except Exception:
                # A single upstream or push provider failure must not stop the web server.
                continue

    def scan_subscriptions(self) -> None:
        if not self.sending_enabled or not self.store:
            return
        subscriptions = self.store.subscriptions()
        scopes = {scope_key(record.get("scope", {})): record.get("scope", {}) for record in subscriptions}
        for scope in scopes.values():
            self._scan_scope(scope)

    def _scan_scope(self, scope: dict[str, str]) -> None:
        if not self.store:
            return
        key = scope_key(scope)
        try:
            results = self.catalog.get_many(
                source_id=scope["source_id"],
                grade=scope["grade"],
                feed_group=scope["feed"],
                source_group=scope["group"],
                refresh=True,
            )
        except CatalogError:
            return
        current = {notice.id: notice.to_summary() for result in results for notice in result.notices}
        state = self.store.scope_state(key)
        if state is None:
            self.store.save_scope_state(key, {"known_ids": list(current), "notified_ids": list(current), "updated_at": time.time()})
            return
        notified = set(str(value) for value in state.get("notified_ids", []))
        pending = [notice for notice_id, notice in current.items() if notice_id not in notified]
        if not pending:
            self.store.save_scope_state(key, {"known_ids": list(current), "notified_ids": list(notified & set(current)), "updated_at": time.time()})
            return
        subscriptions = [record for record in self.store.subscriptions() if record.get("scope") == scope]
        if not subscriptions:
            return
        message = self._message(pending[:5], len(pending))
        delivered = True
        for record in subscriptions:
            try:
                self._send(record, message)
            except Exception as exc:
                delivered = False
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in {404, 410}:
                    self.store.remove(str(record.get("endpoint", "")))
        if delivered:
            notified.update(notice["id"] for notice in pending)
        self.store.save_scope_state(key, {"known_ids": list(current), "notified_ids": list(notified & set(current)), "updated_at": time.time()})

    def _send(self, record: dict[str, Any], message: dict[str, str]) -> None:
        if not self.private_key or not self.contact:
            return
        try:
            from pywebpush import webpush
        except ImportError as exc:
            raise RuntimeError("pywebpush is not installed") from exc
        webpush(
            subscription_info={"endpoint": record["endpoint"], "keys": record["keys"]},
            data=json.dumps(message, ensure_ascii=False),
            vapid_private_key=self.private_key,
            vapid_claims={"sub": self.contact},
        )

    @staticmethod
    def _message(notices: list[dict[str, Any]], total: int) -> dict[str, str]:
        first = notices[0]
        suffix = f" ほか{total - 1}件" if total > 1 else ""
        return {
            "title": "おたより desk｜新着のお知らせ",
            "body": f"{first.get('source_name', '学校')}：{first.get('title', '新しいお知らせ')}{suffix}",
            "url": f"/?source_id={first.get('source_id', 'all')}",
        }
