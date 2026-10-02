from __future__ import annotations

import unicodedata
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier import pdf_ocr
from sakurano_line_notifier.extractor import ExtractionError, extract_document_text


# Exact first 220 native characters from 202609-6.pdf and 202609-7.pdf,
# page 1, read with pypdf 6.19.0. These visibly Japanese pages have broken
# Identity-H text mappings, including unassigned code points and controls.
OONODEN = (
    'ʮͳͭ·ͭΓʯͷήʔϜίʔφʔ\u0378Ͳ͏Ͱ͔ͨ͠ʁ \n೦ \n͖ Ͷ Μ \n\u0cd4\nͼ\nʯͷ૬ஊ \nͦ͏ͩΜ \n'
    '࢝ \n\u0378͡ \n·Γ· \n͢ɻΈΜͳͰ͍ΖΜͳήʔϜ\u038d͓ళ \nΈͤ \nߟ \n͔Μ͕ \n͑·͠ΐ͏ɻ \n'
    '\u0cd4ʢ\u0c54ʣ ɺ ࣍\nͭ͗ \nͷ͜Ͳ\u038b \nҕһձ \n͍͍Μ͔͍ \n\u0378\x01 \n࣌ \n͡\n'
    '\x14\x11\u0dfc \n; Μ \n͔ΒͰ͢ɻ\x01 \nҭ \n͠ ͍ ͘ \nέʔεͷத \nͳ͔ \nͰɺ͍ͭͷ·ʹ͔খ \n'
    '͍ͪ \n͞\nͳ ༮ \u0bac \nΑ͏ͪΎ͏ \n͕ҭ \nͦͩ \nͬ'
)
KYONAN = (
    'ٳ \nͳͭ\u038d͢ \n࡞\u07bb \n͜͏͘͞ \n݄ \n͖ͭ \nΑΓछྨ \n͠ΎΔ͍ \n\u038bଟ \n͓͓ \nت \n'
    '͓͓ΑΖ͜ \n࡞ \nͭ͘ \n͍ͬͯ·ͨ͠Ͷʂ\x01 \nྩ\u0fe8 \nΕ ͍ Θ \n̐\u0ce5 \nͶΜ \n࢝ \n'
    '\u0378͡ \nΊ͓ͨՈ \n͏ͪ \nͷਓ \nͻͱ \nͱҰॹ \n͍ͬ͠ΐ \n࡞\u07bb \n͜͏͘͞ \nࣨڭ \n'
    '͖ΐ͏ͭ͠ \nʯ \u038dΦʔϓϯ͋ͦ\u0382͑\u038bར༻ \nΓ Α ͏ \n\u0ce5 \n͜ ͱ ͠ \nೋճ\u0ee8 \n'
    'ʹ ͔ ͍ Ί \nࡇ \nͳͭ·ͭ \nָ \nͨͷ \n͠ΜͰ\u038bΒ͑·'
)
GOOD_TEXT = "学校からのお知らせです。明日は水筒と帽子を持って登校してください。"


def native_reader(*texts: str) -> Mock:
    return Mock(is_encrypted=False, pages=[Mock(extract_text=Mock(return_value=text)) for text in texts])


