You are writing one Python script: `span_quality.py`.
This is a CLI test for the chunker. It checks whether chunks can be laid back into the source corpus, built from page `clean_text`, in a sequential and plausible way.

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
- whether overlap exceeds the allowed threshold;
- whether meaningful holes remain between chunk spans;
- whether chunk page metadata agrees with the page inferred from the span position in the source;
- whether effective source coverage has degraded;
- whether the share of suspicious chunk boundaries is too high.

This is a positional / geometry test, not an aggregate token-consistency test.

## 2. INPUTS
CLI arguments:
- `--pages` (`Path`) required
- `--chunks` (`Path`) required
- `--metadata` (`Path`) required
- `--scope` choices = `("metadata-union", "chunk-pages", "all-pages")`, default = `"metadata-union"`
- `--overlap-mode` choices = `("off", "on")`, default = `"off"`
- `--expected-overlap` (`int`) default = `0`
- `--overlap-tolerance` (`int`) default = `30`
- `--max-overlap` (`int`) default = `40`
- `--min-coverage` (`float`) default = `0.98`
- `--min-coverage-warn` (`float`) default = `0.99`
- `--ignore-leading-gap` (`store_true`)
- `--max-page-start-delta` (`int`) default = `1`
- `--boundary-warn-ratio` (`float`) default = `0.10`
- `--report-only` (`store_true`)

Important:
- `--pages`, `--chunks`, and `--metadata` must not have default paths;
- the script must not try to auto-fill paths;
- if `--pages` is not provided, the CLI must fail with an argument error;
- if `--chunks` is not provided, the CLI must fail with an argument error;
- if `--metadata` is not provided, the CLI must fail with an argument error.

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
  - `section_path` (array[str])

File `--metadata`:
- JSON object;
- arrays used:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- for each entry only:
  - `ranges.pdf.start`
  - `ranges.pdf.end`

Metadata can be assumed valid and should already satisfy the shared validator logic:
- `parts`, `chapters`, `sections`, `subsections` are arrays;
- all `ranges.pdf.start` and `ranges.pdf.end` are `int`;
- `start <= end`;
- string sentinels such as `"end_of_book"` are not allowed.

Skip empty lines.

For this task the input can be assumed valid:
- required CLI arguments are provided correctly;
- JSONL is syntactically valid;
- required fields are present;
- field types are correct.

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
Load both JSONL files and `--metadata` through the shared metadata validator.

Sort:
- `pages_sorted = sorted(pages, key=lambda x: int(x["page"]))`
- `chunks = sorted(chunks, key=lambda x: int(x["chunk_index"]))`

Define:
- `min_chunk_page = min(int(row["page_start"]) for row in chunks)`
- `max_chunk_page = max(int(row["page_end"]) for row in chunks)`

Define:
`metadata_union_pages(metadata) -> Set[int]`

Logic:
- iterate arrays `parts`, `chapters`, `sections`, `subsections`;
- for each valid entry with `ranges.pdf.start` and `ranges.pdf.end`
- add all pages in `range(start, end + 1)` to the set.

Scope logic:
- if `scope == "metadata-union"`:
  - `metadata_pages = metadata_union_pages(metadata)`
  - `pages_scope = [row for row in pages_sorted if int(row["page"]) in metadata_pages]`
- else if `scope == "chunk-pages"`:
  - `pages_scope = [row for row in pages_sorted if min_chunk_page <= int(row["page"]) <= max_chunk_page]`
- else:
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
- otherwise `None`

## 5. STRIP HEADING PREFIX
Define:
`strip_heading_prefix(chunk_text: str, section_path: str) -> str`

Exact logic:
- `text = norm_ws(chunk_text)`
- if `section_path` is an `array[str]`, then `parts = [str(p).strip() for p in section_path if str(p).strip()]`
- otherwise `parts = [p.strip() for p in str(section_path or "").split("/") if p.strip()]`
- `heading = ""`
- if `len(parts) >= 4` and `parts[-1] != "Overview"`, then `heading = parts[-1]`
- else if `len(parts) >= 3` and `parts[-1] != "Overview"`, then `heading = parts[-1]`
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
- `path = row["section_path"]`
- `stripped_text = strip_heading_prefix(raw_text, path)`
- first call `locate_span(source, stripped_text, cursor)`
- if `stripped_text` is not found and `raw_text != stripped_text`, repeat for `raw_text`
- if the raw search works:
  - the method must become `exact_unstripped` or `anchor_unstripped`

## 7. GAP, OVERLAP, PAGE, AND BOUNDARY HEURISTICS
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

Overlap logic:
- `overlap = max(0, prev_end - s)`
- if `overlap_mode == "off"`:
  - overlap violation if `overlap > max_overlap`
