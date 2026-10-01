from __future__ import annotations

import base64
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from sakurano_line_notifier.web_catalog import CatalogError
from sakurano_line_notifier.web_push import (
    CONSENT_VERSION,
    MAX_SUBSCRIPTIONS,
    PUSH_TIMEOUT_SECONDS,
    PostgresPushSubscriptionStore,
    PushSubscriptionError,
    PushSubscriptionStore,
    SQLitePushSubscriptionStore,
    WebPushNotifier,
    _validated_subscription,
    normalize_push_scope,
)


OWNER = "a" * 64
OTHER = "b" * 64
SCOPE = {"source_id": "school", "grade": "1年生", "feed": "notices", "group": "school"}


def encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def subscription(name: str = "one", scalar: int = 1) -> dict:
    point = ec.derive_private_key(scalar, ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return {
        "endpoint": f"https://fcm.googleapis.com/fcm/send/{name}",
        "keys": {"p256dh": encoded(point), "auth": encoded(bytes([scalar]) * 16)},
    }


def result(*ids: str, warnings=(), source_id="school", coverage_kind="notices", refreshing=False,
           extraction_status="ok"):
    notices = [
        SimpleNamespace(id=value, coverage_kind=coverage_kind, extraction_status=extraction_status,
                        to_summary=lambda value=value: {
            "id": value, "title": "Private school notice", "source_name": "Private school",
            "source_id": source_id,
        }) for value in ids
    ]
    return SimpleNamespace(source=SimpleNamespace(id=source_id, coverage_kind=coverage_kind),
                           notices=notices, warnings=warnings, refreshing=refreshing)


class ValidationTests(unittest.TestCase):
    def test_grade_normalizes_only_supported_pilot_grades(self):
        for raw, expected in (("１学年", "1年生"), ("第6年生", "6年生"),
                              ("2", "2年生"), ("all", "全学年"), ("全校", "全学年")):
            self.assertEqual(normalize_push_scope({"grade": raw}, {"school"})["grade"], expected)
        for raw in ("garbage", "0", "7年生", "99", None):
            with self.subTest(grade=raw), self.assertRaises(PushSubscriptionError):
                normalize_push_scope({"grade": raw}, {"school"})

    def test_only_known_literal_https_provider_hosts(self):
        for host in (
            "fcm.googleapis.com", "updates.push.services.mozilla.com",
            "eu.updates.push.services.mozilla.com", "web.push.apple.com",
            "wns2.notify.windows.com",
        ):
            with self.subTest(host=host):
                item = subscription()
                item["endpoint"] = f"https://{host}/path?token=valid"
                _validated_subscription(item)
        for endpoint in (
            "http://fcm.googleapis.com/path", "https://example.org/push",
            "https://127.0.0.1/push", "https://[::1]/push", "https://localhost/push",
            "https://169.254.169.254/latest/meta-data", "https://fcm.googleapis.com.evil.test/x",
            "https://evilfcm.googleapis.com/x", "https://fcm.googleapis.com@127.0.0.1/x",
            "https://user:password@fcm.googleapis.com/x", "https://@fcm.googleapis.com/x",
            "https://fcm.googleapis.com:8443/x", "https://fcm.googleapis.com:bad/x",
            "https://fcm.googleapis.com/x#fragment", "https://fcm.googleapis.com/x#",
            "https://fcm.googleapis.com./x", "https://fcm.googleapis.com\n/x",
            "https://fcm.googleapis.com/with space", "https://push.apple.com/x",
            "https://notify.windows.com/x", "https://evil.push.apple.com.evil.test/x",
            "https://.push.apple.com/x", "https://a..push.apple.com/x",
            "https://-a.push.apple.com/x", "https://fcm%2egoogleapis.com/x",
            "https://fcm.googleapis.com\\@127.0.0.1/x",
        ):
            with self.subTest(endpoint=endpoint):
                item = subscription()
                item["endpoint"] = endpoint
                with self.assertRaises(PushSubscriptionError):
                    _validated_subscription(item)

    def test_key_lengths_encoding_and_curve_point(self):
        for key, value in (
            ("auth", encoded(b"a" * 15)), ("auth", encoded(b"a" * 17)),
            ("auth", "!!!!"), ("auth", " auth "), ("auth", "a" * 10_000),
            ("p256dh", encoded(b"\x04" + b"a" * 63)),
            ("p256dh", encoded(b"\x02" + b"a" * 64)),
            ("p256dh", encoded(b"\x04" + bytes(64))),
            ("p256dh", "not-a-point"), ("p256dh", None),
        ):
            with self.subTest(key=key, value=str(value)[:30]):
                item = subscription()
                item["keys"][key] = value
                with self.assertRaises(PushSubscriptionError):
                    _validated_subscription(item)
        valid = subscription()
        valid["keys"]["auth"] += "=="
        valid["keys"]["p256dh"] += "="
        _validated_subscription(valid)
        # A noncanonical representation with nonzero padding bits is rejected.
        valid["keys"]["auth"] = valid["keys"]["auth"][:-3] + "B=="
        with self.assertRaises(PushSubscriptionError):
            _validated_subscription(valid)


class StoreSecurityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def stores(self):
        return (
            PushSubscriptionStore(self.root / "push.json"),
            SQLitePushSubscriptionStore(self.root / "push.sqlite3"),
        )

    def test_ownership_consent_export_status_and_delete_isolation(self):
        for store in self.stores():
            with self.subTest(backend=type(store).__name__):
                for owner, consent in (("", CONSENT_VERSION), ("raw-cookie", CONSENT_VERSION),
                                       (OWNER, ""), (OWNER, "old-version")):
                    with self.assertRaises(PushSubscriptionError):
                        store.upsert(subscription(), SCOPE, owner, consent)
                self.assertEqual(store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION),
                                 {"subscribed": True})
                with self.assertRaises(PushSubscriptionError):
                    store.upsert(subscription(scalar=2), SCOPE, OTHER, CONSENT_VERSION)
                store.upsert(subscription("two"), SCOPE, OTHER, CONSENT_VERSION)
                records = store.subscriptions()
                record = next(record for record in records if record["owner_hash"] == OWNER)
                store.save_delivery_state(record, {"known_ids": ["old"], "accepted_ids": ["old"]})
                exported = store.export_owner(OWNER)
                self.assertEqual(len(exported["subscriptions"]), 1)
                self.assertEqual(set(exported["subscriptions"][0]),
                                 {"scope", "created_at", "updated_at", "consent_version"})
                self.assertNotIn("endpoint", json.dumps(exported))
                self.assertNotIn("keys", json.dumps(exported))
                self.assertEqual(store.owner_status(OWNER), {"subscribed": True, "scopes": [SCOPE]})
                self.assertEqual(store.delete_owner(OWNER), 1)
                self.assertEqual(store.delete_owner(OWNER), 0)
                self.assertEqual(store.owner_status(OWNER), {"subscribed": False, "scopes": []})
                self.assertTrue(store.owner_status(OTHER)["subscribed"])
                # Saving a stale scan's ledger cannot resurrect deleted state.
                store.save_delivery_state(record, {"known_ids": ["new"], "accepted_ids": ["new"]})
                store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
                fresh = next(record for record in store.subscriptions() if record["owner_hash"] == OWNER)
                self.assertIsNone(fresh["delivery_state"])

    def test_renewal_preserves_ledger_but_changed_scope_resets_baseline(self):
        for store in self.stores():
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            before = store.subscriptions()[0]
            state = {"known_ids": ["old"], "accepted_ids": ["old"]}
            store.save_delivery_state(before, state)
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            renewed = store.subscriptions()[0]
            self.assertEqual(renewed["created_at"], before["created_at"])
            self.assertEqual(renewed["delivery_state"], state)
            changed = {**SCOPE, "grade": "2年生"}
            store.upsert(subscription(), changed, OWNER, CONSENT_VERSION)
            store.save_delivery_state(before, state)
            self.assertIsNone(store.subscriptions()[0]["delivery_state"])

    def test_stale_provider_failure_cannot_remove_renewed_subscription(self):
        for store in self.stores():
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            before = store.subscriptions()[0]
            self.assertTrue(store.is_current(before))
            store.upsert(subscription(scalar=2), SCOPE, OWNER, CONSENT_VERSION)
            self.assertFalse(store.is_current(before))
            store.remove(before["endpoint"], expected_record=before)
            self.assertEqual(len(store.subscriptions()), 1)
            self.assertTrue(store.is_current(store.subscriptions()[0]))

    def test_expiry_purges_subscription_and_delivery_state_without_scanner_refresh(self):
        expired = (datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
        for store in self.stores():
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            record = store.subscriptions()[0]
            store.save_delivery_state(record, {"known_ids": ["old"], "accepted_ids": ["old"]})
            self.assertEqual(store.subscriptions()[0]["updated_at"], record["updated_at"])
            if isinstance(store, PushSubscriptionStore):
                payload = store._read()
                payload["subscriptions"][record["endpoint"]]["updated_at"] = expired
                store._write(payload)
            else:
                with store._transaction() as cursor:
                    store._execute(cursor, "UPDATE push_subscriptions SET updated_at = ?", (expired,))
            self.assertFalse(store.owner_status(OWNER)["subscribed"])
            self.assertEqual(store.subscriptions(), [])
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            self.assertIsNone(store.subscriptions()[0]["delivery_state"])

    def test_unknown_legacy_date_is_preserved_and_needs_reconsent(self):
        for store in self.stores():
            store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
            if isinstance(store, PushSubscriptionStore):
                payload = store._read()
                payload["subscriptions"][subscription()["endpoint"]]["updated_at"] = "unknown"
                store._write(payload)
            else:
                with store._transaction() as cursor:
                    store._execute(cursor, "UPDATE push_subscriptions SET updated_at = ?", ("unknown",))
            self.assertEqual(len(store.subscriptions()), 1)
            self.assertFalse(store.owner_status(OWNER)["subscribed"])
            self.assertEqual(store.legacy_reconsent_count(), 1)

    def test_scanner_lock_excludes_another_store_instance(self):
        for store in self.stores():
            peer = type(store)(store.path)
            with store.scan_lock() as first:
                self.assertTrue(first)
                with peer.scan_lock() as second:
                    self.assertFalse(second)
            with peer.scan_lock() as available:
                self.assertTrue(available)

    def test_capacity_allows_renewal_and_reuses_expired_slots(self):
        self.assertEqual(MAX_SUBSCRIPTIONS, 1000)
        for store in self.stores():
            with self.subTest(backend=type(store).__name__), patch(
                "sakurano_line_notifier.web_push.MAX_SUBSCRIPTIONS", 2
            ):
                store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
                store.upsert(subscription("two"), SCOPE, OTHER, CONSENT_VERSION)
                with self.assertRaises(PushSubscriptionError):
                    store.upsert(subscription("three"), SCOPE, OWNER, CONSENT_VERSION)
                store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
                expired = (datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
                if isinstance(store, PushSubscriptionStore):
                    payload = store._read()
                    payload["subscriptions"][subscription("two")["endpoint"]]["updated_at"] = expired
                    store._write(payload)
                else:
                    with store._transaction() as cursor:
                        store._execute(cursor, "UPDATE push_subscriptions SET updated_at = ? WHERE endpoint = ?",
                                       (expired, subscription("two")["endpoint"]))
                store.upsert(subscription("three"), SCOPE, OWNER, CONSENT_VERSION)
                self.assertEqual(len(store.subscriptions()), 2)

    def test_sqlite_migration_is_idempotent_and_legacy_claim_needs_matching_keys(self):
        path = self.root / "legacy.sqlite3"
        item = subscription()
        with sqlite3.connect(path) as connection:
            connection.execute("""
                CREATE TABLE push_subscriptions (
                    endpoint TEXT PRIMARY KEY, p256dh TEXT NOT NULL, auth TEXT NOT NULL,
                    scope_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )
            """)
            connection.execute("INSERT INTO push_subscriptions VALUES (?, ?, ?, ?, ?, ?)",
                               (item["endpoint"], item["keys"]["p256dh"], item["keys"]["auth"],
                                json.dumps(SCOPE), "legacy-created", datetime.now(timezone.utc).isoformat()))
        store = SQLitePushSubscriptionStore(path)
        store.save_scope_state("legacy", {"known_ids": ["a"], "notified_ids": ["a"]})
        store = SQLitePushSubscriptionStore(path)
        self.assertEqual(store.scope_state("legacy")["known_ids"], ["a"])
        self.assertEqual(len(store.subscriptions()), 1)
        self.assertIsNone(store.subscriptions()[0]["owner_hash"])
        self.assertEqual(store.legacy_reconsent_count(), 1)
        self.assertFalse(store.owner_status(OWNER)["subscribed"])
        with self.assertRaises(PushSubscriptionError):
            store.upsert(subscription(scalar=2), SCOPE, OWNER, CONSENT_VERSION)
        store.upsert(item, SCOPE, OWNER, CONSENT_VERSION)
        self.assertEqual(store.subscriptions()[0]["created_at"], "legacy-created")
        self.assertIsNone(store.subscriptions()[0]["delivery_state"])
        self.assertEqual(store.legacy_reconsent_count(), 0)

    def test_json_legacy_is_preserved_but_cannot_send_without_consent(self):
        path = self.root / "legacy.json"
        item = subscription()
        store = PushSubscriptionStore(path)
        store._write({"subscriptions": {item["endpoint"]: {
            **item, "scope": SCOPE, "updated_at": datetime.now(timezone.utc).isoformat(),
        }}, "scopes": {"legacy": {"known_ids": ["a"]}}})
        self.assertEqual(len(store.subscriptions()), 1)
        self.assertEqual(store.legacy_reconsent_count(), 1)
        with self.assertRaises(PushSubscriptionError):
            store.upsert(subscription(scalar=2), SCOPE, OWNER, CONSENT_VERSION)
        store.upsert(item, SCOPE, OWNER, CONSENT_VERSION)
        self.assertEqual(store.scope_state("legacy"), {"known_ids": ["a"]})
        self.assertTrue(store.owner_status(OWNER)["subscribed"])
        self.assertEqual(store.legacy_reconsent_count(), 0)

    def test_sqlite_connections_close_after_success_and_exception(self):
        connections = []

        class Connection(sqlite3.Connection):
            closed = False

            def close(self):
                self.closed = True
                super().close()

        class Store(SQLitePushSubscriptionStore):
            def _connect(inner):
                connection = sqlite3.connect(inner.path, factory=Connection)
                connections.append(connection)
                return connection

        store = Store(self.root / "closed.sqlite3")
        store.upsert(subscription(), SCOPE, OWNER, CONSENT_VERSION)
        with self.assertRaises(PushSubscriptionError):
            store.upsert(subscription(), SCOPE, OTHER, CONSENT_VERSION)
        store.owner_status(OWNER)
        self.assertTrue(connections)
        self.assertTrue(all(connection.closed for connection in connections))

    def test_postgres_migration_and_lock_use_contexts_and_idempotent_sql(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (True,)
        with patch.object(PostgresPushSubscriptionStore, "_connect", return_value=connection):
            store = PostgresPushSubscriptionStore("postgresql://local/mock")
            store._initialize()
            with store.scan_lock() as acquired:
                self.assertTrue(acquired)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertEqual(sum("ADD COLUMN IF NOT EXISTS" in sql for sql in statements), 6)
        self.assertTrue(any("pg_try_advisory_lock" in sql for sql in statements))
        self.assertTrue(any("pg_advisory_unlock" in sql for sql in statements))
        self.assertEqual(connection.__exit__.call_count, 3)
        self.assertFalse(any("PRAGMA" in sql for sql in statements))


class ScannerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.catalog = SimpleNamespace(
            sources=[SimpleNamespace(id="school", enabled=True, collection_root=True,
                                     collection_id="school", feed_group="notices", source_group="school")],
            get_many=MagicMock()
        )
        settings = SimpleNamespace(
            web_push_public_key="public", web_push_private_key="private",
            web_push_contact="mailto:local@example.test",
            web_push_database_path=Path(self.directory.name) / "push.sqlite3",
        )
        self.notifier = WebPushNotifier(self.catalog, settings)
        self.notifier._send = MagicMock()

    def tearDown(self):
        self.directory.cleanup()

    def subscribe(self, name="one", owner=OWNER):
        self.notifier.subscribe(subscription(name), SCOPE, owner, CONSENT_VERSION)

    def scan(self, *ids, warnings=()):
        self.catalog.get_many.return_value = [result(*ids, warnings=warnings)]
        self.notifier.scan_subscriptions()

    def test_effective_scope_matches_collection_feed_and_group_without_scanning(self):
        club = SimpleNamespace(id="club", enabled=True, collection_root=False,
                               collection_id="school", feed_group="notices", source_group="after_school")
        events = SimpleNamespace(id="events", enabled=True, collection_root=False,
                                 collection_id="school", feed_group="events", source_group="municipality")
        unrelated = SimpleNamespace(id="unrelated", enabled=True, collection_root=True,
                                    collection_id="other", feed_group="events", source_group="after_school")
        self.catalog.sources.extend([club, events, unrelated])
        self.notifier.subscribe(subscription(), {**SCOPE, "group": "after_school", "grade": "１年"},
                                OWNER, CONSENT_VERSION)
        self.assertEqual(self.notifier.store.subscriptions()[0]["scope"]["grade"], "1年生")
        self.notifier.subscribe(subscription("events"), {**SCOPE, "feed": "events", "group": "municipality"},
                                OWNER, CONSENT_VERSION)
        for scope in (
            {**SCOPE, "feed": "events", "group": "school"},
            {**SCOPE, "feed": "events", "group": "after_school"},
            {**SCOPE, "source_id": "club", "group": "school"},
            {**SCOPE, "grade": "garbage"},
        ):
            with self.subTest(scope=scope), self.assertRaises(PushSubscriptionError):
                self.notifier.subscribe(subscription("invalid"), scope, OWNER, CONSENT_VERSION)
        club.enabled = False
        with self.assertRaises(PushSubscriptionError):
            self.notifier.subscribe(subscription("disabled"), {**SCOPE, "group": "after_school"}, OWNER, CONSENT_VERSION)
        self.catalog.get_many.assert_not_called()
        self.notifier._send.assert_not_called()

    def test_mixed_failure_retries_only_failed_recipient(self):
        self.subscribe()
        self.subscribe("two", OTHER)
        self.scan("old")
        self.notifier._send.assert_not_called()

        def fail_second(record, message):
            if record["endpoint"] == subscription("two")["endpoint"]:
                raise RuntimeError("provider failure")

        self.notifier._send.side_effect = fail_second
        self.scan("old", "new")
        self.assertEqual(self.notifier._send.call_count, 2)
        self.notifier._send.reset_mock(side_effect=True)
        self.scan("old", "new")
        self.notifier._send.assert_called_once()
        self.assertEqual(self.notifier._send.call_args.args[0]["owner_hash"], OTHER)
        self.notifier._send.reset_mock()
        self.scan("old", "new")
        self.notifier._send.assert_not_called()

    def test_disappearing_reappearing_source_does_not_redeliver(self):
        self.subscribe()
        self.scan("old")
        self.scan("old", "new")
        self.notifier._send.assert_called_once()
        self.notifier._send.reset_mock()
        self.scan()
        self.scan("old", "new")
        self.notifier._send.assert_not_called()
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(set(state["accepted_ids"]), {"old", "new"})

    def test_initial_baseline_requires_successful_complete_source(self):
        self.subscribe()
        self.scan("partial", warnings=("one source failed",))
        self.assertIsNone(self.notifier.store.subscriptions()[0]["delivery_state"])
        self.catalog.get_many.return_value = []
        self.notifier.scan_subscriptions()
        self.assertIsNone(self.notifier.store.subscriptions()[0]["delivery_state"])
        self.catalog.get_many.side_effect = CatalogError("source unavailable")
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_not_called()
        self.catalog.get_many.side_effect = None
        self.scan("partial", "old")
        self.notifier._send.assert_not_called()
        self.scan("partial", "old", "new", warnings=("partial",))
        self.notifier._send.assert_not_called()
        self.scan("partial", "old", "new")
        self.notifier._send.assert_called_once()

    def test_new_subscriber_is_not_blasted_historical_items(self):
        self.subscribe()
        self.scan("old")
        self.scan("old", "recent")
        self.subscribe("two", OTHER)
        self.notifier._send.reset_mock()
        self.scan("old", "recent")
        self.notifier._send.assert_not_called()
        self.scan("old", "recent", "new")
        self.assertEqual(self.notifier._send.call_count, 2)

    def test_newly_covered_source_is_baselined_without_historical_blast(self):
        self.subscribe()
        self.scan("old")
        self.catalog.get_many.return_value = [result("old"), result("archive", source_id="library")]
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_not_called()
        self.catalog.get_many.return_value = [result("old"), result("archive", "fresh", source_id="library")]
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_called_once()

    def test_facility_reference_changes_do_not_send_notifications(self):
        self.subscribe()
        self.scan("old")
        original = result("old")
        original.notices.append(SimpleNamespace(id="facility", coverage_kind="reference"))
        self.catalog.get_many.return_value = [original]
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_not_called()

    def test_legacy_migration_preserves_pending_until_provider_acceptance(self):
        self.subscribe()
        record = self.notifier.store.subscriptions()[0]
        self.notifier.store.save_delivery_state(record, {"known_ids": ["old", "pending"], "accepted_ids": ["old"]})
        self.notifier._send.side_effect = RuntimeError("provider failure")
        with patch.object(self.notifier, "_message", wraps=self.notifier._message) as message:
            self.scan("old", "pending", "unseen-archive")
            self.assertEqual([item["id"] for item in message.call_args.args[0]], ["pending"])
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(set(state["known_ids"]), {"old", "pending", "unseen-archive"})
        self.assertEqual(set(state["accepted_ids"]), {"old", "unseen-archive"})
        self.assertEqual(state["source_ids"], ["school"])
        self.notifier._send.reset_mock(side_effect=True)
        self.scan("old", "pending", "unseen-archive")
        self.notifier._send.assert_called_once()
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertIn("pending", state["accepted_ids"])
        self.notifier._send.reset_mock()
        self.scan("old", "pending", "unseen-archive")
        self.notifier._send.assert_not_called()

    def test_migration_keeps_pending_from_failed_source_until_it_recovers(self):
        self.subscribe()
        record = self.notifier.store.subscriptions()[0]
        self.notifier.store.save_delivery_state(record, {"known_ids": ["old", "library-pending"], "accepted_ids": ["old"]})
        self.catalog.get_many.return_value = [result("old"), result("library-pending", source_id="library", warnings=("failed",))]
        self.notifier.scan_subscriptions()
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(state["source_ids"], ["school"])
        self.assertEqual(state["accepted_ids"], ["old"])
        self.assertIn("library-pending", state["known_ids"])
        self.notifier._send.assert_not_called()
        self.catalog.get_many.return_value = [result("old"), result("library-pending", "library-archive", source_id="library")]
        with patch.object(self.notifier, "_message", wraps=self.notifier._message) as message:
            self.notifier.scan_subscriptions()
            self.assertEqual([item["id"] for item in message.call_args.args[0]], ["library-pending"])
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(set(state["accepted_ids"]), {"old", "library-pending", "library-archive"})
        self.assertEqual(state["source_ids"], ["library", "school"])

    def test_failed_sources_do_not_block_healthy_sources_or_advance_their_ledger(self):
        self.subscribe()
        self.catalog.get_many.return_value = [result("old"), result("library-old", source_id="library")]
        self.notifier.scan_subscriptions()
        self.catalog.get_many.return_value = [
            result("old", "new-z", "new-a"),
            result("library-old", "library-new", source_id="library", warnings=("partial",)),
        ]
        with patch.object(self.notifier, "_message", wraps=self.notifier._message) as message:
            self.notifier.scan_subscriptions()
            self.assertEqual([item["id"] for item in message.call_args.args[0]], ["new-z", "new-a"])
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertNotIn("library-new", state["known_ids"])
        self.assertNotIn("library-new", state["accepted_ids"])
        self.assertIn("library-old", state["accepted_ids"])
        self.notifier._send.reset_mock()
        self.catalog.get_many.return_value[1] = result("library-old", "library-new", source_id="library")
        with patch.object(self.notifier, "_message", wraps=self.notifier._message) as message:
            self.notifier.scan_subscriptions()
            self.assertEqual([item["id"] for item in message.call_args.args[0]], ["library-new"])
        self.notifier._send.assert_called_once()

    def test_failed_reference_sources_are_ignored_for_baseline_and_delivery(self):
        self.subscribe()
        reference = result("facility", source_id="facility", coverage_kind="reference", warnings=("failed",))
        self.catalog.get_many.return_value = [reference]
        self.notifier.scan_subscriptions()
        self.assertIsNone(self.notifier.store.subscriptions()[0]["delivery_state"])
        self.catalog.get_many.return_value = [result("old"), reference]
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_not_called()
        self.catalog.get_many.return_value = [result("old", "new"), reference]
        self.notifier.scan_subscriptions()
        self.notifier._send.assert_called_once()
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(state["source_ids"], ["school"])
        self.assertEqual(set(state["known_ids"]), {"old", "new"})

    def test_successful_empty_sources_baseline_before_their_first_notice(self):
        self.subscribe()
        self.catalog.get_many.return_value = [result(), result(source_id="library")]
        self.notifier.scan_subscriptions()
        state = self.notifier.store.subscriptions()[0]["delivery_state"]
        self.assertEqual(state, {"known_ids": [], "accepted_ids": [], "source_ids": ["library", "school"]})
        self.catalog.get_many.return_value = [result("first-school"), result("first-library", source_id="library")]
        with patch.object(self.notifier, "_message", wraps=self.notifier._message) as message:
            self.notifier.scan_subscriptions()
            self.assertEqual([item["id"] for item in message.call_args.args[0]], ["first-school", "first-library"])
        self.notifier._send.assert_called_once()

    def test_refreshing_and_original_only_sources_fail_closed_without_warnings(self):
        self.subscribe()
        for change in ({"refreshing": True}, {"extraction_status": "original_only"}):
            with self.subTest(change=change):
                self.catalog.get_many.return_value = [result("partial", **change)]
                self.notifier.scan_subscriptions()
                self.assertIsNone(self.notifier.store.subscriptions()[0]["delivery_state"])
        self.scan("old")
        for index, change in enumerate(({"refreshing": True}, {"extraction_status": "original_only"})):
            with self.subTest(change=change):
                self.catalog.get_many.return_value = [result("old", f"healthy-{index}"), result("partial", source_id="library", **change)]
                self.notifier.scan_subscriptions()
                state = self.notifier.store.subscriptions()[0]["delivery_state"]
                self.assertNotIn("library", state["source_ids"])
                self.assertNotIn("partial", state["known_ids"])
        self.assertEqual(self.notifier._send.call_count, 2)

    def test_corrupt_delivery_ledgers_are_not_sent_or_rewritten(self):
        self.subscribe()
        base = {"known_ids": ["old"], "accepted_ids": ["old"], "source_ids": ["school"]}
        malformed = [[], "invalid", {}, {**base, "known_ids": "old"}, {**base, "accepted_ids": None},
                     {**base, "known_ids": [{}]}, {**base, "accepted_ids": ["unknown"]},
                     {**base, "source_ids": "school"}, {**base, "source_ids": [{}]},
                     {**base, "source_ids": [1]}, {**base, "source_ids": [""]}]
        for state in malformed:
            with self.subTest(state=state):
                record = self.notifier.store.subscriptions()[0]
                self.notifier.store.save_delivery_state(record, state)
                self.scan("old", "new")
                self.assertEqual(self.notifier.store.subscriptions()[0]["delivery_state"], state)
                self.notifier._send.assert_not_called()

    def test_legacy_and_expired_consent_never_send_or_fetch(self):
        self.subscribe()
        with self.notifier.store._transaction() as cursor:
            self.notifier.store._execute(cursor, "UPDATE push_subscriptions SET consent_version = NULL, owner_hash = NULL")
        self.scan("old", "new")
        self.catalog.get_many.assert_not_called()
        self.notifier._send.assert_not_called()
        self.subscribe()
        with self.notifier.store._transaction() as cursor:
            self.notifier.store._execute(cursor, "UPDATE push_subscriptions SET updated_at = ?",
                                        ((datetime.now(timezone.utc) - timedelta(days=181)).isoformat(),))
        self.scan("old", "new")
        self.catalog.get_many.assert_not_called()
        self.assertEqual(self.notifier.store.subscriptions(), [])

    def test_gone_provider_removes_recipient_and_ledger(self):
        self.subscribe()
        self.scan("old")
        error = RuntimeError("gone")
        error.response = SimpleNamespace(status_code=410)
        self.notifier._send.side_effect = error
        self.scan("old", "new")
        self.assertEqual(self.notifier.store.subscriptions(), [])

    def test_deletion_during_scan_prevents_later_recipient_send(self):
        self.subscribe()
        self.subscribe("two", OTHER)
        self.scan("old")

        def delete_other(record, message):
            self.notifier.delete_owner(OTHER)

        self.notifier._send.side_effect = delete_other
        self.scan("old", "new")
        self.notifier._send.assert_called_once()
        self.assertEqual(self.notifier._send.call_args.args[0]["owner_hash"], OWNER)

    def test_send_rejects_deleted_snapshot(self):
        self.subscribe()
        record = self.notifier.store.subscriptions()[0]
        self.notifier.delete_owner(OWNER)
        with patch("pywebpush.webpush") as webpush:
            with self.assertRaises(PushSubscriptionError):
                WebPushNotifier._send(self.notifier, record, {})
            webpush.assert_not_called()

    def test_peer_scanner_lock_suppresses_source_fetch(self):
        self.subscribe()
        with self.notifier.store.scan_lock():
            self.scan("old")
        self.catalog.get_many.assert_not_called()

    def test_lockscreen_is_generic_and_public_contract_has_no_counts(self):
        self.subscribe()
        message = self.notifier._message([{"title": "Private", "source_name": "School", "source_id": "school"}], 10)
        self.assertEqual(message["url"], "/")
        self.assertNotIn("Private", json.dumps(message))
        self.assertNotIn("school", json.dumps(message))
        self.assertEqual(self.notifier.config()["consent_version"], CONSENT_VERSION)
        self.assertEqual(self.notifier.config()["retention_days"], 180)
        self.assertFalse(any("count" in key for key in self.notifier.config()))
        self.assertEqual(len(self.notifier.export_owner(OWNER)["subscriptions"]), 1)
        self.assertEqual(self.notifier.delete_owner(OWNER), 1)
        self.assertEqual(self.notifier.owner_status(OWNER), {"subscribed": False, "scopes": []})

    def test_environment_kill_switch_keeps_owner_privacy_operations_available(self):
        self.subscribe()
        self.assertTrue(self.notifier.sending_enabled)
        record = self.notifier.store.subscriptions()[0]
        with patch.dict("os.environ", {"WEB_PUSH_ENABLED": "false"}):
            self.assertFalse(self.notifier.config()["enabled"])
            self.assertFalse(self.notifier.config()["sending_enabled"])
            with self.assertRaises(PushSubscriptionError):
                self.subscribe("two")
            self.scan("old", "new")
            self.catalog.get_many.assert_not_called()
            with self.assertRaises(RuntimeError):
                WebPushNotifier._send(self.notifier, record, {})
            self.assertTrue(self.notifier.owner_status(OWNER)["subscribed"])
            self.assertEqual(len(self.notifier.export_owner(OWNER)["subscriptions"]), 1)
            self.assertEqual(self.notifier.delete_owner(OWNER), 1)

    def test_send_revalidates_stored_endpoint_consent_and_keys(self):
        self.subscribe()
        record = self.notifier.store.subscriptions()[0]
        for change in (
            {"endpoint": "https://127.0.0.1/x"}, {"keys": {"p256dh": "bad", "auth": "bad"}},
            {"owner_hash": None}, {"consent_version": "old"},
        ):
            with patch("pywebpush.webpush") as webpush:
                with self.assertRaises(PushSubscriptionError):
                    WebPushNotifier._send(self.notifier, {**record, **change}, {})
                webpush.assert_not_called()

    def test_http_redirects_disabled_timeout_enforced_and_3xx_not_accepted(self):
        self.subscribe()
        record = self.notifier.store.subscriptions()[0]
        response = SimpleNamespace(status_code=302, headers={"Location": "http://127.0.0.1/private"})
        sessions = []

        def webpush(**kwargs):
            self.assertEqual(kwargs["timeout"], PUSH_TIMEOUT_SECONDS)
            session = kwargs["requests_session"]
            sessions.append(session)
            self.assertFalse(session.trust_env)
            return session.post(kwargs["subscription_info"]["endpoint"], allow_redirects=True, timeout=None)

        with patch("pywebpush.webpush", side_effect=webpush), patch(
            "requests.sessions.Session.request", return_value=response
        ) as request, patch("requests.sessions.Session.close") as close:
            with self.assertRaises(RuntimeError):
                WebPushNotifier._send(self.notifier, record, {})
            self.assertEqual(request.call_count, 1)
            self.assertFalse(request.call_args.kwargs["allow_redirects"])
            self.assertEqual(request.call_args.kwargs["timeout"], PUSH_TIMEOUT_SECONDS)
            close.assert_called_once()
        self.assertEqual(len(sessions), 1)


if __name__ == "__main__":
    unittest.main()
