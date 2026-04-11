You are writing one Python script: `page_mapping.py`.
This is a CLI test for the fixed chunker. It verifies whether chunks can be laid back into the source corpus, built from page `clean_text`, in a sequential and plausible way, and whether `page_start/page_end` agree with the fixed chunker page-coverage contract.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print the report in a strictly fixed format;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- whether each chunk can be localized in the source;
- whether chunk spans remain monotonic;
- whether meaningful holes remain between chunk spans;
- whether chunk page metadata agrees with the page range inferred from the span position in the source;
- whether effective source coverage has degraded;
- whether the share of suspicious chunk boundaries is too high;
- whether the fixed chunker behaves correctly for duplicate pages and empty pages.

This is a positional / page-coverage test, not an aggregate token-consistency test.

## 2. INPUTS
CLI arguments:
- `--pages` (`Path`) required
- `--chunks` (`Path`) required
- `--scope` choices = `("chunk-pages", "all-pages")`, default = `"chunk-pages"`
- `--min-coverage` (`float`) default = `0.98`
- `--min-coverage-warn` (`float`) default = `0.99`
- `--ignore-leading-gap` (`store_true`)
- `--max-page-start-delta` (`int`) default = `1`
- `--max-page-end-delta` (`int`) default = `1`
- `--boundary-warn-ratio` (`float`) default = `0.10`
- `--report-only` (`store_true`)

Important:
- `--pages` and `--chunks` must not have default paths;
- the script must not try to auto-fill paths;
- if `--pages` is not provided, the CLI must fail with an argument error;
- if `--chunks` is not provided, the CLI must fail with an argument error.

File `--pages`:
- JSONL;
- each non-empty line is a JSON object;
- fields used:
  - `page` (int)
  - `clean_text` (str)

File `--chunks`:
- JSONL;
- each non-empty line is a JSON object;
- fields used:
  - `chunk_index` (int)
  - `page_start` (int)
  - `page_end` (int)
  - `text` (str)
  - `section_path` (array[str]) optional

Skip empty lines.

For this task the input can be assumed valid:
- required CLI arguments are provided correctly;
- JSONL is syntactically valid;
- required fields are present;
- field types are correct.

As a consequence:
- do not design separate behavior for broken JSON;
- do not design separate behavior for invalid field types;
- do not design separate behavior for invalid CLI values.

If `pages` contains no rows:
- print exactly `FAIL: no pages in <path>`
- exit code 1

If `chunks` contains no rows:
- print exactly `FAIL: no chunks in <path>`
- exit code 1

If sorted `chunk_index` values are not exactly `0..N-1`:
- print exactly `FAIL: chunk_index is not strictly increasing 0..N-1`
- exit code 1

## 3. PREPROCESSING
Load both JSONL files.

Sort:
- `pages_sorted = sorted(pages, key=lambda x: int(x["page"]))`
- `chunks = sorted(chunks, key=lambda x: int(x["chunk_index"]))`

Define:
- `min_chunk_page = min(int(row["page_start"]) for row in chunks)`
- `max_chunk_page = max(int(row["page_end"]) for row in chunks)`

Scope logic:
- if `scope == "chunk-pages"`:
  - `pages_scope = [row for row in pages_sorted if min_chunk_page <= int(row["page"]) <= max_chunk_page]`
- otherwise:
  - `pages_scope = pages_sorted`

If `pages_scope` is empty:
- print exactly `FAIL: no scoped pages for scope=<scope>`
- exit code 1

## 4. NORMALIZATION AND SOURCE
Define:
- `norm_ws(s)` = `re.sub(r"\s+", " ", (s or "").strip())`

Define:
`build_source_with_page_spans(pages_scope) -> Tuple[str, List[Tuple[int, int, int]]]`

