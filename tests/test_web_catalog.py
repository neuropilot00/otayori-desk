from __future__ import annotations

import json
import base64
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

from sakurano_line_notifier.fetcher import LinkCandidate
from sakurano_line_notifier.web_catalog import CatalogResult, CatalogService, _date_labels, _parse_source, load_sources
from sakurano_line_notifier.web_push import PushSubscriptionError, SQLitePushSubscriptionStore, normalize_push_scope
from sakurano_line_notifier.web_server import _RequestRateLimiter


class SourceRegistryTests(unittest.TestCase):
    def test_registry_contains_multiple_school_levels_and_normalized_grades(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        sources = load_sources(project_root / "sources.json")
        self.assertGreaterEqual(len(sources), 8)
        self.assertEqual({source.level for source in sources}, {"小学校", "中学校", "高等学校"})
        self.assertEqual(sources[0].default_grade, "1年生")
        sakurano_pages = {url for source in sources if source.collection_id == "sakurano" and source.source_group == "school" for url in source.page_urls}
        self.assertGreaterEqual(len(sakurano_pages), 5)
        for section in ("hp_jpage34", "hp_jpage14", "hp_jpage27", "hp_jpage38"):
            self.assertTrue(any(section in url for url in sakurano_pages))
        self.assertEqual(next(source for source in sources if source.id == "sakurano_gakudo").grades, ("全学年",))
        musashino_schools = {source.collection_id for source in sources if source.ward == "武蔵野市" and source.source_group == "school" and source.level == "小学校"}
        musashino_clubs = {source.id for source in sources if source.ward == "武蔵野市" and source.source_group == "after_school" and source.coverage_kind == "reference" and source.id.endswith("_gakudo")}
        self.assertEqual(len(musashino_schools), 12)
        self.assertEqual(len(musashino_clubs), 12)

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

    def test_sqlite_push_store_round_trips_subscription_and_scope_state(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        point = ec.derive_private_key(1, ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        with tempfile.TemporaryDirectory() as directory:
            store = SQLitePushSubscriptionStore(Path(directory) / "push.sqlite3")
            subscription = {
                "endpoint": "https://fcm.googleapis.com/subscription/test-only",
                "keys": {"p256dh": base64.urlsafe_b64encode(point).decode().rstrip("="), "auth": base64.urlsafe_b64encode(b"0123456789abcdef").decode().rstrip("=")},
            }
            scope = {"source_id": "sakurano", "grade": "1年生", "feed": "notices", "group": "school"}
            store.upsert(subscription, scope, "a" * 64, "2026-10-01")
            self.assertEqual(store.subscriptions()[0]["scope"], scope)
            store.save_scope_state("scope-key", {"known_ids": ["a"], "notified_ids": ["a"], "updated_at": 1.0})
            self.assertEqual(store.scope_state("scope-key")["known_ids"], ["a"])
            store.remove(subscription["endpoint"])
            self.assertEqual(store.subscriptions(), [])


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
        self.assertEqual(_date_labels(school, "学校だより 第7号\n令和8 年9 月18 日\n10月の行事予定"), ("2026/09/18", "2026/09/18"))
        self.assertEqual(_date_labels(grade, "学年だより（10月号）\n令和8年9月18日"), ("2026/10月号", "2026/09/18"))


class CatalogPayloadTests(unittest.TestCase):
    def test_source_file_is_json_serializable_for_api(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        payload = json.loads((project_root / "sources.json").read_text(encoding="utf-8"))
        self.assertIn("sources", payload)
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "sources.json"
            copy.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(len(load_sources(copy)), len(payload["sources"]))


class CatalogConcurrencyTests(unittest.TestCase):
    def test_simultaneous_all_source_requests_share_scan_futures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {"id": "one", "name": "One", "ward": "武蔵野市", "level": "小学校", "page_url": "https://example.test/one", "mode": "static", "static_text": "one"},
                            {"id": "two", "name": "Two", "ward": "武蔵野市", "level": "小学校", "page_url": "https://example.test/two", "mode": "static", "static_text": "two"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            service = CatalogService(SimpleNamespace(web_cache_ttl_seconds=300, web_catalog_max_wait_seconds=2), registry)
            calls: dict[str, int] = {"one": 0, "two": 0}
            calls_lock = threading.Lock()

            def fake_get_source(source_id: str, grade: str | None = None, refresh: bool = False) -> CatalogResult:
                with calls_lock:
                    calls[source_id] += 1
                time.sleep(0.05)
                source = next(item for item in service.sources if item.id == source_id)
                return CatalogResult(source, grade or source.default_grade, "2026-10-01T00:00:00+00:00", ())

            service.get_source = fake_get_source  # type: ignore[method-assign]
            try:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    first = executor.submit(service.get_many, source_id="all", grade="全学年")
                    second = executor.submit(service.get_many, source_id="all", grade="全学年")
                    first.result()
                    second.result()
                self.assertEqual(calls, {"one": 1, "two": 1})
            finally:
                service.close()

    def test_catalog_cache_survives_service_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            registry = Path(directory) / "sources.json"
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "sources": [
                            {"id": "one", "name": "One", "ward": "武蔵野市", "level": "小学校", "page_url": "https://example.test/one", "mode": "static", "static_text": "cached public notice"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            cache_path = Path(directory) / "catalog.sqlite3"
            settings = SimpleNamespace(
                web_cache_ttl_seconds=300,
                web_catalog_max_wait_seconds=2,
                web_catalog_cache_path=cache_path,
                request_timeout_seconds=1,
                max_document_bytes=1_000_000,
                user_agent="test",
            )
            first = CatalogService(settings, registry)
            try:
                original = first.get_source("one", "全学年", refresh=True)
            finally:
                first.close()

            second = CatalogService(settings, registry)
            second._scan_source = lambda *_args: (_ for _ in ()).throw(AssertionError("should use persistent cache"))  # type: ignore[method-assign]
            try:
                restored = second.get_source("one", "全学年")
            finally:
                second.close()
            self.assertEqual(restored.notices[0].text, original.notices[0].text)

    def test_expensive_mutation_endpoints_have_a_small_request_limit(self) -> None:
        limiter = _RequestRateLimiter()
        self.assertTrue(limiter.allow("127.0.0.1", "refresh", 1, 60)[0])
        allowed, retry_after = limiter.allow("127.0.0.1", "refresh", 1, 60)
        self.assertFalse(allowed)
        self.assertGreaterEqual(retry_after, 1)
