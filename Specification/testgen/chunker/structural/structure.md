You are writing one Python script: `structure.py`.
This is a CLI test for the chunker. It checks structural consistency of `chunks` against the ground truth from `book_content_metadata.json`.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print the report in a strictly fixed format;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- that heading ids in chunks appear in the correct order;
- that there are no illegal sibling jumps;
- that the path-based hierarchy built from chunk `section_path` does not diverge from the metadata hierarchy;
- that there are no duplicate heading ids;
- that chunk headings cover all expected metadata headings inside the chunk page span;
- that chunk headings do not invent unexpected ids not present in metadata;
- that the title at the start of the chunk agrees with the title from metadata.

Ground truth must come from metadata:
- `parts`
- `chapters`
- `sections`
- `subsections`

Do not reconstruct the expected hierarchy heuristically from page text.

Important:
- the expected heading truth set consists only of `sections ∪ subsections`;
- `parts` and `chapters` do not form an independent expected heading set;
- `parts` and `chapters` are used only for scope/counts and metadata-title enrichment.

## 2. INPUTS
CLI arguments:
- `--chunks` (`Path`) required
- `--metadata` (`Path`) required
- `--prefix-window` (`int`) default = `220`
- `--allow-title-mismatch-ratio` (`float`) default = `0.20`
- `--report-only` (`store_true`)
- `--max-errors` (`int`) default = `30`

Important:
- `--chunks` and `--metadata` must not have default paths;
- the script must not try to auto-fill paths;
- if `--chunks` is not provided, the CLI must fail with an argument error;
- if `--metadata` is not provided, the CLI must fail with an argument error.

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
- top-level fields used:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`

Metadata can be assumed valid and should already satisfy the shared validator logic:
- `parts`, `chapters`, `sections`, `subsections` are arrays;
- all `ranges.pdf.start` and `ranges.pdf.end` are `int`;
- `start <= end`;
- parent references are valid;
- string sentinels such as `"end_of_book"` are not allowed.

Skip empty lines in JSONL.

For this task the input can be assumed valid:
- required CLI arguments are provided correctly;
- JSON / JSONL is syntactically valid;
- required fields are present;
- field types are correct.

If `chunks` contains no rows:
- print exactly `FAIL: no chunks in <path>`
- exit code 1

If sorted `chunk_index` values are not exactly `0..N-1`:
- print exactly `FAIL: chunk_index is not strictly increasing 0..N-1`
- exit code 1

## 3. NORMALIZATION AND HEADING PARSING
Define:
- `HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2})\s+(.+)$")`

Define:
- `normalize_text(s)` = `re.sub(r"\s+", " ", (s or "").strip())`

Define:
- `id_to_tuple(section_id)` = `tuple(int(x) for x in section_id.split("."))`

Define:
`parse_chunk_heading(text: str) -> Optional[Tuple[str, str]]`

Logic:
- `t = normalize_text(text)`
- apply `HEADING_RE`
- if no match -> `None`
- if matched:
  - `section_id = m.group(1)`
  - `title = normalize_text(m.group(2))`
  - return `(section_id, title)`

Define:
`title_tokens(s: str) -> List[str]`

Logic:
- `re.findall(r"[A-Za-z0-9']+", s.lower())`

## 4. TITLE CONSISTENCY
Define:
`title_consistent(meta_title: str, chunk_head: str, prefix_window: int) -> bool`

Exact logic:
- `meta_toks = set(title_tokens(meta_title))`
- `head_toks = set(title_tokens(chunk_head[:prefix_window]))`
- if `meta_toks` is empty -> `True`
- `common = meta_toks & head_toks`
- return `len(common) >= min(2, len(meta_toks))`

Meaning:
- a chunk heading is considered consistent with the metadata title if the chunk prefix window contains at least 2 shared tokens;
- for very short titles the requirement is reduced to the size of the title itself.

## 5. METADATA SCOPE
Expected headings must be selected only within the chunk-derived metadata scope.

Define:
`overlaps_pdf_range(start, end, chunk_start, chunk_end) -> bool`

Logic:
- if `start` is not int -> `False`
- if `end` is not int -> `False`
- return `start <= chunk_end and chunk_start <= end`

Define:
`metadata_entries_in_scope(entries, chunk_start, chunk_end) -> List[dict]`

