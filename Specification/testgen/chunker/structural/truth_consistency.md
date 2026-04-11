You are writing one Python script: `truth_consistency.py`.
This is a CLI test for the chunker. It compares the aggregated chunk text with the aggregated `clean_text` of the source pages and prints a deterministic text report.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print the report in a strictly fixed format;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- whether chunk corpus content is preserved relative to the source corpus;
- whether extra token mass was introduced;
- the level of duplication;
- stability under technical tokenization;
- whether total character length of chunk corpus and source corpus remains consistent.

This is an aggregate-level test, not an exact-span matching test.

## 2. INPUTS
CLI arguments:
- `--pages` (`Path`) required
- `--chunks` (`Path`) required
- `--metadata` (`Path`) required
- `--sep` (`str`) default = `"\n\n"`
- `--scope` choices = `("metadata-union", "chunk-pages", "all-pages")`, default = `"metadata-union"`
- `--min-recall` (`float`) default = `0.940`
- `--min-recall-warn` (`float`) default = `0.955`
- `--min-precision` (`float`) default = `0.992`
- `--min-precision-warn` (`float`) default = `0.994`
- `--min-char-ratio` (`float`) default = `0.900`
- `--min-char-ratio-warn` (`float`) default = `0.930`
- `--max-char-ratio` (`float`) default = `1.030`
- `--max-char-ratio-warn` (`float`) default = `1.020`
- `--max-dup-factor` (`float`) default = `0.020`
- `--max-dup-factor-warn` (`float`) default = `0.010`
- `--min-recall-tech` (`float`) default = `0.900`
- `--min-recall-tech-warn` (`float`) default = `0.930`
- `--min-precision-tech` (`float`) default = `0.955`
- `--min-precision-tech-warn` (`float`) default = `0.970`
- `--max-dup-factor-tech` (`float`) default = `0.045`
- `--max-dup-factor-tech-warn` (`float`) default = `0.025`
- `--report-only` (`store_true`)

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

File `--metadata`:
- JSON;
- top-level object;
- only these arrays are used:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- for each entry, only:
  - `ranges.pdf.start`
  - `ranges.pdf.end`

Metadata can be assumed valid and should already satisfy the shared validator logic:
- `parts`, `chapters`, `sections`, `subsections` are arrays;
- all `ranges.pdf.start` and `ranges.pdf.end` are `int`;
- `start <= end`;
- parent references are valid;
- string sentinels such as `"end_of_book"` are not allowed.

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

If the selected `scope` leaves zero pages:
- print exactly `FAIL: no scoped pages for scope=<scope>`
- exit code 1

If `--pages` is not provided:
- the CLI must fail with an argument error

If `--chunks` is not provided:
- the CLI must fail with an argument error

If `--metadata` is not provided:
- the CLI must fail with an argument error

## 3. PREPROCESSING
Load both JSONL files and `--metadata` using the shared metadata validator.

Sort:
- `pages` by `int(row["page"])`
- `chunks` by `int(row["chunk_index"])`

Define:
- `min_chunk_page = min(int(row["page_start"]) for row in chunks)`
- `max_chunk_page = max(int(row["page_end"]) for row in chunks)`

Define helper:
`metadata_union_pages(metadata: dict) -> Set[int]`

Exact logic:
- create an empty `set[int]`
- iterate top-level keys in this order:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- for each `entry` in `metadata.get(key) or []`:
  - `ranges = entry.get("ranges")` if `entry` is a dict
  - `pdf = ranges.get("pdf")` if `ranges` is a dict
  - `start = pdf.get("start")` if `pdf` is a dict
  - `end = pdf.get("end")` if `pdf` is a dict
  - if both `start` and `end` are `int`, add all pages in `range(start, end + 1)` to the set
- return the set

Scope logic:
- if `scope == "metadata-union"`:
  - `metadata_pages = metadata_union_pages(metadata)`
  - `pages_scope = [row for row in pages if int(row["page"]) in metadata_pages]`
- if `scope == "chunk-pages"`:
  - `pages_scope = [row for row in pages if min_chunk_page <= int(row["page"]) <= max_chunk_page]`
- otherwise:
  - `pages_scope = pages`

`excluded_pages = len(pages) - len(pages_scope)`

If `pages_scope` is empty:
- print exactly `FAIL: no scoped pages for scope=<scope>`
- exit code 1

Define:
- `min_scope_page = min(int(row["page"]) for row in pages_scope)`
- `max_scope_page = max(int(row["page"]) for row in pages_scope)`

Assemble texts:
- `full_clean_text = sep.join((row["clean_text"] or "").strip() for row in pages_scope)`
- `full_chunks_text = sep.join((row["text"] or "").strip() for row in chunks)`

Normalization:
- `normalize_text(s)` must return `re.sub(r"\s+", " ", (s or "").strip())`

Define:
- `clean_norm = normalize_text(full_clean_text)`
- `chunks_norm = normalize_text(full_chunks_text)`
- `ratio = len(chunks_norm) / len(clean_norm)` if `clean_norm` is not empty, otherwise `0.0`

## 4. TOKENIZATION
Define two regexes:
- `PLAIN_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")`
- `TECH_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_:\-./']*")`

Functions:
- `tokenize_plain(s)` -> `PLAIN_TOKEN_RE.findall(s.lower())`
- `tokenize_tech(s)` -> `TECH_TOKEN_RE.findall(s.lower())`

