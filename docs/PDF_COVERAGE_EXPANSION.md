# PDF page coverage repair - 2026-10-01

Scope: `extractor.py`, `pdf_ocr.py`, `tests/test_pdf_ocr.py`, and this report. No source registry, catalog implementation, deployment, commit, or production cache mutation was performed by this PDF task. Other owners are integrating those areas concurrently.

## Reproduction and behavior

An offline PDF with native page 1 and an image-only page 2 returned only page 1. OCR ran only when the entire PDF had no native text, so an unread page could be counted as a successful document. Three regression tests failed before the fix: missing image text, an OCR failure failing to reject the hybrid, and an entirely blank PDF incorrectly going through OCR. The old image fixture was actually a blank page; it now contains an image XObject.

The extractor now selects unread pages, runs one bounded OCR request, and merges its results in original page order. Native pages retain their original extraction, including whitespace. Any selected page failing OCR rejects the document through `ExtractionError`; the existing catalog path retains its URL as `original_only`, with zero readable-body credit. A catalog integration test verifies that behavior without changing the catalog.

- Contentless pages with no annotations are skipped. Other textless pages, including vectors, inline images, Form XObjects and annotations, are rendered. Only a completely white, size-validated raster is skipped without recognition; even one nonwhite pixel prevents this exemption. An entirely blank document is not a readable notice.
- Short numeric/date/page labels alone are retained as native text. When accompanied by painted content or annotations, the whole page requires OCR. No arbitrary low character count by itself triggers OCR.
- Live inspection found another concrete case: Seishi newsletters preserve the masthead as native text but draw the body as thousands of vector paths. A conservative guard selects pages with fewer than 200 cleaned native characters AND at least 1,000 path segments AND a fill operation. Ordinary short native text with a photo does not meet that guard. This heuristic can also select dense illustrations; failure remains explicit instead of claiming their contents were read.
- `extract_pdf_ocr_pages` returns a result for every requested 1-based page or raises. The existing whole-document `extract_pdf_ocr` entry point remains available. Cache keys include content hash, document page count and selected pages; cached mappings are copied, and incomplete/failed OCR selections are not cached.

## Unchanged quality and resource limits

OCR still requires at least **40 Japanese characters**, character-weighted mean confidence **70**, and at most **20%** of characters in words below confidence 50. PSM 3, Japanese language and the 3,200-pixel render bound are unchanged. No external AI/OCR service, document upload, paid call, new dependency or runtime language download was used.

The PDF byte cap is 10 MB, total page cap 50, and merged native/OCR text cap 200,000 characters including separators. At most six selected pages may be rasterized per document, even in a 50-page native PDF. A seventh unread page rejects the document before subprocess work; it is never silently truncated. All selected pages share one semaphore slot, one 120-second document deadline and the existing 30-second subprocess timeout. Queue wait remains 360 seconds. Image/output/file-size/CPU/memory bounds, subprocess reaping and temporary-directory cleanup remain in force. Cache size remains 32 selections.

## Actual public PDF checks

Ordinary bounded HTTP GETs sampled up to three registered documents per PDF school source, excluding the previously exhausted Dai4 and Sakuramachi OCR cases. The sample inspected 42 PDFs from 14 sources; Jinnan's first attempted document returned HTML instead of PDF, so that source was not validated by this diagnostic. This was a targeted sample, not a full source audit. Five documents had suspect pages and were downloaded to `/private/tmp/sakurano-pdf-coverage.C2hWZO` for local verification. Published issue labels below come from the source; upload timestamps are not relabelled as publication dates.

| Public document | Previously omitted/suspect pages | Actual final local result |
| --- | --- | --- |
| [Dai1 October linked PDF](https://dai1-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260930100402.pdf) | Page 3 had 160 raw whitespace characters but no readable native text. | OCR only page 3; 2,070 total characters; 0.90 s. Its rendered page contains the illustrated explanation of tears. |
| [Kyonan July](https://kyounan-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260630105808.pdf) | Page 4 had only whitespace. | Render proved page 4 white; no page-recognition call; native body retained, 4,115 characters; 0.19 s. |
| [Dai3 July](https://dai3-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260702171322.pdf) | Page 5 had only whitespace. | Render proved page 5 white; no page-recognition call; 6,180 characters; 0.31 s. Existing pypdf rotated-text/layout warnings were observed. |
| [Seishi September](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/13,1992,c,html/1992/20260914-115318.pdf) | Page 1: masthead only (90 raw characters), drawn body; pages 2-4: no readable native text. | OCR all 4 pages with unchanged quality gates; 3,633 characters; 7.99 s. The rendered first page confirms a substantial article below the native masthead. |
| [Seishi July](https://www.bunkyo-tky.ed.jp/seishi-ps/index.cfm/13,1992,c,html/1992/20260630-095014.pdf) | Pages 1-2: only masthead/title (86/55 raw characters), drawn body; pages 3-5: no readable native text. | OCR all 5 pages with unchanged quality gates; 4,222 characters; 9.56 s. |
| [Seta September](https://school.setagaya.ed.jp/tseta/download/document/18540195?tm=20260907150938) | Four normal native pages. | 1,186,405 bytes; 5,676 extracted characters; zero OCR tool calls. |

A four-page local synthetic hybrid (native / clean Japanese scan / blank / native) also passed real Poppler and Tesseract in 0.67 s, returning 133 characters with both native pages in place. Its scan was visually inspected using the PDF skill's render-first workflow. Japanese data came from `/private/tmp/sakurano-ocr-check.QJpoIu`; tools came from the user-provided Homebrew and bundled-runtime PATH locations.

These are extraction-gate outcomes, not claims of transcription perfection. Visual inspection and output comparison still showed OCR artifacts, including short stray characters and title/date errors. Confidence gates do not prove semantic accuracy or completeness within arbitrary mixed text/image pages. Header images on an otherwise substantial native page, and shapes below the conservative sparse-vector guard, remain outside this repair's detection guarantee.

## Validation and audit handoff

- `.venv/bin/python -B -m unittest tests.test_pdf_ocr tests.test_pdf_limits -q`: **46 passed** after the sparse-vector regression was added. Coverage includes hybrid ordering, preserved native whitespace, blank handling, numeric headers, vectors/forms/inline images/annotations, failure-to-original-only integration, selected-page cache isolation, invalid selections, six/50-page and byte/text caps, shared deadline/slot, confidence rejection, child limits and cleanup.
- `.venv/bin/python -B -m unittest discover -s tests -q`: final integrated snapshot **196 passed** in 6.34 s. An earlier 195-test snapshot had an unrelated root-URL-count expectation failure during concurrent registry integration; that owner resolved it. This PDF task did not edit the registry or its tests.
- Scoped `git diff --check` passed.

The prior five Linux `original_only` documents are an existing audit baseline, not a claim reverified in this task. Their quality thresholds were not lowered, and the prior 24 Dai4 OCR/resolution experiments were not repeated. **If the full audit now reports more `original_only` documents, that is an honest disclosure of previously unread pages, not a regression to hide or a reason to relax quality gates.** Run the full audit after integrating all owners' changes; historical cached successes do not prove the new extractor read every page. No deployment or completeness claim is made here.