Exact logic:
- iterate through pages in order;
- `page_no = int(row["page"])`
- `text = norm_ws(row["clean_text"] or "")`
- if `text` is empty, skip that page;
- build `source` as `" ".join(non_empty_page_texts)`;
- insert exactly one space between adjacent non-empty pages;
- in parallel build `page_spans`, where each entry is:
  - `(page_no, start, end)`
  - `start` inclusive
  - `end` exclusive
  - the range describes which characters of the combined `source` belong to that page.

Then:
- `source, page_spans = build_source_with_page_spans(pages_scope)`
- `source_len = len(source)`
- `min_scope_page = min(int(row["page"]) for row in pages_scope)`
- `max_scope_page = max(int(row["page"]) for row in pages_scope)`

Define:
`charpos_to_page(pos, page_spans)`

Logic:
- return `page_no` if `s <= pos < e`
- otherwise return `None`

Important:
- empty pages do not contribute characters to `source`;
- empty pages may still lie inside declared `chunk.page_start..chunk.page_end`;
- duplicate pages are allowed and must preserve stable ordering after sort.

## 5. STRIP HEADING PREFIX
Define:
`strip_heading_prefix(chunk_text: str, section_path: str) -> str`

Exact logic:
- `text = norm_ws(chunk_text)`
- if `section_path` is an `array[str]`, then `parts = [str(p).strip() for p in section_path if str(p).strip()]`
- otherwise `parts = [p.strip() for p in str(section_path or "").split("/") if p.strip()]`
- `heading = ""`
- if `len(parts) >= 1`, then `heading = parts[-1]`
- if `heading` is empty, return `text`
- otherwise remove one prefix from the start of `text` using regex:
  - `rf"^{re.escape(heading)}(?:\s*[:\-]\s*|\s+)"`
  - `count=1`
  - `flags=re.I`

Purpose:
- the test first tries to match the chunk without the heading prefix;
- if the stripped version is not found, it tries the raw chunk text.

## 6. MATCHING LOGIC
Define:
`word_anchor_patterns(text: str, width: int = 10) -> Tuple[str, str]`

Logic:
- take words using regex `[A-Za-z0-9']+` from `norm_ws(text)`
- if there are no words, return `("", "")`
- if number of words `<= width`, return the same regex for both start and end:
  - `r"\b" + r"\W+".join(map(re.escape, words)) + r"\b"`
- otherwise:
  - `start = words[:width]`
  - `end = words[-width:]`
  - `p_start = r"\b" + r"\W+".join(map(re.escape, start)) + r"\b"`
  - `p_end = r"\b" + r"\W+".join(map(re.escape, end)) + r"\b"`
  - return `(p_start, p_end)`

Define:
`locate_span(source: str, text: str, cursor: int) -> Tuple[Optional[int], Optional[int], str]`

Exact logic:
- if `text` is empty:
  - return `(None, None, "empty")`
- first try exact substring search:
  - `pos = source.find(text, max(0, cursor))`
  - if found, return `(pos, pos + len(text), "exact")`
- if exact search fails:
  - for `width` in `(12, 10, 8, 6)`:
    - build `(p_start, p_end) = word_anchor_patterns(text, width)`
    - if `p_start` is empty, continue
    - search `p_start` in `source[max(0, cursor):]` with `re.search(..., flags=re.I)`
    - if not found, continue
    - `abs_start = max(0, cursor) + m1.start()`
    - `probe_from = max(0, cursor) + m1.end()`
    - search `p_end` in `source[probe_from:]`
    - if not found, continue
    - `abs_end = probe_from + m2.end()`
    - if `abs_end <= abs_start`, continue
    - return `(abs_start, abs_end, "anchor")`
- if nothing matches:
  - return `(None, None, "missing")`

For each chunk:
- `raw_text = norm_ws(row["text"])`
- `path = row.get("section_path", [])`
- `stripped_text = strip_heading_prefix(raw_text, path)`
- first call `locate_span(source, stripped_text, cursor)`
- if `stripped_text` is not found and `raw_text != stripped_text`, repeat for `raw_text`
- if the raw search works:
  - the method must become `exact_unstripped` or `anchor_unstripped`