- if `overlap_mode == "on"`:
  - `lo = max(0, expected_overlap - overlap_tolerance)`
  - `hi = expected_overlap + overlap_tolerance`
  - overlap violation if `not (lo <= overlap <= hi)` and at the same time `overlap > max_overlap`

Gap logic:
- if `s > prev_end`, take `gap = source[prev_end:s]`
- `is_leading_gap = (not spans and prev_end == 0)`
- hole violation if `is_significant_gap(gap)` and not:
  - `is_leading_gap and ignore_leading_gap`

Page sanity:
- `page_start = charpos_to_page(s, page_spans)`
- `page_end = charpos_to_page(max(s, e - 1), page_spans)`
- `chunk_page_start = int(row["page_start"])`
- `chunk_page_end = int(row["page_end"])`
- page violation if:
  - `page_start is None` or `page_end is None`
  - or `abs(chunk_page_start - page_start) > max_page_start_delta`
  - or `chunk_page_end != page_end`
  - or `page_start < prev_page_start`

Boundary warning:
- if `is_bad_boundary_start(raw_text)` or `is_bad_boundary_end(raw_text)`, add the chunk to `boundary_warn`

## 8. MAIN PASS
Required containers:
- `spans: List[Tuple[int, int]]`
- `misses`
- `overlap_viol`
- `hole_viol`
- `order_viol`
- `page_viol`
- `boundary_warn`

Required method counters:
`method_counts = {"exact": 0, "anchor": 0, "empty": 0, "exact_unstripped": 0, "anchor_unstripped": 0}`

Method order in the output must be strictly:
- `exact`
- `anchor`
- `empty`
- `exact_unstripped`
- `anchor_unstripped`
- `missing` only if that key appeared during execution

State variables:
- `cursor = 0`
- `prev_end = 0`
- `prev_start = -1`
- `prev_page_start = -1`

For each chunk:
- compute `(s, e, method)` as described above;
- increment `method_counts[method]` through `get(method, 0) + 1`, so `missing` also appears if encountered;
- if `(s is None or e is None)`:
  - add the chunk to `misses`
  - `continue`
- if `s < prev_start`:
  - add to `order_viol`
- apply page sanity checks
- apply boundary warning check
- apply overlap checks
- apply hole checks
- add `(s, e)` to `spans`
- `prev_start = s`
- `prev_end = max(prev_end, e)`
- `cursor = max(cursor, e)`

Important:
- process all chunks to the end;
- do not stop early;
- `misses` is not printed as a separate metric, but it contributes to fail status.

## 9. COVERAGE
Define:
`merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]`

Logic:
- sort intervals;
- merge overlapping and touching intervals;
- return the merged list.

After the pass:
- `merged = merge_intervals(spans)`
- `covered_chars = sum(e - s for s, e in merged)`
- `coverage_raw = covered_chars / source_len` if `source_len > 0`, otherwise `0.0`
- `significant_gap_chars = sum(gap_len for _, gap_len, _ in hole_viol)`
- `coverage_effective = (source_len - significant_gap_chars) / source_len` if `source_len > 0`, otherwise `0.0`
- `boundary_warn_ratio = len(boundary_warn) / len(chunks)` if `chunks` is not empty, otherwise `0.0`

## 10. WARN AND FAIL LOGIC
Required helper functions:
- `min_threshold_status(value, threshold, fail_label, ok_label)`:
  - `OK` if `value >= threshold`
  - otherwise `WARN` or `FAIL`
- `max_threshold_status(value, threshold, fail_label, ok_label)`:
  - `OK` if `value <= threshold`
  - otherwise `WARN` or `FAIL`

Warning rows:
- `coverage_effective_warn`: value=`coverage_effective`, threshold=`min_coverage_warn`, rule=`value >= threshold`
- `boundary_warning_ratio_warn`: value=`boundary_warn_ratio`, threshold=`args.boundary_warn_ratio`, rule=`value <= threshold`

Fail rows:
- `coverage_effective_fail`: value=`coverage_effective`, threshold=`min_coverage`, rule=`value >= threshold`

Separately from fail-row:
- `fail = True` if there is at least one of:
  - `misses`
  - `overlap_viol`
  - `hole_viol`
  - `order_viol`
  - `page_viol`
  - `coverage_effective < min_coverage`

`boundary_warnings` do not cause fail on their own.

`any_warn = True` if:
- `coverage_effective < min_coverage_warn`
- or `boundary_warn_ratio > boundary_warn_ratio_threshold`

## 11. OUTPUT FORMAT
The format is mandatory. Do not add extra lines.

There must be exactly 5 sections:
- `--- corpus ---`
- `--- chunks ---`
- `--- coverage ---`
- `--- warnings ---`
- `--- fails ---`

