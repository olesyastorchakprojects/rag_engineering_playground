You are writing a single Python script: `sanity.py`.
Goal: smoke + structural sanity checks for a JSONL file of pages produced by the PDF extractor.
The script must be deterministic, use no external dependencies (stdlib only), and run as a CLI.

INPUT DATA
- `--input`: path to a JSONL file. Each line is a JSON object with fields:
  - `page`: int (page number, expected `1..N`)
  - `raw_text`: str
  - `clean_text`: str
- If a line is empty, skip it.
- If the JSONL is empty (0 rows), FAIL.

STRUCTURAL INVARIANTS (FAIL if violated)
1. Page numbering: `pages == [1,2,...,N]`. Otherwise FAIL.
2. Expected page count:
   - CLI `--expected-pages-count` (int) has priority.
   - Otherwise try to load `expected_pages_count` from JSON file `--metadata` (if present).
   - If `expected_pages_count` is set (via CLI or metadata) and `N != expected`, FAIL.
3. Types: `raw_text` and `clean_text` must be strings for every row. Otherwise FAIL.

PAGE CLASSIFICATION (labels)
For every page, compute a set of labels:
- `toc-like`
- `figure/table-heavy`
- `separator-like`

Define functions (you may choose exact names, but the logic must match exactly):

1. `toc-like`:
   - Use `text = clean_text` or `raw_text` (if `clean_text` is empty).
   - Split into non-empty lines.
   - Count these signals:
     - `dot_leader`: lines containing a sequence of dots `.{2,}`
     - `numbered_tail`: lines ending with a 1..3 digit number
     - `toc_hits`: occurrences of words `contents/chapter/part` (case-insensitive)
     - `dot_entry_hits`: pattern `.{2,}\s*(number or roman)\b`
   - Return `True` if at least one of these holds:
     - `dot_leader >= 2 and numbered_tail >= 2`
     - `numbered_tail >= 4 and len(lines) >= 6`
     - `toc_hits >= 2 and numbered_tail >= 2`
     - `toc_hits >= 1 and dot_entry_hits >= 5`

2. `figure/table-heavy`:
   - Operate on `raw_text`.
   - Find caption-like IDs only where a colon appears after the number.
     Pattern (case-insensitive): `(figure|fig\.|table|diagram|chart|illustration|listing)\s*(\d+([.\-]\d+)*)\s*:`
   - `caption_like_hits` = number of unique `(label,num)` pairs with a colon.
   - `removed_most_text = (raw_len >= 120) and (clean_len <= 40) and (clean_len <= raw_len*0.2)`
   - Return `True` if `caption_like_hits >= 1 and removed_most_text`

3. `separator-like`:
   - Strictly: `True` only if `raw_text.strip()` is empty.

If a condition is true, add the corresponding label.

METRIC DEFINITIONS
Let `clean_len[i] = len(clean_text.strip())`.
`tiny_threshold` defaults to `120` (CLI `--tiny-threshold`).
`text_neighbor_threshold` defaults to `300` (CLI `--text-neighbor-threshold`).

GENERAL METRICS:
- `pages` - the number of pages found in the PDF document
- `core_pages` - the number of pages without labels

CATEGORY METRICS:
For each metric, the computation rule is defined below.

1. Category: pages with labels
`pages_with_labels` = the number of unique pages that have at least one label
`figure_table_heavy_empty` = the number of pages with label `figure/table-heavy` where `clean_len = 0`
`figure_table_heavy_tiny` = the number of pages with label `figure/table-heavy` where `0 < clean_len <= tiny_threshold`
`figure_table_heavy_pages` = the number of pages with label `figure/table-heavy`
`figure_table_heavy_samples` = array of page numbers with label `figure/table-heavy`
`toc_like_pages` = the number of pages with label `toc-like`
`toc_like_samples` = array of page numbers with label `toc-like`
`separator_like_pages` = the number of pages with label `separator-like`
`separator_like_samples` = array of page numbers with label `separator-like`

