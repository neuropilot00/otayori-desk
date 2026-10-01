"""Parent pilot push storage and scanner.

Set WEB_PUSH_ENABLED=false to disable subscription enrollment and outbound push
(restart the server after changing deployment environment variables). Owner
status, export and deletion remain available. The pilot holds at most 1,000
subscriptions; existing records may renew at capacity. No counts are public.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import json
import os
import re
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .extractor import normalize_grade
from .web_catalog import CatalogError, CatalogService, SOURCE_GROUP_LABELS

CONSENT_VERSION = "2026-10-01"
RETENTION_DAYS = 180
MAX_SUBSCRIPTIONS = 1_000
PUSH_TIMEOUT_SECONDS = 10
# Stable, application-specific PostgreSQL advisory lock (held by a live session).
SCAN_LOCK_ID = 7541296301001


class PushSubscriptionError(ValueError):
    """Raised when a browser push subscription or consent is invalid."""


def _validated_endpoint(endpoint: Any) -> str:
    if not isinstance(endpoint, str) or not endpoint or len(endpoint) > 2_000:
        raise PushSubscriptionError("invalid push endpoint")
    if not endpoint.isascii() or any(character.isspace() or ord(character) < 0x20 or ord(character) == 0x7f for character in endpoint):
        raise PushSubscriptionError("invalid push endpoint")
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise PushSubscriptionError("invalid push endpoint") from exc
    allowed = (
        host == "fcm.googleapis.com"
        or host == "updates.push.services.mozilla.com"
        or host.endswith(".updates.push.services.mozilla.com")
        or host.endswith(".push.apple.com")
        or host.endswith(".notify.windows.com")
    )
    # DNS labels must be literal: no IPs, percent encoding, empty labels or
    # suffix tricks. Explicit standard HTTPS port is allowed; custom ports are not.
    if (
        parsed.scheme != "https" or not allowed
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
        or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split("."))
        or parsed.username is not None or parsed.password is not None
        or port not in {None, 443} or "#" in endpoint or "\\" in endpoint
    ):
        raise PushSubscriptionError("endpoint must use an approved HTTPS push provider")
    return endpoint


def _decode_key(value: Any, name: str, length: int) -> bytes:
    if not isinstance(value, str) or len(value) > 4 * ((length + 2) // 3) or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise PushSubscriptionError(f"invalid subscription key: {name}")
    try:
        decoded = base64.b64decode(value.rstrip("=") + "=" * (-len(value.rstrip("=")) % 4), altchars=b"-_", validate=True)
    except (ValueError, binascii.Error) as exc:
        raise PushSubscriptionError(f"invalid subscription key: {name}") from exc
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii")
    if len(decoded) != length or value not in {canonical, canonical.rstrip("=")}:
        raise PushSubscriptionError(f"invalid subscription key: {name}")
    return decoded


def _validated_subscription(subscription: dict[str, Any]) -> tuple[str, str, str]:
    if not isinstance(subscription, dict):
        raise PushSubscriptionError("subscription must be an object")
    endpoint = _validated_endpoint(subscription.get("endpoint"))
    keys = subscription.get("keys")
    if not isinstance(keys, dict):
        raise PushSubscriptionError("subscription keys are required")
    point = _decode_key(keys.get("p256dh"), "p256dh", 65)
    _decode_key(keys.get("auth"), "auth", 16)
    if point[0] != 4:
        raise PushSubscriptionError("p256dh must be an uncompressed P-256 point")
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    except ValueError as exc:
        raise PushSubscriptionError("invalid P-256 point") from exc
    return endpoint, keys["p256dh"], keys["auth"]


def _validated_owner(owner_hash: str) -> str:
    # The HTTP server supplies SHA-256 of its secure, opaque owner cookie.
    if not isinstance(owner_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", owner_hash):
        raise PushSubscriptionError("a server-issued owner hash is required")
    return owner_hash


def _validated_consent(owner_hash: str, consent_version: str) -> None:
    _validated_owner(owner_hash)
    if consent_version != CONSENT_VERSION:
        raise PushSubscriptionError("current explicit notification consent is required")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _revalidated_at(record: dict[str, Any]) -> datetime | None:
    try:
        updated = datetime.fromisoformat(record["updated_at"])
        return updated if updated.tzinfo is not None else None
    except (KeyError, TypeError, ValueError):
        return None


def _expired(record: dict[str, Any]) -> bool:
    updated = _revalidated_at(record)
    # Unknown/malformed legacy dates suppress delivery but never justify
    # silently deleting data during migration or retention housekeeping.
    return updated is not None and updated <= datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def _active(record: dict[str, Any]) -> bool:
    return (
        bool(re.fullmatch(r"[0-9a-f]{64}", str(record.get("owner_hash", ""))))
        and record.get("consent_version") == CONSENT_VERSION
        and _revalidated_at(record) is not None and not _expired(record)
    )


def _same_record(current: dict[str, Any], scanned: dict[str, Any]) -> bool:
    return all(current.get(name) == scanned.get(name)
               for name in ("owner_hash", "consent_version", "updated_at", "scope", "keys"))


def _claimed_record(old: dict[str, Any] | None, subscription: dict[str, Any], scope: dict[str, str],
                    owner_hash: str, consent_version: str) -> dict[str, Any]:
    _validated_consent(owner_hash, consent_version)
    endpoint, p256dh, auth = _validated_subscription(subscription)
    now = _now()
    keys = {"p256dh": p256dh, "auth": auth}
    if old:
        if old.get("owner_hash") and old["owner_hash"] != owner_hash:
            raise PushSubscriptionError("endpoint belongs to another owner")
        if not old.get("owner_hash"):
            old_keys = old.get("keys", {})
            try:
                matches = (
                    _decode_key(old_keys.get("p256dh"), "p256dh", 65) == _decode_key(p256dh, "p256dh", 65)
                    and _decode_key(old_keys.get("auth"), "auth", 16) == _decode_key(auth, "auth", 16)
                )
            except PushSubscriptionError:
                matches = False
            if not matches:
                raise PushSubscriptionError("legacy endpoint keys do not match")
    # Renewing an expired subscription, changing scope/keys, or claiming a
    # legacy subscription starts a fresh baseline; it never backfills history.
    keep_state = (
        old is not None and _active(old) and old.get("scope") == scope
        and old.get("keys") == keys
    )
    return {
        "endpoint": endpoint, "keys": keys, "scope": scope,
        "owner_hash": owner_hash, "consent_version": consent_version,
        "created_at": (old or {}).get("created_at") or now, "updated_at": now,
        "delivery_state": old.get("delivery_state") if keep_state else None,
    }


@contextmanager
def _file_scan_lock(path: Path):
    # Kernel lock has no TTL that could expire while an upstream scan is slow.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as handle:
        try:
            path.chmod(0o600)
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


class _OwnerOperations:
    def export_owner(self, owner_hash: str) -> dict[str, Any]:
        _validated_owner(owner_hash)
        return {"subscriptions": [
            {name: record.get(name) for name in ("scope", "created_at", "updated_at", "consent_version")}
            for record in self.subscriptions() if record.get("owner_hash") == owner_hash
        ]}

    def owner_status(self, owner_hash: str) -> dict[str, Any]:
        _validated_owner(owner_hash)
        scopes = {scope_key(record["scope"]): record["scope"] for record in self.subscriptions()
                  if record.get("owner_hash") == owner_hash and _active(record)}
        return {"subscribed": bool(scopes), "scopes": list(scopes.values())}


class PushSubscriptionStore(_OwnerOperations):
    """JSON fallback, strictly one application process; not multi-replica ready.

    Scan flock prevents overlapping workers on a shared local file, but JSON
    subscription mutations have only a process lock. Use SQL for deployment.
    Legacy records stay intact but require renewed owner-bound consent.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"subscriptions": {}, "scopes": {}}
        # Fail closed on corruption, rather than overwriting subscriptions.
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid push state")
        for name in ("subscriptions", "scopes"):
            payload.setdefault(name, {})
            if not isinstance(payload[name], dict):
                raise ValueError("invalid push state")
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        # Set private permissions before writing endpoints and keys.
        with temporary.open("w", encoding="utf-8") as handle:
            temporary.chmod(0o600)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        temporary.replace(self.path)

    def upsert(self, subscription: dict[str, Any], scope: dict[str, str],
               owner_hash: str, consent_version: str) -> dict[str, bool]:
        endpoint, _, _ = _validated_subscription(subscription)
        with self._lock:
            payload = self._read()
            if endpoint not in payload["subscriptions"] and len(payload["subscriptions"]) >= MAX_SUBSCRIPTIONS:
                # Expired rows are removed only by the explicit retention rule.
                payload["subscriptions"] = {key: value for key, value in payload["subscriptions"].items() if not _expired(value)}
                if len(payload["subscriptions"]) >= MAX_SUBSCRIPTIONS:
                    raise PushSubscriptionError("free pilot subscription capacity reached")
            payload["subscriptions"][endpoint] = _claimed_record(
                payload["subscriptions"].get(endpoint), subscription, scope, owner_hash, consent_version)
            self._write(payload)
        return {"subscribed": True}

    def legacy_reconsent_count(self) -> int:
        """Internal operator diagnostic; never include this in a public API."""
        with self._lock:
            return sum(not _active(record) and not _expired(record)
                       for record in self._read()["subscriptions"].values())

    def remove(self, endpoint: str, *, expected_record: dict[str, Any] | None = None) -> None:
        with self._lock:
            payload = self._read()
            current = payload["subscriptions"].get(endpoint)
            if current and (expected_record is None or _same_record(current, expected_record)):
                payload["subscriptions"].pop(endpoint)
                self._write(payload)

    def is_current(self, record: dict[str, Any]) -> bool:
        with self._lock:
            current = self._read()["subscriptions"].get(record["endpoint"])
            return bool(current and _active(current) and _same_record(current, record))

    def delete_owner(self, owner_hash: str) -> int:
        _validated_owner(owner_hash)
        with self._lock:
            payload = self._read()
            endpoints = [endpoint for endpoint, record in payload["subscriptions"].items()
                         if record.get("owner_hash") == owner_hash]
            for endpoint in endpoints:
                del payload["subscriptions"][endpoint]  # includes the delivery ledger
            self._write(payload)
        return len(endpoints)

    def subscriptions(self) -> list[dict[str, Any]]:
        with self._lock:
            payload = self._read()
            expired = [endpoint for endpoint, record in payload["subscriptions"].items() if _expired(record)]
            for endpoint in expired:
                del payload["subscriptions"][endpoint]
            if expired:
                self._write(payload)
            return list(payload["subscriptions"].values())

    def delivery_state(self, record: dict[str, Any]) -> dict[str, Any] | None:
        return record.get("delivery_state")

    def save_delivery_state(self, record: dict[str, Any], state: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read()
            current = payload["subscriptions"].get(record["endpoint"])
            if current and _same_record(current, record):
                current["delivery_state"] = state
                self._write(payload)

    def scope_state(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            return self._read()["scopes"].get(key)

    def save_scope_state(self, key: str, state: dict[str, Any]) -> None:
        with self._lock:
            payload = self._read()
            payload["scopes"][key] = state
            self._write(payload)

    def scan_lock(self):
        return _file_scan_lock(self.path.with_suffix(self.path.suffix + ".scan.lock"))


class SQLitePushSubscriptionStore(_OwnerOperations):
    """SQLite pilot store: one shared database on one host.

    A kernel scan lock excludes other workers using the same database path.
    Separate replica volumes are independent stores and are NOT supported.
    All connections are explicitly closed, including migration/error paths.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self._lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        self.path.chmod(0o600)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def _transaction(self):
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            with closing(connection.cursor()) as cursor:
                yield cursor

    def _execute(self, cursor, sql: str, params=()):
        cursor.execute(sql, params)
        return cursor

    def _add_columns(self, cursor) -> None:
        names = {row[1] for row in self._execute(cursor, "PRAGMA table_info(push_subscriptions)").fetchall()}
        for name in ("owner_hash", "consent_version", "delivery_state_json"):
            if name not in names:
                self._execute(cursor, f"ALTER TABLE push_subscriptions ADD COLUMN {name} TEXT")

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
        with self._transaction() as cursor:
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    endpoint TEXT PRIMARY KEY, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
                    scope_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            self._add_columns(cursor)
            self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_scope ON push_subscriptions(scope_json)")
            self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_owner ON push_subscriptions(owner_hash)")
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS push_scope_state (
                    scope_key TEXT PRIMARY KEY, known_ids_json TEXT NOT NULL,
                    notified_ids_json TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL
                )
            """)

    @staticmethod
    def _record(row) -> dict[str, Any]:
        endpoint, p256dh, auth, scope_json, created, updated, owner, consent, delivery = row
        return {"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth},
                "scope": json.loads(scope_json), "created_at": created, "updated_at": updated,
                "owner_hash": owner, "consent_version": consent,
                "delivery_state": json.loads(delivery) if delivery else None}

    _columns = "endpoint, p256dh, auth, scope_json, created_at, updated_at, owner_hash, consent_version, delivery_state_json"
    _for_update = ""

    def _enrollment_lock(self, cursor) -> None:
        # BEGIN IMMEDIATE already serializes SQLite enrollment transactions.
        pass

    def upsert(self, subscription: dict[str, Any], scope: dict[str, str],
               owner_hash: str, consent_version: str) -> dict[str, bool]:
        _validated_consent(owner_hash, consent_version)
        endpoint, p256dh, auth = _validated_subscription(subscription)
        with self._transaction() as cursor:
            self._enrollment_lock(cursor)
            existing = self._execute(cursor, "SELECT endpoint FROM push_subscriptions WHERE endpoint = ?", (endpoint,)).fetchone()
            count = self._execute(cursor, "SELECT COUNT(*) FROM push_subscriptions").fetchone()[0]
            if existing is None and count >= MAX_SUBSCRIPTIONS:
                rows = self._execute(cursor, "SELECT endpoint, updated_at FROM push_subscriptions").fetchall()
                for old_endpoint, updated in rows:
                    if _expired({"updated_at": updated}):
                        self._execute(cursor, "DELETE FROM push_subscriptions WHERE endpoint = ?", (old_endpoint,))
                        count -= 1
                if count >= MAX_SUBSCRIPTIONS:
                    raise PushSubscriptionError("free pilot subscription capacity reached")
            # Insert first to serialize PostgreSQL claims even for a new endpoint;
            # a rejected claim rolls back this insert.
            self._execute(cursor, """
                INSERT INTO push_subscriptions(endpoint, p256dh, auth, scope_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(endpoint) DO NOTHING
            """, (endpoint, p256dh, auth, scope_key(scope), _now(), _now()))
            row = self._execute(cursor, f"SELECT {self._columns} FROM push_subscriptions WHERE endpoint = ?{self._for_update}", (endpoint,)).fetchone()
            record = _claimed_record(self._record(row), subscription, scope, owner_hash, consent_version)
            self._execute(cursor, """
                UPDATE push_subscriptions SET p256dh = ?, auth = ?, scope_json = ?,
                    owner_hash = ?, consent_version = ?, updated_at = ?, delivery_state_json = ?
                WHERE endpoint = ?
            """, (p256dh, auth, scope_key(scope), owner_hash, consent_version, record["updated_at"],
                  json.dumps(record["delivery_state"]) if record["delivery_state"] is not None else None, endpoint))
        return {"subscribed": True}

    def legacy_reconsent_count(self) -> int:
        """Internal diagnostic, including records with outdated consent."""
        with self._transaction() as cursor:
            rows = self._execute(cursor, "SELECT owner_hash, consent_version, updated_at FROM push_subscriptions").fetchall()
        return sum(not _active(record) and not _expired(record) for record in
                   ({"owner_hash": owner, "consent_version": consent, "updated_at": updated}
                    for owner, consent, updated in rows))

    def remove(self, endpoint: str, *, expected_record: dict[str, Any] | None = None) -> None:
        with self._transaction() as cursor:
            if expected_record is None:
                self._execute(cursor, "DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
            elif endpoint == expected_record["endpoint"]:
                self._execute(cursor, """
                    DELETE FROM push_subscriptions WHERE endpoint = ? AND owner_hash = ?
                        AND updated_at = ? AND scope_json = ? AND p256dh = ? AND auth = ?
                        AND consent_version = ?
                """, self._identity(expected_record))

    @staticmethod
    def _identity(record: dict[str, Any]):
        return (record["endpoint"], record["owner_hash"], record["updated_at"],
                scope_key(record["scope"]), record["keys"]["p256dh"], record["keys"]["auth"],
                record["consent_version"])

    def is_current(self, record: dict[str, Any]) -> bool:
        if not _active(record):
            return False
        with self._transaction() as cursor:
            return self._execute(cursor, """
                SELECT 1 FROM push_subscriptions WHERE endpoint = ? AND owner_hash = ?
                    AND updated_at = ? AND scope_json = ? AND p256dh = ? AND auth = ?
                    AND consent_version = ?
            """, self._identity(record)).fetchone() is not None

    def delete_owner(self, owner_hash: str) -> int:
        _validated_owner(owner_hash)
        with self._transaction() as cursor:
            return self._execute(cursor, "DELETE FROM push_subscriptions WHERE owner_hash = ?", (owner_hash,)).rowcount

    def subscriptions(self) -> list[dict[str, Any]]:
        records = []
        with self._transaction() as cursor:
            rows = self._execute(cursor, f"SELECT {self._columns} FROM push_subscriptions").fetchall()
            for row in rows:
                # Retention applies to legacy and owned subscriptions alike.
                if _expired({"updated_at": row[5]}):
                    self._execute(cursor, "DELETE FROM push_subscriptions WHERE endpoint = ?", (row[0],))
                    continue
                try:
                    record = self._record(row)
                except (ValueError, TypeError):
                    continue
                if isinstance(record["scope"], dict):
                    records.append(record)
        return records

    def delivery_state(self, record: dict[str, Any]) -> dict[str, Any] | None:
        return record.get("delivery_state")

    def save_delivery_state(self, record: dict[str, Any], state: dict[str, Any]) -> None:
        with self._transaction() as cursor:
            # A concurrent owner deletion/renewal must not recreate or overwrite
            # the replacement subscription's baseline.
            self._execute(cursor, """
                UPDATE push_subscriptions SET delivery_state_json = ?
                WHERE endpoint = ? AND owner_hash = ? AND updated_at = ?
                    AND scope_json = ? AND p256dh = ? AND auth = ? AND consent_version = ?
            """, (json.dumps(state), *self._identity(record)))

    def scope_state(self, key: str) -> dict[str, Any] | None:
        with self._transaction() as cursor:
            row = self._execute(cursor, "SELECT known_ids_json, notified_ids_json, updated_at FROM push_scope_state WHERE scope_key = ?", (key,)).fetchone()
        if row is None:
            return None
        return {"known_ids": json.loads(row[0]), "notified_ids": json.loads(row[1]), "updated_at": row[2]}

    def save_scope_state(self, key: str, state: dict[str, Any]) -> None:
        # Compatibility for existing scope migrations/tools; delivery uses only
        # the renewed per-subscription ledger, never this legacy global state.
        with self._transaction() as cursor:
            self._execute(cursor, """
                INSERT INTO push_scope_state(scope_key, known_ids_json, notified_ids_json, updated_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(scope_key) DO UPDATE SET
                    known_ids_json = excluded.known_ids_json,
                    notified_ids_json = excluded.notified_ids_json, updated_at = excluded.updated_at
            """, (key, json.dumps(state.get("known_ids", [])), json.dumps(state.get("notified_ids", [])), state.get("updated_at", time.time())))

    def scan_lock(self):
        return _file_scan_lock(self.path.with_suffix(self.path.suffix + ".scan.lock"))


class PostgresPushSubscriptionStore(SQLitePushSubscriptionStore):
    """Shared PostgreSQL storage with an atomic session advisory scanner lock.

    Every scanner must use this implementation and the same database. Lock loss
    or a process crash can still occur after provider acceptance but before the
    ledger commit; retries can duplicate acceptance, with no exactly-once promise.
    """

    _for_update = " FOR UPDATE"

    def __init__(self, database_url: str) -> None:
        if not database_url.startswith(("postgres://", "postgresql://")):
            raise ValueError("WEB_PUSH_DATABASE_URL must be a PostgreSQL URL")
        self.database_url = database_url
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for PostgreSQL push storage") from exc
        return psycopg.connect(
            self.database_url, connect_timeout=10,
            options="-c statement_timeout=10000 -c lock_timeout=5000",
        )

    @contextmanager
    def _transaction(self):
        with self._lock, self._connect() as connection, connection.cursor() as cursor:
            yield cursor

    def _execute(self, cursor, sql: str, params=()):
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor

    def _add_columns(self, cursor) -> None:
        for name in ("owner_hash", "consent_version", "delivery_state_json"):
            self._execute(cursor, f"ALTER TABLE push_subscriptions ADD COLUMN IF NOT EXISTS {name} TEXT")

    def _enrollment_lock(self, cursor) -> None:
        # Serializes capacity checks for different endpoints across replicas.
        self._execute(cursor, "SELECT pg_advisory_xact_lock(?)", (SCAN_LOCK_ID + 1,))

    def _initialize(self) -> None:
        # No SQLite-specific PRAGMAs on PostgreSQL.
        with self._transaction() as cursor:
            self._enrollment_lock(cursor)
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    endpoint TEXT PRIMARY KEY, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
                    scope_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            self._add_columns(cursor)
            self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_scope ON push_subscriptions(scope_json)")
            self._execute(cursor, "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_owner ON push_subscriptions(owner_hash)")
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS push_scope_state (
                    scope_key TEXT PRIMARY KEY, known_ids_json TEXT NOT NULL,
                    notified_ids_json TEXT NOT NULL, updated_at DOUBLE PRECISION NOT NULL
                )
            """)

    @contextmanager
    def scan_lock(self):
        with self._connect() as connection, connection.cursor() as cursor:
            # Session locks survive transactions. Avoid keeping an idle
            # transaction open throughout potentially slow upstream scans.
            connection.autocommit = True
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (SCAN_LOCK_ID,))
            acquired = bool(cursor.fetchone()[0])
            try:
                yield acquired
            finally:
                if acquired:
                    cursor.execute("SELECT pg_advisory_unlock(%s)", (SCAN_LOCK_ID,))


def normalize_push_scope(payload: dict[str, Any], source_ids: set[str]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise PushSubscriptionError("scope must be an object")
    source_id = str(payload.get("source_id", "all")).strip() or "all"
    if source_id not in {"all", "*"} and source_id not in source_ids:
        raise PushSubscriptionError("unknown source_id")
    grade = str(payload.get("grade", "全学年")).strip() or "全学年"
    if len(grade) > 30:
        raise PushSubscriptionError("grade is too long")
    grade = normalize_grade(grade)
    if grade not in {"全学年", *(f"{number}年生" for number in range(1, 7))}:
        raise PushSubscriptionError("unsupported grade")
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
    """One scanner per store; provider acceptance does not mean viewed.

    A crash between acceptance and ledger persistence can cause a retry.
    """

    def __init__(self, catalog: CatalogService, settings: Any) -> None:
        self.catalog = catalog
        self.settings = settings
        self.public_key = getattr(settings, "web_push_public_key", None)
        self.private_key = getattr(settings, "web_push_private_key", None)
        self.contact = getattr(settings, "web_push_contact", None)
        database_url = getattr(settings, "web_push_database_url", None)
        database_path = getattr(settings, "web_push_database_path", None)
        state_path = getattr(settings, "web_push_state_path", None)
        if database_url:
            self.store = PostgresPushSubscriptionStore(database_url)
        elif database_path:
            self.store = SQLitePushSubscriptionStore(database_path)
        else:
            self.store = PushSubscriptionStore(state_path) if state_path else None
        self.interval = float(getattr(settings, "web_push_scan_interval_seconds", 900))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._scanner_lock = threading.Lock()

    @property
    def browser_enabled(self) -> bool:
        enabled = os.getenv("WEB_PUSH_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
        return bool(enabled and self.public_key and self.store)

    @property
    def sending_enabled(self) -> bool:
        return bool(self.browser_enabled and self.private_key and self.contact)

    def config(self) -> dict[str, Any]:
        return {
            "enabled": self.browser_enabled, "sending_enabled": self.sending_enabled,
            "public_key": self.public_key if self.browser_enabled else None,
            "scan_interval_seconds": int(self.interval),
            "consent_version": CONSENT_VERSION, "retention_days": RETENTION_DAYS,
        }

    def subscribe(self, subscription: dict[str, Any], scope: dict[str, Any],
                  owner_hash: str, consent_version: str) -> dict[str, bool]:
        if not self.store:
            raise PushSubscriptionError("push storage is not configured")
        if not self.browser_enabled:
            raise PushSubscriptionError("push enrollment is disabled")
        _validated_consent(owner_hash, consent_version)
        selected = [source for source in self.catalog.sources if source.enabled]
        normalized = normalize_push_scope(scope, {source.id for source in selected})
        # Match CatalogService.get_many's collection expansion and filters
        # using registry metadata only; enrollment must never trigger scans.
        if normalized["source_id"] != "all":
            requested = next(source for source in selected if source.id == normalized["source_id"])
            if requested.collection_root:
                selected = [source for source in selected if source.collection_id == requested.collection_id]
            else:
                selected = [requested]
        selected = [source for source in selected if source.feed_group == normalized["feed"]
                    and (normalized["group"] == "all" or source.source_group == normalized["group"])]
        if not selected:
            raise PushSubscriptionError("scope matches no enabled source")
        return self.store.upsert(subscription, normalized, owner_hash, consent_version)

    def export_owner(self, owner_hash: str) -> dict[str, Any]:
        _validated_owner(owner_hash)
        return self.store.export_owner(owner_hash) if self.store else {"subscriptions": []}

    def delete_owner(self, owner_hash: str) -> int:
        _validated_owner(owner_hash)
        return self.store.delete_owner(owner_hash) if self.store else 0

    def owner_status(self, owner_hash: str) -> dict[str, Any]:
        _validated_owner(owner_hash)
        return self.store.owner_status(owner_hash) if self.store else {"subscribed": False, "scopes": []}

    def legacy_reconsent_count(self) -> int:
        """For operator logs only; server must not expose global counts."""
        return self.store.legacy_reconsent_count() if self.store else 0

    def start(self) -> None:
        with self._scanner_lock:
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
                # Upstream or push provider failure must not stop the server.
                continue

    def scan_subscriptions(self) -> None:
        if not self.sending_enabled or not self.store or not self._scanner_lock.acquire(blocking=False):
            return
        try:
            with self.store.scan_lock() as acquired:
                if not acquired:
                    return
                records = [record for record in self.store.subscriptions() if _active(record)]
                scopes = {scope_key(record["scope"]): record["scope"] for record in records}
                for scope in scopes.values():
                    self._scan_scope(scope)
        finally:
            self._scanner_lock.release()

    def _scan_scope(self, scope: dict[str, str]) -> None:
        if not self.store:
            return
        try:
            results = self.catalog.get_many(
                source_id=scope["source_id"], grade=scope["grade"],
                feed_group=scope["feed"], source_group=scope["group"], refresh=True,
            )
        except CatalogError:
            return
        # No initial baseline or delivery on empty/partial upstream responses.
        if not results or any(result.warnings for result in results):
            return
        current = {notice.id: notice.to_summary() for result in results for notice in result.notices}
        records = [record for record in self.store.subscriptions() if record.get("scope") == scope and _active(record)]
        for record in records:
            try:
                _validated_subscription(record)  # old/tampered storage is not trusted
            except PushSubscriptionError:
                continue
            state = self.store.delivery_state(record)
            if state is None:
                self.store.save_delivery_state(record, {"known_ids": list(current), "accepted_ids": list(current)})
                continue
            if not isinstance(state, dict) or not isinstance(state.get("known_ids"), list) or not isinstance(state.get("accepted_ids"), list):
                # Corrupted ledgers fail closed; never backfill.
                continue
            known = set(state["known_ids"]) | set(current)
            accepted = set(state["accepted_ids"])
            pending = [notice for notice_id, notice in current.items() if notice_id not in accepted]
            if pending:
                if not self.sending_enabled or not self.store.is_current(record):
                    continue
                try:
                    self._send(record, self._message(pending[:5], len(pending)))
                except Exception as exc:
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status in {404, 410}:
                        self.store.remove(record["endpoint"], expected_record=record)
                        continue
                else:
                    accepted.update(notice["id"] for notice in pending)
            # Persist independently per recipient, retaining IDs through outages.
            self.store.save_delivery_state(record, {"known_ids": sorted(known), "accepted_ids": sorted(accepted)})

    def _send(self, record: dict[str, Any], message: dict[str, str]) -> None:
        if not self.sending_enabled:
            raise RuntimeError("push sending is not configured")
        if not _active(record):
            raise PushSubscriptionError("subscription needs renewed consent")
        endpoint, p256dh, auth = _validated_subscription(record)
        if not self.store or not self.store.is_current(record):
            raise PushSubscriptionError("subscription was deleted or changed")
        try:
            from pywebpush import webpush
        except ImportError as exc:
            raise RuntimeError("pywebpush is not installed") from exc
        import requests

        class ProviderSession(requests.Session):
            def request(self, method, url, **kwargs):
                _validated_endpoint(url)
                kwargs["allow_redirects"] = False
                kwargs["timeout"] = PUSH_TIMEOUT_SECONDS
                return super().request(method, url, **kwargs)

        with ProviderSession() as session:
            # Disable environment proxies and .netrc credential injection.
            session.trust_env = False
            response = webpush(
                subscription_info={"endpoint": endpoint, "keys": {"p256dh": p256dh, "auth": auth}},
                data=json.dumps(message, ensure_ascii=False), vapid_private_key=self.private_key,
                vapid_claims={"sub": self.contact}, timeout=PUSH_TIMEOUT_SECONDS,
                requests_session=session,
            )
            if not 200 <= response.status_code < 300:
                error = RuntimeError("push provider did not accept delivery")
                error.response = response
                raise error

    @staticmethod
    def _message(notices: list[dict[str, Any]], total: int) -> dict[str, str]:
        # Lockscreen content and link never identify a school, child grade or title.
        return {"title": "おたより desk", "body": "新しいお知らせがあります。アプリでご確認ください。", "url": "/"}