`corpus` section:
- one line:
  - `pages_total=<len(pages)> pages_scope=<len(pages_scope)> chunks=<len(chunks)> scope_page_span=<min_scope_page>..<max_scope_page> scope=<scope>`

`chunks` section:
- first line:
  - `matched_chunks=<len(spans)>/<len(chunks)>`
- then line:
  - `methods:`
- then each method on its own line with two leading spaces:
  - `  exact              = 1`
  - `  anchor             = 148`
  - ...
- `=` must line up across all method rows
- values after `=` must start in one column
- method order must be strictly:
  - `exact`
  - `anchor`
  - `empty`
  - `exact_unstripped`
  - `anchor_unstripped`
  - `missing` if present
- if `missing` appears, print it as the last method row
- then line:
  - `violations:`
- then each violation metric on its own line with two leading spaces:
  - `  order_violations   = 0`
  - `  overlap_violations = 0`
  - ...
- `=` must line up across all violation rows
- values after `=` must start in one column
- violation row order:
  - `order_violations`
  - `overlap_violations`
  - `hole_violations`
  - `page_violations`
  - `boundary_warnings`

`coverage` section:
- one line:
  - `coverage_raw=<coverage_raw:.4f> coverage_effective=<coverage_effective:.4f> significant_gap_chars=<significant_gap_chars>`

`warnings` and `fails` sections:
- status rows must use fixed columns
- `status_name_width = max(len("coverage_effective_warn"), len("boundary_warning_ratio_warn"), len("coverage_effective_fail"))`
- exact row format:
  - `{name:<{status_name_width}} {'status':<9}= {status:<4} {'value':<9}= {value:<8.4f} {'threshold':<9}= {threshold:<8.4f}`

`warnings` section:
- first `coverage_effective_warn`
- then `boundary_warning_ratio_warn`

`fails` section:
- one line `coverage_effective_fail`

Forbidden variations:
- printing chunk-level examples;
- printing `source_chars`;
- printing `covered_chars`;
- printing a separate `matched_unstripped_only` metric;
- printing a separate `misses` metric;
- duplicating `coverage_effective` in a second line outside status tables;
- printing values/thresholds as percentages;
- changing section headers;
- changing section order;
- changing violation-row order;
- changing warning/fail-row order.

## 12. REPORT SHAPE EXAMPLE
Below is an example shape. Numbers are illustrative. You must reproduce structure, section names, line breaks, and column alignment:

```text
--- corpus ---
pages_total=346 pages_scope=328 chunks=157 scope_page_span=19..346 scope=metadata-union
--- chunks ---
matched_chunks=149/158
methods:
  exact              = 1
  anchor             = 148
  empty              = 0
  exact_unstripped   = 0
  anchor_unstripped  = 0
  missing            = 9
violations:
  order_violations   = 0
  overlap_violations = 0
  hole_violations    = 12
  page_violations    = 0
  boundary_warnings  = 8
--- coverage ---
coverage_raw=0.8355 coverage_effective=0.8789 significant_gap_chars=49054
--- warnings ---
coverage_effective_warn   status   = WARN value     = 0.8789   threshold = 0.9900
boundary_warning_ratio_warn status = OK   value     = 0.0506   threshold = 0.1000
--- fails ---
coverage_effective_fail   status   = FAIL value     = 0.8789   threshold = 0.9800
FAIL: span quality test failed
```

This is the reference shape:
- section names must match;
- metric names must match;
- line breaks must match;
- the final status line must match one of the allowed variants.

Additional reproducibility invariant:
- summary content in sections `corpus`, `chunks`, `coverage`, `warnings`, `fails` must be fully determined by input data and CLI thresholds;
- the absence of detailed examples is part of the contract;
- the absence of default paths is part of the contract.

## 13. FINAL STATUS AND EXIT CODE
After printing all sections:
- if `fail == True` and `report_only == False`:
  - print `FAIL: span quality test failed`
  - exit code 1
- if `fail == True` and `report_only == True`:
  - do not print any extra final line
  - exit code 0
- if `fail == False` and `any_warn == True`:
  - print `WARN: span quality checks degraded`
  - exit code 0
- if `fail == False` and `any_warn == False`:
  - print `OK: span quality checks passed`
  - exit code 0

## 14. IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Use `argparse`, `json`, `re`, `sys`, `Path`, type hints from `typing`.
- Keep the code readable and straightforward.
- No external dependencies.
- Do not add new metrics.
- Do not change the meaning of existing metrics and thresholds.
- Do not change output order.
- Small helper functions are allowed.
- Equivalent helper functions are allowed only if calculations and final output stay unchanged.
- Do not introduce fallback path resolution.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
