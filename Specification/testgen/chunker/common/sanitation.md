You are writing one Python script: `sanitation.py`.
This is a CLI test for the chunker. It checks chunk-corpus sanitation: chunk length distribution, repeated sentence artifacts, mid-word boundary artifacts, and whether chunk names agree with allowed metadata titles on the page.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print the report in a strictly fixed format;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- chunk length distribution in characters;
- the share of too-small and too-large chunks;
- repeated sentence artifacts inside a chunk;
- mid-word boundary artifacts;
- whether the chunk name agrees with allowed metadata titles on the page.

This is a sanitation / anomaly test.
This is not an aggregate truth-consistency test.
This is not an exact-span geometry test.
This is not a strict structure/hierarchy test.

## 2. INPUTS
CLI arguments:
- `--input` (`Path`) required
- `--metadata` (`Path`) required
- `--tiny-chars` (`int`) default = `250`
- `--huge-chars` (`int`) default = `12000`
- `--tiny-ratio-warn` (`float`) default = `0.10`
- `--tiny-ratio-fail` (`float`) default = `0.20`
- `--huge-ratio-warn` (`float`) default = `0.02`
- `--huge-ratio-fail` (`float`) default = `0.05`
- `--repeated-ratio-warn` (`float`) default = `0.04`
- `--repeated-ratio-fail` (`float`) default = `0.08`
- `--midword-ratio-warn` (`float`) default = `0.05`
- `--midword-ratio-abs-fail` (`float`) default = `0.10`
- `--chunk-name-mismatch-ratio-warn` (`float`) default = `0.01`
- `--chunk-name-mismatch-ratio-fail` (`float`) default = `0.02`
- `--report-only` (`store_true`)

Important:
- `--input` and `--metadata` must not have default paths;
- the script must not try to auto-fill paths;
- if `--input` is not provided, the CLI must fail with an argument error;
- if `--metadata` is not provided, the CLI must fail with an argument error.

File `--input`:
- JSONL;
- each non-empty line is a JSON object;
- fields used:
  - `text` (str)
  - `section_path` (array[str])
  - `page_start` (int)

