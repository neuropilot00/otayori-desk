# Sakurano Asobee bounded OCR recovery check - 2026-10-02

## Outcome

The public [Sakurano Asobee September PDF](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-12.pdf) remains **original-only**. The two visually justified alternative segmentation modes both fail the existing quality gates. No production OCR fallback was added, and neither `pdf_ocr.py` nor `tests/test_pdf_ocr.py` was changed: there is no demonstrated safe recovery to ship. This is an explicitly unresolved extraction limitation, not a successful transcription.

Only this report was edited by this task. Main/UI files belong to other owners. No commit, deployment, production cache change, paid/cloud OCR, secret access, dependency installation, or language download was performed. The previous Dai4/Sakuramachi experiments were read in `PDF_COVERAGE_EXPANSION.md` and `COLLECTION_FIX_AUDIT.md`, not repeated.

## Original and visual evidence

- Fresh bounded HTTP GET: **1,221,250 bytes**, two pages, SHA-256 `833ff37f76473bec795630c37cacce34237a7a1c860b696dde55c156c90cc49f`.
- Both pages are portrait, 595 x 842 PDF units, with `/Rotate` 0. Poppler previews were rendered at a 1,600-pixel maximum side and both were visually inspected following the PDF skill. Both are already upright; rotating either page has no visual justification.
- Page 1 is an illustrated newsletter with horizontal Japanese text, small furigana, photos and bordered notices. Its publication line visually reads `令和8年8月27日`; its issue is September, and some content concerns October. These dates are not interchangeable.
- Page 2 is a **monthly calendar covering September 1-30**, not a weekly calendar: ruled columns for date/day, classroom, morning schoolyard, after-school schoolyard, library and notes, followed by three photos with vertical Japanese captions. Small furigana, repeated time ranges, arrows and star-shaped closure symbols coexist with the photographs.
- Native extraction returns only 74 numeric/punctuation/whitespace characters on page 1 (49 after the extractor's line cleanup), and zero on page 2. Page 1 is selected by the existing sparse-native/dense-vector guard: 69,043 path segments with fill operations. Page 2 has 23,026 path segments and no native text. Both pages are already selected for OCR; this document is not being accepted on its numeric-only native layer.

Inspection artifacts remain in `/private/tmp/sakurano-ocr-recovery.Tbw8DQ`: `original.pdf`, `preview-1.png`, `preview-2.png`, and the bounded `page-1.pgm` / `page-2.pgm` OCR rasters. These are temporary local evidence, not repository fixtures or deployed assets.

## Bounded experiments

Environment: repository `.venv/bin/python`, Tesseract **5.5.3**, Poppler **26.05.0**, Japanese language data SHA-256 `1f5de9236d2e85f5fdf4b3c500f2d4926f8d9449f28f5394472d9e8d83b91b4d`.

```sh
export PATH=/opt/homebrew/bin:/Users/jongho/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override:$PATH
export TESSDATA_PREFIX=/private/tmp/sakurano-ocr-check.QJpoIu
```

Each OCR raster used the unchanged full-page `-scale-to 3200 -gray` render and `_check_image` validation. Recognition used `-l jpn --oem 1 -c tessedit_create_tsv=1`. The existing `_run` executed each command with one thread, child resource/output limits, the 30-second process cap and one 120-second deadline shared across the comparison. No cropping, uncertain-word removal, manual substitution, resolution increase, or partial-page acceptance was used.

PSM 3 is the baseline automatic page layout. Only PSM 6 (one text block, to test calendar row grouping) and PSM 11 (sparse text, to test separated cells/captions) were tried as alternatives on page 2. No rotation sweep or broader parameter search followed.

| Page | PSM | Character-weighted confidence | Characters below confidence 50 | Japanese characters | OCR seconds | Existing gate |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 3 | 82.9482 | 11.37% | 748 | 1.53 | Pass, with visible transcription errors |
| 2 | 3 | 39.3775 | 59.81% | 250 | 1.75 | Reject |
| 2 | 6 | 42.2555 | 58.36% | 233 | 1.39 | Reject |
| 2 | 11 | 67.4382 | 24.12% | 439 | 1.59 | Reject |

These timings cover each recognition call, not rendering or the full extraction. Metrics are computed over all nonempty level-5 TSV words using the production character weighting; every candidate was also passed through the unchanged `_text_from_tsv` gate.

PSM 11 improves aggregate confidence but still fails **both** required quality thresholds. Its output also damages actionable values: numeric time ranges contain `OO`/`O0` and broken/missing digits, while closure stars are transcribed as unrelated characters such as `福`, `支` and `壇`. PSM 6 loses or garbles substantial calendar rows. These are not cosmetic differences that can be repaired safely by replacing individual characters; guessing would risk wrong opening hours or closures. Sparse segmentation also does not establish reliable date-to-column associations.

Page 1's statistical pass is not proof of accuracy: for example, its visible `令和` publication line is transcribed as `今和`, and some body/title text is omitted or garbled. No page 1 text is returned as a substitute for the failed full document. A future recovery would need evidence of accurate full-calendar content and associations under the same gates; this check does not establish that further local preprocessing would succeed.

## Preserved limits and final verification

All runtime code and thresholds remain unchanged: at least **40 Japanese characters**, mean confidence **70**, at most **20%** uncertain characters, **six OCR pages**, **120 seconds per document**, **30 seconds per child**, 3,200-pixel image side, 10 MB PDF cap, 50 total PDF pages, bounded output/text/cache and one OCR slot. Failed and partial results are not cached.

- `.venv/bin/python -B -m unittest tests.test_pdf_ocr tests.test_pdf_limits -q`: **46 tests passed**, 0.530 s. The expected corrupt-PDF fixture prints `EOF marker not found`; the suite completes with `OK`. Existing coverage includes confidence/uncertain-character rejection, numeric headers, sparse native/vector pages, full-document rejection, original-only catalog handling, no failed-result cache, deadline/size/page limits, and cleanup.
- Fresh-process full extraction of the downloaded original through `extract_document_text`, with real Poppler/Tesseract and no OCR mocks: **rejected page 2**, confidence **39.4**, uncertain **60%**, 250 Japanese characters, **5.23 s**, **zero cache entries**. The earlier baseline gave the same failure in 5.36 s.
- In-memory catalog integration using that same freshly downloaded public payload: **one retained original URL, `extraction_status=original_only`, `readable_count=0`, zero OCR cache entries**, **5.25 s**. Only HTTP fetching was substituted to reuse the exact bytes and a one-link source page; the catalog, extractor and OCR ran normally. The warning retains the page 2 quality failure. No production data was written.
- Scoped `git diff --check`: passed. Main/UI changes visible during the work were left untouched.

The bounded recovery attempt is complete. The original PDF must remain available to guardians, with no readable-body credit or completeness claim for this document. Results describe the checked local toolchain; Linux deployment behavior was not reverified.
