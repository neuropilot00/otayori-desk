from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier.catalog_sync import accept_snapshot, snapshot_payload
from sakurano_line_notifier.catalog_watchdog import CatalogDispatchWatchdog
from sakurano_line_notifier.web_catalog import CatalogNotice, CatalogResult, CatalogService
from sakurano_line_notifier.web_server import BetaRequestHandler


class CollectionRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = root / "sources.json"
        registry.write_text(json.dumps({"sources": [{"id": "city", "name": "市", "ward": "市", "level": "小学校",
            "page_url": "https://city.example/notice", "mode": "html_page", "grades": ["全学年"],
            "collection_driver": "scheduled"}]}))
        with patch.dict("os.environ", {"WEB_SCHEDULED_COLLECTION": "true", "CATALOG_DISPATCH_TOKEN": "test-recovery-token-" + "x" * 32}):
            self.catalog = CatalogService(SimpleNamespace(web_catalog_cache_path=root / "cache.sqlite3"), registry)
        source = self.catalog.sources[0]
        notice = CatalogNotice(id="a" * 20, source_id="city", source_name="市", ward="市", level="小学校", grade="全学年",
            title="お知らせ", kind="document", url="https://city.example/notice", text="公開のお知らせです。",
            content_hash="b" * 64, date_label="更新資料", published_label="", source_group="school", feed_group="notices")
        self.result = CatalogResult(source, "全学年", (datetime.now(timezone.utc) - timedelta(minutes=25)).isoformat(), (notice,), (), 1)
        accept_snapshot(self.catalog, snapshot_payload(self.result))

    def tearDown(self):
        self.catalog.close()
        self.directory.cleanup()

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_proactive_recovery_runs_before_stale_warning_and_never_fakes_import(self, factory):
        factory.return_value.__enter__.return_value.post.return_value.status_code = 204
        self.assertEqual(self.catalog.get_source("city").freshness_status, "fresh")
        self.catalog.get_many = Mock(side_effect=AssertionError("school OCR must not block recovery"))
        self.catalog._scan_source = Mock(side_effect=AssertionError("city requests must stay on the external runner"))
        self.assertEqual(self.catalog._check_collection_recovery(), "dispatched")
        result = self.catalog.get_source("city")
        self.assertTrue(result.refreshing)
        self.assertEqual(result.scanned_at, self.result.scanned_at)
        self.assertEqual(self.catalog._cache_store.load(self.result.source, self.result.grade).scanned_at, self.result.scanned_at)
        self.catalog.get_many.assert_not_called()
        self.catalog._scan_source.assert_not_called()
        newer = replace(self.result, scanned_at=datetime.now(timezone.utc).isoformat())
        self.assertTrue(accept_snapshot(self.catalog, snapshot_payload(newer)))
        self.assertFalse(self.catalog.get_source("city").refreshing)
        self.assertEqual(self.catalog.get_source("city").scanned_at, newer.scanned_at)

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_manual_request_is_nonblocking_coalesced_and_forces_a_fresh_scope(self, factory):
        factory.return_value.__enter__.return_value.post.return_value.status_code = 204
        fresh = replace(self.result, scanned_at=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat())
        accept_snapshot(self.catalog, snapshot_payload(fresh))
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        for _ in range(8):
            self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "queued")
        factory.assert_not_called()
        self.assertTrue(self.catalog._recovery_wake.is_set())
        self.assertEqual(self.catalog._check_collection_recovery(), "dispatched")
        factory.return_value.__enter__.return_value.post.assert_called_once()
        self.assertEqual(self.catalog.get_source("city").scanned_at, fresh.scanned_at)

    def test_disabled_or_stopped_recovery_does_not_claim_a_queued_refresh(self):
        self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "unavailable")
        self.catalog._dispatch_watchdog._token = ""
        self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "disabled")
        self.assertFalse(self.catalog.get_source("city").refreshing)
        self.assertIsNone(self.catalog._scheduled_pending_since)
        status = self.catalog.collection_status()
        self.assertFalse(status["ok"])
        self.assertFalse(status["recovery"]["enabled"])
        self.assertEqual(status["sources"][0]["checked_at"], self.result.scanned_at)

    def test_unknown_or_server_only_scopes_do_not_request_external_jobs(self):
        self.assertEqual(self.catalog.request_scheduled_refresh(["unknown"]), "not_required")
        self.catalog._scheduled_collection = False
        self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "not_required")
        self.assertEqual(self.catalog._check_collection_recovery(), "not_required")

    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_refresh_api_queues_external_collection_but_an_ordinary_get_does_not(self, factory):
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        handler = object.__new__(BetaRequestHandler)
        handler.server = SimpleNamespace(catalog=self.catalog)
        normal = handler._notices_payload({"source_id": ["city"]})
        self.assertFalse(normal["refreshing"])
        self.assertFalse(self.catalog._recovery_wake.is_set())
        refreshed = handler._notices_payload({"source_id": ["city"]}, force_refresh=True)
        self.assertTrue(refreshed["refreshing"])
        self.assertTrue(self.catalog._recovery_wake.is_set())
        self.assertEqual(refreshed["coverage"][0]["checked_at"], self.result.scanned_at)
        self.assertIn("refreshing", refreshed["coverage"][0]["issue_codes"])
        factory.assert_not_called()

    def test_failed_or_throttled_manual_request_stops_polling_without_advancing_time(self):
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        for outcome in ("failed", "cooldown"):
            self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "queued")
            with patch.object(self.catalog._dispatch_watchdog, "check", return_value=outcome):
                self.catalog._check_collection_recovery()
            self.assertFalse(self.catalog.get_source("city").refreshing)
            self.assertEqual(self.catalog.get_source("city").scanned_at, self.result.scanned_at)

    def test_pending_external_refresh_is_bounded_even_if_no_snapshot_arrives(self):
        self.catalog._scheduled_pending_since = datetime.now(timezone.utc)
        self.catalog._scheduled_pending_until = time.monotonic() + 120
        self.catalog._scheduled_request_status = "accepted"
        self.assertTrue(self.catalog.get_source("city").refreshing)
        self.catalog._scheduled_pending_until = time.monotonic() - 1
        self.assertFalse(self.catalog.get_source("city").refreshing)
        self.assertEqual(self.catalog.get_source("city").scanned_at, self.result.scanned_at)

    def test_force_queued_during_an_automatic_dispatch_is_covered_by_that_accepted_job(self):
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        def dispatch(*_, **__):
            self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "queued")
            return "dispatched"
        with patch.object(self.catalog._dispatch_watchdog, "check", side_effect=dispatch):
            self.catalog._check_collection_recovery()
        self.assertFalse(self.catalog._recovery_force)
        self.assertTrue(self.catalog.get_source("city").refreshing)
        with patch.object(self.catalog._dispatch_watchdog, "check", return_value="cooldown"):
            self.catalog._check_collection_recovery()
        self.assertTrue(self.catalog.get_source("city").refreshing)
        self.assertEqual(self.catalog.get_source("city").scanned_at, self.result.scanned_at)

    def test_rejected_refresh_is_exposed_separately_from_cached_snapshot_completeness(self):
        handler = object.__new__(BetaRequestHandler)
        handler.server = SimpleNamespace(catalog=self.catalog)
        for status in ("disabled", "unavailable", "cooldown"):
            with self.subTest(status=status), patch.object(self.catalog, "request_scheduled_refresh", return_value=status):
                response = handler._notices_payload({"source_id": ["city"]}, force_refresh=True)
            self.assertEqual(response["external_refresh_status"], status)
            self.assertTrue(response["refresh_requested"])
            self.assertFalse(response["refreshed"])
            self.assertFalse(response["refreshing"])
            self.assertEqual(response["coverage"][0]["checked_at"], self.result.scanned_at)

    def test_force_queued_during_failed_automatic_dispatch_preserves_the_failure(self):
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        def dispatch(*_, **__):
            self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "queued")
            return "failed"
        with patch.object(self.catalog._dispatch_watchdog, "check", side_effect=dispatch):
            self.catalog._check_collection_recovery()
        self.assertFalse(self.catalog._recovery_force)
        with patch.object(self.catalog._dispatch_watchdog, "check", return_value="cooldown"):
            self.catalog._check_collection_recovery()
        result = self.catalog.get_source("city")
        self.assertEqual(result.refresh_request_status, "failed")
        self.assertFalse(result.refreshing)
        self.assertEqual(result.scanned_at, self.result.scanned_at)

    @patch("sakurano_line_notifier.web_catalog.threading.Thread")
    def test_stop_restart_waits_for_a_live_old_worker_without_reviving_its_cancellation(self, factory):
        alive = [True]
        old = SimpleNamespace(is_alive=lambda: alive[0], join=lambda **_: None)
        self.catalog._recovery_thread = old
        self.catalog.stop_background_refresh()
        self.assertIs(self.catalog._recovery_thread, old)
        self.catalog.start_background_refresh()
        factory.assert_not_called()
        self.assertTrue(self.catalog._refresh_stop.is_set())
        self.assertFalse(self.catalog.collection_status()["recovery"]["running"])
        self.assertEqual(self.catalog.request_scheduled_refresh(["city"]), "unavailable")
        alive[0] = False
        self.catalog.start_background_refresh()
        self.assertEqual(factory.call_count, 2)
        self.assertFalse(self.catalog._refresh_stop.is_set())
        self.assertIsNot(self.catalog._recovery_thread, old)

    def test_independent_timer_starts_even_when_the_school_scan_is_blocked(self):
        scan_started, release_scan, recovered = threading.Event(), threading.Event(), threading.Event()
        def scan(_):
            scan_started.set()
            release_scan.wait(2)
        self.catalog._refresh_loop = scan
        self.catalog._check_collection_recovery = Mock(side_effect=lambda: recovered.set())
        try:
            self.catalog.start_background_refresh()
            self.assertTrue(scan_started.wait(1))
            self.assertTrue(recovered.wait(1))
        finally:
            release_scan.set()

    def test_collection_status_reports_missing_delayed_and_imported_sources_without_fetching(self):
        self.catalog._scan_source = Mock(side_effect=AssertionError("status must be read only"))
        self.catalog._recovery_thread = SimpleNamespace(is_alive=lambda: True, join=lambda **_: None)
        self.assertTrue(self.catalog.collection_status()["ok"])
        old = replace(self.result, scanned_at=(datetime.now(timezone.utc) - timedelta(minutes=100)).isoformat())
        self.catalog._cache.clear()
        self.catalog._cache_store.save(old)
        status = self.catalog.collection_status()
        self.assertFalse(status["ok"])
        self.assertEqual(status["delayed_sources"], 1)
        self.assertEqual(status["sources"][0]["checked_at"], old.scanned_at)
        self.catalog._scan_source.assert_not_called()
        self.assertNotIn(self.catalog._dispatch_watchdog._token, json.dumps(status))

    def test_public_status_endpoint_distinguishes_collection_from_database_readiness(self):
        handler = object.__new__(BetaRequestHandler)
        handler.path = "/api/collection/status"
        handler.server = SimpleNamespace(catalog=self.catalog)
        handler._send_json = Mock()
        self.catalog._dispatch_watchdog._token = ""
        handler.do_GET()
        args, kwargs = handler._send_json.call_args
        self.assertFalse(args[0]["ok"])
        self.assertEqual(kwargs["status"], 503)


class ConcurrentWatchdogTests(unittest.TestCase):
    @patch("sakurano_line_notifier.catalog_watchdog.requests.Session")
    def test_timer_and_manual_request_share_one_dispatch_reservation(self, factory):
        entered, release = threading.Event(), threading.Event()
        reply = Mock(status_code=204)
        def post(*_, **__):
            entered.set()
            self.assertTrue(release.wait(2))
            return reply
        factory.return_value.__enter__.return_value.post.side_effect = post
        with patch.dict("os.environ", {"CATALOG_DISPATCH_TOKEN": "x" * 40}):
            watchdog = CatalogDispatchWatchdog()
        result = SimpleNamespace(source=SimpleNamespace(collection_driver="scheduled"), scanned_at="")
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(watchdog.check, [result])
            try:
                self.assertTrue(entered.wait(1))
                second = pool.submit(watchdog.check, [result], force=True)
                self.assertEqual(second.result(timeout=1), "cooldown")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=1), "dispatched")
        factory.return_value.__enter__.return_value.post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
