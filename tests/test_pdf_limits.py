from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from sakurano_line_notifier.extractor import ExtractionError, extract_document_text


class PdfLimitsTests(unittest.TestCase):
    def test_too_many_pages_are_rejected_before_extraction(self):
        reader = Mock(is_encrypted=False, pages=[Mock()] * 51)
        with patch("pypdf.PdfReader", return_value=reader), self.assertRaises(ExtractionError):
            extract_document_text(b"%PDF-test")
        reader.pages[0].extract_text.assert_not_called()

    def test_text_size_limit(self):
        page = Mock()
        page.extract_text.return_value = "a" * 200_001
        with patch("pypdf.PdfReader", return_value=Mock(is_encrypted=False, pages=[page])), self.assertRaises(ExtractionError):
            extract_document_text(b"%PDF-test")

    def test_normal_pdf_not_extracted_twice(self):
        page = Mock()
        page.extract_text.return_value = "持ち物：水筒"
        with patch("pypdf.PdfReader", return_value=Mock(is_encrypted=False, pages=[page])):
            self.assertEqual(extract_document_text(b"%PDF-test"), "持ち物：水筒")
        page.extract_text.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