File `--metadata`:
- JSON object;
- top-level arrays used:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`

For each metadata entry the fields used are:
- `title` (str)
- `ranges.pdf.start` (int)
- `ranges.pdf.end` (int)

Metadata can be assumed valid and should already satisfy the shared validator logic:
- `parts`, `chapters`, `sections`, `subsections` are arrays;
- all `ranges.pdf.start` and `ranges.pdf.end` are `int`;
- `start <= end`;
- string sentinels such as `"end_of_book"` are not allowed.

Skip empty lines in JSONL.

For this task the input can be assumed valid:
- provided paths are correct;
- JSONL and JSON are syntactically valid;
- required fields are present;
- field types are correct.

If `--input` contains no rows:
- print exactly `FAIL: no chunks in <path>`
- exit code 1

## 3. HELPER FUNCTIONS
Define:
- `TOKEN_RE = re.compile(r"[A-Za-z0-9']+")`

Functions:

`load_rows(path: Path) -> list`
- reads JSONL;
- skips empty lines;
- runs `json.loads(line)` for each non-empty line.

`load_json(path: Path) -> dict`
- reads the full JSON file through `json.load`.

`normalize_text(s: str) -> str`
- returns `re.sub(r"\s+", " ", (s or "").strip())`

`token_count(s: str) -> int`
- returns `len(TOKEN_RE.findall(s))`

`pct(values, p: float) -> float`
- if `values` is empty, return `0.0`
- otherwise:
  - `xs = sorted(values)`
  - `k = (len(xs) - 1) * p`
  - `lo = int(k)`
  - `hi = min(lo + 1, len(xs) - 1)`
  - `w = k - lo`
  - return `xs[lo] * (1 - w) + xs[hi] * w`

`format_samples(values, max_samples: int = 5) -> str`
- `shown = ",".join(str(v) for v in values[:max_samples])`
- `suffix = ",..." if len(values) > max_samples else ""`
- return exactly `f"samples=[{shown}{suffix}]"`

## 4. REPEATED SENTENCE LOGIC
Define:
`sentence_dupe_score(s: str) -> int`

Exact logic:
- `parts = [normalize_text(x) for x in re.split(r"[.!?;:]\s+", s)]`
- keep only `parts` where `len(x) >= 30`
- `c = Counter(parts)`
- return `sum(v - 1 for v in c.values() if v > 1)`

Meaning:
- repeated sentence artifacts are searched only inside one chunk;
- do not search for repetitions across the whole book or corpus.

## 5. CHUNK NAME MATCHING THROUGH METADATA
Define:
`title_tokens(s: str) -> list[str]`
- return `TOKEN_RE.findall((s or "").lower())`

Define:
`titles_compatible(tail: str, expected_title: str) -> bool`

Exact logic:
- `tail_toks = title_tokens(tail)`
- `expected_toks = title_tokens(expected_title)`
- if `tail_toks` is empty or `expected_toks` is empty -> `False`
- if `len(tail_toks) <= len(expected_toks)`:
  - return `tail_toks == expected_toks[: len(tail_toks)]`
- otherwise:
  - return `expected_toks == tail_toks[: len(expected_toks)]`

Define:
`build_page_title_index(metadata: dict) -> dict[int, set[str]]`

Exact logic:
- create empty `by_page`
- iterate top-level keys strictly in this order:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- for each entry:
  - `title = normalize_text(entry.get("title", ""))`
  - `pdf_ranges = (entry.get("ranges") or {}).get("pdf") or {}`
  - `start = pdf_ranges.get("start")`
  - `end = pdf_ranges.get("end")`
  - if `start` or `end` is not int, skip the entry
  - for `page` in `range(start, end + 1)`:
    - `by_page.setdefault(page, set()).add(title)`
- return `by_page`

Meaning of `chunk_name_mismatch`:
- for each chunk, take `section_path`;
- `parts = [str(p).strip() for p in section_path if str(p).strip()]`
- if `parts` is empty, skip the chunk and do not increase mismatch count;
- `tail = parts[-1]`
- `page = int(row.get("page_start", 0) or 0)`
- `expected_titles = page_title_index.get(page, set())`
- if `expected_titles` is empty, this is a mismatch;
- otherwise it is a mismatch if no `expected_title` is compatible with `tail` under `titles_compatible`

## 6. HOW TO COMPUTE METRICS
Define:
`metrics(rows, tiny_chars: int, huge_chars: int, page_title_index: dict) -> dict`

Exact logic:
- `texts = [normalize_text(r.get("text", "")) for r in rows]`
- `char_lens = [len(t) for t in texts]`
- `tok_lens = [token_count(t) for t in texts]`
- `n = len(texts)`

Size metrics:
- `chars_min = min(char_lens) if char_lens else 0`
- `chars_max = max(char_lens) if char_lens else 0`
- `chars_p50 = pct(char_lens, 0.50)`
- `chars_p90 = pct(char_lens, 0.90)`
- `chars_p95 = pct(char_lens, 0.95)`
- `chars_p99 = pct(char_lens, 0.99)`

Tiny / huge:
- `tiny = sum(1 for x in char_lens if x < tiny_chars)`
- `huge = sum(1 for x in char_lens if x > huge_chars)`
- `tiny_ratio = tiny / n if n else 0.0`
- `huge_ratio = huge / n if n else 0.0`

Repeated sentence:
- `repeated = sum(1 for t in texts if sentence_dupe_score(t) > 0)`
- `repeated_sentence_ratio = repeated / n if n else 0.0`

Mid-word boundary heuristic:
- initialize `start_mid = 0`, `end_mid = 0`
- for each `t in texts`:
  - if `t` is empty, continue
  - if `re.match(r"^-?[A-Za-z]{2,}-[A-Za-z]{2,}\b", t)`: `start_mid += 1`
  - if `re.match(r"^-?\s*[A-Za-z]{2,}\b", t)` and `re.search(r"[A-Za-z]{2,}-$", t[:20])`: `start_mid += 1`
  - if `re.search(r"[A-Za-z]{2,}-$", t)`: `end_mid += 1`
- `midword_ratio = (start_mid + end_mid) / (2 * n) if n else 0.0`

Chunk name mismatch:
- `chunk_name_mismatch = 0`
- `chunk_name_mismatch_examples = []`
- iterate through `rows` in order
- when a mismatch is found:
  - `chunk_name_mismatch += 1`
  - if `len(chunk_name_mismatch_examples) < 10`, append `tail`
- `chunk_name_mismatch_ratio = chunk_name_mismatch / n if n else 0.0`

The returned dict must contain:
- `chunks`
- `chars_min`
- `chars_max`
- `chars_p50`
- `chars_p90`
- `chars_p95`
- `chars_p99`
- `tiny_chars`
- `tiny_ratio`
- `huge_chars`
- `huge_ratio`
- `repeated_sentence_chunks`
- `repeated_sentence_ratio`
- `midword_ratio`
- `chunk_name_mismatch`
- `chunk_name_mismatch_ratio`
- `chunk_name_mismatch_examples`

## 7. WARNING AND FAIL LOGIC
You need two row collections:
- `warning_rows`
- `fail_rows`

You need two flags:
- `warn`
- `fail`

You need:
`threshold_row(name: str, value: float, threshold: float, *, mode: str = "max", bad_status: str = "FAIL")`

Logic:
- if `mode == "max"`, then `ok = value <= threshold`
- otherwise `ok = value >= threshold`
- `status = "OK" if ok else bad_status`
- return tuple:
  - dict with:
    - `name`
    - `status`
    - `value`
    - `threshold`
  - and bool `not ok`

Absolute warning rows:
- `tiny_ratio_warn`: `value = cur["tiny_ratio"]`, `threshold = tiny_ratio_warn`, rule `<=`, status `OK/WARN`
- `huge_ratio_warn`: `value = cur["huge_ratio"]`, `threshold = huge_ratio_warn`, rule `<=`, status `OK/WARN`
- `repeated_sentence_ratio_warn`: `value = cur["repeated_sentence_ratio"]`, `threshold = repeated_ratio_warn`, rule `<=`, status `OK/WARN`
- `midword_ratio_warn`: `value = cur["midword_ratio"]`, `threshold = midword_ratio_warn`, rule `<=`, status `OK/WARN`
- `chunk_name_mismatch_ratio_warn`: `value = cur["chunk_name_mismatch_ratio"]`, `threshold = chunk_name_mismatch_ratio_warn`, rule `<=`, status `OK/WARN`

Absolute fail rows:
- `tiny_ratio_fail`: `value = cur["tiny_ratio"]`, `threshold = tiny_ratio_fail`, rule `<=`, status `OK/FAIL`
- `huge_ratio_fail`: `value = cur["huge_ratio"]`, `threshold = huge_ratio_fail`, rule `<=`, status `OK/FAIL`
- `repeated_sentence_ratio_fail`: `value = cur["repeated_sentence_ratio"]`, `threshold = repeated_ratio_fail`, rule `<=`, status `OK/FAIL`
- `midword_ratio_fail`: `value = cur["midword_ratio"]`, `threshold = midword_ratio_abs_fail`, rule `<=`, status `OK/FAIL`
- `chunk_name_mismatch_ratio_fail`: `value = cur["chunk_name_mismatch_ratio"]`, `threshold = chunk_name_mismatch_ratio_fail`, rule `<=`, status `OK/FAIL`

For each warning row:
- append to `warning_rows`
- if breached, set `warn = True`

For each fail row:
- append to `fail_rows`
- if breached, set `fail = True`

## 8. OUTPUT FORMAT
The format is mandatory. Do not add extra lines.

Overall report order is strictly:

1. `chunks=<int>`
2. `chunk length distribution:`
3. eight lines inside `chunk length distribution`
4. `violations:`
5. three lines inside `violations`
6. `warnings:`
7. warning rows
8. `fails:`
9. fail rows
10. final status line, if it should be printed

For `chunk length distribution:` and `violations:` blocks:
- use shared `shared_label_width`
- `shared_label_width = max(...)` strictly over:
  - `"min"`
  - `"p50"`
  - `"p90"`
  - `"p95"`
  - `"p99"`
  - `"max"`
  - `f"tiny (<{args.tiny_chars})"`
  - `f"huge (>{args.huge_chars})"`
  - `"repeated_sentence"`
  - `"midword_ratio"`
  - `"chunk_name_mismatch"`

Lines in `chunk length distribution:`:
- `min`
- `p50`
- `p90`
- `p95`
- `p99`
- `max`
- `tiny (<threshold>)`
- `huge (>threshold)`

Template:
- `f"  {label:<{shared_label_width}} = {value}"`

Values:
- `min` and `max`: int
- `p50`, `p90`, `p95`, `p99`: `:.1f`
- `tiny`, `huge`: `"<count> (<ratio:.1%>)"`

`violations:` block:
- `repeated_sentence` line:
  - count as int
- `midword_ratio` line:
  - ratio as `:.1%`
- `chunk_name_mismatch` line:
  - `"<count> samples=[...]"`, where samples are built through `format_samples(cur["chunk_name_mismatch_examples"])`
- each line uses two-space indentation and shared `shared_label_width`

Warning/fail rows:
- first `warnings:`
- then `fails:`
- each row:
  - `  {name:<{name_width}} status = {status:<{status_width}} value = {value:.4f} threshold = {threshold:.4f}`
- `name_width = max(len(row["name"]) for row in rows)`
- `status_width = max(len(row["status"]) for row in rows)`

Important:
- in `warnings:` and `fails:` values are printed as fractions, not percentages
- do not use prefix `VIOLATION:`

## 9. FINAL STATUS AND EXIT CODE
After printing all sections:

If `fail == True`:
- if `report_only == True`:
  - print exactly `WARN: sanitation checks degraded (report-only)`
  - return
- otherwise:
  - exit code 1
  - do not print a separate line `FAIL: sanitation checks failed`

If `fail == False` and `warn == True`:
- print exactly `WARN: sanitation checks degraded`
- return

If `fail == False` and `warn == False`:
- print exactly `OK: sanitation checks passed`

## 10. FORBIDDEN VARIATIONS
Do not:
- add hidden/conditional verbose blocks;
- print `VIOLATION:` lines;
- print a baseline drift section or baseline raw lines;
- print a separate `FAIL: sanitation checks failed`;
- print `long_tail` or any metric derived from it;
- print `heading_only_ratio` or `one_word_ratio`;
- use paragraph-like heuristics for section path;
- compare chunk names against chunk text instead of metadata titles;
- search repeated sentences across the whole book;
- change section order;
- change metric names;
- change the `samples=[...]` format;
- change warning/fail rows to percentages.

## 11. CANONICAL REPORT SHAPE
Below is the reference shape. Numbers are illustrative; format is what matters.

```text
chunks=158
chunk length distribution:
  min                   = 68
  p50                   = 2077.5
  p90                   = 4313.2
  p95                   = 5668.7
  p99                   = 7796.3
  max                   = 9359
  tiny (<250)           = 3 (1.9%)
  huge (>12000)         = 0 (0.0%)
violations:
  repeated_sentence     = 1
  midword_ratio         = 3.2%
  chunk_name_mismatch   = 6 samples=[Foo,Bar]
warnings:
  tiny_ratio_warn                    status = OK   value = 0.0190 threshold = 0.1000
  huge_ratio_warn                    status = OK   value = 0.0000 threshold = 0.0200
  repeated_sentence_ratio_warn       status = OK   value = 0.0063 threshold = 0.0400
  midword_ratio_warn                 status = OK   value = 0.0316 threshold = 0.0500
  chunk_name_mismatch_ratio_warn     status = WARN value = 0.0380 threshold = 0.0100
fails:
  tiny_ratio_fail                    status = OK   value = 0.0190 threshold = 0.2000
  huge_ratio_fail                    status = OK   value = 0.0000 threshold = 0.0500
  repeated_sentence_ratio_fail       status = OK   value = 0.0063 threshold = 0.0800
  midword_ratio_fail                 status = OK   value = 0.0316 threshold = 0.1000
  chunk_name_mismatch_ratio_fail     status = FAIL value = 0.0380 threshold = 0.0200
```

If `report_only` is off and there is a fail:
- no final line is printed after this;
- the process exits with code 1.
