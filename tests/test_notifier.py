from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sakurano_line_notifier.extractor import GradeSectionNotFound, extract_grade_section, normalize_grade
from sakurano_line_notifier.fetcher import FetchedDocument, parse_relevant_links
from sakurano_line_notifier.formatter import MessageDocument, format_notification
from sakurano_line_notifier.config import Settings
from sakurano_line_notifier.line_client import LineClient, PushResult
from sakurano_line_notifier.pipeline import PipelineError, SchoolNotifier, build_notification_id, build_retry_key
from sakurano_line_notifier.state import empty_state, load_state, save_state


class ExtractorTests(unittest.TestCase):
    def test_normalize_grade_accepts_multiple_user_forms(self) -> None:
        self.assertEqual(normalize_grade("１"), "1年生")
        self.assertEqual(normalize_grade("第６学年"), "6年生")
        self.assertEqual(normalize_grade("全校"), "全学年")

    def test_extract_grade_section_stops_at_next_grade(self) -> None:
        source = """学年だより（８・９月号）
１年
学年からの連絡
〇持ち物：防災頭巾
２年
学年からの連絡
〇別の学年の内容
３年
学年からの連絡
"""
        result = extract_grade_section(source, "1年生")
        self.assertIn("防災頭巾", result)
        self.assertNotIn("別の学年", result)

    def test_missing_grade_does_not_fall_back_to_unrelated_text(self) -> None:
        with self.assertRaises(GradeSectionNotFound):
            extract_grade_section("学校だより\n２年\n連絡", "1年生")

    def test_extracts_compact_grade_when_pdf_split_characters_into_lines(self) -> None:
        source = "学\n年\nだ\nよ\nり\n１\n年\n学\n年\nか\nら\nの\n連\n絡\n〇持ち物\n２\n年\n学習予定"
        result = extract_grade_section(source, "1年生")
        self.assertIn("持ち物", result)
        self.assertNotIn("学習予定", result)


class LinkParserTests(unittest.TestCase):
    def test_filters_menu_link_and_classifies_news_links(self) -> None:
        html = """
        <a href="/modules/hp_jpage34/">学校／学年だより</a>
        <a href="/files/school.pdf">（表面）学校だより</a>
        <a href="/files/grade.pdf"><span>（裏面）</span>学年だより</a>
        <a href="/files/other.pdf">別資料</a>
        <a href="/files/grade.pdf">重複</a>
        <a href="/contact">お問い合わせ</a>
        """
        result = parse_relevant_links(html, "https://example.test/modules/hp_jpage34/")
        self.assertEqual([item.kind for item in result], ["school_news", "grade_news", "document"])
        self.assertEqual(result[1].url, "https://example.test/files/grade.pdf")


class FormatterTests(unittest.TestCase):
    def test_groups_original_text_and_keeps_source_link(self) -> None:
        document = MessageDocument(
            title="（裏面）学年だより",
            kind="grade_news",
            url="https://example.test/grade.pdf",
            reason="new_link",
            text="""１年
学年からの連絡
〇９月１日 持ち物：図書バッグ
〇９月５日までに提出してください。
学習予定
国語 こんなことがあったよ
""",
        )
        message = format_notification("1年生", [document])
        self.assertIn("【持ち物・準備】", message)
        self.assertIn("【提出物・締切】", message)
        self.assertIn("【学習予定】", message)
        self.assertIn("こんなことがあったよ", message)
        self.assertIn("https://example.test/grade.pdf", message)

    def test_message_is_bounded(self) -> None:
        document = MessageDocument(
            title="長い文書",
            kind="school_news",
            url="https://example.test/school.pdf",
            reason="content_changed",
            text="重要なお知らせ " * 1000,
        )
        message = format_notification("1年生", [document], max_chars=500)
        self.assertLessEqual(len(message), 500)
        self.assertIn("原文リンク", message)


class StateTests(unittest.TestCase):
    def test_state_round_trips_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "state.json"
            state = empty_state()
            state["baseline_grades"].append("1年生")
            save_state(path, state)
            loaded = load_state(path)
            self.assertEqual(loaded, state)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["version"], 1)


class IdempotencyTests(unittest.TestCase):
    def test_retry_key_is_stable_for_same_notification(self) -> None:
        document = MessageDocument("title", "grade_news", "https://example.test/a.pdf", "new_link", "本文")
        notification_id = build_notification_id("1年生", [document])
        self.assertEqual(build_retry_key(notification_id), build_retry_key(notification_id))
        self.assertNotEqual(build_retry_key(notification_id), build_retry_key(notification_id + "changed"))

    def test_line_409_is_treated_as_already_accepted(self) -> None:
        class Response:
            status_code = 409
            headers = {"x-line-request-id": "request-2"}

            def json(self):
                return {"message": "The retry key is already accepted"}

            def close(self):
                pass

        class Session:
            def __init__(self):
                self.calls = []

            def post(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return Response()

        session = Session()
        result = LineClient("secret-not-printed", "Urecipient", session=session).push_text("本文", "retry-key")
        self.assertTrue(result.accepted_via_retry)
        self.assertEqual(result.request_id, "request-2")
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0][1]["headers"]["X-Line-Retry-Key"], "retry-key")


