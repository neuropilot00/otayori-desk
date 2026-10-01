from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from pathlib import Path

from sakurano_line_notifier.fetcher import LinkCandidate
from sakurano_line_notifier.web_catalog import CatalogService, _parse_source, _candidate_sort_key, _candidate_matches_grade, load_sources
from sakurano_line_notifier.notice_dates import activity_dates


class CoverageExpansionTests(TestCase):
    def setUp(self):
        self.source = _parse_source({"id": "school", "name": "学校", "ward": "市", "level": "小学校", "page_url": "https://school.example/notices", "mode": "pdf", "max_documents": 1}, 0)
        self.service = object.__new__(CatalogService)
        self.service.settings = SimpleNamespace(request_timeout_seconds=1, max_document_bytes=10000, user_agent="test")

    def test_other_grade_files_cannot_consume_target_grade_limit(self):
        fetcher = Mock()
        fetcher.fetch_page.return_value = '<a href="/20261002000000.pdf">2年生 10月号</a><a href="/20261001000000.pdf">1年生 10月号</a>'
        self.service._read_candidate = Mock(return_value=None)
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher):
            result = self.service._scan_source(self.source, "1年生")
        self.assertEqual(self.service._read_candidate.call_args.args[2].title, "1年生 10月号")
        self.assertFalse(result.limit_reached)
        self.assertEqual(result.discovered_count, 1)

    def test_embedded_official_pdf_discovery_does_not_require_anchor(self):
        html = '<embed src="/handbook.pdf"><object data="/forms.pdf"></object><iframe src="/video"></iframe><iframe src="/calendar.pdf" title="年間予定"></iframe>'
        candidates = self.service._document_links(html, self.source, self.source.page_url)
        self.assertEqual({x.url for x in candidates}, {"https://school.example/handbook.pdf", "https://school.example/forms.pdf", "https://school.example/calendar.pdf"})

    def test_generic_download_title_uses_own_source_even_when_unreadable(self):
        self.assertEqual(self.service._display_title(LinkCandidate("https://school.example/a.pdf", "PDFダウンロード", "document"), self.source, "全学年", ""), self.source.name)

    def test_recurring_event_does_not_claim_first_past_session_as_whole_event(self):
        body = "令和8年度市民スポーツデー\n開催日\n令和8年4月19日(日曜日)\n、5月17日(日曜日)\n、10月18日(日曜日)\n開催時間\n午後1時30分"
        self.assertEqual(activity_dates(body), ("", ""))
        self.assertEqual(activity_dates("開催日\n2026年10月12日(月曜日)\n持ち物\n上履き"), ("2026/10/12", ""))

    def test_each_asobee_letter_is_scoped_to_one_school_and_future_years(self):
        sources = load_sources(Path(__file__).resolve().parents[1] / "sources.json")
        letters = [s for s in sources if s.id.endswith("_asobee_public_letters")]
        self.assertEqual(len(letters), 12)
        self.assertEqual(len({s.collection_id for s in letters}), 12)
        html = ''.join(f'<a href="202710-{i}.pdf">PDFダウンロード</a>' for i in range(1, 13))
        urls = []
        for source in letters:
            self.assertFalse(source.shared_with_ward)
            self.assertFalse(source.collection_root)
            matches = self.service._scoped_links(html, source, source.page_url)
            self.assertEqual(len(matches), 1)
            urls.append(matches[0].url)
            if source.collection_id != "sakurano":
                self.assertEqual(source.related_collections, (source.collection_id.replace("_es", "_gakudo"),))
        self.assertEqual(len(set(urls)), 12)

    def test_related_collection_validation_rejects_non_registry_input(self):
        with self.assertRaisesRegex(Exception, "related_collections"):
            _parse_source({**self.source.to_dict(), "related_collections": "all"}, 0)

    def test_club_collection_includes_own_letter_not_another_schools(self):
        self.service.sources = load_sources(Path(__file__).resolve().parents[1] / "sources.json")
        self.service._max_wait_seconds = 0
        self.service._cached_result = Mock(return_value=True)
        results = self.service.get_many(source_id="musashino_dai1_gakudo", source_group="after_school", feed_group="notices")
        letters = [r.source.id for r in results if r.source.id.endswith("_asobee_public_letters")]
        self.assertEqual(letters, ["musashino_dai1_es_asobee_public_letters"])

    def test_download_ids_sort_numerically_not_by_month_title(self):
        nine = LinkCandidate("https://school.example/download/document/999", "9月号", "document")
        ten = LinkCandidate("https://school.example/download/document/1000", "10月号", "document")
        self.assertGreater(_candidate_sort_key(ten), _candidate_sort_key(nine))

    def test_grade_ranges_and_joint_grade_titles_keep_each_target(self):
        for title in ("3・4年生", "3〜4年生", "3・4・5年生"):
            candidate = LinkCandidate("https://school.example/common.pdf", title, "document")
            self.assertTrue(_candidate_matches_grade(candidate, "3年生"))
            self.assertTrue(_candidate_matches_grade(candidate, "4年生"))
            self.assertFalse(_candidate_matches_grade(candidate, "1年生"))

    def test_cms_timestamps_have_the_same_scale(self):
        old = LinkCandidate("https://school.example/20260901000000.pdf", "9月号", "document")
        new = LinkCandidate("https://school.example/20261001.pdf", "10月号", "document")
        self.assertGreater(_candidate_sort_key(new), _candidate_sort_key(old))

    def test_html_keeps_body_attachments_but_not_navigation_or_unsafe_links(self):
        source = replace(self.source, mode="html_page")
        html = '<nav><a href="/navigation.pdf">Nav</a></nav><main><h1>10月のお知らせ</h1><p>申込書をご確認ください。</p><a href="/apply.pdf">申込書</a><a href="/apply.pdf#page=2">申込書</a><a href="https://evil.example/x.pdf">Outside</a><a href="javascript:alert(1)">Unsafe</a><img src="/flyer.jpg" alt="行事案内"><footer><a href="/footer.pdf">Footer</a></footer></main>'
        result = self.service._read_candidate(Mock(), source, LinkCandidate(source.page_url, "案内", "document"), "全学年", html)
        self.assertEqual(result.to_detail()["attachments"], [{"title": "申込書", "url": "https://school.example/apply.pdf"}, {"title": "行事案内", "url": "https://school.example/flyer.jpg"}])

    def test_social_icons_are_not_attachments_but_official_application_forms_are(self):
        source = replace(self.source, mode="html_page")
        html = '<main><h1>申込案内</h1><img src="/_template_/_res/images/post.png" alt="SNS"><a href="/form.xlsx">申請書</a></main>'
        result = self.service._read_candidate(Mock(), source, LinkCandidate(source.page_url, "案内", "document"), "全学年", html)
        self.assertEqual(result.attachments, (("申請書", "https://school.example/form.xlsx"),))
