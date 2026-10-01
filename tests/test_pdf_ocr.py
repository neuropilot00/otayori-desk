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

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from sakurano_line_notifier import pdf_ocr
from sakurano_line_notifier.extractor import ExtractionError, extract_document_text


HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
GOOD_TEXT = "学校からのお知らせです。持ち物を確認してください。明日は水筒と帽子を持って登校してください。"


def tsv(*words: tuple[str, float, int]) -> bytes:
    return (HEADER + "".join(
        f"5\t1\t1\t1\t{line}\t{index}\t0\t0\t100\t20\t{confidence}\t{word}\n"
        for index, (word, confidence, line) in enumerate(words, 1)
    )).encode()


def pdf_fixture(*pages: tuple[str, bytes | None]) -> bytes:
    """Real native text, image XObjects, and blank pages; no OCR dependency."""
    writer = PdfWriter()
    for text, pixels in pages:
        page = writer.add_blank_page(width=595, height=842)
        resources = DictionaryObject()
        commands = b""
        if text:
            font = DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            })
            resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
            commands += b"BT /F1 12 Tf 20 800 Td (" + text.encode("ascii") + b") Tj ET\n"
        if pixels is not None:
            scan = DecodedStreamObject()
            scan.set_data(pixels)
            scan.update({
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(2),
                NameObject("/Height"): NumberObject(2),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                NameObject("/BitsPerComponent"): NumberObject(8),
            })
            resources[NameObject("/XObject")] = DictionaryObject({NameObject("/Scan"): scan})
            commands += b"q 500 0 0 700 20 20 cm /Scan Do Q\n"
        page[NameObject("/Resources")] = resources
        if commands:
            content = DecodedStreamObject()
            content.set_data(commands)
            page[NameObject("/Contents")] = content
    payload = io.BytesIO()
    writer.write(payload)
    return payload.getvalue()


