from __future__ import annotations

import json
import tempfile
import time
import unittest
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from sakurano_line_notifier.web_catalog import CatalogService, CatalogError


class CatalogFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = root / "sources.json"
        self.source = {"id": "one", "name": "School", "ward": "武蔵野市", "level": "小学校", "page_url": "https://school.example/", "mode": "static", "static_text": "持ち物：水筒"}
        self.registry.write_text(json.dumps({"sources": [self.source]}))
        self.settings = SimpleNamespace(web_cache_ttl_seconds=30, web_catalog_max_wait_seconds=1, web_catalog_cache_path=root / "cache.sqlite3", request_timeout_seconds=1, max_document_bytes=1000, user_agent="test")
        self.service = CatalogService(self.settings, self.registry)

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def test_old_persistent_cache_triggers_actual_scan(self):
        original = self.service.get_source("one", "1年生")
        old = replace(original, scanned_at="2000-01-01T00:00:00+00:00")
        self.service._cache_store.save(old)
        self.service.close()
        self.service = CatalogService(self.settings, self.registry)
        scanner = Mock(return_value=original)
        self.service._scan_source = scanner
        results = self.service.get_many(source_id="one", grade="1年生")
        scanner.assert_called_once()
        self.assertEqual(results[0].scanned_at, original.scanned_at)

    def test_failed_refresh_preserves_last_good_and_marks_warning(self):
        original = self.service.get_source("one", "1年生")
        self.service._scan_source = Mock(side_effect=CatalogError("failure"))
        result = self.service.get_many(source_id="one", grade="1年生", refresh=True)[0]
        self.assertEqual(result.notices, original.notices)
        self.assertEqual(result.scanned_at, original.scanned_at)
        self.assertTrue(result.warnings)
        self.assertFalse(self.service._cache_store.load(original.source, original.grade).warnings)

    def test_partial_scan_does_not_erase_readable_document(self):
        original = self.service.get_source("one", "1年生")
        self.service._scan_source = Mock(return_value=replace(original, notices=(), warnings=("PDF failure",)))
        result = self.service.get_source("one", "1年生", refresh=True)
        self.assertEqual(result.notices, original.notices)
        self.assertTrue(result.warnings)

    def test_partial_readable_snapshot_keeps_stale_marker_after_restart(self):
        original = self.service.get_source("one", "1年生")
        self.service._scan_source = Mock(return_value=replace(original, notices=(), warnings=("PDF failure",)))
        partial = self.service.get_source("one", "1年生", refresh=True)
        self.service.close()
        self.service = CatalogService(self.settings, self.registry)
        restored = self.service._last_cached(partial.source, partial.grade)[1]
        self.assertEqual(restored.notices, original.notices)
        self.assertEqual(restored.warnings, partial.warnings)
        self.assertEqual(restored.coverage()["freshness_status"], "stale")
        self.assertEqual(restored.coverage()["issue_codes"], ["stale"])

    def test_original_only_link_and_failure_survive_restart_without_readable_credit(self):
        original = self.service.get_source("one", "1年生")
        failed = replace(original, grade="2年生", notices=(replace(original.notices[0], grade="2年生", extraction_status="original_only", text="本文未確認"),), warnings=("OCR failed",))
        self.service._scan_source = Mock(return_value=failed)
        result = self.service.get_source("one", "2年生", refresh=True)
        self.assertEqual(result.coverage()["readable_count"], 0)
        self.service.close()
        self.service = CatalogService(self.settings, self.registry)
        restored = self.service._last_cached(failed.source, failed.grade)[1]
        self.assertEqual(restored.notices[0].url, failed.notices[0].url)
        self.assertEqual(restored.warnings, failed.warnings)
        self.assertEqual(restored.coverage()["readable_count"], 0)
        self.assertEqual(restored.coverage()["issue_codes"], ["extraction"])

    def test_empty_failure_does_not_create_a_successful_persistent_snapshot(self):
        original = self.service.get_source("one", "1年生")
        self.service._scan_source = Mock(return_value=replace(original, grade="2年生", notices=(), warnings=("failed",)))
        result = self.service.get_source("one", "2年生", refresh=True)
        self.assertIsNone(self.service._cache_store.load(result.source, result.grade))

    def test_changed_registry_invalidates_persistent_content(self):
        original = self.service.get_source("one", "1年生")
        changed = replace(original.source, page_url="https://school.example/new", static_text="new")
        self.assertIsNone(self.service._cache_store.load(changed, "1年生"))

    def test_single_school_concurrent_refreshes_share_work(self):
        original = self.service.get_source("one", "1年生")
        def scan(*_):
            time.sleep(0.05)
            return original
        scanner = Mock(side_effect=scan)
        self.service._scan_source = scanner
        with ThreadPoolExecutor(max_workers=2) as executor:
            requests = [executor.submit(self.service.get_many, source_id="one", grade="1年生", refresh=True) for _ in range(2)]
            for request in requests:
                request.result()
        self.assertEqual(scanner.call_count, 1)

    def test_background_scan_prioritizes_default_family_without_changing_response_order(self):
        original = self.service.get_source("one", "1年生")
        root = original.source
        unrelated = replace(root, id="other", collection_id="other")
        related = replace(root, id="club", collection_id="club", related_collections=(root.collection_id,), collection_root=False)
        self.service.sources = (root, unrelated, related)
        submitted = []
        def submit(source, *_):
            submitted.append(source.id)
            future = Future()
            future.set_result(replace(original, source=source))
            return future
        self.service._cached_result = Mock(return_value=False)
        self.service._submit_source = submit
        results = self.service.get_many(source_id="all", refresh=True)
        self.assertEqual(submitted, ["one", "club", "other"])
        self.assertEqual([result.source.id for result in results], ["one", "other", "club"])


if __name__ == "__main__":
    unittest.main()
