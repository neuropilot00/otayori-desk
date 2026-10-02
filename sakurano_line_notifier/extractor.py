from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from html.parser import HTMLParser


class ExtractionError(RuntimeError):
    """Raised when a document cannot be converted into trustworthy text."""


class GradeSectionNotFound(ExtractionError):
    """Raised when a grade-specific newsletter has no target section."""


def normalize_grade(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value)).strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    if normalized in {"all", "*", "全学年", "全校", "全て", "すべて", "共通"}:
        return "全学年"
    match = re.fullmatch(r"(?:第)?(\d+)(?:年|学年)(?:生)?", normalized)
    if match:
        return f"{int(match.group(1))}年生"
    if normalized.isdigit():
        return f"{int(normalized)}年生"
    if not normalized:
        raise ValueError("grade must not be empty")
    return normalized


def _clean_line(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\x00", "")
    return re.sub(r"[ \t\u3000]+", " ", normalized).strip()


def clean_text_lines(text: str) -> list[str]:
    lines: list[str] = []
    previous = ""
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n").split("\n"):
        line = _clean_line(raw_line)
        if not line:
            continue
        # PDF extractors sometimes duplicate a page header on adjacent lines.
        if line == previous:
            continue
        lines.append(line)
        previous = line
    return lines


def _numeric_grade_heading(line: str) -> int | None:
    compact = re.sub(r"[\s:：・]+", "", unicodedata.normalize("NFKC", line))
    match = re.fullmatch(r"(?:第)?(\d+)(?:年|学年)(?:生)?", compact)
    return int(match.group(1)) if match else None


def _is_target_heading(line: str, target_grade: str) -> bool:
    target = normalize_grade(target_grade)
    target_number = _numeric_grade_heading(target)
    if target_number is not None:
        return _numeric_grade_heading(line) == target_number
    compact_line = re.sub(r"\s+", "", unicodedata.normalize("NFKC", line)).lower()
    compact_target = re.sub(r"\s+", "", unicodedata.normalize("NFKC", target)).lower()
    return compact_line == compact_target


def extract_grade_section(text: str, target_grade: str) -> str:
    target = normalize_grade(target_grade)
    lines = clean_text_lines(text)
    if not lines:
        raise GradeSectionNotFound("document contains no text")
    if target == "全学年":
        return "\n".join(lines)

    start: int | None = None
    for index, line in enumerate(lines):
        if _is_target_heading(line, target):
            start = index
            break
    if start is None:
        # Some older PDFs on the school site are extracted by pypdf as one
        # character per line. In that layout a visible "１年" heading becomes
        # "1" and "年" on separate lines, so use a compact-text fallback.
        compact = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))
        target_number = _numeric_grade_heading(target)
        if target_number is None:
            compact_target = re.sub(r"\s+", "", unicodedata.normalize("NFKC", target)).lower()
            compact_start = compact.lower().find(compact_target)
            if compact_start < 0:
                raise GradeSectionNotFound(f"target grade section not found: {target}")
            return compact[compact_start:]

        target_match = re.search(rf"(?<!\d)(?:第)?{target_number}(?:年|学年)(?:生)?", compact)
        if target_match is None:
            raise GradeSectionNotFound(f"target grade section not found: {target}")
        compact_end = len(compact)
        next_heading = re.compile(r"(?<!\d)(?:第)?([1-6])(?:年|学年)(?:生)?")
        for match in next_heading.finditer(compact, target_match.end()):
            if int(match.group(1)) != target_number:
                compact_end = match.start()
                break
        return compact[target_match.start() : compact_end]

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _numeric_grade_heading(lines[index]) is not None:
            end = index
            break
    section = lines[start:end]
    if section and _is_target_heading(section[0], target):
        section = section[1:]
    if not section:
        raise GradeSectionNotFound(f"target grade section is empty: {target}")
    return "\n".join(section)


