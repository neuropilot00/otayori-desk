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

## Security-patch recheck - pypdf 6.19.0

Confirmed `.venv` runs **pypdf 6.19.0** after main's security upgrade; reused the same PATH/TESSDATA_PREFIX and unchanged OCR gates. This is a parser-behavior recheck, not a new advisory audit.

- **Asobee:** reused the original temporary PDF and verified its SHA-256 above. Real full extraction still rejects page 2 at **39.4 confidence / 60% uncertain / 250 Japanese characters**, **5.28 s**, zero cached successes. Catalog verification took **5.26 s** and retained one `original_only` notice, `readable_count=0`, `date_label=更新資料`, `date_kind=unknown`, and empty publication/event/deadline dates. No date or partial readable body was invented.
- **Readable Sakurano grade PDF:** [20260918181117.pdf](https://sakurano-e.musashino-city.ed.jp/modules/ictea_base/include/js/ckeditor/kcfinder/upload/files/20260918181117.pdf), fetched with a 30-second/10 MB bound: **284,781 bytes**, SHA-256 `9706015d9df92ca90506d94ed205e8573f41b5802be5a093026efe693c8d932b`, **six pages / 5,299 extracted characters**. The rendered first page confirms `学年だより（10月号）` and `1年`. Grade-1 selection returns **968 characters**, excludes the next grade's September 28 instruction, and the catalog returns **`ok`, `1年生 学年だより・10月号`, `2026/10月号`, `date_kind=issue`**, with no OCR calls or warnings. Publication stays empty: the filename's September 18 timestamp is not treated as a publication date. Final extraction/selection/catalog assertions passed in **0.22 s**.
- Catalog checks reused the exact PDF bytes through an in-memory one-link HTTP fixture; all extraction, selection, OCR and label logic ran normally. `.venv/bin/python -B -m unittest tests.test_pdf_ocr tests.test_pdf_limits tests.test_web_catalog.NewsIndexTests.test_issue_month_does_not_replace_publication_date -q`: **47 passed**, 0.572 s. An initial diagnostic incorrectly expected a September 18 publication date; the final assertion correctly requires the observed empty value. An initial targeted-test command used the wrong class name; the corrected command above passed. Only this report was appended; no runtime/test edits, commit or deployment.

## Native CMap corruption guard - 2026-10-02

The subsequent after-school verification found a separate false-success path: five Asobee PDFs have substantial native text, but its Unicode mapping is corrupt. Before this change all five returned garbage as readable text with **zero OCR calls**. Both pages of every sample bypassed `_page_needs_ocr` because they contained more than 200 characters.

Bounded public downloads (25 seconds / 10 MB per file) and pypdf 6.19.0 reproduced the following. Counts refer to plain native extraction before layout fallback; invalid values are non-whitespace controls or unassigned code points in these samples.

| Original PDF | Bytes | Native characters, pages 1 / 2 | Invalid values, pages 1 / 2 | Final direct extraction and catalog |
| --- | ---: | ---: | ---: | --- |
| [Oonoden, 202609-6.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-6.pdf) | 398,938 | 1,404 / 741 | 137 / 82 | Reject page 1; `original_only` |
| [Kyonan, 202609-7.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-7.pdf) | 356,807 | 1,897 / 536 | 186 / 194 | Reject page 1; `original_only` |
| [Senkawa, 202609-9.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-9.pdf) | 245,553 | 1,757 / 1,549 | 145 / 153 | Reject page 1; `original_only` |
| [Inokashira, 202609-10.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-10.pdf) | 410,687 | 1,960 / 1,145 | 106 / 265 | Reject page 1; `original_only` |
| [Dai2, 202609-2.pdf](https://mu-kodomo.kids.coocan.jp/kodomokan/202609-2.pdf) | 181,620 | 1,565 / 841 | 128 / 284 | Reject page 1; `original_only` |

Visual inspection distinguishes a readable original from a broken extraction: macOS Quick Look correctly renders the Japanese first pages of all five files. Oonoden and Kyonan use `/Identity-H` fonts without `/ToUnicode` maps. The installed Poppler instead reports `Missing language pack for 'Adobe-Japan1' mapping` and renders most body text absent in the inspected Oonoden/Kyonan previews. OCR of those incomplete rasters cannot prove that the original body was read. No new renderer, font pack or dependency was installed, and no inferred Unicode substitutions were attempted. Downloads and both renderer previews remain under `/private/tmp/asobee-native-integrity.iSIos2`.

`extractor.py` now checks both plain and selected layout text, before normalization and the long-native-text shortcut. It rejects the **whole PDF** with a page-specific `ExtractionError` when at least **eight** characters, comprising at least **2% of non-whitespace text on that page**, are Unicode replacement characters, non-whitespace controls, unassigned code points or surrogates. The observed invalid fractions were 8.1%-55.4%. This deliberately fails closed instead of accepting a possibly incomplete OCR raster. The existing OCR confidence/page/time/resource limits and other image-PDF handling remain unchanged.

This is not a script blacklist: valid English, Korean, Chinese, Greek (including decomposed accents), Arabic, Indic and Cyrillic paragraphs, mixed-language terms, combining marks, formatting controls and private-use symbols remain eligible for native extraction. Isolated/sparse missing glyphs do not trigger the guard. Corruption made solely of assigned Unicode characters, or below these bounds, is outside this narrow detector's guarantee; this is not a claim of complete semantic validation.

Verification:

- Exact 220-character Oonoden/Kyonan native excerpts are retained in `tests/test_pdf_text_quality.py` and were compared against the downloaded bytes' extraction. Before the guard, the corruption regressions failed. The final `.venv/bin/python -B -m unittest tests.test_pdf_text_quality tests.test_pdf_ocr tests.test_pdf_limits -q` passes **55 tests** (0.606 s), including nine new test methods covering known corruption, mixed pages/body, legitimate foreign text, sparse missing glyphs, both extraction modes and catalog failure/date handling. The parser's expected malformed-fixture `EOF marker not found` diagnostic remains harmless.
- Actual sample checks use real parsing with no extraction/OCR mocks: **all 10 native pages trigger the guard**. Direct extraction rejects each document; in-memory catalog checks retain all **five original URLs**, each with `readable_count=0`, unknown date, empty publication/event/deadline values, zero OCR calls and zero OCR cache entries. Only the one-link HTTP fixture is substituted. Direct-plus-catalog checks take 0.044-0.328 s per file; no production data is written.
- Previously checked readable Sakurano grade PDF still extracts **5,299 characters**, selects **968 grade-1 characters**, and makes **zero OCR calls**. Scoped diff whitespace validation passes.

Changed files for this subtask: `sakurano_line_notifier/extractor.py`, new `tests/test_pdf_text_quality.py`, and this report. Main/UI/registry/cache ownership is unchanged; registry-kind cache invalidation remains main's integration work. No commit, push or deployment. After-school coverage must distinguish **original links retained** from **body/date/event information successfully read**: these five documents, plus the separately verified Sakurano OCR failure, require the original PDF and must not count as readable notices or verified schedules.