class PdfOcrTests(unittest.TestCase):
    def setUp(self):
        with pdf_ocr._cache_lock:
            pdf_ocr._cache.clear()

    def test_hybrid_pdf_recovers_image_pages_in_order_without_replacing_native_text(self):
        payload = pdf_fixture(("Native first", None), ("", b"\x00" * 4), ("Native third", None))
        with patch.object(pdf_ocr, "_extract_uncached", return_value={2: GOOD_TEXT}) as work:
            self.assertEqual(extract_document_text(payload), "Native first\n" + GOOD_TEXT + "\nNative third")
        work.assert_called_once_with(payload, (2,))

    def test_hybrid_ocr_failure_cannot_return_partial_native_text(self):
        payload = pdf_fixture(("Native first", None), ("", b"\x00" * 4))
        with patch.object(pdf_ocr, "_extract_uncached", side_effect=pdf_ocr.PdfOcrError("low OCR quality on page 2")):
            with self.assertRaisesRegex(ExtractionError, "page 2"):
                extract_document_text(payload)
        self.assertEqual(len(pdf_ocr._cache), 0)

    def test_native_and_truly_blank_pages_do_not_use_ocr(self):
        payload = pdf_fixture(("Native first", None), ("", None), ("Native third", None))
        with patch.object(pdf_ocr, "_extract_uncached") as work:
            self.assertEqual(extract_document_text(payload), "Native first\n\nNative third")
            with self.assertRaisesRegex(ExtractionError, "no readable"):
                extract_document_text(pdf_fixture(("", None)))
        work.assert_not_called()

    def test_numeric_header_with_image_is_read_but_plain_number_is_native(self):
        for label in ("2", "- 2 -", "2026/10/01"):
            with self.subTest(label=label):
                payload = pdf_fixture((label, b"\x00" * 4), ("3", None))
                with patch.object(pdf_ocr, "_extract_uncached", return_value={1: GOOD_TEXT}) as work:
                    self.assertEqual(extract_document_text(payload), GOOD_TEXT + "\n3")
                work.assert_called_once_with(payload, (1,))

    def test_numeric_header_ocr_failure_is_not_success(self):
        payload = pdf_fixture(("1", b"\x00" * 4))
        with patch.object(pdf_ocr, "_extract_uncached", side_effect=pdf_ocr.PdfOcrError("low OCR quality")):
            with self.assertRaisesRegex(ExtractionError, "low OCR quality"):
                extract_document_text(payload)

    def test_native_body_with_illustration_is_retained_without_ocr(self):
        payload = pdf_fixture(("Native body text", b"\x00" * 4))
        with patch.object(pdf_ocr, "_extract_uncached") as work:
            self.assertEqual(extract_document_text(payload), "Native body text\n")
        work.assert_not_called()

    def test_sparse_native_header_cannot_hide_dense_vector_body(self):
        writer = PdfWriter()
        writer.append(PdfReader(io.BytesIO(pdf_fixture(("Newsletter header", None)))))
        page = writer.pages[0]
        content = DecodedStreamObject()
        content.set_data(page.get_contents().get_data() + b" 20 20 m " + b"21 21 22 22 23 23 c " * 1000 + b" f")
        page[NameObject("/Contents")] = content
        payload = io.BytesIO()
        writer.write(payload)
        with patch.object(pdf_ocr, "_extract_uncached", return_value={1: GOOD_TEXT}) as work:
            self.assertEqual(extract_document_text(payload.getvalue()), GOOD_TEXT)
        work.assert_called_once_with(payload.getvalue(), (1,))
        with patch.object(pdf_ocr, "_extract_uncached", side_effect=pdf_ocr.PdfOcrError("low OCR quality")):
            pdf_ocr._cache.clear()
            with self.assertRaisesRegex(ExtractionError, "low OCR quality"):
                extract_document_text(payload.getvalue())

    def test_textless_vectors_inline_images_and_forms_cannot_be_skipped(self):
        for kind in ("vectors", "inline", "form", "annotation"):
            with self.subTest(kind=kind):
                writer = PdfWriter()
                writer.append(PdfReader(io.BytesIO(pdf_fixture(("Native first", None), ("", b"\x00" * 4)))))
                page = writer.pages[1]
                content = DecodedStreamObject()
                if kind == "vectors":
                    content.set_data(b"0 g 20 20 400 600 re f")
                    page[NameObject("/Contents")] = content
                elif kind == "inline":
                    content.set_data(b"q 500 0 0 700 20 20 cm BI /W 2 /H 2 /BPC 8 /CS /G ID \x00\x00\x00\x00 EI Q")
                    page[NameObject("/Contents")] = content
                elif kind == "form":
                    form = DecodedStreamObject()
                    form.set_data(page.get_contents().get_data())
                    form.update({NameObject("/Type"): NameObject("/XObject"),
                                 NameObject("/Subtype"): NameObject("/Form"),
                                 NameObject("/BBox"): page.mediabox,
                                 NameObject("/Resources"): page["/Resources"]})
                    page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject("/Form"): form})})
                    content.set_data(b"q /Form Do Q")
                    page[NameObject("/Contents")] = content
                else:
                    from pypdf.annotations import FreeText
                    del page["/Contents"]
                    writer.add_annotation(1, FreeText(text="Image notice", rect=(20, 20, 500, 700)))
                payload = io.BytesIO()
                writer.write(payload)
                with patch.object(pdf_ocr, "_extract_uncached", return_value={2: GOOD_TEXT}) as work:
                    self.assertEqual(extract_document_text(payload.getvalue()), "Native first\n" + GOOD_TEXT)
                work.assert_called_once_with(payload.getvalue(), (2,))

    def test_pdf_byte_limit_precedes_native_parsing(self):
        with patch.object(pdf_ocr, "MAX_PDF_BYTES", 10), patch("pypdf.PdfReader") as reader:
            with self.assertRaisesRegex(ExtractionError, "byte safety limit"):
                extract_document_text(b"%PDF" + b"x" * 7)
        reader.assert_not_called()

    def test_large_native_document_can_ocr_one_page_with_same_six_page_cap(self):
        payload = pdf_fixture(*([("Native body", None)] * 49), ("", b"\x00" * 4))
        with patch.object(pdf_ocr, "_extract_uncached", return_value={50: GOOD_TEXT}) as work:
            self.assertEqual(extract_document_text(payload), "Native body\n" * 49 + GOOD_TEXT)
        work.assert_called_once_with(payload, (50,))
        payload = pdf_fixture(("Native body", None), *([("", b"\x00" * 4)] * 7))
        with patch.object(pdf_ocr, "_extract_uncached") as work:
            with self.assertRaisesRegex(ExtractionError, "OCR supports 1-6 pages; got 7"):
                extract_document_text(payload)
        work.assert_not_called()

    def test_six_scans_and_structural_blanks_fit_ocr_cap(self):
        payload = pdf_fixture(*([("", b"\x00" * 4)] * 6), *([("", None)] * 2))
        with patch.object(pdf_ocr, "_extract_uncached", return_value={n: GOOD_TEXT for n in range(1, 7)}) as work:
            self.assertEqual(extract_document_text(payload), "\n".join([GOOD_TEXT] * 6 + ["", ""]))
        work.assert_called_once_with(payload, (1, 2, 3, 4, 5, 6))

    def test_merged_native_and_ocr_text_obey_total_character_limit(self):
        payload = pdf_fixture(("a" * 60, None), ("", b"\x00" * 4))
        with patch.object(pdf_ocr, "MAX_TEXT_CHARACTERS", 100), patch.object(
            pdf_ocr, "_extract_uncached", return_value={2: GOOD_TEXT}
        ), self.assertRaisesRegex(ExtractionError, "text exceeds safety limit"):
            extract_document_text(payload)

    def test_incomplete_page_result_is_rejected_and_not_cached(self):
        payload = pdf_fixture(("Native body", None), ("", b"\x00" * 4), ("", b"\x00" * 4))
        with patch.object(pdf_ocr, "_extract_uncached", return_value={2: GOOD_TEXT}):
            with self.assertRaisesRegex(ExtractionError, "incomplete page selection"):
                extract_document_text(payload)
        self.assertEqual(len(pdf_ocr._cache), 0)

    def test_image_only_pdf_uses_fallback_and_returns_body_without_prefix(self):
        payload = pdf_fixture(("", b"\x00" * 4))
        with patch.object(pdf_ocr, "extract_pdf_ocr_pages", return_value={1: GOOD_TEXT}) as ocr:
            self.assertEqual(extract_document_text(payload), GOOD_TEXT)
        ocr.assert_called_once_with(payload, page_count=1, page_numbers=(1,))

    def test_successful_text_pdf_and_html_never_use_ocr(self):
        page = Mock()
        page.extract_text.return_value = "持ち物：水筒"
        with patch.object(pdf_ocr, "extract_pdf_ocr_pages") as ocr, patch(
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
                pdf_ocr, "extract_pdf_ocr_pages"
            ) as ocr, self.assertRaises(ExtractionError):
                extract_document_text(b"%PDF-test")
            ocr.assert_not_called()

    def test_corrupt_pdf_does_not_trigger_ocr(self):
        with patch.object(pdf_ocr, "extract_pdf_ocr_pages") as ocr, self.assertRaises(ExtractionError):
            extract_document_text(b"%PDF-broken")
        ocr.assert_not_called()

    def test_ocr_failure_is_existing_extraction_error_with_reason(self):
        with patch.object(
            pdf_ocr, "extract_pdf_ocr_pages", side_effect=pdf_ocr.PdfOcrError("low OCR quality")
        ), self.assertRaisesRegex(ExtractionError, "low OCR quality"):
            extract_document_text(pdf_fixture(("", b"\x00" * 4)))

    def test_ocr_byte_and_page_caps_before_subprocess(self):
        with patch.object(pdf_ocr, "_extract_uncached") as work, patch.object(pdf_ocr, "MAX_PDF_BYTES", 20):
            for payload, pages in ((b"x" * 21, 1), (b"x", 0), (b"x", 7)):
                with self.subTest(pages=pages), self.assertRaises(pdf_ocr.PdfOcrError):
                    pdf_ocr.extract_pdf_ocr(payload, page_count=pages)
            work.assert_not_called()

    def test_selected_page_bounds_are_checked_before_subprocess(self):
        with patch.object(pdf_ocr, "_extract_uncached") as work:
            for pages, numbers in ((0, (1,)), (51, (1,)), (2, (0,)), (2, (-1,)), (2, (3,)),
                                   (2, (1, 1)), (2, (True,)), (2, (1.5,)), (2, ()), (8, tuple(range(1, 8)))):
                with self.subTest(pages=pages, numbers=numbers), self.assertRaises(pdf_ocr.PdfOcrError):
                    pdf_ocr.extract_pdf_ocr_pages(b"pdf", page_count=pages, page_numbers=numbers)
        work.assert_not_called()

    def test_page_selection_is_in_cache_key_and_cached_results_are_not_mutable(self):
        def work(payload, numbers):
            return {number: GOOD_TEXT + str(number) for number in numbers}

        with patch.object(pdf_ocr, "_extract_uncached", side_effect=work) as run:
            for numbers in ((2,), (1,), (2,), (1, 2), (2, 1)):
                pages = pdf_ocr.extract_pdf_ocr_pages(b"same", page_count=2, page_numbers=numbers)
                self.assertEqual(pages, {n: GOOD_TEXT + str(n) for n in numbers})
                pages.clear()
            self.assertEqual(run.call_count, 3)
            pdf_ocr.extract_pdf_ocr_pages(b"same", page_count=3, page_numbers=(2,))
            self.assertEqual(run.call_count, 4)

    def test_content_cache_avoids_repeat_work(self):
        with patch.object(pdf_ocr, "_extract_uncached", return_value={1: GOOD_TEXT}) as work:
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"same bytes", page_count=1), GOOD_TEXT)
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"same bytes", page_count=1), GOOD_TEXT)
            work.assert_called_once()
            pdf_ocr.extract_pdf_ocr(b"changed bytes", page_count=1)
            self.assertEqual(work.call_count, 2)

    def test_cache_is_bounded_and_uses_lru_eviction(self):
        with patch.object(pdf_ocr, "CACHE_ENTRIES", 2), patch.object(
            pdf_ocr, "_extract_uncached", return_value={1: GOOD_TEXT}
        ) as work:
            for payload in (b"a", b"b", b"a", b"c", b"b"):
                pdf_ocr.extract_pdf_ocr(payload, page_count=1)
            self.assertEqual(work.call_count, 4)
            self.assertEqual(len(pdf_ocr._cache), 2)

    def test_errors_are_not_cached_and_slot_is_released(self):
        with patch.object(pdf_ocr, "_extract_uncached", side_effect=[pdf_ocr.PdfOcrError("bad"), {1: GOOD_TEXT}]) as work:
            with self.assertRaises(pdf_ocr.PdfOcrError):
                pdf_ocr.extract_pdf_ocr(b"retry", page_count=1)
            self.assertEqual(pdf_ocr.extract_pdf_ocr(b"retry", page_count=1), GOOD_TEXT)
            self.assertEqual(work.call_count, 2)

    def test_simultaneous_identical_requests_run_ocr_once(self):
        entered, finish = threading.Event(), threading.Event()

        def work(*args):
            entered.set()
            self.assertTrue(finish.wait(2))
            return {1: GOOD_TEXT}

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
            return {1: GOOD_TEXT}

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
            documents[f"https://example.test/{number}.pdf"] = pdf_fixture(("", bytes([number]) * 4))
        barrier = threading.Barrier(4)

        def fetch(url):
            barrier.wait(timeout=2)
            return FetchedDocument(url, documents[url], "application/pdf", None, None)

        def slow_ocr(*args):
            time.sleep(0.04)
            return {1: GOOD_TEXT}

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

    def test_catalog_retains_failed_hybrid_as_original_only(self):
        from sakurano_line_notifier.fetcher import FetchedDocument
        from sakurano_line_notifier.web_catalog import CatalogService, _parse_source

        source = _parse_source({
            "id": "hybrid", "name": "Hybrid school", "ward": "武蔵野市", "level": "小学校",
            "page_url": "https://example.test/letters/", "mode": "pdf", "max_documents": 4,
        }, 0)
        url = "https://example.test/hybrid.pdf"
        payload = pdf_fixture(("Native first", None), ("", b"\x00" * 4))
        service = CatalogService.__new__(CatalogService)
        service.settings = SimpleNamespace(request_timeout_seconds=5, max_document_bytes=10_000_000, user_agent="ocr-test")
        fetcher = Mock()
        fetcher.fetch_page.return_value = f'<a href="{url}">学校だより</a>'
        fetcher.fetch_document.return_value = FetchedDocument(url, payload, "application/pdf", None, None)
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher), patch.object(
            pdf_ocr, "_extract_uncached", side_effect=pdf_ocr.PdfOcrError("low OCR quality on page 2")
        ):
            result = service._scan_source(source, "全学年")
        self.assertEqual(len(result.notices), 1)
        self.assertEqual(result.notices[0].url, url)
        self.assertEqual(result.notices[0].extraction_status, "original_only")
        self.assertEqual(result.coverage()["readable_count"], 0)
        self.assertIn("page 2", " ".join(result.warnings))

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
            self.assertTrue(pdf_ocr._check_image(image))
            image.write_bytes(b"P5\n2 2\n255\n" + b"\xff" * 3 + b"\xfe")
            self.assertFalse(pdf_ocr._check_image(image))
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
                Path(command[-1]).with_suffix(".pgm").write_bytes(b"P5\n2 2\n255\n" + b"\x00" * 4)
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

    def test_selected_pages_share_one_deadline_and_white_raster_skips_recognition(self):
        calls = []
        locations = []

        def run(command, deadline, stage):
            calls.append((command, deadline))
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                image = Path(command[-1]).with_suffix(".pgm")
                locations.append(image)
                # Page 4 is provably blank; page 7 must go through quality checks.
                pixels = b"\xff" * 4 if command[2] == "4" else b"\x00" * 4
                image.write_bytes(b"P5\n2 2\n255\n" + pixels)
                return b""
            return tsv((GOOD_TEXT, 95, 1))

        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", side_effect=run
        ):
            pages = pdf_ocr.extract_pdf_ocr_pages(b"hybrid", page_count=8, page_numbers=(4, 7))
        self.assertEqual(pages, {4: "", 7: GOOD_TEXT})
        self.assertEqual(len({deadline for _, deadline in calls}), 1)
        renders = [cmd for cmd, _ in calls if cmd[0].endswith("pdftoppm")]
        self.assertEqual([cmd[1:5] for cmd in renders], [["-f", "4", "-l", "4"], ["-f", "7", "-l", "7"]])
        self.assertEqual(len([cmd for cmd, _ in calls if "--psm" in cmd]), 1)
        self.assertTrue(all(not path.exists() for path in locations))

    def test_selected_ocr_failure_reports_original_page_and_rejects_all_results(self):
        def run(command, deadline, stage):
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                Path(command[-1]).with_suffix(".pgm").write_bytes(b"P5\n2 2\n255\n" + b"\x00" * 4)
                return b""
            return tsv((GOOD_TEXT, 95 if stage.endswith("2") else 10, 1))

        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", side_effect=run
        ), self.assertRaisesRegex(pdf_ocr.PdfOcrError, "low OCR quality on page 5"):
            pdf_ocr.extract_pdf_ocr_pages(b"hybrid", page_count=8, page_numbers=(2, 5))
        self.assertEqual(len(pdf_ocr._cache), 0)

    def test_ocr_combined_text_and_final_document_deadline_are_bounded(self):
        def run(command, deadline, stage):
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                Path(command[-1]).with_suffix(".pgm").write_bytes(b"P5\n2 2\n255\n" + b"\x00" * 4)
                return b""
            return tsv((GOOD_TEXT, 95, 1))

        with patch.object(pdf_ocr.shutil, "which", side_effect=lambda tool: "/usr/bin/" + tool), patch.object(
            pdf_ocr, "_run", side_effect=run
        ):
            with patch.object(pdf_ocr, "MAX_TEXT_CHARACTERS", len(GOOD_TEXT) * 2), self.assertRaisesRegex(
                pdf_ocr.PdfOcrError, "text exceeds safety limit"
            ):
                pdf_ocr.extract_pdf_ocr_pages(b"long", page_count=6, page_numbers=(2, 5))
            with patch.object(pdf_ocr.time, "monotonic", side_effect=[100, 221]), self.assertRaisesRegex(
                pdf_ocr.PdfOcrError, "document time limit"
            ):
                pdf_ocr.extract_pdf_ocr_pages(b"slow", page_count=6, page_numbers=(2, 5))
        self.assertEqual(len(pdf_ocr._cache), 0)

    def test_partial_document_is_rejected_not_cached_and_temp_files_removed(self):
        locations = []

        def run(command, deadline, stage):
            if "--list-langs" in command:
                return b"jpn\n"
            if command[0].endswith("pdftoppm"):
                image = Path(command[-1]).with_suffix(".pgm")
                locations.append(image)
                image.write_bytes(b"P5\n2 2\n255\n" + b"\x00" * 4)
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