2. Category: pages (all)
`pages_all_empty_pages` = the number of pages where `clean_len = 0`, excluding pages with label `separator-like` and `figure/table-heavy`
`pages_all_empty_pcnt = pages_all_empty_pages / pages`
`pages_all_empty_samples` = array of pages where `clean_len = 0`, excluding pages with label `separator-like` and `figure/table-heavy`
`tiny_total_pages` = the number of pages where `0 < clean_len <= tiny_threshold`
`tiny_total_pcnt = tiny_total_pages / pages`
`tiny_total_samples` = array of pages where `0 < clean_len <= tiny_threshold`
`unexpected_empty_pages` = the number of pages where `clean_len = 0`, with no `separator-like` label, no `figure/table-heavy` label, not first or last page, and both neighbors satisfy `clean_len >= text_neighbor_threshold`
`unexpected_empty_pages_pcnt = unexpected_empty_pages / pages`
`unexpected_empty_pages_samples` = array of pages where `clean_len = 0`, with no `separator-like` label, no `figure/table-heavy` label, not first or last page, and both neighbors satisfy `clean_len >= text_neighbor_threshold`

3. Category: core (pages without labels)
`core_pages` = the number of pages without labels
`core_pages_pcnt = core_pages / pages`
`empty_core_pages` = the number of pages where `clean_len = 0` and there are no labels
`empty_core_pages_samples` = array of pages where `clean_len = 0` and there are no labels
`empty_core_pages_pcnt = empty_core_pages / core_pages`
`tiny_core_pages` = the number of unlabeled pages where `0 < clean_len <= tiny_threshold`
`tiny_core_pages_pcnt = tiny_core_pages / core_pages`
`tiny_core_pages_samples` = array of unlabeled pages where `0 < clean_len <= tiny_threshold`
`unexpected_empty_core_pages` = the number of pages where `clean_len = 0`, there are no labels, the page is not first or last, both neighbors satisfy `clean_len >= text_neighbor_threshold`, and both neighbors are also unlabeled
`unexpected_empty_core_pages_pcnt = unexpected_empty_core_pages / core_pages`
`unexpected_empty_core_samples` = array of pages where `clean_len = 0`, there are no labels, the page is not first or last, both neighbors satisfy `clean_len >= text_neighbor_threshold`, and both neighbors are also unlabeled

4. Category: `length_violations` (clean_text expansion over raw_text on text-heavy pages)
Check only text-heavy raw pages: `len(raw_page.strip()) >= 200`.
For each such page:
   - `raw_page_no_ws` = remove all whitespace from the raw page (`\s+`)
   - `clean_page_no_ws` = remove all whitespace from the clean page
   - `is_violation = len(clean_page_no_ws) > len(raw_page_no_ws) * len_factor` (default `1.10`)
   - `is_violation_with_ws = len(clean_page.strip()) > len(raw_page.strip()) * len_whitespace_only_factor` (default `1.50`)
   - `is_ws_only = is_violation_with_ws and NOT is_violation`

`length_violations_total_metric` = the number of pages where `len(raw_page.strip()) >= 200` and `is_violation = true`
`length_violations_total_samples` = array of pages where `len(raw_page.strip()) >= 200` and `is_violation = true`
`length_violations_core_metric` = the number of unlabeled pages where `len(raw_page.strip()) >= 200` and `is_violation = true`
`length_violations_core_samples` = array of unlabeled pages where `len(raw_page.strip()) >= 200` and `is_violation = true`
`length_violations_whitespace_only_total_metric` = the number of pages where `len(raw_page.strip()) >= 200` and `is_ws_only = true`
`length_violations_whitespace_only_total_samples` = array of pages where `len(raw_page.strip()) >= 200` and `is_ws_only = true`
`length_violations_whitespace_only_core_metric` = the number of unlabeled pages where `len(raw_page.strip()) >= 200` and `is_ws_only = true`
`length_violations_whitespace_only_core_samples` = array of unlabeled pages where `len(raw_page.strip()) >= 200` and `is_ws_only = true`

