from __future__ import annotations

import tempfile
import threading
import time
import unittest
from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier.fetcher import FetchedDocument, LinkCandidate
from sakurano_line_notifier.notice_dates import activity_dates, publication_date
from sakurano_line_notifier.web_catalog import CatalogResult, CatalogService, _parse_source, _date_labels


class CollectionCoverageTests(unittest.TestCase):
    def setUp(self):
        self.source = _parse_source({"id": "school", "name": "学校", "ward": "武蔵野市", "level": "小学校", "page_url": "https://school.example/", "mode": "mixed"}, 0)
        self.service = object.__new__(CatalogService)
        self.service._scheduled_collection = False
        self.service.settings = SimpleNamespace(request_timeout_seconds=1, max_document_bytes=100000, user_agent="test")

    def test_html_event_date_is_not_publication_date(self):
        source = replace(self.source, mode="html_page", feed_group="events")
        html = '<main><h1>収穫体験</h1><dl><dt>開催日</dt><dd>2026年11月22日</dd><dt>申込み締め切り日</dt><dd>2026年10月14日</dd></dl></main>'
        notice = self.service._read_candidate(Mock(), source, LinkCandidate(source.page_url, "収穫体験", "city_info"), "全学年", html)
        self.assertEqual(notice.published_label, "")
        self.assertEqual(notice.event_date, "2026/11/22")
        self.assertEqual(notice.deadline_date, "2026/10/14")
        self.assertEqual(notice.date_kind, "event")

    def test_publication_label_requires_its_own_date(self):
        self.assertEqual(publication_date("", "開催日\n2026年11月22日"), "")
        self.assertEqual(publication_date('<meta content="2026-09-28" name="dateModified">', ""), "2026/09/28")
        self.assertEqual(publication_date("", "更新日 2026年9月28日\n開催日 2026年11月22日"), "2026/09/28")
        self.assertEqual(activity_dates("開催日 未定\n申込み締め切り日 2026年10月14日"), ("", "2026/10/14"))

    def test_fiscal_issue_month_does_not_invent_publication_date(self):
        candidate = LinkCandidate("https://school.example/file/7798", "R8 9月号.pdf", "document")
        self.assertEqual(_date_labels(candidate, "芝浦だより\n令和 ８年度 ９ 月 号"), ("2026/09月号", "更新資料"))
        candidate = replace(candidate, title="3月号.pdf")
        self.assertEqual(_date_labels(candidate, "令和7年度 3月号"), ("2026/03月号", "更新資料"))

    def test_upload_timestamp_and_future_schedule_do_not_become_publication(self):
        candidate = LinkCandidate("https://school.example/20260901000100.pdf", "学校だより", "school_news")
        self.assertEqual(_date_labels(candidate, "運動会 2026年10月10日"), ("更新資料", "更新資料"))
        self.assertEqual(_date_labels(candidate, "令和8 年 9 月 18 日"), ("2026/09/18", "2026/09/18"))
        self.assertEqual(_date_labels(candidate, "2026/02/31"), ("更新資料", "更新資料"))
        self.assertEqual(_date_labels(candidate, "学年だより10月号"), ("2026/10月号", "更新資料"))
        self.assertEqual(_date_labels(candidate, "令和8年5月14日発行"), ("2026/05/14", "2026/05/14"))

    def test_pdf_issue_header_survives_grade_section_selection(self):
        source = replace(self.source, mode="pdf")
        fetcher = Mock()
        url = "https://school.example/20260918181117.pdf"
        fetcher.fetch_document.return_value = FetchedDocument(url, b"%PDF-test", "application/pdf", None, None)
        candidate = LinkCandidate(url, "学年だより", "grade_news")
        with patch("sakurano_line_notifier.web_catalog.extract_document_text", return_value="学年だより10月号\n1年生\n持ち物: 水筒"), patch("sakurano_line_notifier.web_catalog.select_relevant_text", return_value="持ち物: 水筒"):
            notice = self.service._read_candidate(fetcher, source, candidate, "1年生")
        self.assertEqual(notice.date_label, "2026/10月号")
        self.assertEqual(notice.published_label, "")

    def test_registration_datetime_is_not_event_datetime(self):
        self.assertEqual(activity_dates("申込開始日時 2026年10月1日\n開催日時 2026年11月22日"), ("2026/11/22", ""))

    def test_downloaded_html_respects_declared_shift_jis(self):
        source = replace(self.source, mode="link_index")
        fetcher = Mock()
        content = '<main><h1>学校のお知らせ</h1><p>持ち物は水筒です。</p></main>'.encode("shift_jis")
        fetcher.fetch_document.return_value = FetchedDocument(source.page_url, content, "text/html; charset=Shift_JIS", None, None)
        notice = self.service._read_candidate(fetcher, source, LinkCandidate(source.page_url, "案内", "document"), "全学年")
        self.assertIn("持ち物は水筒です。", notice.text)
        self.assertNotIn("\ufffd", notice.text)

    def test_fresh_cache_keeps_refreshing_flag_while_forced_scan_is_running(self):
        source = self.source
        result = CatalogResult(source, source.default_grade, "2026-10-01T00:00:00+00:00", ())
        self.service._lock = threading.RLock()
        self.service._cache_ttl_seconds = 300
        self.service._last_cached = Mock(return_value=(time.monotonic(), result))
        pending = Future()
        self.service._inflight = {(source.id, source.default_grade): pending}
        results = {}
        self.assertTrue(self.service._cached_result(source, source.default_grade, False, results))
        self.assertTrue(results[source.id].refreshing)
        pending.set_result(result)
        self.assertTrue(self.service._cached_result(source, source.default_grade, False, results))
        self.assertFalse(results[source.id].refreshing)

    def test_library_inline_notice_is_included_without_navigation(self):
        html = '<nav>ナビゲーション</nav><div id="hp_jpage38_read"><div>図書館だより</div><p>読書旬間 9/25～10/9</p></div><footer>フッター</footer>'
        notice = self.service._read_candidate(Mock(), self.source, LinkCandidate(self.source.page_url, "図書館だより", "document"), "1年生", html)
        self.assertIn("読書旬間", notice.text)
        self.assertNotIn("ナビゲーション", notice.text)
        self.assertNotIn("フッター", notice.text)
        self.assertEqual(notice.date_kind, "unknown")

    def test_extensionless_reviewed_download_is_discovered(self):
        html = '<a href="/plugin/attachments/2/3/4">10月号</a><a href="/tseta/download/document/18540195?tm=20260907150938">9月号</a><a href="/login">ログイン</a>'
        links = self.service._document_links(html, self.source, self.source.page_url)
        self.assertEqual([link.title for link in links], ["10月号", "9月号"])

    def test_new_index_article_is_discovered_and_external_hosts_excluded(self):
        source = replace(self.source, mode="link_index", link_patterns=(r"/events/\d+\.html$",))
        html = '<a href="/events/123.html">新しい催し</a><a href="https://evil.example/events/123.html">外部</a>'
        self.assertEqual([item.url for item in self.service._scoped_links(html, source, source.page_url)], ["https://school.example/events/123.html"])

    def test_facility_is_reference_not_a_fresh_notice(self):
        source = replace(self.source, mode="static", coverage_kind="reference")
        coverage = CatalogResult(source, "全学年", "2026-10-01T00:00:00+00:00", ()).coverage()
        self.assertEqual(coverage["status"], "reference")
        self.assertEqual(coverage["checked_at"], "")

    def test_standalone_other_grade_pdf_is_not_labelled_grade_one(self):
        fetcher = Mock()
        self.assertIsNone(self.service._read_candidate(fetcher, self.source, LinkCandidate("https://school.example/two.pdf", "２年生", "document"), "1年生"))
        fetcher.fetch_document.assert_not_called()

    def test_bounded_scan_reports_limit_instead_of_claiming_full_coverage(self):
        source = replace(self.source, mode="pdf", max_documents=1)
        fetcher = Mock()
        fetcher.fetch_page.return_value = '<a href="/20261001000100.pdf">10月号</a><a href="/20260901000100.pdf">9月号</a>'
        self.service._read_candidate = Mock(return_value=None)
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher):
            result = self.service._scan_source(source, "全学年")
        self.assertEqual(result.discovered_count, 2)
        self.assertTrue(result.limit_reached)

    def test_failed_pdf_keeps_original_link_and_explicit_incomplete_state(self):
        from sakurano_line_notifier.extractor import ExtractionError
        source = replace(self.source, mode="pdf")
        fetcher = Mock()
        fetcher.fetch_page.return_value = '<a href="/20261001000100.pdf">10月号</a>'
        self.service._read_candidate = Mock(side_effect=ExtractionError("unreadable"))
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher):
            result = self.service._scan_source(source, "全学年")
        self.assertEqual(len(result.notices), 1)
        self.assertEqual(result.notices[0].url, "https://school.example/20261001000100.pdf")
        self.assertEqual(result.notices[0].extraction_status, "original_only")
        self.assertTrue(result.warnings)
        self.assertEqual(result.coverage()["readable_count"], 0)

    def test_shared_city_notices_follow_other_same_ward_school_selections(self):
        import json
        root = {"id": "school", "name": "School", "ward": "武蔵野市", "level": "小学校", "page_url": "https://school.example/", "mode": "static", "static_text": "body"}
        city = {**root, "id": "city", "name": "City", "shared_with_ward": True, "source_group": "municipality"}
        other = {**city, "id": "other-city", "ward": "渋谷区"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps({"sources": [root, city, other]}))
            service = CatalogService(self.service.settings, path)
            try:
                self.assertEqual({result.source.id for result in service.get_many(source_id="school")}, {"school", "city"})
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