Logic:
- for each entry, take `entry["ranges"]["pdf"]["start"]` and `entry["ranges"]["pdf"]["end"]`
- include the entry if `overlaps_pdf_range(...) == True`

From chunks define:
- `min_chunk_page = min(int(row["page_start"]) for row in chunks)`
- `max_chunk_page = max(int(row["page_end"]) for row in chunks)`

Define helper:
`metadata_union_page_span(metadata) -> Optional[Tuple[int, int]]`

Logic:
- iterate top-level keys:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- for each entry, take `ranges.pdf.start` and `ranges.pdf.end`
- if both values are `int`, add them to an intermediate page list
- if the list is empty, return `None`
- otherwise return `(min(pages), max(pages))`

From metadata take:
- `chapters = metadata.get("chapters") or []`
- `sections = metadata.get("sections") or []`
- `subsections = metadata.get("subsections") or []`
- `parts = metadata.get("parts") or []`

Then:
- `metadata_chapters = metadata_entries_in_scope(chapters, min_chunk_page, max_chunk_page)`
- `metadata_sections = metadata_entries_in_scope(sections, min_chunk_page, max_chunk_page)`
- `metadata_subsections = metadata_entries_in_scope(subsections, min_chunk_page, max_chunk_page)`

## 6. EXPECTED HIERARCHY FROM METADATA
Build:
- `chapter_titles: Dict[int, str]`
- `part_titles: Dict[str, str]`

Logic:
- for chapters: `chapter -> normalized title`
- for parts: `part -> normalized title`

Build:
- `part_ids_in_scope = {str(entry["part"]) for entry in metadata_chapters if entry.get("part") is not None}`

Build:
- `expected_headings: List[Tuple[str, str, str, str]]`
- `expected_by_id: Dict[str, Tuple[str, str, str, str]]`

First add `sections`:
- `section_id = str(entry["section"]).strip()`
- `title = normalize_text(entry["title"])`
- `chapter_title = chapter_titles[int(entry["chapter"])]` if chapter is int, otherwise `""`
- `part_title = part_titles[str(entry["part"])]` if part is not `None`, otherwise `""`
- `expected = (section_id, title, chapter_title, part_title)`
- append to `expected_headings`
- store `expected_by_id[section_id] = expected`

Then add `subsections`:
- `subsection_id = str(entry["subsection"]).strip()`
- all other fields the same
- `expected = (subsection_id, title, chapter_title, part_title)`
- append to `expected_headings`
- store `expected_by_id[subsection_id] = expected`

After that:
- `expected_headings.sort(key=lambda item: id_to_tuple(item[0]))`

Important:
- expected ids must come only from metadata `sections` and `subsections`;
- do not reconstruct expected headings from chunk text;
- do not reconstruct expected headings from page text.

## 7. CHUNK HEADINGS
Build:
- `chunk_headings: List[Tuple[int, str, str, str]]`

Logic:
- iterate through chunks in order;
- parse heading through `parse_chunk_heading(row["text"])`
- if heading does not parse, skip the chunk;
- if it parses:
  - `chunk_index = int(row["chunk_index"])`
  - `sid = parsed section id`
  - `title = parsed title`
  - `section_path = row.get("section_path", "")`
  - append `(chunk_index, sid, title, section_path)`

Build:
- `expected_ids = [sid for sid, _, _, _ in expected_headings]`
- `chunk_ids = [sid for _, sid, _, _ in chunk_headings]`
- `expected_id_set = set(expected_ids)`
- `chunk_id_set = set(chunk_ids)`

## 8. STRUCTURE CHECKS
Need to compute the following violations.

1. `order_viol`
- iterate neighboring `chunk_headings`
- `a = id_to_tuple(prev_sid)`
- `b = id_to_tuple(cur_sid)`
- if `b <= a`, add `(cur_idx, prev_sid, cur_sid)`

2. `jump_viol`
- if `len(a) == len(b)` and `a[:-1] == b[:-1]` and `b[-1] > a[-1] + 1`,
  add `(cur_idx, prev_sid, cur_sid)`

3. `dup_ids`
- `sid` from `chunk_ids` where `Counter(chunk_ids)[sid] > 1`

4. `missing_ids`
- `sorted(expected_id_set - chunk_id_set, key=id_to_tuple)`