Meaning:
- plain tokenization splits on `_ : - . /`
- tech tokenization preserves those separators inside tokens
- therefore `token_source` and `token_chunks` in the `tech` section may be smaller than in `plain`

## 5. HOW TO COMPUTE METRICS
Define:
`projection_metrics(src_text: str, chk_text: str, tokenizer) -> dict`

Exact logic:
- `src_tokens = Counter(tokenizer(src_text))`
- `chk_tokens = Counter(tokenizer(chk_text))`
- `overlap = sum(min(src_count, chk_tokens.get(tok, 0)) for tok, src_count in src_tokens.items())`
- `src_total = sum(src_tokens.values())`
- `chk_total = sum(chk_tokens.values())`
- `recall = overlap / src_total` if `src_total > 0`, otherwise `0.0`
- `precision = overlap / chk_total` if `chk_total > 0`, otherwise `0.0`
- `token_ratio = chk_total / src_total` if `src_total > 0`, otherwise `0.0`
- `dup_excess = sum(max(0, chk_tokens.get(tok, 0) - src_count) for tok, src_count in src_tokens.items())`
- then add to `dup_excess` the sum `cnt for tok, cnt in chk_tokens.items() if tok not in src_tokens`
- `dup_factor = dup_excess / src_total` if `src_total > 0`, otherwise `0.0`
- `src_unique = len(src_tokens)`
- `chk_unique = len(chk_tokens)`
- `unique_overlap = len(set(src_tokens.keys()) & set(chk_tokens.keys()))`
- `unique_recall = unique_overlap / src_unique` if `src_unique > 0`, otherwise `0.0`
- `unique_precision = unique_overlap / chk_unique` if `chk_unique > 0`, otherwise `0.0`

The returned dict must contain:
- `src_total`
- `chk_total`
- `overlap`
- `recall`
- `precision`
- `token_ratio`
- `dup_excess`
- `dup_factor`
- `src_unique`
- `chk_unique`
- `unique_overlap`
- `unique_recall`
- `unique_precision`

Call:
- `plain = projection_metrics(clean_norm, chunks_norm, tokenize_plain)`
- `tech = projection_metrics(clean_norm, chunks_norm, tokenize_tech)`

## 6. WARN AND FAIL LOGIC
Required helper functions:
- `min_threshold_status(value, threshold, fail_label, ok_label)`:
  - `OK` if `value >= threshold`
  - otherwise `WARN` or `FAIL` depending on `fail_label`
- `max_threshold_status(value, threshold, fail_label, ok_label)`:
  - `OK` if `value <= threshold`
  - otherwise `WARN` or `FAIL`

Warning rows:
- `plain_recall_warn`: value=`plain["recall"]`, threshold=`min_recall_warn`, rule=`value >= threshold`
- `plain_precision_warn`: value=`plain["precision"]`, threshold=`min_precision_warn`, rule=`value >= threshold`
- `plain_dup_factor_warn`: value=`plain["dup_factor"]`, threshold=`max_dup_factor_warn`, rule=`value <= threshold`
- `tech_recall_warn`: value=`tech["recall"]`, threshold=`min_recall_tech_warn`, rule=`value >= threshold`
- `tech_precision_warn`: value=`tech["precision"]`, threshold=`min_precision_tech_warn`, rule=`value >= threshold`
- `tech_dup_factor_warn`: value=`tech["dup_factor"]`, threshold=`max_dup_factor_tech_warn`, rule=`value <= threshold`
- `char_ratio_min_warn`: value=`ratio`, threshold=`min_char_ratio_warn`, rule=`value >= threshold`
- `char_ratio_max_warn`: value=`ratio`, threshold=`max_char_ratio_warn`, rule=`value <= threshold`

Fail rows:
- `plain_recall_fail`: value=`plain["recall"]`, threshold=`min_recall`, rule=`value >= threshold`
- `plain_precision_fail`: value=`plain["precision"]`, threshold=`min_precision`, rule=`value >= threshold`
- `plain_dup_factor_fail`: value=`plain["dup_factor"]`, threshold=`max_dup_factor`, rule=`value <= threshold`
- `tech_recall_fail`: value=`tech["recall"]`, threshold=`min_recall_tech`, rule=`value >= threshold`
- `tech_precision_fail`: value=`tech["precision"]`, threshold=`min_precision_tech`, rule=`value >= threshold`
- `tech_dup_factor_fail`: value=`tech["dup_factor"]`, threshold=`max_dup_factor_tech`, rule=`value <= threshold`
- `char_ratio_min_fail`: value=`ratio`, threshold=`min_char_ratio`, rule=`value >= threshold`
- `char_ratio_max_fail`: value=`ratio`, threshold=`max_char_ratio`, rule=`value <= threshold`

## 7. OUTPUT
Print a deterministic fixed-format report that includes:
- scoped page range and excluded page count
- source/chunk character sizes
- one section for plain metrics
- one section for tech metrics
- warning and fail tables
- final status line

## 8. FINAL STATUS
- if fail conditions are present and `--report-only` is off:
  - `FAIL: truth consistency checks failed`
- if fail conditions are present and `--report-only` is on:
  - `WARN: truth consistency checks failed (report-only)`
- if no fail conditions are present but warning conditions exist:
  - `WARN: truth consistency checks degraded`
- otherwise:
  - `OK: truth consistency checks passed`
