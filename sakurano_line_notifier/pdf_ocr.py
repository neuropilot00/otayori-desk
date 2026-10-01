"""Bounded, offline Japanese OCR for unread pages, including hybrid PDFs.

Requires Poppler's pdftoppm and Tesseract with the jpn language pack. There
are no downloads or network calls at runtime. The caller checks encryption
and the existing 50-page cap before calling this stricter fallback.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import OrderedDict

MAX_PDF_BYTES = 10_000_000
MAX_PDF_PAGES = 50
MAX_OCR_PAGES = 6
MAX_IMAGE_SIDE = 3200
MAX_IMAGE_BYTES = MAX_IMAGE_SIDE * MAX_IMAGE_SIDE + 256
MAX_OUTPUT_BYTES = 8_000_000
MAX_TEXT_CHARACTERS = 200_000
PROCESS_TIMEOUT_SECONDS = 30
DOCUMENT_TIMEOUT_SECONDS = 120
# The catalog fetches four documents concurrently. Let three earlier OCR
# documents finish within their deadlines instead of rejecting the fourth
# merely because a healthy OCR job takes more than ten seconds.
QUEUE_TIMEOUT_SECONDS = 3 * DOCUMENT_TIMEOUT_SECONDS
CACHE_ENTRIES = 32
MIN_JAPANESE_CHARACTERS = 40
MIN_MEAN_CONFIDENCE = 70
MAX_LOW_CONFIDENCE_FRACTION = 0.20

_JAPANESE = re.compile(r"[\u3041-\u3096\u30a1-\u30fa\u3400-\u4dbf\u4e00-\u9fff]")
_CJK_SPACE = re.compile(r"(?<=[\u3000-\u9fff]) +| +(?=[\u3000-\u9fff])")
_slots = threading.BoundedSemaphore(1)
_cache_lock = threading.Lock()
_cache: OrderedDict[tuple[str, int, tuple[int, ...]], dict[int, str]] = OrderedDict()

# Apply OS limits in a fresh interpreter, NOT preexec_fn (unsafe in the
# threaded catalog service). exec replaces that interpreter, so run(timeout)
# kills and reaps the actual tool. No shell, subprocess tree, or pipe buffer.
_LIMITED_EXEC = """
import os, resource, sys
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (16_000_000, 16_000_000))
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
if sys.platform.startswith('linux'):
    resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