5. Category: duplicate
Eligible pages: `len(clean_page) > tiny_threshold`.
Check only eligible pages.
For each eligible page, normalize `clean_text` (collapse whitespace) and compute its SHA-1 hash in UTF-8.
Group pages by identical hash.
`duplicate_hash_extra_pages` = the sum of extra copies across all groups: `sum(group_size - 1)`. Example: if group sizes are `2` and `3`, then `duplicate_hash_extra_pages = (2-1)+(3-1) = 3`
`duplicate_hash_extra_pcnt = duplicate_hash_extra_pages / eligible_pages_count`
`eligible_pages_count` = the number of pages where `len(clean_page) > tiny_threshold`
`duplicate_groups_count` = the number of groups with identical content where group size is greater than `1`
`duplicate_hash_extra_total_pct_of_all_pages = duplicate_hash_extra_pages / pages`

WARNING THRESHOLDS:
All values are percentages.
`empty_total_warn_threshold = 0.05`
`tiny_total_warn_threshold = None / disabled`
`empty_core_warn_threshold = 0.05`
`tiny_core_warn_threshold = 0.08`
`unexpected_empty_core_warn_threshold = 0.05`
`len_core_warn_threshold = 0.10`
`len_total_warn_threshold = None / disabled`
`len_ws_only_total_warn_threshold = 0.50`
`duplicate_warn_threshold = 0.01`

FAIL THRESHOLDS:
All values are percentages.
`unexpected_empty_core_fail_threshold = 0.10`
`len_core_fail_threshold = 0.50`
`len_total_fail_threshold = None / disabled`
`duplicate_fail_threshold = 0.03`

WARNING VALUES:
All values are percentages.
`empty_total_warn_val = pages_all_empty_pcnt`
`tiny_total_warn_val = tiny_total_pcnt`
`empty_core_warn_val = empty_core_pages_pcnt`
`tiny_core_warn_val = tiny_core_pages_pcnt`
`unexpected_empty_core_warn_val = unexpected_empty_core_pages_pcnt`
`len_core_warn_val = length_violations_core_metric / core_pages`
`len_total_warn_val = length_violations_total_metric / pages`
`len_ws_only_total_warn_val = length_violations_whitespace_only_total_metric / pages`
`duplicate_warn_val = duplicate_hash_extra_pcnt`

FAIL VALUES:
All values are percentages.
`unexpected_empty_core_fail_val = unexpected_empty_core_pages_pcnt`
`len_core_fail_val = length_violations_core_metric / core_pages`
`len_total_fail_val = length_violations_total_metric / pages`
`duplicate_fail_val = duplicate_hash_extra_pcnt`

EXPLANATIONS:
We isolate core pages as a separate subset in order to detect cases where the extractor performed overly aggressive cleanup that cannot be explained by removing tables or figures.

RULES:
1. Print samples in the form `samples=[...]`, maximum array length = 10; if there are more than 10 elements, append a comma and ellipsis, for example `samples=[1,2,3,4,5,6,7,8,9,10,...]`

