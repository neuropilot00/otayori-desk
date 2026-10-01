from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sakurano_line_notifier.fetcher import LinkCandidate
from sakurano_line_notifier.web_catalog import CatalogService, _date_labels, _parse_source, load_sources
from sakurano_line_notifier.web_push import PushSubscriptionError, normalize_push_scope


class SourceRegistryTests(unittest.TestCase):
    def test_registry_contains_multiple_school_levels_and_normalized_grades(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        sources = load_sources(project_root / "sources.json")
        self.assertGreaterEqual(len(sources), 8)
        self.assertEqual({source.level for source in sources}, {"小学校", "中学校", "高等学校"})
        self.assertEqual(sources[0].default_grade, "1年生")
        self.assertGreaterEqual(len(sources[0].page_urls), 5)
        self.assertEqual(sources[1].grades, ("全学年",))

    def test_source_rejects_invalid_mode(self) -> None:
        with self.assertRaisesRegex(Exception, "mode"):
            _parse_source(
                {
                    "id": "broken",
                    "name": "Broken",
                    "ward": "港区",
                    "level": "小学校",
                    "page_url": "https://example.test/",
                    "mode": "unknown",
                },
                0,
            )

    def test_source_can_be_defined_with_multiple_pages_without_page_url_alias(self) -> None:
        source = _parse_source(
            {
                "id": "multi",
                "name": "Multi",
                "ward": "港区",
                "level": "小学校",
                "page_urls": ["https://example.test/letters/", "https://example.test/events/"],
            },
            0,
        )
        self.assertEqual(source.page_url, "https://example.test/letters/")
        self.assertEqual(source.page_urls[1], "https://example.test/events/")

    def test_source_groups_and_feed_groups_are_normalized(self) -> None:
        source = _parse_source(
            {
                "id": "events",
                "name": "Municipality",
                "ward": "武蔵野市",
                "level": "小学校",
                "page_url": "https://example.test/events/",
                "mode": "html_page",
                "source_group": "municipality",
                "feed_group": "events",
                "content_kind": "city_info",
            },
            0,
        )
        self.assertEqual(source.source_group, "municipality")
        self.assertEqual(source.feed_group, "events")
        self.assertEqual(source.content_kind, "city_info")

    def test_source_coordinates_are_optional_but_must_be_a_pair(self) -> None:
        source = _parse_source(
            {
                "id": "mapped",
                "name": "Mapped",
                "ward": "武蔵野市",
                "level": "小学校",
                "page_url": "https://example.test/",
                "latitude": 35.7,
                "longitude": 139.5,
            },
            0,
        )
        self.assertEqual((source.latitude, source.longitude), (35.7, 139.5))
        with self.assertRaisesRegex(Exception, "both latitude and longitude"):
            _parse_source({**source.to_dict(), "longitude": None}, 0)

    def test_push_scope_is_limited_to_known_public_filters(self) -> None:
        scope = normalize_push_scope(
            {"source_id": "sakurano", "grade": "1年生", "feed": "notices", "group": "after_school"},
            {"sakurano"},
        )
        self.assertEqual(scope["group"], "after_school")
        with self.assertRaises(PushSubscriptionError):
            normalize_push_scope({"source_id": "unknown"}, {"sakurano"})


class NewsIndexTests(unittest.TestCase):
    def test_html_news_parser_keeps_article_links_and_filters_navigation(self) -> None:
        source = _parse_source(
            {
                "id": "high",
                "name": "High",
                "ward": "渋谷区",
                "level": "高等学校",
                "page_url": "https://www.metro.ed.jp/aoyama-h/news/news-01/index.html",
                "mode": "html_news",
                "include_patterns": ["お知らせ"],
                "exclude_patterns": ["採用"],
            },
            0,
        )
        html = """
        <a href="/aoyama-h/news/news-01/index.html">一覧</a>
        <a href="/aoyama-h/news/2026/09/newsentry_85.html"><span>2026/09/08</span> お知らせ 第1回学校説明会</a>
        <a href="/aoyama-h/news/2026/09/teacher.html">採用 お知らせ</a>
        """
        links = CatalogService._parse_news_links(html, source)
        self.assertEqual(len(links), 1)
        self.assertIn("newsentry_85", links[0].url)

    def test_issue_month_does_not_replace_publication_date(self) -> None:
        school = LinkCandidate(
            url="https://example.test/20260918180945.pdf",
            title="(表面)学校だより",
            kind="school_news",
        )
        grade = LinkCandidate(
            url="https://example.test/20260918181117.pdf",
            title="(裏面)学年だより",
            kind="grade_news",
        )
        self.assertEqual(_date_labels(school, "学校だより 第7号\n10月の行事予定"), ("2026/09/18", "2026/09/18"))
        self.assertEqual(_date_labels(grade, "学年だより（10月号）"), ("2026/10月号", "2026/09/18"))


class CatalogPayloadTests(unittest.TestCase):
    def test_source_file_is_json_serializable_for_api(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        payload = json.loads((project_root / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("sources", payload)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "sources.json"
            copy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(len(load_sources(copy)), len(payload["sources"]))