os.execv(sys.argv[1], sys.argv[1:])
"""


class PdfOcrError(RuntimeError):
    """OCR is unavailable, exceeded a limit, or did not produce reliable text."""


def _cached(key: tuple[str, int, tuple[int, ...]]) -> dict[int, str] | None:
    with _cache_lock:
        pages = _cache.get(key)
        if pages is not None:
            _cache.move_to_end(key)
            return pages.copy()
        return None


def extract_pdf_ocr(payload: bytes, *, page_count: int) -> str:
    """Whole-document compatibility entry point; blank pages contain no text."""
    pages = extract_pdf_ocr_pages(payload, page_count=page_count)
    text = "\n".join(pages.values())
    if not text.strip():
        raise PdfOcrError("PDF contains no readable text")
    return text


def extract_pdf_ocr_pages(
    payload: bytes, *, page_count: int, page_numbers: tuple[int, ...] | None = None,
) -> dict[int, str]:
    """Return every requested 1-based page or fail the entire request.

    At most six pages share ONE slot and document deadline, even in a larger
    native PDF. A blank result means a verified entirely white raster, never
    empty/failed OCR. The LRU includes content and selection. Recheck after
    acquiring the single OCR slot to coalesce simultaneous requests for the
    same PDF. Errors and partial documents are never cached as successes.
    """
    if len(payload) > MAX_PDF_BYTES:
        raise PdfOcrError("PDF exceeds OCR byte limit")
    if not 1 <= page_count <= MAX_PDF_PAGES:
        raise PdfOcrError(f"PDF supports 1-{MAX_PDF_PAGES} pages; got {page_count}")
    numbers = tuple(range(1, page_count + 1)) if page_numbers is None else tuple(page_numbers)
    if not 1 <= len(numbers) <= MAX_OCR_PAGES:
        raise PdfOcrError(f"OCR supports 1-{MAX_OCR_PAGES} pages; got {len(numbers)}")
    if any(type(number) is not int or not 1 <= number <= page_count for number in numbers) or len(set(numbers)) != len(numbers):
        raise PdfOcrError("invalid OCR page selection")
    numbers = tuple(sorted(numbers))
    key = (hashlib.sha256(payload).hexdigest(), page_count, numbers)
    cached = _cached(key)
    if cached is not None:
        return cached
    if not _slots.acquire(timeout=QUEUE_TIMEOUT_SECONDS):
        raise PdfOcrError("OCR is busy; retry later")
    try:
        cached = _cached(key)
        if cached is not None:
            return cached
        pages = _extract_uncached(payload, numbers)
        if set(pages) != set(numbers):
            raise PdfOcrError("OCR returned an incomplete page selection")
        with _cache_lock:
            _cache[key] = pages.copy()
            while len(_cache) > CACHE_ENTRIES:
                _cache.popitem(last=False)
        return pages
    except OSError as exc:
        raise PdfOcrError("OCR could not access its temporary files or tools") from exc
    finally:
        _slots.release()


def _run(command: list[str], deadline: float, stage: str) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PdfOcrError("OCR document time limit exceeded")
    # Regular files plus RLIMIT_FSIZE bound stdout AND stderr, including a
    # noisy/crashing tool. Never accumulate unbounded subprocess output in RAM.
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            subprocess.run(
                [sys.executable, "-I", "-c", _LIMITED_EXEC, *command],
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=errors,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
                timeout=min(PROCESS_TIMEOUT_SECONDS, remaining),
                check=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise PdfOcrError(f"{stage} timed out") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise PdfOcrError(f"{stage} failed; check OCR tools and resource limits") from exc
        output.seek(0)
        result = output.read(MAX_OUTPUT_BYTES + 1)
        if len(result) > MAX_OUTPUT_BYTES:
            raise PdfOcrError(f"{stage} output exceeds safety limit")
        return result


def _check_image(path: Path) -> bool:
    # Poppler produces an uncompressed 8-bit PGM, so dimensions AND disk size
    # can be checked without another image decoder/decompression allocation.
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise PdfOcrError("OCR image exceeds byte limit")
    with path.open("rb") as image:
        header = image.read(256)
    match = re.match(rb"P5\s+(\d+)\s+(\d+)\s+255\s", header)
    if match is None:
        raise PdfOcrError("OCR renderer returned an invalid grayscale image")
    width, height = int(match[1]), int(match[2])
    if not (0 < width <= MAX_IMAGE_SIDE and 0 < height <= MAX_IMAGE_SIDE):
        raise PdfOcrError("OCR image exceeds pixel limit")
    if path.stat().st_size != match.end() + width * height:
        raise PdfOcrError("OCR renderer returned an incomplete image")
    # Only an entirely white raster is proven blank. Do not use a percentage
    # threshold that could hide a faint notice, a footer, or a small image.
    with path.open("rb") as image:
        image.seek(match.end())
        while chunk := image.read(65_536):
            if chunk.count(b"\xff") != len(chunk):
                return False
    return True


def _text_from_tsv(data: bytes, page: int) -> str:
    """Use Tesseract word confidence; never treat it as a correctness proof.

    Weight by character count so many confident one-character punctuation
    tokens cannot conceal long illegible words. Reject the whole page on low
    quality, rather than silently dropping uncertain passages/negations.
    """
    lines: OrderedDict[tuple[str, ...], list[str]] = OrderedDict()
    characters = japanese = low_confidence = 0
    confidence_total = 0.0
    try:
        if len(data) > MAX_OUTPUT_BYTES:
            raise PdfOcrError("OCR output exceeds safety limit")
        rows = csv.DictReader(io.StringIO(data.decode("utf-8")), delimiter="\t", quoting=csv.QUOTE_NONE)
        required = {"level", "page_num", "block_num", "par_num", "line_num", "conf", "text"}
        if not required.issubset(rows.fieldnames or []):
            raise ValueError("invalid TSV header")
        for row in rows:
            if row["level"] != "5":
                continue
            word = row["text"].strip()
            if not word:
                continue
            confidence = float(row["conf"])
            if not math.isfinite(confidence) or not 0 <= confidence <= 100:
                raise ValueError("invalid word confidence")
            count = len(word)
            characters += count
            if characters > MAX_TEXT_CHARACTERS:
                raise PdfOcrError("OCR text exceeds safety limit")
            japanese += len(_JAPANESE.findall(word))
            confidence_total += confidence * count
            if confidence < 50:
                low_confidence += count
            key = tuple(row[name] for name in ("page_num", "block_num", "par_num", "line_num"))
            lines.setdefault(key, []).append(word)
    except (UnicodeError, ValueError, TypeError, AttributeError, csv.Error) as exc:
        raise PdfOcrError(f"OCR returned invalid confidence data on page {page}") from exc
    mean = confidence_total / max(1, characters)
    low_fraction = low_confidence / max(1, characters)
    if japanese < MIN_JAPANESE_CHARACTERS or mean < MIN_MEAN_CONFIDENCE or low_fraction > MAX_LOW_CONFIDENCE_FRACTION:
        raise PdfOcrError(
            f"low OCR quality on page {page} (confidence {mean:.1f}, "
            f"uncertain {low_fraction:.0%}, Japanese characters {japanese}); consult the original PDF"
        )
    # Tesseract separates Japanese characters/words with artificial spaces.
    # Retain ASCII word boundaries, numeric groups, and the detected lines.
    text = "\n".join(_CJK_SPACE.sub("", " ".join(words)) for words in lines.values())
    if len(text) > MAX_TEXT_CHARACTERS:
        raise PdfOcrError("OCR text exceeds safety limit")
    return text


def _extract_uncached(payload: bytes, page_numbers: tuple[int, ...]) -> dict[int, str]:
    if os.name != "posix":
        raise PdfOcrError("bounded OCR requires a POSIX host")
    renderer, tesseract = shutil.which("pdftoppm"), shutil.which("tesseract")
    if not renderer or not tesseract:
        raise PdfOcrError("install poppler-utils, tesseract-ocr, and tesseract-ocr-jpn")
    deadline = time.monotonic() + DOCUMENT_TIMEOUT_SECONDS
    languages = _run([tesseract, "--list-langs"], deadline, "OCR language check")
    if b"jpn" not in languages.splitlines():
        raise PdfOcrError("Tesseract Japanese language data (jpn) is missing")
    with tempfile.TemporaryDirectory(prefix="sakurano-ocr-") as directory:
        # Resolving /tmp also avoids Leptonica's macOS symlink-path failures.
        root = Path(directory).resolve()
        pdf, prefix = root / "document.pdf", root / "page"
        image = prefix.with_suffix(".pgm")
        pdf.write_bytes(payload)
        pages: dict[int, str] = {}
        for number in page_numbers:
            _run([
                renderer, "-f", str(number), "-l", str(number), "-singlefile",
                "-scale-to", str(MAX_IMAGE_SIDE), "-gray", str(pdf), str(prefix),
            ], deadline, f"PDF rasterization page {number}")
            if _check_image(image):
                pages[number] = ""
                image.unlink()
                continue
            data = _run([
                tesseract, str(image), "stdout", "-l", "jpn", "--oem", "1",
                "--psm", "3", "-c", "tessedit_create_tsv=1",
            ], deadline, f"Japanese OCR page {number}")
            pages[number] = _text_from_tsv(data, number)
            image.unlink()
            if sum(map(len, pages.values())) + len(pages) - 1 > MAX_TEXT_CHARACTERS:
                raise PdfOcrError("OCR text exceeds safety limit")
        if sum(map(len, pages.values())) + len(pages) - 1 > MAX_TEXT_CHARACTERS:
            raise PdfOcrError("OCR text exceeds safety limit")
        if time.monotonic() > deadline:
            raise PdfOcrError("OCR document time limit exceeded")
        return pages
