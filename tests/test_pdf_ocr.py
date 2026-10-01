from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pypdf import PdfWriter

from sakurano_line_notifier import pdf_ocr
from sakurano_line_notifier.extractor import ExtractionError, extract_document_text


HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
GOOD_TEXT = "学校からのお知らせです。持ち物を確認してください。明日は水筒と帽子を持って登校してください。"


def tsv(*words: tuple[str, float, int]) -> bytes:
    return (HEADER + "".join(
        f"5\t1\t1\t1\t{line}\t{index}\t0\t0\t100\t20\t{confidence}\t{word}\n"
        for index, (word, confidence, line) in enumerate(words, 1)
    )).encode()


class PdfOcrTests(unittest.TestCase):
    def setUp(self):
        with pdf_ocr._cache_lock:
            pdf_ocr._cache.clear()

    def test_image_only_pdf_uses_fallback_and_returns_body_without_prefix(self):
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        payload = io.BytesIO()
        writer.write(payload)
        with patch.object(pdf_ocr, "extract_pdf_ocr", return_value=GOOD_TEXT) as ocr:
            self.assertEqual(extract_document_text(payload.getvalue()), GOOD_TEXT)
        ocr.assert_called_once_with(payload.getvalue(), page_count=1)

    def test_successful_text_pdf_and_html_never_use_ocr(self):
        page = Mock()
        page.extract_text.return_value = "持ち物：水筒"
        with patch.object(pdf_ocr, "extract_pdf_ocr") as ocr, patch(
            "pypdf.PdfReader", return_value=Mock(is_encrypted=False, pages=[page])
        ):
            self.assertEqual(extract_document_text(b"%PDF-test"), "持ち物：水筒")
            self.assertEqual(extract_document_text(b"<p>notice</p>"), "notice")
            ocr.assert_not_called()

    def test_existing_pdf_guards_cannot_be_bypassed_by_ocr(self):
        for reader in (
            Mock(is_encrypted=True, pages=[]),
            Mock(is_encrypted=False, pages=[Mock()] * 51),
            Mock(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value="a" * 200_001))]),
        ):
            with self.subTest(reader=reader), patch("pypdf.PdfReader", return_value=reader), patch.object(
                pdf_ocr, "extract_pdf_ocr"
            ) as ocr, self.assertRaises(ExtractionError):
                extract_document_text(b"%PDF-test")
            ocr.assert_not_called()

    def test_corrupt_pdf_does_not_trigger_ocr(self):
        with patch.object(pdf_ocr, "extract_pdf_ocr") as ocr, self.assertRaises(ExtractionError):
            extract_document_text(b"%PDF-broken")
        ocr.assert_not_called()

    def test_ocr_failure_is_existing_extraction_error_with_reason(self):
        reader = Mock(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value=""))])
        with patch("pypdf.PdfReader", return_value=reader), patch.object(
            pdf_ocr, "extract_pdf_ocr", side_effect=pdf_ocr.PdfOcrError("low OCR quality")
        ), self.assertRaisesRegex(ExtractionError, "low OCR quality"):
            extract_document_text(b"%PDF-test")

    def test_ocr_byte_and_page_caps_before_subprocess(self):
        with patch.object(pdf_ocr, "_extract_uncached") as work, patch.object(pdf_ocr, "MAX_PDF_BYTES", 20):
            for payload, pages in ((b"x" * 21, 1), (b"x", 0), (b"x", 7)):
                with self.subTest(pages=pages), self.assertRaises(pdf_ocr.PdfOcrError):
                    pdf_ocr.extract_pdf_ocr(payload, page_count=pages)
            work.assert_not_called()

    def test_content_cache_avoids_repeat_work(self):
        with patch.object(pdf_ocr, "_extract_uncached", return_value=GOOD_TEXT) as work:
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"same bytes", page_count=1), GOOD_TEXT)
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"same bytes", page_count=1), GOOD_TEXT)
            work.assert_called_once()
            pdf_ocr.extract_pdf_ocr(b"changed bytes", page_count=1)
            self.assertEqual(work.call_count, 2)

    def test_cache_is_bounded_and_uses_lru_eviction(self):
        with patch.object(pdf_ocr, "CACHE_ENTRIES", 2), patch.object(
            pdf_ocr, "_extract_uncached", return_value=GOOD_TEXT
        ) as work:
            for payload in (b"a", b"b", b"a", b"c", b"b"):
                pdf_ocr.extract_pdf_ocr(payload, page_count=1)
            self.assertEqual(work.call_count, 4)
            self.assertEqual(len(pdf_ocr._cache), 2)

    def test_errors_are_not_cached_and_slot_is_released(self):
        with patch.object(pdf_ocr, "_extract_uncached", side_effect=[pdf_ocr.PdfOcrError("bad"), GOOD_TEXT]) as work:
            with self.assertRaises(pdf_ocr.PdfOcrError):
                pdf_ocr.extract_pdf_ocr(b"retry", page_count=1)
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"retry", page_count=1), GOOD_TEXT)
            self.assertEqual(work.call_count, 2)

    def test_simultaneous_identical_requests_run_ocr_once(self):
        entered, finish = threading.Event(), threading.Event()

        def work(*args):
            entered.set()
            self.assertTrue(finish.wait(2))
            return GOOD_TEXT

        with patch.object(pdf_ocr, "_extract_uncached", side_effect=work) as run, ThreadPoolExecutor(2) as executor:
            first = executor.submit(pdf_ocr.extract_pdf_ocr, b"shared", page_count=1)
            self.assertTrue(entered.wait(2))
            second = executor.submit(pdf_ocr.extract_pdf_ocr, b"shared", page_count=1)
            finish.set()
            self.assertEqual(first.result(2), GOOD_TEXT)
            self.assertEqual(second.result(2), GOOD_TEXT)
            self.assertEqual(run.call_count, 1)

    def test_different_documents_share_one_ocr_slot(self):
        entered, finish = threading.Event(), threading.Event()

        def work(*args):
            entered.set()
            self.assertTrue(finish.wait(2))
            return GOOD_TEXT

        with patch.object(pdf_ocr, "QUEUE_TIMEOUT_SECONDS", 0.02), patch.object(
            pdf_ocr, "_extract_uncached", side_effect=work
        ) as run, ThreadPoolExecutor(1) as executor:
            first = executor.submit(pdf_ocr.extract_pdf_ocr, b"first", page_count=1)
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(pdf_ocr.PdfOcrError, "busy"):
                    pdf_ocr.extract_pdf_ocr(b"second", page_count=1)
                self.assertEqual(run.call_count, 1)
            finally:
                finish.set()
            self.assertEqual(first.result(2), GOOD_TEXT)

    def test_four_catalog_workers_wait_for_ocr_without_busy_warnings(self):
        from sakurano_line_notifier.fetcher import FetchedDocument
        from sakurano_line_notifier.web_catalog import CatalogService, _parse_source

        # Exercise the real catalog executor and extractor with four distinct
        # image-only PDFs. A barrier guarantees simultaneous OCR submissions.
        source = _parse_source({
            "id": "ocr", "name": "OCR school", "ward": "武蔵野市", "level": "小学校",
            "page_url": "https://example.test/letters/", "mode": "pdf", "max_documents": 4,
        }, 0)
        documents = {}
        for number in range(4):
            writer = PdfWriter()
            writer.add_blank_page(width=595, height=842)
            writer.add_metadata({"/Title": str(number)})
            payload = io.BytesIO()
            writer.write(payload)
            documents[f"https://example.test/{number}.pdf"] = payload.getvalue()
        barrier = threading.Barrier(4)

        def fetch(url):
            barrier.wait(timeout=2)
            return FetchedDocument(url, documents[url], "application/pdf", None, None)

        def slow_ocr(*args):
            time.sleep(0.04)
            return GOOD_TEXT

        service = CatalogService.__new__(CatalogService)
        service.settings = SimpleNamespace(request_timeout_seconds=5, max_document_bytes=10_000_000, user_agent="ocr-test")
        fetcher = Mock()
        fetcher.fetch_page.return_value = "".join(f'<a href="{url}">{i}号</a>' for i, url in enumerate(documents))
        fetcher.fetch_document.side_effect = fetch
        # Three bounded OCR jobs may be ahead of the last catalog worker.
        self.assertGreaterEqual(pdf_ocr.QUEUE_TIMEOUT_SECONDS, 3 * pdf_ocr.DOCUMENT_TIMEOUT_SECONDS)
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher), patch.object(
            pdf_ocr, "_extract_uncached", side_effect=slow_ocr
        ) as run:
            result = service._scan_source(source, "全学年")
        self.assertEqual(len(result.notices), 4)
        self.assertEqual(result.warnings, ())
        self.assertEqual(run.call_count, 4)

    def test_missing_tools_and_language_fail_clearly(self):
        with patch.object(pdf_ocr.shutil, "which", return_value=None), self.assertRaisesRegex(
            pdf_ocr.PdfOcrError, "install poppler-utils"
        ):
            pdf_ocr.extract_pdf_ocr(b"pdf", page_count=1)
        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", return_value=b"List of available languages (1):\neng\n"
        ), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "jpn.*missing"):
            pdf_ocr.extract_pdf_ocr(b"pdf", page_count=1)

    def test_good_japanese_retains_lines_and_ascii_word_boundaries(self):
        data = tsv((GOOD_TEXT, 95, 1), ("日本", 95, 2), ("語", 95, 2), ("School", 95, 3), ("News", 95, 3))
        self.assertEqual(pdf_ocr._text_from_tsv(data, 1), GOOD_TEXT + "\n日本語\nSchool News")

    def test_low_confidence_blank_or_non_japanese_text_is_rejected(self):
        for data in (HEADER.encode(), tsv((GOOD_TEXT, 40, 1)), tsv(("English only " * 40, 95, 1))):
            with self.subTest(data=data[:60]), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "low OCR quality on page 2"):
                pdf_ocr._text_from_tsv(data, 2)

    def test_confident_short_tokens_cannot_hide_long_bad_words(self):
        data = tsv(*[("。", 100, 1)] * 100, (GOOD_TEXT * 10, 20, 2))
        with self.assertRaisesRegex(pdf_ocr.PdfOcrError, "low OCR quality"):
            pdf_ocr._text_from_tsv(data, 1)

    def test_high_mean_cannot_hide_many_uncertain_characters(self):
        data = tsv((GOOD_TEXT * 3, 100, 1), (GOOD_TEXT, 49, 2))
        with self.assertRaisesRegex(pdf_ocr.PdfOcrError, "uncertain 25%"):
            pdf_ocr._text_from_tsv(data, 1)

    def test_invalid_confidence_and_tsv_rejected(self):
        for data in (b"not a tsv", b"\xff", tsv((GOOD_TEXT, float("nan"), 1)), tsv((GOOD_TEXT, -1, 1)), tsv((GOOD_TEXT, 101, 1))):
            with self.subTest(data=data[:60]), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "invalid confidence"):
                pdf_ocr._text_from_tsv(data, 1)

    def test_ocr_text_limit(self):
        with patch.object(pdf_ocr, "MAX_TEXT_CHARACTERS", 50), self.assertRaisesRegex(
            pdf_ocr.PdfOcrError, "text exceeds safety limit"
        ):
            pdf_ocr._text_from_tsv(tsv((GOOD_TEXT * 2, 95, 1)), 1)

    def test_image_header_pixel_size_and_file_size_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "page.pgm"
            image.write_bytes(b"P5\n2 2\n255\n" + b"\xff" * 4)
            pdf_ocr._check_image(image)
            for content in (b"bad", b"P5\n3201 1\n255\n", b"P5\n0 2\n255\n", b"P5\n2 2\n255\n\xff"):
                image.write_bytes(content)
                with self.subTest(content=content), self.assertRaises(pdf_ocr.PdfOcrError):
                    pdf_ocr._check_image(image)
            image.write_bytes(b"12345")
            with patch.object(pdf_ocr, "MAX_IMAGE_BYTES", 4), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "byte limit"):
                pdf_ocr._check_image(image)

    def test_multiple_pages_use_one_bounded_image_and_cleanup(self):
        commands = []

        def run(command, deadline, stage):
            commands.append(command)
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                Path(command[-1]).with_suffix(".pgm").write_bytes(b"P5\n2 2\n255\n" + b"\xff" * 4)
                return b""
            return tsv((GOOD_TEXT, 95, 1))

        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", side_effect=run
        ):
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"pdf", page_count=2), GOOD_TEXT + "\n" + GOOD_TEXT)
        renders = [command for command in commands if command[0].endswith("pdftoppm")]
        self.assertEqual(len(renders), 2)
        for number, command in enumerate(renders, 1):
            self.assertEqual(command[1:5], ["-f", str(number), "-l", str(number)])
            self.assertIn("-singlefile", command)
            self.assertEqual(command[command.index("-scale-to") + 1], "3200")
            self.assertFalse(Path(command[-2]).exists())

    def test_partial_document_is_rejected_not_cached_and_temp_files_removed(self):
        locations = []

        def run(command, deadline, stage):
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                image = Path(command[-1]).with_suffix(".pgm")
                locations.append(image)
                image.write_bytes(b"P5\n2 2\n255\n" + b"\xff" * 4)
                return b""
            return tsv((GOOD_TEXT, 95 if len(locations) == 1 else 10, 1))

        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", side_effect=run
        ), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "page 2"):
            pdf_ocr.extract_pdf_ocr(b"partial", page_count=2)
        self.assertEqual(len(pdf_ocr._cache), 0)
        self.assertTrue(all(not path.exists() for path in locations))

    def test_subprocess_deadline_timeout_and_failure_are_bounded(self):
        with patch.object(pdf_ocr.subprocess, "run") as run, self.assertRaisesRegex(pdf_ocr.PdfOcrError, "time limit"):
            pdf_ocr._run(["tool"], time.monotonic() - 1, "test")
        run.assert_not_called()
        for error in (subprocess.TimeoutExpired("tool", 1), subprocess.CalledProcessError(1, "tool")):
            with patch.object(pdf_ocr.subprocess, "run", side_effect=error) as run, self.assertRaises(pdf_ocr.PdfOcrError):
                pdf_ocr._run(["/usr/bin/tool"], time.monotonic() + 100, "test")
            self.assertEqual(run.call_args.kwargs["timeout"], 30)
            self.assertEqual(run.call_args.kwargs["env"]["OMP_THREAD_LIMIT"], "1")
            self.assertNotIn("shell", run.call_args.kwargs)
            self.assertNotIn("preexec_fn", run.call_args.kwargs)

    @unittest.skipUnless(sys.platform in ("darwin", "linux"), "POSIX resource limits")
    def test_real_child_resource_limits_output_limit_and_timeout(self):
        code = "import resource,json; print(json.dumps([resource.getrlimit(resource.RLIMIT_FSIZE), resource.getrlimit(resource.RLIMIT_CPU)]))"
        limits = json.loads(pdf_ocr._run([sys.executable, "-c", code], time.monotonic() + 5, "test"))
        self.assertEqual(limits, [[16_000_000, 16_000_000], [30, 30]])
        with patch.object(pdf_ocr, "MAX_OUTPUT_BYTES", 20), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "output exceeds"):
            pdf_ocr._run([sys.executable, "-c", "print('a' * 21)"], time.monotonic() + 5, "test")
        with self.assertRaisesRegex(pdf_ocr.PdfOcrError, "timed out"):
            pdf_ocr._run([sys.executable, "-c", "import time; time.sleep(5)"], time.monotonic() + 0.1, "test")


if __name__ == "__main__":
    unittest.main()