## 7. GAP, PAGE, AND BOUNDARY HEURISTICS
Define:
`is_significant_gap(gap: str) -> bool`

Exact logic:
- `g = norm_ws(gap)`
- if `g` is empty -> `False`
- if `len(g) <= 40` -> `False`
- if `g` contains no `[A-Za-z0-9]` -> `False`
- `lead = re.sub(r"^[\W_]+", "", g)`
- `heading_like = bool(...)`, where true if one of these regexes matches:
  - `r"^(Chapter\s+\d+\b.*)$"` with `re.I`
  - `r"^(Part\s+[IVXLCDM]+\b.*)$"` with `re.I`
  - `r"^(\d+\.\d+(?:\.\d+)?\s+[A-Z].*)$"`
- if `heading_like` and `len(lead) <= 320` -> `False`
- otherwise `True`

Define:
`is_bad_boundary_start(text: str) -> bool`

Logic:
- `t = norm_ws(text)`
- if `t` is empty -> `False`
- otherwise true if:
  - `re.match(r"^[,;:)\]}\-]", t)`
  - or `re.match(r"^(and|or|of|the|to)\b", t, flags=re.I)`

Define:
`is_bad_boundary_end(text: str) -> bool`

Logic:
- `t = norm_ws(text)`
- if `t` is empty -> `False`
- otherwise true if:
  - `re.search(r"[(\[{\-]$", t)`
  - or `re.search(r"\b(and|or|of|the|to)$", t, flags=re.I)`

Gap logic:
- if `s > prev_end`, take `gap = source[prev_end:s]`
- `is_leading_gap = (not spans and prev_end == 0)`
- this is a hole violation if `is_significant_gap(gap)` and not:
  - `is_leading_gap and ignore_leading_gap`

Page sanity:
- `page_start = charpos_to_page(s, page_spans)`
- `page_end = charpos_to_page(max(s, e - 1), page_spans)`
- `chunk_page_start = int(row["page_start"])`
- `chunk_page_end = int(row["page_end"])`
- page violation if:
  - mapped start page is not `None` and `abs(chunk_page_start - page_start) > max_page_start_delta`
  - or mapped end page is not `None` and `abs(chunk_page_end - page_end) > max_page_end_delta`

Boundary warnings:
- count a boundary warning if `is_bad_boundary_start(raw_text)` or `is_bad_boundary_end(raw_text)`

## 8. COVERAGE
Build matched spans in order.

Definitions:
- `coverage_raw = sum(max(0, e - s) for s, e in spans) / source_len` if `source_len > 0` else `0.0`
- for effective coverage, subtract non-significant holes only;
- significant holes reduce effective coverage.

Define:
- `coverage_effective`
- `boundary_warning_ratio = boundary_warning_count / len(chunks)` if chunks exist else `0.0`

## 9. WARN / FAIL LOGIC
Fail if any of the following is true:
- there is at least one missing span;
- there is at least one order violation;
- there is at least one significant hole violation;
- there is at least one page violation;
- `coverage_effective < min_coverage`

Warn if:
- `coverage_effective < min_coverage_warn`
- or `boundary_warning_ratio > boundary_warn_ratio`

## 10. OUTPUT FORMAT
Always print a compact fixed-format report that includes:
- source/chunk counts
- matched chunks
- method counts
- violation counts
- `coverage_raw`
- `coverage_effective`
- warning/fail tables
- final status line

## 11. FINAL STATUS
- if fail conditions are present and `--report-only` is off:
  - `FAIL: page mapping validation failed`
- if fail conditions are present and `--report-only` is on:
  - `WARN: page mapping validation failed (report-only)`
- if there are no fail conditions but warning conditions exist:
  - `WARN: page mapping validation degraded`
- otherwise:
  - `OK: page mapping validation passed`