class _FakeFetcher:
    def __init__(self, page_html: str, url: str, content: bytes) -> None:
        self.page_html = page_html
        self.url = url
        self.content = content
        self.etag = '"v1"'
        self.return_304 = False
        self.page_calls = 0
        self.document_calls = 0

    def fetch_page(self, url: str) -> str:
        self.page_calls += 1
        return self.page_html

    def fetch_document(self, url: str, conditional_headers: dict[str, str] | None = None) -> FetchedDocument:
        self.document_calls += 1
        if self.return_304 and conditional_headers:
            return FetchedDocument(url, None, "", self.etag, None, not_modified=True)
        return FetchedDocument(url, self.content, "text/html", self.etag, None)


class PipelineTests(unittest.TestCase):
    def _settings(self, state_path: Path, grade: str = "1年生", notify_existing: bool = False) -> Settings:
        return Settings(
            config_path=state_path.parent / "config.json",
            page_url="https://example.test/letters/",
            grade=grade,
            state_path=state_path,
            notify_existing_on_first_run=notify_existing,
            request_timeout_seconds=1,
            max_document_bytes=100_000,
            line_max_chars=4_800,
            pending_retry_max_hours=23,
            line_channel_access_token="token",
            line_to="Urecipient",
            user_agent="test",
        )

    def test_first_run_baselines_and_changed_html_creates_pending_notification(self) -> None:
        page = '<a href="grade.html">学年だより</a>'
        content_v1 = "<html><body><h1>１年</h1><p>学年からの連絡</p><p>〇持ち物：防災頭巾</p></body></html>".encode()
        content_v2 = "<html><body><h1>１年</h1><p>学年からの連絡</p><p>〇持ち物：防災頭巾と図書バッグ</p></body></html>".encode()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            fake = _FakeFetcher(page, "https://example.test/letters/grade.html", content_v1)
            notifier = SchoolNotifier(self._settings(state_path), fetcher=fake)

            first = notifier.prepare()
            self.assertEqual(first.status, "baselined")
            self.assertIsNone(load_state(state_path)["pending"])

            fake.return_304 = True
            unchanged = notifier.prepare()
            self.assertEqual(unchanged.status, "unchanged")

            fake.return_304 = False
            fake.content = content_v2
            fake.etag = '"v2"'
            changed = notifier.prepare()
            self.assertEqual(changed.status, "prepared")
            pending = load_state(state_path)["pending"]
            self.assertIsNotNone(pending)
            self.assertIn("図書バッグ", pending["message"])

    def test_pending_blocks_rescan_and_delivery_uses_one_line_request(self) -> None:
        page = '<a href="grade.html">学年だより</a>'
        content = "<html><body><h1>１年</h1><p>学年からの連絡</p><p>〇提出：9月1日まで</p></body></html>".encode()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            fake = _FakeFetcher(page, "https://example.test/letters/grade.html", content)
            settings = self._settings(state_path, notify_existing=True)
            notifier = SchoolNotifier(settings, fetcher=fake)
            prepared = notifier.prepare()
            self.assertEqual(prepared.status, "prepared")
            calls_after_prepare = fake.page_calls

            pending_again = notifier.prepare()
            self.assertEqual(pending_again.status, "pending_exists")
            self.assertEqual(fake.page_calls, calls_after_prepare)

            with patch("sakurano_line_notifier.pipeline.LineClient") as client_class:
                client_class.return_value.push_text.return_value = PushResult(200, "request-1")
                delivered = notifier.deliver()

            self.assertEqual(delivered.status, "sent")
            self.assertEqual(client_class.return_value.push_text.call_count, 1)
            sent_state = load_state(state_path)
            self.assertIsNone(sent_state["pending"])
            self.assertEqual(sent_state["notifications"][prepared.notification_id]["status"], "sent")

    def test_new_grade_has_its_own_baseline(self) -> None:
        page = '<a href="grade.html">学年だより</a>'
        content = "<html><body><h1>１年</h1><p>一年の連絡</p><h1>２年</h1><p>二年の連絡</p></body></html>".encode()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            fake = _FakeFetcher(page, "https://example.test/letters/grade.html", content)
            first = SchoolNotifier(self._settings(state_path, grade="1"), fetcher=fake)
            self.assertEqual(first.prepare().grade, "1年生")
            second = SchoolNotifier(self._settings(state_path, grade="2年生"), fetcher=fake)
            result = second.prepare()
            self.assertEqual(result.status, "baselined")
            self.assertEqual(set(load_state(state_path)["baseline_grades"]), {"1年生", "2年生"})


if __name__ == "__main__":
    unittest.main()
