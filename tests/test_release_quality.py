from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch

from sakurano_line_notifier.release_quality import evaluate_catalog, fetch_public_snapshot, MAX_BYTES
from sakurano_line_notifier.web_catalog import _parse_source


class ReleaseQualityTests(unittest.TestCase):
    def setUp(self):
        self.source = _parse_source({"id": "school", "name": "School", "ward": "武蔵野市",
            "level": "小学校", "page_url": "https://school.example/", "mode": "mixed"}, 0)
        self.now = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
        self.payload = {"filters": {"source_id": "all", "grade": "default", "feed": "all",
            "group": "all", "level": "all", "ward": "all"}, "coverage": [{
            "source_id": "school", "page_url": self.source.page_url, "collection_driver": "server",
            "coverage_kind": "notices", "content_kind": self.source.content_kind,
            "notice_count": 2, "readable_count": 2, "issue_codes": [], "freshness_status": "fresh",
            "checked_at": "2026-10-03T11:59:00+00:00"}]}
        self.payload["notices"] = [{
            "source_id": "school", "source_name": "School", "ward": "武蔵野市", "level": "小学校",
            "source_group": "school", "feed_group": "notices", "coverage_kind": "notices",
            "grade": self.source.default_grade, "url": "https://school.example/a.pdf",
            "extraction_status": "ok", "excerpt": "公開の本文", "line_count": 1,
        } for _ in range(2)]

    def audit(self, payload=None, sources=None):
        return evaluate_catalog(payload or self.payload, sources or [self.source], now=self.now)

    def test_valid_public_snapshot_is_not_full_school_coverage_claim(self):
        result = self.audit()
        self.assertTrue(result["ok"])
        self.assertIn("not proof", result["scope"])
        self.assertEqual(result["sources"][0]["age_minutes"], 1)

    def test_history_limit_not_misreported_as_outage(self):
        self.payload["coverage"][0]["issue_codes"] = ["limit"]
        self.assertTrue(self.audit()["ok"])
        self.assertEqual(self.audit()["sources"][0]["notes"], ["limit"])

    def test_missing_duplicate_and_unknown_sources_fail(self):
        for coverage in ([], self.payload["coverage"] * 2,
                         [{**self.payload["coverage"][0], "source_id": "other"}]):
            with self.subTest(coverage=coverage):
                data = {**self.payload, "coverage": coverage}
                self.assertFalse(self.audit(data)["ok"])

    def test_inflight_refresh_with_recent_readable_cache_is_not_failure(self):
        self.payload["coverage"][0]["issue_codes"] = ["refreshing"]
        self.assertTrue(self.audit()["ok"])
        self.payload["coverage"][0]["checked_at"] = ""
        self.assertFalse(self.audit()["ok"])

    def test_fresh_label_does_not_hide_delayed_future_or_naive_timestamp(self):
        for stamp, reason in (
            ("2026-10-03T11:15:00+00:00", "over_freshness_target"),
            ("2026-10-03T12:06:00+00:00", "future_timestamp"),
            ("2026-10-03T11:59:00", "unknown_check_time"), ("", "unknown_check_time")):
            self.payload["coverage"][0]["checked_at"] = stamp
            result = self.audit()
            self.assertFalse(result["ok"])
            self.assertIn(reason, result["sources"][0]["issues"])

    def test_ocr_and_failed_collection_cannot_pass(self):
        for changes in ({"readable_count": 1}, {"issue_codes": ["extraction"]},
                        {"issue_codes": ["collection"]}, {"freshness_status": "stale"},
                        {"readable_count": True}, {"issue_codes": "limit"}):
            payload = deepcopy(self.payload)
            payload["coverage"][0].update(changes)
            self.assertFalse(self.audit(payload)["ok"])

    def test_registry_drift_is_flagged(self):
        for key, value in (("page_url", "https://other.example/"), ("content_kind", "gakudo_daily"),
                           ("coverage_kind", "reference"), ("collection_driver", "scheduled")):
            payload = deepcopy(self.payload)
            payload["coverage"][0][key] = value
            self.assertIn("registry_mismatch", self.audit(payload)["sources"][0]["issues"])

    def test_filtered_snapshot_cannot_claim_all_sources_pass(self):
        for key, value in (("source_id", "school"), ("grade", "1年生"), ("feed", "notices"),
                           ("group", "school"), ("ward", "武蔵野市"), ("level", "小学校")):
            payload = deepcopy(self.payload)
            payload["filters"][key] = value
            with self.assertRaises(ValueError):
                self.audit(payload)

    def test_static_reference_not_promoted_to_live_data(self):
        source = replace(self.source, mode="static", coverage_kind="reference")
        row = self.payload["coverage"][0]
        row.update(coverage_kind="reference", checked_at="")
        for notice in self.payload["notices"]:
            notice["coverage_kind"] = "reference"
            notice["url"] = source.page_url
        result = self.audit(sources=[source])
        self.assertTrue(result["ok"])
        self.assertIn("static_reference_not_live", result["sources"][0]["notes"])

    def test_current_empty_audience_result_is_not_automatically_an_outage(self):
        self.payload["coverage"][0].update(notice_count=0, readable_count=0, audience_excluded_count=3)
        self.payload["notices"] = []
        self.assertTrue(self.audit()["ok"])

    def test_notice_ownership_and_original_link_must_match_registry(self):
        for key, value in (("source_id", "unknown"), ("source_name", "Other School"),
                           ("ward", "港区"), ("level", "中学校"), ("grade", "9年生"),
                           ("source_group", "municipality"), ("coverage_kind", "reference"),
                           ("url", "https://other.example/a.pdf")):
            payload = deepcopy(self.payload)
            payload["notices"][0][key] = value
            self.assertFalse(self.audit(payload)["ok"])

    def test_incomplete_notice_list_is_not_silently_accepted(self):
        self.payload["notices"].pop()
        self.assertIn("notice_count_mismatch", self.audit()["sources"][0]["issues"])

    def test_empty_source_without_audience_evidence_requires_review(self):
        self.payload["notices"] = []
        self.payload["coverage"][0].update(notice_count=0, readable_count=0)
        self.assertFalse(self.audit()["ok"])

    def test_malformed_filter_object_fails_closed(self):
        self.payload["filters"] = []
        with self.assertRaises(ValueError):
            self.audit()

    def test_same_host_other_facility_page_cannot_pass(self):
        source = replace(self.source, mode="html_page")
        # Same host, but another institution's page.
        self.assertIn("notice_source_url_mismatch:school", self.audit(sources=[source])["registry_errors"])
        for notice in self.payload["notices"]:
            notice["url"] = source.page_url + "#notice"
        self.assertTrue(self.audit(sources=[source])["ok"])

    def test_empty_readable_body_or_forged_counts_fail(self):
        for changes in ({"excerpt": ""}, {"line_count": 0}, {"line_count": True},
                        {"extraction_status": "original_only"}, {"extraction_status": "invented"}):
            data = deepcopy(self.payload)
            data["notices"][0].update(changes)
            self.assertFalse(self.audit(data)["ok"])

    def test_static_notices_never_receive_no_timestamp_exemption(self):
        source = replace(self.source, mode="static", coverage_kind="notices")
        result = self.audit(sources=[source])
        self.assertFalse(result["ok"])
        self.assertNotIn("static_reference_not_live", result["sources"][0]["notes"])

    @patch("sakurano_line_notifier.release_quality.requests.Session")
    def test_fetch_uses_fixed_public_endpoint_no_redirects_and_bounded_payload(self, factory):
        session = factory.return_value.__enter__.return_value
        response = session.get.return_value.__enter__.return_value
        response.status_code = 200
        response.iter_content.return_value = [b'{"coverage":[]}']
        self.assertEqual(fetch_public_snapshot(), {"coverage": []})
        self.assertFalse(session.trust_env)
        self.assertFalse(session.get.call_args.kwargs["allow_redirects"])
        self.assertNotIn("headers", session.get.call_args.kwargs)
        response.iter_content.return_value = [b"x" * (MAX_BYTES + 1)]
        with self.assertRaises(ValueError):
            fetch_public_snapshot()
        response.status_code = 302
        with self.assertRaises(ValueError):
            fetch_public_snapshot()


if __name__ == "__main__":
    unittest.main()
