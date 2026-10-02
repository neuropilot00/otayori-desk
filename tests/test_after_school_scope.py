from __future__ import annotations

import http.client
import json
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier.web_catalog import CatalogError, CatalogNotice, CatalogResult, CatalogService, _parse_source, load_sources
from sakurano_line_notifier.web_server import BetaRequestHandler, _BetaHTTPServer


REGISTRY = Path(__file__).resolve().parents[1] / "sources.json"


class AfterSchoolScopeTests(unittest.TestCase):
    def setUp(self):
        with patch.dict("os.environ", {"WEB_SCHEDULED_COLLECTION": "false"}):
            self.catalog = CatalogService(SimpleNamespace(web_catalog_max_wait_seconds=1), REGISTRY)
        self.catalog._scan_source = Mock(side_effect=self.result)
        self.handler = object.__new__(BetaRequestHandler)
        self.handler.server = SimpleNamespace(catalog=self.catalog)

    def tearDown(self):
        self.catalog.close()

    @staticmethod
    def result(source, grade):
        notice = CatalogNotice(
            id=source.id, source_id=source.id, source_name=source.name, ward=source.ward,
            level=source.level, grade=grade, title=source.name, kind=source.content_kind,
            url=source.page_url, text="公式の資料です。", content_hash="a" * 64,
            date_label="2026/10/01", published_label="2026/10/01",
            source_group=source.source_group, feed_group=source.feed_group,
            coverage_kind=source.coverage_kind,
        )
        return CatalogResult(source, grade, "2026-10-02T00:00:00+00:00", (notice,))

    def payload(self, source="sakurano", group="all", feed="notices"):
        return self.handler._notices_payload({"source_id": [source], "grade": ["1年生"], "group": [group], "feed": [feed]})

    def test_all_registered_after_school_sources_have_verified_material_types(self):
        sources = [s for s in load_sources(REGISTRY) if s.source_group == "after_school"]
        kinds = [s.content_kind for s in sources]
        self.assertEqual(kinds.count("gakudo_facility"), 12)
        self.assertEqual(kinds.count("asobee_letter"), 12)
        self.assertEqual(kinds.count("gakudo_admissions"), 1)
        self.assertEqual(kinds.count("asobee_reference"), 1)
        self.assertNotIn("gakudo_daily", kinds)
        for source in sources:
            if source.content_kind != "asobee_letter":
                self.assertEqual(source.coverage_kind, "reference")

    def test_admission_source_cannot_be_registered_as_daily_notice(self):
        with self.assertRaisesRegex(CatalogError, "must be reference"):
            _parse_source({"id": "bad", "name": "bad", "ward": "市", "level": "小学校", "page_url": "https://example.test/", "content_kind": "gakudo_admissions"}, 0)

    def test_combined_feed_does_not_claim_daily_club_collection(self):
        payload = self.payload()
        self.assertEqual(payload["after_school_scope"]["daily_notice_status"], "not_collected")
        self.assertEqual(payload["after_school_scope"]["source_ids"], [])
        admission = next(n for n in payload["notices"] if n["source_id"] == "musashino_gakudo_notices")
        self.assertEqual(admission["coverage_kind"], "reference")
        self.assertEqual(admission["kind_label"], "入会・制度案内")
        self.assertNotIn("学校全体への連絡", admission["category_names"])
        self.assertTrue(admission["url"].startswith("https://www.city.musashino.lg.jp/"))

    def test_group_filter_preserves_school_and_its_related_sources(self):
        payload = self.payload(group="after_school")
        self.assertEqual(payload["filters"]["source_id"], "sakurano")
        self.assertEqual({n["source_id"] for n in payload["notices"]}, {
            "sakurano_gakudo", "sakurano_asobee_public_letters", "musashino_gakudo_notices", "musashino_asobee_reference",
        })
        self.assertEqual(payload["reference_count"], 3)
        letter = next(n for n in payload["notices"] if n["kind"] == "asobee_letter")
        self.assertEqual(letter["kind_label"], "あそべえだより")
        self.assertEqual(letter["source_group_label"], "学童・あそべえ")
        self.assertEqual(next(c for c in payload["coverage"] if c["source_id"] == letter["source_id"])["content_kind"], "asobee_letter")

    def test_each_nearby_school_selects_only_its_facility_and_asobee(self):
        roots = [s for s in self.catalog.sources if s.collection_root and s.source_group == "school" and s.ward == "武蔵野市" and s.level == "小学校"]
        self.assertEqual(len(roots), 12)
        for root in roots:
            with self.subTest(school=root.id):
                payload = self.payload(root.id, "after_school")
                self.assertEqual(payload["filters"]["source_id"], root.id)
                for kind in ("gakudo_facility", "asobee_letter"):
                    notices = [n for n in payload["notices"] if n["kind"] == kind]
                    self.assertEqual(len(notices), 1)
                    source = next(s for s in self.catalog.sources if s.id == notices[0]["source_id"])
                    self.assertTrue(source.collection_id == root.collection_id or root.collection_id in source.related_collections)

    def test_school_municipal_and_event_filters_do_not_display_club_scope(self):
        for group, feed in (("school", "notices"), ("municipality", "notices"), ("all", "events")):
            with self.subTest(group=group, feed=feed):
                self.assertIsNone(self.payload(group=group, feed=feed)["after_school_scope"])

    def test_empty_or_failed_sources_do_not_erase_not_collected_status(self):
        self.catalog._scan_source.side_effect = lambda source, grade: replace(self.result(source, grade), notices=(), warnings=("unavailable",))
        payload = self.payload(group="after_school")
        self.assertEqual(payload["notices"], [])
        self.assertEqual(payload["after_school_scope"]["daily_notice_status"], "not_collected")
        self.assertFalse(payload["complete"])

    def test_future_daily_source_registration_does_not_claim_success(self):
        facility = next(s for s in self.catalog.sources if s.id == "sakurano_gakudo")
        daily = replace(facility, id="test_daily", content_kind="gakudo_daily", coverage_kind="notices")
        self.catalog.sources.append(daily)
        self.catalog._scan_source.side_effect = lambda source, grade: replace(self.result(source, grade), notices=(), warnings=("unavailable",))
        payload = self.payload(group="after_school")
        self.assertEqual(payload["after_school_scope"]["daily_notice_status"], "registered")
        self.assertEqual(payload["after_school_scope"]["source_ids"], ["test_daily"])
        self.assertFalse(payload["complete"])

    def test_http_group_selection_keeps_scope_and_original_link(self):
        with patch.dict("os.environ", {"WEB_PUBLIC_ORIGIN": ""}):
            server = _BetaHTTPServer(("127.0.0.1", 0), BetaRequestHandler, self.catalog)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            connection.request("GET", "/api/notices?source_id=sakurano&group=after_school&feed=notices")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read())
            self.assertEqual(payload["filters"]["source_id"], "sakurano")
            self.assertEqual(payload["after_school_scope"]["daily_notice_status"], "not_collected")
            self.assertTrue(all(n["url"].startswith("https://") for n in payload["notices"]))
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