class _VisibleTextParser(HTMLParser):
    BLOCK_TAGS = {
        "address",
        "article",
        "br",
        "div",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif self._skip_depth == 0 and lowered in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif self._skip_depth == 0 and lowered in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


def html_to_text(payload: bytes, encoding: str = "utf-8") -> str:
    parser = _VisibleTextParser()
    parser.feed(payload.decode(encoding, errors="replace"))
    parser.close()
    return "\n".join(clean_text_lines("".join(parser.parts)))


def extract_document_text(payload: bytes, content_type: str = "", url: str = "") -> str:
    is_pdf = payload.lstrip().startswith(b"%PDF") or "application/pdf" in content_type.lower() or url.lower().split("?", 1)[0].endswith(".pdf")
    if not is_pdf:
        text = html_to_text(payload)
        if not text:
            raise ExtractionError(f"document contains no readable HTML text: {url}")
        return text

    from .pdf_ocr import MAX_PDF_BYTES, MAX_PDF_PAGES, MAX_TEXT_CHARACTERS, PdfOcrError, extract_pdf_ocr_pages

    if len(payload) > MAX_PDF_BYTES:
        raise ExtractionError("PDF exceeds byte safety limit")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(payload))
        if reader.is_encrypted or len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractionError("encrypted PDFs or PDFs over 50 pages are not supported")
        pages = []
        unread_pages = []
        characters = 0
        for number, page in enumerate(reader.pages, 1):
            plain_text = page.extract_text() or ""
            text = plain_text
            if _looks_fragmented(plain_text):
                text = page.extract_text(extraction_mode="layout") or plain_text
            characters += len(text)
            if characters > MAX_TEXT_CHARACTERS:
                raise ExtractionError("PDF text exceeds safety limit")
            if _has_corrupted_native_text(plain_text) or (text != plain_text and _has_corrupted_native_text(text)):
                # Broken CMaps can also produce incomplete OCR rasters when
                # the renderer lacks the font mapping. Fail the whole PDF;
                # neither surviving glyphs nor a partial page establish text.
                raise ExtractionError(f"PDF has corrupted native text on page {number}; consult the original PDF")
            pages.append(text)
            if _page_needs_ocr(page, text):
                unread_pages.append(number)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"could not extract PDF text: {url}") from exc
    if unread_pages:
        try:
            recovered = extract_pdf_ocr_pages(payload, page_count=len(pages), page_numbers=tuple(unread_pages))
        except PdfOcrError as exc:
            raise ExtractionError(f"PDF OCR failed: {exc}: {url}") from exc
        for number, recovered_text in recovered.items():
            pages[number - 1] = recovered_text
    text = "\n".join(pages)
    if len(text) > MAX_TEXT_CHARACTERS:
        raise ExtractionError("PDF text exceeds safety limit")
    if not clean_text_lines(text):
        raise ExtractionError(f"PDF contains no readable text: {url}")
    return text


def _has_corrupted_native_text(text: str) -> bool:
    """Detect repeated unmapped values, not the presence of foreign scripts.

    Asobee's broken Identity-H mappings emit controls/unassigned code points
    throughout otherwise long text. Require both eight such values and 2%
    of non-whitespace characters; an isolated missing glyph is insufficient.
    Assigned letters, combining marks, format controls and private-use icons
    are not evidence of corruption. Inspect before normalization removes NUL.
    """
    characters = invalid = 0
    for char in text:
        if char.isspace():
            continue
        characters += 1
        if char == "\ufffd" or unicodedata.category(char) in {"Cc", "Cn", "Cs"}:
            invalid += 1
    return invalid >= 8 and invalid * 50 >= characters


def _page_needs_ocr(page, text: str) -> bool:
    compact = "".join(clean_text_lines(text))
    # A short number/date/page label cannot establish that an accompanying
    # image was read. Require painting evidence; standalone numbers are valid
    # native text. Character count alone is not evidence of an unread body.
    numeric_only = re.fullmatch(r"[\d\s.,/():\-–—]{1,32}", compact) is not None
    if compact and not numeric_only:
        if len(compact) >= 200:
            return False
        # Some public newsletters retain only the masthead as native text;
        # thousands of vector segments draw the body glyphs (e.g. Seishi).
        # This conservative fallback requires BOTH sparse text and dense
        # painted paths, not merely a short body or an accompanying photo.
        content = page.get_contents()
        operations = getattr(content, "operations", ())
        if not isinstance(operations, (list, tuple)):
            return False
        segments = sum(op in {b"m", b"l", b"c", b"v", b"y"} for _, op in operations)
        return segments >= 1000 and any(op in {b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"} for _, op in operations)
    content = page.get_contents()
    annotations = bool(page.get("/Annots"))
    if not compact:
        # A missing/empty content stream with no annotation cannot paint a
        # notice. Other textless pages must be rasterized, including vectors,
        # inline images and nested Form XObjects (without decoding images here).
        return annotations or (content is not None and bool(content.get_data().strip()))
    paint = {b"Do", b"INLINE IMAGE", b"sh", b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
    return annotations or (content is not None and any(op in paint for _, op in content.operations))


def _looks_fragmented(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    single_character_lines = sum(len(line) <= 1 for line in lines)
    return single_character_lines / len(lines) >= 0.25


def select_relevant_text(text: str, kind: str, target_grade: str) -> str:
    if kind == "grade_news":
        return extract_grade_section(text, target_grade)
    # A school newsletter is addressed to the whole school. It contains common
    # notices that apply to every grade, so retaining that text is safer than
    # guessing at a timetable column from a PDF's layout.
    return "\n".join(clean_text_lines(text))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