5. `path_hierarchy_viol`
- build helper:
  - `canonical_path(path)` must accept `array[str]` and return `tuple(normalize_text(part).lower() for part in path if normalize_text(part))`
- build `chunk_paths = [(chunk_index, section_path, canonical_path(section_path)) for chunk in chunks]`
- build `metadata_path_set`
  - part-level paths:
    - `part_title`
  - if `metadata_chapters` contains entries with `part is None`, add path `Introduction`
  - chapter-level paths:
    - `part_title/chapter_title`
  - section-level paths:
    - `part_title/chapter_title/section_title`
  - subsection-level paths:
    - `part_title/chapter_title/section_title/subsection_title`
- build `metadata_parent_paths`
  - chapter-level parent paths from `metadata_chapters`:
    - `part_title/chapter_title`
  - section-level parent paths only for `sections` that have child `subsections`:
    - `part_title/chapter_title/section_title`
- for entries without `part`, use `part_title = "Introduction"`
- for each chunk path:
  - if canonical path is not in `metadata_path_set`,
    add `("unknown_path", chunk_index, section_path)` to `path_hierarchy_viol`
- for each `parent_path` in `metadata_parent_paths`:
  - `descendant_positions` = `chunk_index` of all chunks whose canonical path starts with `parent_path`, but is longer than it
  - if there are no descendants, skip this parent path
  - `lo = min(descendant_positions)`, `hi = max(descendant_positions)`
  - if there exists a chunk with canonical path exactly `parent_path` and `lo < chunk_index < hi`,
    add `("midstream_parent", chunk_index, section_path)` to `path_hierarchy_viol`

6. `unexpected_ids`
- `sorted(chunk_id_set - expected_id_set, key=id_to_tuple)`

## 9. TITLE MISMATCH CHECK
Need to compute:
- `title_mismatch`
- `checked`
- `mismatch_ratio`

Logic:
- iterate through `chunk_headings`
- if `sid` is not in `expected_by_id`, that chunk does not participate in title consistency check
- otherwise:
  - `checked += 1`
  - `expected_title = expected_by_id[sid][1]`
  - if `not title_consistent(expected_title, head_title, prefix_window)`:
    - add `(idx, sid, expected_title, head_title[:120])` to `title_mismatch`

After that:
- `mismatch_ratio = len(title_mismatch) / checked` if `checked > 0`, otherwise `0.0`

## 10. METADATA / VIOLATION COUNTS AND SAMPLES
Build:
- `metadata_counts`
  - `metadata_parts`
  - `metadata_chapters`
  - `metadata_sections`
  - `metadata_subsections`

Where:
- `metadata_parts = len(part_ids_in_scope)`
- `metadata_chapters = len(metadata_chapters)`
- `metadata_sections = len(metadata_sections)`
- `metadata_subsections = len(metadata_subsections)`

Build:
- `violation_counts`
  - `order_violations`
  - `jump_violations`
  - `path_hierarchy_violations`
  - `duplicate_heading_ids`
  - `missing_heading_ids`
  - `unexpected_heading_ids`

Build:
- `violation_samples`
  - `order_violations`: `[cur_sid for _, _, cur_sid in order_viol]`
  - `jump_violations`: `[cur_sid for _, _, cur_sid in jump_viol]`
  - `path_hierarchy_violations`: `[f"{kind}:{path}@{idx}" for kind, idx, path in path_hierarchy_viol]`
  - `duplicate_heading_ids`: `dup_ids`
  - `missing_heading_ids`: `missing_ids`
  - `unexpected_heading_ids`: `unexpected_ids`

Define helper:
`format_samples(values, max_samples=10) -> str`

Logic:
- `shown = ",".join(str(v) for v in values[:max_samples])`
- `suffix = ",..." if len(values) > max_samples else ""`
- return `f"samples=[{shown}{suffix}]"`

## 11. OUTPUT FORMAT
The format is mandatory. Do not add extra lines.

First print a summary line:
- if `metadata_union_page_span(metadata)` is not `None`:
  - `chunks=<len(chunks)> scope_page_span=<min_scope_page>..<max_scope_page> expected_headings=<len(expected_headings)> chunk_headings=<len(chunk_headings)>`