OUTPUT FORMAT (mandatory)
All `*_pcnt` and `*_val` values are printed as percent = `value*100` with one decimal place and a `%` suffix (for example `0.02 -> 2.0%`).
The script must print a report in exactly this style (approximately line by line as below):
-------------------
pages=<N> expected=<expected if known>
--- pages_with_labels ---
all=<pages_with_labels>
figure/table-heavy: pages=<figure_table_heavy_pages> empty=<figure_table_heavy_empty> tiny=<figure_table_heavy_tiny> samples=<figure_table_heavy_samples>
toc-like: pages=<toc_like_pages> samples=<toc_like_samples>
separator-like: pages=<separator_like_pages> samples=<separator_like_samples>
--- pages (all) ---
empty=<pages_all_empty_pages> (<pages_all_empty_pcnt>%) [excluding separator-like + figure/table-heavy] samples=<pages_all_empty_samples>
tiny_total(0<len<=<tiny_threshold>)=<tiny_total_pages> (<tiny_total_pcnt>%) samples=<tiny_total_samples>
unexpected_empty(neighbors>=<text_neighbor_threshold>)=<unexpected_empty_pages> (<unexpected_empty_pages_pcnt>%) samples=<unexpected_empty_pages_samples>
--- core (pages without labels) ---
core_pages = <core_pages> (<core_pages_pcnt>% of total pages)
empty_core = <empty_core_pages> (<empty_core_pages_pcnt>% of core pages) samples=<empty_core_pages_samples>
tiny_core(0<len<=<tiny_threshold>) = <tiny_core_pages> (<tiny_core_pages_pcnt>% of core pages) samples=<tiny_core_pages_samples>
unexpected_empty_core(neighbors>=<text_neighbor_threshold>) = <unexpected_empty_core_pages> (<unexpected_empty_core_pages_pcnt>%) samples=<unexpected_empty_core_samples>
--- length_violations (clean_text expansion over raw_text on text-heavy pages) ---
text-heavy pages: raw text >= 200
length_violations_total=<length_violations_total_metric> (factor=1.1) samples=<length_violations_total_samples>
length_violations_core=<length_violations_core_metric> samples=<length_violations_core_samples>
length_violations_whitespace_only_total=<length_violations_whitespace_only_total_metric> (factor=1.5) samples=<length_violations_whitespace_only_total_samples>
length_violations_whitespace_only_core=<length_violations_whitespace_only_core_metric> samples=<length_violations_whitespace_only_core_samples>
--- duplicate ---
eligible pages: clean text > <tiny_threshold>
duplicate_hash_extra=<duplicate_hash_extra_pages> (<duplicate_hash_extra_pcnt>% of eligible) eligible_pages=<eligible_pages_count> duplicate_groups=<duplicate_groups_count>
duplicate_hash_extra_total_pct_of_all_pages=<duplicate_hash_extra_total_pct_of_all_pages>%
--- WARNINGS ---
<fixed-width row table with name/status/value/threshold fields>
Print `status = OK` if `value < threshold`, otherwise `WARN`
empty_total_warn status=... value = <empty_total_warn_val> threshold = <empty_total_warn_threshold>
tiny_total_warn status=... value = <tiny_total_warn_val> threshold = <tiny_total_warn_threshold>
empty_core_warn status=... value = <empty_core_warn_val> threshold = <empty_core_warn_threshold>
tiny_core_warn status=... value = <tiny_core_warn_val> threshold = <tiny_core_warn_threshold>
unexpected_empty_core_warn status=... value = <unexpected_empty_core_warn_val> threshold = <unexpected_empty_core_warn_threshold>
len_core_warn status=... value = <len_core_warn_val> threshold = <len_core_warn_threshold>
len_total_warn status=... value = <len_total_warn_val> threshold = <len_total_warn_threshold>
len_ws_only_total_warn status=... value = <len_ws_only_total_warn_val> threshold = <len_ws_only_total_warn_threshold>
duplicate_warn status=... value = <duplicate_warn_val> threshold = <duplicate_warn_threshold>
--- FAILS ---
<fixed-width row table with name/status/value/threshold fields>
Print `status = OK` if `value < threshold`, otherwise `FAIL`
unexpected_empty_core_fail status=... value = <unexpected_empty_core_fail_val> threshold = <unexpected_empty_core_fail_threshold>
len_core_fail status=... value = <len_core_fail_val> threshold = <len_core_fail_threshold>
len_total_fail status=... value = <len_total_fail_val> threshold = <len_total_fail_threshold>
duplicate_fail status=... value = <duplicate_fail_val> threshold = <duplicate_fail_threshold>
-------------------
And at the end:
- if fail -> `FAIL: sanity checks failed` and exit code `1`
- else if warn -> `WARN: sanity checks degraded` and exit code `0`
- else -> `OK: sanity checks passed` and exit code `0`

CLI AND DEFAULTS
Create argparse flags:
`--input`, `--metadata`, `--expected-pages-count`,
`--tiny-threshold`, `--text-neighbor-threshold`,
`--empty-core-warn` (alias `--empty-warn`), `--tiny-core-warn` (alias `--tiny-warn`),
`--empty-total-warn`, `--tiny-total-warn`,
`--unexpected-empty-core-warn`, `--unexpected-empty-core-fail`
`--len-factor`,
`--len-core-warn` (alias `--len-warn`), `--len-core-fail` (alias `--len-fail`),
`--len-total-warn`, `--len-total-fail`,
`--len-whitespace-only-factor`,
`--dup-warn`, `--dup-fail`,
`--max-samples` (default `10`).

IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Do not add new metrics and do not change the meaning of existing ones.