class PdfTextQualityTests(unittest.TestCase):
    def test_actual_cmap_excerpts_cannot_count_as_readable_native_text(self):
        for text in (OONODEN, KYONAN):
            with self.subTest(text=text[:20]), patch("pypdf.PdfReader", return_value=native_reader(text)):
                with patch.object(pdf_ocr, "extract_pdf_ocr_pages") as ocr, self.assertRaisesRegex(
                    ExtractionError, "corrupted native text on page 1.*original PDF"
                ):
                    extract_document_text(b"%PDF-test")
                ocr.assert_not_called()

    def test_corrupted_middle_page_rejects_whole_document(self):
        with patch("pypdf.PdfReader", return_value=native_reader(GOOD_TEXT, OONODEN, "Final readable page")), self.assertRaisesRegex(
            ExtractionError, "corrupted native text on page 2"
        ):
            extract_document_text(b"%PDF-test")

    def test_readable_header_does_not_hide_corrupted_body_over_200_characters(self):
        with patch("pypdf.PdfReader", return_value=native_reader(GOOD_TEXT * 4 + "\n" + KYONAN)), self.assertRaisesRegex(
            ExtractionError, "corrupted native text on page 1"
        ):
            extract_document_text(b"%PDF-test")

    def test_languages_terms_and_combining_marks_remain_native(self):
        paragraphs = (
            "English school news: bring a water bottle tomorrow.",
            "한국어 안내입니다. 내일 물병과 모자를 가져오세요.",
            "学校通知：请明天带水壶和帽子。放学后请在图书馆集合。",
            "Ελληνική ανακοίνωση: αύριο θα γίνει συνάντηση στο σχολείο.",
            unicodedata.normalize("NFD", "ἄνθρωπος ἐν ἀρχῇ λόγος café déjà vu"),
            "إعلان المدرسة: يرجى إحضار الماء غدًا. नमस्ते विद्यालय समाचार।",
            "Объявление школы: завтра принесите воду и головной убор.",
            "日本語とEnglish、한국어、中文、α・β・Ωを併記します。",
        )
        for paragraph in paragraphs:
            with self.subTest(paragraph=paragraph), patch("pypdf.PdfReader", return_value=native_reader(paragraph * 8)), patch.object(
                pdf_ocr, "extract_pdf_ocr_pages"
            ) as ocr:
                self.assertEqual(extract_document_text(b"%PDF-test"), paragraph * 8)
                ocr.assert_not_called()
        multilingual = GOOD_TEXT + "\n" + "\n".join(paragraphs[:4])
        with patch("pypdf.PdfReader", return_value=native_reader(multilingual)):
            self.assertEqual(extract_document_text(b"%PDF-test"), multilingual)

    def test_isolated_missing_glyph_and_valid_formatting_are_not_page_corruption(self):
        for text in (GOOD_TEXT * 8 + "\ufffd", GOOD_TEXT * 40 + "\ufffd" * 8,
                     "cafe\u0301\tΑ\u0301\n안내\r\n学校\f",
                     GOOD_TEXT + "\ue000\u200d\u200c\u200f"):
            with self.subTest(text=text), patch("pypdf.PdfReader", return_value=native_reader(text)), patch.object(
                pdf_ocr, "extract_pdf_ocr_pages"
            ) as ocr:
                self.assertEqual(extract_document_text(b"%PDF-test"), text)
                ocr.assert_not_called()

    def test_repeated_unmapped_values_fail_without_language_blacklist(self):
        for value in ("\ufffd", "\u0378", "\x01", "\x00"):
            with self.subTest(value=value), patch("pypdf.PdfReader", return_value=native_reader(GOOD_TEXT + value * 12)), self.assertRaisesRegex(
                ExtractionError, "corrupted native text"
            ):
                extract_document_text(b"%PDF-test")

    def test_layout_cannot_hide_corruption_in_either_extraction(self):
        for plain, layout in ((OONODEN, GOOD_TEXT), ("持\nち\n物\n水\n筒", KYONAN)):
            page = Mock()
            page.extract_text.side_effect = [plain, layout]
            with self.subTest(plain=plain[:20]), patch(
                "pypdf.PdfReader", return_value=Mock(is_encrypted=False, pages=[page])
            ), patch.object(pdf_ocr, "extract_pdf_ocr_pages") as ocr, self.assertRaisesRegex(
                ExtractionError, "corrupted native text on page 1"
            ):
                extract_document_text(b"%PDF-test")
            ocr.assert_not_called()

    def test_pdf_guard_does_not_change_html_extraction(self):
        self.assertEqual(extract_document_text(("<p>" + "\ufffd" * 12 + "</p>").encode()), "\ufffd" * 12)

    def test_catalog_keeps_corrupted_pdf_original_only_without_inventing_dates(self):
        from sakurano_line_notifier.fetcher import FetchedDocument
        from sakurano_line_notifier.web_catalog import CatalogService, _parse_source

        url = "https://example.test/202609-6.pdf"
        source = _parse_source({
            "id": "asobee", "name": "あそべえ", "ward": "武蔵野市", "level": "小学校",
            "page_url": "https://example.test/", "mode": "pdf", "max_documents": 1,
        }, 0)
        fetcher = Mock()
        fetcher.fetch_page.return_value = f'<a href="{url}">あそべえ</a>'
        fetcher.fetch_document.return_value = FetchedDocument(url, b"%PDF-test", "application/pdf", None, None)
        service = CatalogService.__new__(CatalogService)
        service.settings = SimpleNamespace(request_timeout_seconds=5, max_document_bytes=10_000_000, user_agent="test")
        with patch("sakurano_line_notifier.web_catalog.HttpFetcher", return_value=fetcher), patch(
            "pypdf.PdfReader", return_value=native_reader(GOOD_TEXT, OONODEN)
        ), patch.object(pdf_ocr, "extract_pdf_ocr_pages") as ocr:
            result = service._scan_source(source, "全学年")
        ocr.assert_not_called()
        self.assertEqual(len(result.notices), 1)
        notice = result.notices[0]
        self.assertEqual(notice.url, url)
        self.assertEqual(notice.extraction_status, "original_only")
        self.assertEqual(result.coverage()["readable_count"], 0)
        self.assertEqual((notice.date_label, notice.date_kind), ("更新資料", "unknown"))
        self.assertEqual((notice.published_label, notice.event_date, notice.deadline_date), ("", "", ""))
        self.assertNotIn(OONODEN, notice.text)
        self.assertIn("corrupted native text on page 2", " ".join(result.warnings))


if __name__ == "__main__":
    unittest.main()