- otherwise:
  - `chunks=<len(chunks)> scope_page_span=<min_chunk_page>..<max_chunk_page> expected_headings=<len(expected_headings)> chunk_headings=<len(chunk_headings)>`

Then block:
- `metadata:`
- then 4 lines with two leading spaces:
  - `metadata_parts`
  - `metadata_chapters`
  - `metadata_sections`
  - `metadata_subsections`

Then block:
- `violations:`
- then 6 lines with two leading spaces:
  - `order_violations`
  - `jump_violations`
  - `path_hierarchy_violations`
  - `duplicate_heading_ids`
  - `missing_heading_ids`
  - `unexpected_heading_ids`

Row format in `metadata:` and `violations:`:
- `=` must align in one column across both blocks;
- numbers after `=` must start in one column;
- for `violations:` print `samples=[...]` after the count.

The shape must look like:

```text
metadata:
  metadata_parts        = 5
  metadata_chapters     = 33
  metadata_sections     = 104
  metadata_subsections  = 14
violations:
  order_violations      = 0 samples=[]
  jump_violations       = 0 samples=[]
  path_hierarchy_violations = 0 samples=[]
  duplicate_heading_ids = 0 samples=[]
  missing_heading_ids   = 1 samples=[23.1]
  unexpected_heading_ids= 0 samples=[]
```

After that print:
- `title_consistency_checked=<checked> title_mismatch=<len(title_mismatch)> mismatch_ratio=<mismatch_ratio:.3f> allow_title_mismatch_ratio=<allow_title_mismatch_ratio:.3f>`

Important:
- do not print any detail blocks;
- do not print a separate line `Missing heading IDs (first N): ...`;
- samples for `missing_heading_ids` already exist in the summary and that is enough.
- `jump_violations`, `path_hierarchy_violations`, `duplicate_heading_ids`, and `unexpected_heading_ids` must appear only in the `violations:` block through `samples=[...]`;
- do not duplicate them in any verbose output.

Forbidden variations:
- extracting expected headings from `pages`;
- printing `strict_independent`, `heading_candidates_total`, `rejected_base`, `rejected_known_only`;
- printing a one-line violations summary;
- printing values as percentages;
- changing row order in `metadata:` and `violations:`.

## 12. FAIL LOGIC
`fail = True` if at least one of these holds:
- `order_viol` exists
- `jump_viol` exists
- `path_hierarchy_viol` exists
- `dup_ids` exists
- `missing_ids` exists
- `unexpected_ids` exists
- `mismatch_ratio > allow_title_mismatch_ratio`

If `mismatch_ratio > allow_title_mismatch_ratio`, before the final status print:
- `VIOLATION: title mismatch ratio <mismatch_ratio:.3f> > allow_title_mismatch_ratio <allow_title_mismatch_ratio:.3f>`

## 13. FINAL STATUS AND EXIT CODE
After printing the summary:
- if `fail == True` and `report_only == False`:
  - print `FAIL: structure checks failed`
  - exit code 1
- if `fail == True` and `report_only == True`:
  - print `WARN: structure checks failed (report-only)`
  - exit code 0
- if `fail == False`:
  - print `OK: structure checks passed`
  - exit code 0

## 14. REPORT SHAPE EXAMPLE
Below is an example output shape. Numbers are illustrative. You must reproduce the structure, names, row order, and column alignment:

```text
chunks=158 scope_page_span=19..346 expected_headings=118 chunk_headings=117
metadata:
  metadata_parts        = 5
  metadata_chapters     = 33
  metadata_sections     = 104
  metadata_subsections  = 14
violations:
  order_violations      = 0 samples=[]
  jump_violations       = 0 samples=[]
  path_hierarchy_violations = 0 samples=[]
  duplicate_heading_ids = 0 samples=[]
  missing_heading_ids   = 1 samples=[23.1]
  unexpected_heading_ids= 0 samples=[]
title_consistency_checked=117 title_mismatch=3 mismatch_ratio=0.026 allow_title_mismatch_ratio=0.200
FAIL: structure checks failed
```

This is the reference shape:
- summary field names must match;
- block names must match;
- violation metric names must match;
- line breaks must match;
- the final status line must match one of the allowed variants.

## 15. IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Use `argparse`, `json`, `re`, `sys`, `Counter`, `Path`, type hints from `typing`.
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
