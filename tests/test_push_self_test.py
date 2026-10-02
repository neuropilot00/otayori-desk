from __future__ import annotations

import base64
import json
import tempfile
import traceback
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import WebPushException
from requests.exceptions import Timeout

from sakurano_line_notifier.web_push import (
    CONSENT_VERSION,
    PUSH_TIMEOUT_SECONDS,
    PostgresPushSubscriptionStore,
    PushSubscriptionError,
    PushSubscriptionStore,
    WebPushNotifier,
    scope_key,
)


OWNER = "a" * 64
OTHER = "b" * 64
SCOPE = {"source_id": "private-school", "grade": "1年生", "feed": "notices", "group": "school"}
LEDGER = {"known_ids": ["private-title", "pending"], "accepted_ids": ["private-title"],
          "source_ids": ["private-school"]}


def subscription(name="one", scalar=1):
    point = ec.derive_private_key(scalar, ec.SECP256R1()).public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return {
        "endpoint": f"https://fcm.googleapis.com/fcm/send/{name}",
        "keys": {"p256dh": base64.urlsafe_b64encode(point).decode().rstrip("="),
                 "auth": base64.urlsafe_b64encode(bytes([scalar]) * 16).decode().rstrip("=")},
    }


class PushSelfTestTests(unittest.TestCase):
    store_option = "web_push_state_path"

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict("os.environ", {"WEB_PUSH_ENABLED": "true"}))
        self.provider = self.enterContext(patch("pywebpush.webpush", return_value=SimpleNamespace(status_code=201)))
        # Any unexpected HTTP path fails locally; no test contacts a provider.
        self.transport = self.enterContext(patch(
            "requests.sessions.Session.request", side_effect=AssertionError("unexpected network request")
        ))
        self.catalog = MagicMock()
        settings = SimpleNamespace(
            web_push_public_key="public", web_push_private_key="private",
            web_push_contact="mailto:local@example.test",
            **{self.store_option: Path(directory) / "push-state"},
        )
        self.notifier = WebPushNotifier(self.catalog, settings)
        self.store = self.notifier.store
        self.item = subscription()
        self.store.upsert(self.item, SCOPE, OWNER, CONSENT_VERSION)
        self.record = self.store.subscriptions()[0]
        self.store.save_delivery_state(self.record, LEDGER)
        self.store.save_scope_state(scope_key(SCOPE), {
            "known_ids": ["legacy"], "notified_ids": ["legacy"], "updated_at": 123,
        })

    def snapshot(self):
        # Unlike subscriptions(), this also observes expired rows without purging.
        if isinstance(self.store, PushSubscriptionStore):
            return self.store._read()
        with self.store._transaction() as cursor:
            subscriptions = self.store._execute(
                cursor, "SELECT * FROM push_subscriptions ORDER BY endpoint"
            ).fetchall()
            scopes = self.store._execute(cursor, "SELECT * FROM push_scope_state ORDER BY scope_key").fetchall()
        return subscriptions, scopes

    def alter_record(self, **changes):
        if isinstance(self.store, PushSubscriptionStore):
            payload = self.store._read()
            payload["subscriptions"][self.item["endpoint"]].update(changes)
            self.store._write(payload)
            return
        columns = {"scope": "scope_json", "delivery_state": "delivery_state_json"}
        with self.store._transaction() as cursor:
            for name, value in changes.items():
                self.store._execute(
                    cursor, f"UPDATE push_subscriptions SET {columns.get(name, name)} = ? WHERE endpoint = ?",
                    (json.dumps(value) if name in columns else value, self.item["endpoint"]),
                )

    def assert_rejected(self, owner=OWNER, endpoint=None):
        before = self.snapshot()
        with self.assertRaises(PushSubscriptionError):
            self.notifier.test_subscription(owner, endpoint or self.item["endpoint"])
        self.provider.assert_not_called()
        self.transport.assert_not_called()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.catalog.mock_calls, [])

    def test_only_selected_owned_subscription_gets_generic_labelled_test(self):
        self.store.upsert(subscription("same-owner"), SCOPE, OWNER, CONSENT_VERSION)
        self.store.upsert(subscription("other-owner"), SCOPE, OTHER, CONSENT_VERSION)
        self.store.upsert(subscription("expired"), SCOPE, OTHER, CONSENT_VERSION)
        expired = (datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
        with patch("sakurano_line_notifier.web_push._now", return_value=expired):
            self.store.upsert(subscription("expired"), SCOPE, OTHER, CONSENT_VERSION)
        before = self.snapshot()

        result = self.notifier.test_subscription(OWNER, self.item["endpoint"])

        self.assertEqual(result, {"provider_accepted": True, "delivery_confirmed": False})
        self.provider.assert_called_once()
        call = self.provider.call_args.kwargs
        self.assertEqual(call["subscription_info"], self.item)
        message = json.loads(call["data"])
        self.assertEqual(message, {
            "type": "test", "title": "おたより desk · テスト通知",
            "body": "これは通知の動作確認用テストです。", "url": "/",
        })
        for private in (SCOPE["source_id"], SCOPE["grade"], "private-title", OWNER, self.item["endpoint"]):
            self.assertNotIn(private, call["data"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.catalog.mock_calls, [])
        self.transport.assert_not_called()

    def test_new_subscription_does_not_get_a_baseline(self):
        self.store.upsert(subscription("fresh"), SCOPE, OWNER, CONSENT_VERSION)
        before = self.snapshot()
        self.notifier.test_subscription(OWNER, subscription("fresh")["endpoint"])
        self.assertEqual(self.snapshot(), before)
        fresh = self.store.subscription_for_owner(OWNER, subscription("fresh")["endpoint"])
        self.assertIsNone(fresh["delivery_state"])

    def test_unknown_and_other_owner_reject_without_enrollment(self):
        self.assert_rejected(endpoint=subscription("unknown")["endpoint"])
        self.assert_rejected(owner=OTHER)

    def test_invalid_owner_and_endpoint_reject(self):
        for owner in (None, "", "raw-browser-cookie", "A" * 64):
            with self.subTest(owner=owner):
                self.assert_rejected(owner=owner)
        for endpoint in ("https://127.0.0.1/private", "https://example.test/push", "https://fcm.googleapis.com:8443/x"):
            with self.subTest(endpoint=endpoint):
                self.assert_rejected(endpoint=endpoint)

    def test_inactive_consent_or_date_reject_without_retention_cleanup(self):
        expired = (datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
        for changes in (
            {"owner_hash": None}, {"consent_version": None}, {"consent_version": "old"},
            {"updated_at": expired}, {"updated_at": "unknown"}, {"updated_at": "2026-10-01T00:00:00"},
        ):
            with self.subTest(changes=changes):
                self.alter_record(**changes)
                self.assert_rejected()
                self.alter_record(**{name: self.record[name] for name in changes})

    def test_disabled_or_missing_configuration_reject(self):
        with patch.dict("os.environ", {"WEB_PUSH_ENABLED": "false"}):
            self.assert_rejected()
        for name in ("public_key", "private_key", "contact", "store"):
            with self.subTest(missing=name), patch.object(self.notifier, name, None):
                self.assert_rejected()

    def assert_race_rejected(self, mutate):
        lookup = self.store.subscription_for_owner
        after_race = []

        def changed(owner, endpoint):
            record = lookup(owner, endpoint)
            mutate()
            after_race.append(self.snapshot())
            return record

        with patch.object(self.store, "subscription_for_owner", side_effect=changed):
            with self.assertRaises(PushSubscriptionError):
                self.notifier.test_subscription(OWNER, self.item["endpoint"])
        self.provider.assert_not_called()
        self.assertEqual(self.snapshot(), after_race[0])

    def test_deletion_between_lookup_and_send_rejects_without_recreation(self):
        self.assert_race_rejected(lambda: self.store.delete_owner(OWNER))

    def test_renewal_between_lookup_and_send_rejects_stale_keys(self):
        self.assert_race_rejected(lambda: self.store.upsert(subscription(scalar=2), SCOPE, OWNER, CONSENT_VERSION))

    def test_scope_change_between_lookup_and_send_rejects(self):
        self.assert_race_rejected(lambda: self.alter_record(scope={**SCOPE, "grade": "2年生"}))

    def test_owner_change_between_lookup_and_send_rejects(self):
        self.assert_race_rejected(lambda: self.alter_record(owner_hash=OTHER))

    def test_consent_revocation_between_lookup_and_send_rejects(self):
        self.assert_race_rejected(lambda: self.alter_record(consent_version="old"))

    def test_expiration_between_lookup_and_send_rejects(self):
        self.assert_race_rejected(lambda: self.alter_record(
            updated_at=(datetime.now(timezone.utc) - timedelta(days=181)).isoformat()
        ))

    def test_kill_switch_between_lookup_and_send_rejects(self):
        self.assert_race_rejected(lambda: self.enterContext(patch.dict("os.environ", {"WEB_PUSH_ENABLED": "false"})))

    def test_only_2xx_responses_report_provider_acceptance(self):
        before = self.snapshot()
        for status in (200, 201, 202, 204, 299, 199, 300, 302, 404, 410, 429, 500):
            with self.subTest(status=status):
                self.provider.reset_mock()
                self.provider.return_value = SimpleNamespace(status_code=status)
                if 200 <= status < 300:
                    self.assertEqual(self.notifier.test_subscription(OWNER, self.item["endpoint"]),
                                     {"provider_accepted": True, "delivery_confirmed": False})
                else:
                    with self.assertRaisesRegex(PushSubscriptionError, "push test acceptance could not be confirmed"):
                        self.notifier.test_subscription(OWNER, self.item["endpoint"])
                self.provider.assert_called_once()
                self.assertEqual(self.snapshot(), before)

    def test_provider_exceptions_are_sanitized_without_changing_ledgers(self):
        before = self.snapshot()
        secret = self.item["endpoint"] + " private-key=" + self.item["keys"]["auth"]
        for error in (Timeout(secret), RuntimeError(secret),
                      WebPushException(secret, response=SimpleNamespace(status_code=410)),
                      PushSubscriptionError(secret)):
            with self.subTest(kind=type(error).__name__):
                self.provider.reset_mock()
                self.provider.side_effect = error
                try:
                    self.notifier.test_subscription(OWNER, self.item["endpoint"])
                except PushSubscriptionError as exc:
                    self.assertEqual(str(exc), "push test acceptance could not be confirmed; please retry later")
                    self.assertNotIn(secret, "".join(traceback.format_exception(exc)))
                    self.assertIsNone(exc.__cause__)
                else:
                    self.fail("provider exception must not be reported as acceptance")
                self.provider.assert_called_once()
                self.assertEqual(self.snapshot(), before)

    def test_renewal_during_provider_failure_preserves_replacement(self):
        after_race = []

        def fail(**kwargs):
            self.store.upsert(subscription(scalar=2), SCOPE, OWNER, CONSENT_VERSION)
            after_race.append(self.snapshot())
            raise WebPushException("gone", response=SimpleNamespace(status_code=410))

        self.provider.side_effect = fail
        with self.assertRaises(PushSubscriptionError):
            self.notifier.test_subscription(OWNER, self.item["endpoint"])
        self.provider.assert_called_once()
        self.assertEqual(self.snapshot(), after_race[0])

    def test_deletion_during_provider_acceptance_cannot_confirm_device_or_recreate(self):
        after_race = []

        def accept(**kwargs):
            self.store.delete_owner(OWNER)
            after_race.append(self.snapshot())
            return SimpleNamespace(status_code=201)

        self.provider.side_effect = accept
        self.assertEqual(self.notifier.test_subscription(OWNER, self.item["endpoint"]),
                         {"provider_accepted": True, "delivery_confirmed": False})
        self.assertEqual(self.snapshot(), after_race[0])

    def test_provider_session_keeps_timeouts_redirect_and_proxy_guards(self):
        def send(**kwargs):
            self.assertEqual(kwargs["timeout"], PUSH_TIMEOUT_SECONDS)
            session = kwargs["requests_session"]
            self.assertFalse(session.trust_env)
            return session.post(kwargs["subscription_info"]["endpoint"], allow_redirects=True, timeout=None)

        self.provider.side_effect = send
        self.transport.side_effect = None
        self.transport.return_value = SimpleNamespace(status_code=201)
        with patch("requests.sessions.Session.close") as close:
            self.notifier.test_subscription(OWNER, self.item["endpoint"])
            close.assert_called_once()
        self.transport.assert_called_once()
        self.assertFalse(self.transport.call_args.kwargs["allow_redirects"])
        self.assertEqual(self.transport.call_args.kwargs["timeout"], PUSH_TIMEOUT_SECONDS)

    def test_provider_session_revalidates_outbound_url(self):
        self.provider.side_effect = lambda **kwargs: kwargs["requests_session"].post("https://127.0.0.1/private")
        before = self.snapshot()
        with self.assertRaises(PushSubscriptionError):
            self.notifier.test_subscription(OWNER, self.item["endpoint"])
        self.transport.assert_not_called()
        self.assertEqual(self.snapshot(), before)


class SQLitePushSelfTestTests(PushSelfTestTests):
    store_option = "web_push_database_path"


class PostgresPushSelfTestLookupTests(unittest.TestCase):
    def test_lookup_uses_owner_and_endpoint_without_retention_writes(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = connection.cursor.return_value.__enter__.return_value
        item = subscription()
        now = datetime.now(timezone.utc).isoformat()
        row = (item["endpoint"], item["keys"]["p256dh"], item["keys"]["auth"],
               json.dumps(SCOPE), now, now, OWNER, CONSENT_VERSION, json.dumps(LEDGER))
        with patch.object(PostgresPushSubscriptionStore, "_connect", return_value=connection):
            store = PostgresPushSubscriptionStore("postgresql://local/mock")
            cursor.reset_mock()
            cursor.fetchone.return_value = row
            record = store.subscription_for_owner(OWNER, item["endpoint"])
            self.assertEqual(record["delivery_state"], LEDGER)
            cursor.execute.assert_called_once()
            sql, params = cursor.execute.call_args.args
            self.assertTrue(sql.startswith("SELECT "))
            self.assertIn("WHERE endpoint = %s AND owner_hash = %s", sql)
            self.assertEqual(params, (item["endpoint"], OWNER))
            cursor.fetchone.return_value = None
            self.assertIsNone(store.subscription_for_owner(OTHER, item["endpoint"]))


if __name__ == "__main__":
    unittest.main()
