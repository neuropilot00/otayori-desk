from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import requests

from sakurano_line_notifier.catalog_watchdog import CatalogDispatchWatchdog


class WatchdogTests(unittest.TestCase):
    def result(self, minutes=60, driver="scheduled"):
        return SimpleNamespace(source=SimpleNamespace(collection_driver=driver), scanned_at=(datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat())

    def watchdog(self, token="x" * 40):
        with patch.dict("os.environ", {"CATALOG_DISPATCH_TOKEN": token}):
            return CatalogDispatchWatchdog()

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_disabled_invalid_fresh_and_server_only_never_call_github(self, factory):
        for token in ("", "short", "x" * 40 + "\n", "あ" * 40):
            self.assertEqual(self.watchdog(token).check([self.result()]), "disabled")
        for results in ([], [self.result(10)], [self.result(driver="server")]):
            self.assertEqual(self.watchdog().check(results), "fresh")
        factory.assert_not_called()

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_delayed_dispatch_is_fixed_origin_bounded_and_never_advances_timestamp(self, factory):
        session = factory.return_value.__enter__.return_value
        session.post.return_value.status_code = 204
        result = self.result()
        original = result.scanned_at
        watchdog = self.watchdog()
        self.assertEqual(watchdog.check([result]), "dispatched")
        self.assertEqual(watchdog.check([result]), "cooldown")
        self.assertEqual(result.scanned_at, original)
        self.assertFalse(session.trust_env)
        args, kwargs = session.post.call_args
        self.assertEqual(args, (watchdog.dispatch_url,))
        self.assertEqual(kwargs["json"], {"ref": "main"})
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], (5, 15))
        session.post.assert_called_once()
        session.post.return_value.close.assert_called_once()

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_missing_snapshot_requests_recovery_and_200_is_accepted(self, factory):
        factory.return_value.__enter__.return_value.post.return_value.status_code = 200
        result = self.result()
        result.scanned_at = ""
        self.assertEqual(self.watchdog().check([result]), "dispatched")

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_auth_http_redirect_and_network_failures_are_redacted_and_throttled(self, factory):
        session = factory.return_value.__enter__.return_value
        for status in (301, 401, 403, 429, 500):
            watchdog = self.watchdog()
            session.post.return_value.status_code = status
            with self.assertLogs("sakurano_line_notifier.catalog_watchdog", level="WARNING") as logs:
                self.assertEqual(watchdog.check([self.result()]), "failed")
            self.assertNotIn("x" * 40, str(logs.output))
            self.assertEqual(watchdog.check([self.result()]), "cooldown")
        session.post.side_effect = requests.Timeout("SECRET_REMOTE_BODY")
        watchdog = self.watchdog()
        with self.assertLogs("sakurano_line_notifier.catalog_watchdog", level="WARNING") as logs:
            self.assertEqual(watchdog.check([self.result()]), "failed")
        self.assertNotIn("SECRET", str(logs.output))
        self.assertEqual(watchdog.check([self.result()]), "cooldown")

    @patch("sakurano_line_notifier.catalog_watchdog.time.monotonic")
    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_cooldown_expires_and_fresh_snapshots_stop_recovery(self, factory, clock):
        factory.return_value.__enter__.return_value.post.return_value.status_code = 204
        clock.return_value = 100
        watchdog = self.watchdog()
        self.assertEqual(watchdog.check([self.result()]), "dispatched")
        clock.return_value = 1900
        self.assertEqual(watchdog.check([self.result()]), "dispatched")
        self.assertEqual(watchdog.check([self.result(1)]), "fresh")
        self.assertEqual(factory.return_value.__enter__.return_value.post.call_count, 2)

    @patch("sakurano_line_notifier.catalog_watchdog.time.monotonic")
    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_invalid_auth_backs_off_six_hours(self, factory, clock):
        factory.return_value.__enter__.return_value.post.return_value.status_code = 403
        clock.return_value = 100
        watchdog = self.watchdog()
        with self.assertLogs("sakurano_line_notifier.catalog_watchdog", level="WARNING"):
            self.assertEqual(watchdog.check([self.result()]), "failed")
        clock.return_value = 1900
        self.assertEqual(watchdog.check([self.result()]), "cooldown")
        clock.return_value = 21700
        factory.return_value.__enter__.return_value.post.return_value.status_code = 204
        self.assertEqual(watchdog.check([self.result()]), "dispatched")


if __name__ == "__main__":
    unittest.main()
