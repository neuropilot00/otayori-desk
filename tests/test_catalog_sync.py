from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier.catalog_sync import accept_snapshot, snapshot_payload
from sakurano_line_notifier.web_catalog import CatalogError, CatalogNotice, CatalogResult, CatalogService
from sakurano_line_notifier.web_server import BetaRequestHandler, _BetaHTTPServer


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        registry = self.root / "sources.json"
        registry.write_text(json.dumps({"sources": [{"id": "city", "name": "市役所", "ward": "市", "level": "小学校", "page_url": "https://city.example/notice", "mode": "html_page", "grades": ["全学年"], "collection_driver": "scheduled"}]}))
        settings = SimpleNamespace(web_catalog_cache_path=self.root / "cache.sqlite3")
        with patch.dict("os.environ", {"WEB_SCHEDULED_COLLECTION": "true"}):
            self.catalog = CatalogService(settings, registry)
        self.source = self.catalog.sources[0]
        self.notice = CatalogNotice(id="a" * 20, source_id="city", source_name="市役所", ward="市", level="小学校", grade="全学年", title="お知らせ", kind="document", url="https://city.example/notice", text="公開のお知らせです。", content_hash="b" * 64, date_label="更新資料", published_label="", source_group="municipality", feed_group="notices")
        self.result = CatalogResult(self.source, "全学年", datetime.now(timezone.utc).isoformat(), (self.notice,), (), 1)

    def tearDown(self):
        self.catalog.close()
        self.directory.cleanup()

    def test_valid_snapshot_is_durable_and_idempotent(self):
        payload = snapshot_payload(self.result)
        self.assertTrue(accept_snapshot(self.catalog, payload))
        self.assertFalse(accept_snapshot(self.catalog, payload))
        self.assertEqual(self.catalog._cache_store.load(self.source, "全学年").notices[0].text, self.notice.text)

    def test_after_school_snapshot_type_is_derived_from_reviewed_registry(self):
        source = replace(self.source, source_group="after_school", content_kind="gakudo_admissions", coverage_kind="reference")
        self.catalog.sources = [source]
        payload = snapshot_payload(replace(self.result, source=source))
        payload["notices"][0]["kind"] = "gakudo_daily"
        payload["notices"][0]["coverage_kind"] = "notices"
        self.assertTrue(accept_snapshot(self.catalog, payload))
        notice = self.catalog._cache_store.load(source, "全学年").notices[0]
        self.assertEqual(notice.kind, "gakudo_admissions")
        self.assertEqual(notice.coverage_kind, "reference")

    def test_older_snapshot_cannot_replace_current_content(self):
        accept_snapshot(self.catalog, snapshot_payload(self.result))
        older = replace(self.result, scanned_at=(datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat())
        self.assertFalse(accept_snapshot(self.catalog, snapshot_payload(older)))
        self.assertEqual(self.catalog.get_source("city", refresh=True).scanned_at, self.result.scanned_at)

    def test_scheduled_sources_never_retry_from_web_server_even_on_refresh(self):
        self.catalog._scan_source = Mock(side_effect=AssertionError("network not allowed here"))
        self.assertTrue(self.catalog.get_source("city", refresh=True).warnings)
        accept_snapshot(self.catalog, snapshot_payload(self.result))
        self.assertFalse(self.catalog.get_source("city", refresh=True).warnings)
        self.catalog._scan_source.assert_not_called()

    def test_stale_scheduled_snapshot_keeps_original_timestamp_and_warns(self):
        stale = replace(self.result, scanned_at=(datetime.now(timezone.utc) - timedelta(minutes=100)).isoformat())
        accept_snapshot(self.catalog, snapshot_payload(stale))
        result = self.catalog.get_many(source_id="city")[0]
        self.assertTrue(result.warnings)
        self.assertEqual(result.scanned_at, stale.scanned_at)
        self.assertEqual(result.coverage()["freshness_status"], "stale")
        self.assertEqual(result.coverage()["issue_codes"], ["stale"])

    def test_initial_scheduled_wait_is_not_an_extraction_failure(self):
        coverage = self.catalog.get_source("city").coverage()
        self.assertEqual(coverage["freshness_status"], "pending")
        self.assertEqual(coverage["issue_codes"], [])
        self.assertEqual(coverage["checked_at"], "")

    def test_background_refresh_checks_watchdog_only_in_scheduled_mode(self):
        self.catalog.get_many = Mock(return_value=[self.result])
        self.catalog._dispatch_watchdog.check = Mock()
        with patch.object(self.catalog._refresh_stop, "wait", return_value=True):
            self.catalog._refresh_loop(900)
        self.catalog._dispatch_watchdog.check.assert_called_once_with([self.result])
        self.catalog._dispatch_watchdog.check.reset_mock()
        self.catalog._scheduled_collection = False
        with patch.object(self.catalog._refresh_stop, "wait", return_value=True):
            self.catalog._refresh_loop(900)
        self.catalog._dispatch_watchdog.check.assert_not_called()

    def test_coverage_distinguishes_archives_unreadable_pdfs_and_retrieval_errors(self):
        self.assertEqual(self.result.coverage()["issue_codes"], [])
        limited = replace(self.result, limit_reached=True, discovered_count=100)
        self.assertEqual(limited.coverage()["issue_codes"], ["limit"])
        self.assertEqual(limited.coverage()["status"], "checked")
        unreadable = replace(limited, notices=(replace(self.notice, extraction_status="original_only"),), warnings=("OCR failed",))
        self.assertEqual(unreadable.coverage()["issue_codes"], ["extraction", "limit"])
        self.assertEqual(unreadable.coverage()["readable_count"], 0)
        self.assertEqual(replace(self.result, warnings=("a linked page failed",)).coverage()["issue_codes"], ["collection"])
        self.assertEqual(replace(self.result, notices=(), scanned_at="", warnings=("failed",)).coverage()["issue_codes"], ["unavailable"])
        self.assertEqual(replace(self.result, refreshing=True, warnings=("checking",)).coverage()["issue_codes"], ["refreshing"])

    def test_failed_rescan_retains_only_readable_previous_body_as_stale(self):
        accept_snapshot(self.catalog, snapshot_payload(self.result))
        self.catalog._scheduled_collection = False
        failed = replace(self.result, notices=(replace(self.notice, extraction_status="original_only", text="Unreadable PDF"),), warnings=("OCR failed",))
        self.catalog._scan_source = Mock(return_value=failed)
        result = self.catalog.get_source("city", refresh=True)
        self.assertEqual(result.notices[0].text, self.notice.text)
        self.assertEqual(result.coverage()["freshness_status"], "stale")
        self.assertTrue(result.warnings)

    def test_repeated_unreadable_pdf_is_not_mislabeled_as_stale_cached_body(self):
        self.catalog._scheduled_collection = False
        failed = replace(self.result, notices=(replace(self.notice, extraction_status="original_only", text="Unreadable PDF"),), warnings=("OCR failed",))
        self.catalog._scan_source = Mock(return_value=failed)
        self.catalog.get_source("city", refresh=True)
        updated = replace(failed, notices=(replace(failed.notices[0], text="Current OCR failure"),))
        self.catalog._scan_source.return_value = updated
        result = self.catalog.get_source("city", refresh=True)
        self.assertEqual(result.notices[0].text, "Current OCR failure")
        self.assertEqual(result.coverage()["issue_codes"], ["extraction"])

    def test_incomplete_source_is_not_exported(self):
        for result in (replace(self.result, warnings=("failed",)), replace(self.result, refreshing=True), replace(self.result, notices=(replace(self.notice, extraction_status="original_only"),))):
            with self.assertRaises(CatalogError):
                snapshot_payload(result)

    def test_boolean_version_is_not_a_contract_version(self):
        payload = snapshot_payload(self.result)
        payload["version"] = True
        with self.assertRaises(CatalogError):
            accept_snapshot(self.catalog, payload)

    def test_invalid_or_forged_snapshot_does_not_mutate_cache(self):
        invalid = []
        for key, value in (("source_id", "unknown"), ("source_fingerprint", "bad"), ("grade", "1年生"), ("scanned_at", "2020-01-01T00:00:00Z"), ("scanned_at", "2026-10-01"), ("discovered_count", True), ("notices", [])):
            payload = snapshot_payload(self.result)
            payload[key] = value
            invalid.append(payload)
        for key, value in (("url", "https://evil.example/notice"), ("url", "https://city.example@evil.example/"), ("url", "javascript:alert(1)"), ("id", "not-an-id"), ("source_id", "other"), ("text", {}), ("extraction_status", "original_only")):
            payload = snapshot_payload(self.result)
            payload["notices"][0][key] = value
            invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(CatalogError):
                accept_snapshot(self.catalog, payload)
        self.assertIsNone(self.catalog._cache_store.load(self.source, "全学年"))

    def test_registry_labels_override_payload_labels(self):
        payload = snapshot_payload(self.result)
        payload["notices"][0]["source_name"] = "Fake school"
        accept_snapshot(self.catalog, payload)
        self.assertEqual(self.catalog.get_source("city").notices[0].source_name, "市役所")

    def test_attachments_survive_sync_but_external_and_script_urls_are_rejected(self):
        payload = snapshot_payload(replace(self.result, notices=(replace(self.notice, attachments=(("申込書", "https://city.example/form.pdf"),)),)))
        self.assertTrue(accept_snapshot(self.catalog, payload))
        self.assertEqual(self.catalog._cache_store.load(self.source, "全学年").notices[0].attachments, (("申込書", "https://city.example/form.pdf"),))
        for url in ("https://evil.example/a.pdf", "javascript:alert(1)", "https://city.example@evil.example/a.pdf"):
            payload["notices"][0]["attachments"][0]["url"] = url
            with self.assertRaises(CatalogError):
                accept_snapshot(self.catalog, payload)

    def test_storage_failure_cannot_acknowledge_an_import(self):
        with patch.object(self.catalog._cache_store, "save"), self.assertRaises(RuntimeError):
            accept_snapshot(self.catalog, snapshot_payload(self.result))
        self.assertFalse(self.catalog._cache)

    def test_internal_route_requires_secret_and_rejects_browser_origin(self):
        with patch.dict("os.environ", {"CATALOG_SYNC_TOKEN": "z" * 43}):
            server = _BetaHTTPServer(("127.0.0.1", 0), BetaRequestHandler, self.catalog)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def post(headers):
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            connection.request("POST", "/api/internal/catalog", json.dumps(snapshot_payload(self.result)), {"Content-Type": "application/json", **headers})
            response = connection.getresponse()
            status, body = response.status, json.loads(response.read())
            connection.close()
            return status, body
        try:
            self.assertEqual(post({})[0], 401)
            self.assertEqual(post({"Authorization": "Bearer wrong"})[0], 401)
            self.assertEqual(post({"Authorization": "Bearer " + "z" * 43, "Origin": "https://evil.example"})[0], 401)
            self.assertEqual(post({"Authorization": "Bearer " + "z" * 43, "Content-Length": "2000001"})[0], 400)
            self.assertEqual(post({"Authorization": "Bearer " + "z" * 43}), (200, {"ok": True, "imported": True}))
            server.catalog_sync_token = ""
            self.assertEqual(post({"Authorization": "Bearer " + "z" * 43})[0], 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
