import http.client
import json
import threading
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from sakurano_line_notifier.config import Settings
from sakurano_line_notifier.notice_schedule import DELIVERY_DELAY, active_slot, checked_this_slot, delivery_slot, overdue
from sakurano_line_notifier.web_catalog import CatalogCacheStore, CatalogResult, CatalogService
from sakurano_line_notifier.web_server import _BetaHTTPServer, BetaRequestHandler

stamp = datetime.fromisoformat


class FixedCadenceTests(TestCase):
    def test_tokyo_windows_and_staleness_grace(self):
        for start in ("01", "10"):
            self.assertIsNotNone(active_slot(stamp(f"2026-11-25T{start}:00:00+00:00")))
            self.assertIsNone(active_slot(stamp(f"2026-11-25T{start}:00:00+00:00"), delay=DELIVERY_DELAY))
            self.assertIsNotNone(active_slot(stamp(f"2026-11-25T{start}:12:00+00:00"), delay=DELIVERY_DELAY))
            self.assertIsNone(active_slot(stamp(f"2026-11-25T{start}:20:00+00:00")))
        self.assertIsNone(active_slot(stamp("2026-11-25T06:30:00+00:00")))
        previous = "2026-11-24T10:02:00+00:00"
        self.assertFalse(overdue(previous, stamp("2026-11-25T01:19:59+00:00")))
        self.assertTrue(overdue(previous, stamp("2026-11-25T01:20:00+00:00")))

    def test_delivery_waits_for_snapshot_or_deadline(self):
        ready = lambda slot: False
        early = stamp("2026-11-25T01:12:00+00:00")
        late = stamp("2026-11-25T01:14:00+00:00")
        self.assertIsNone(delivery_slot(ready, early))
        self.assertEqual(delivery_slot(lambda slot: checked_this_slot(late.isoformat(), slot), late), active_slot(late))
        self.assertIsNone(delivery_slot(ready, stamp("2026-11-25T01:17:59+00:00")))
        self.assertIsNotNone(delivery_slot(ready, stamp("2026-11-25T01:18:00+00:00")))
        self.assertIsNone(delivery_slot(ready, stamp("2026-11-25T01:20:00+00:00")))
        self.assertFalse(checked_this_slot("2026-11-24T10:03:00+00:00", active_slot(late)))

    def test_persistent_claim_across_restarts(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "catalog.db"
            morning = active_slot(stamp("2026-11-25T01:12:00+00:00"))
            evening = active_slot(stamp("2026-11-25T10:12:00+00:00"))
            a = CatalogCacheStore(path)
            self.assertTrue(a.claim("push", morning))
            self.assertTrue(a.claim("collect", morning))
            b = CatalogCacheStore(path)
            self.assertFalse(b.claim("push", morning))
            self.assertTrue(b.claim("push", evening))
            self.assertFalse(a.claim("push", morning))

    def test_public_read_does_not_collect_and_refresh_post_does(self):
        with TemporaryDirectory() as d, patch.dict("os.environ", {"WEB_PUBLIC_ORIGIN": "https://test.example", "WEB_SCHEDULED_COLLECTION": "true"}):
            cfg = replace(Settings.load(Path("config.json")), web_catalog_cache_path=Path(d) / "catalog.db")
            catalog = CatalogService(cfg, Path("sources.json"))
            catalog._fixed_cadence = True
            calls = []
            def scan(source, grade):
                calls.append((source.id, grade))
                return CatalogResult(source, grade, "2026-11-25T01:03:00+00:00", (), (), 0, False)
            server = _BetaHTTPServer(("127.0.0.1", 0), BetaRequestHandler, catalog)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            q = "?source_id=" + next(s.id for s in catalog.sources if s.enabled and s.source_group == "school" and not s.collection_root)
            def request(method, route):
                c = http.client.HTTPConnection(*server.server_address, timeout=5)
                try:
                    c.request(method, route, "{}" if method == "POST" else None, {"Origin": "https://test.example", "Content-Type": "application/json"})
                    r = c.getresponse()
                    return r.status, json.loads(r.read())
                finally:
                    c.close()
            try:
                with patch.object(catalog, "_scan_source", side_effect=scan), patch.object(catalog._dispatch_watchdog, "check") as watcher:
                    self.assertEqual(request("GET", "/api/notices" + q)[0], 200)
                    self.assertFalse(calls)
                    self.assertEqual(catalog._check_collection_recovery(), "manual_only")
                    watcher.assert_not_called()
                    self.assertEqual(request("POST", "/api/refresh" + q)[0], 200)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(request("GET", "/api/notices" + q)[0], 200)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(request("GET", "/api/collection/status")[1]["schedule_jst"], ["10:00", "19:00"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                catalog.close()
