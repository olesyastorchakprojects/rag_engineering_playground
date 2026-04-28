You are writing a Python PDF → JSONL extractor script (`pdfplumber`).

Goal: for each PDF page, output one JSONL line:
{"page": int, "raw_text": str, "clean_text": str}

## 0. Absolute Constraints
A) All `clean_text` cleanup policy, including regexes, thresholds, and heuristics, must come ONLY from `--rules-metadata`.
   No "built-in" cleanup is allowed in code, such as URL/domain/math-glyph cleanup, unless it is explicitly described in `rules_metadata`.
   Canonical term normalization from `--terms-metadata` is allowed as post-processing
   and is not considered rule-based cleanup from `--rules-metadata`.

B) Determinism:
   - no randomness or parallelism
   - stable ordering of pages / words / lines
   - same input -> same output

C) Strict `rules-metadata` validation:
   - an unknown field at any level -> ERROR (`stderr` + exit 1)
   - an unknown enum value -> ERROR
   - fields must not be "silently ignored"

D) Regexes are compiled "as-is after `json.load`".
   `unicode_escape`, extra decoding, or slash auto-fixing are forbidden.
   If a pattern looks double-escaped for common escapes, for example literal `"\\d"`, `"\\s"`, `"\\w"`, or `"\\b"` in a Python string, -> ERROR.

## 1. CLI (Strict)
python extract_pdf_pages_text.py --pdf <path> --out <path.jsonl> --rules-metadata <rules.json> [--clean-text-metadata <overrides.json>] [--terms-metadata <terms.json>]

--pdf required
--out required
--rules-metadata required (the only source of cleanup rules)
--clean-text-metadata optional (clean_text overrides only)
--terms-metadata optional

Exit: 0 success; 1 error.

## 2. Output JSONL (Strict)
UTF-8 JSONL.
Each line:
{"page": <int>, "raw_text": <str>, "clean_text": <str>}
No other fields.
`page`: `1..N`, where `N = len(pdf.pages)`.

## 3. Clean Text (Strict)
`clean_text`:
- if `--clean-text-metadata` is provided and an override exists for `page_num`: `clean_text = override.clean_text`


## 4. Clean Text Inputs (Strict)
If an override exists for `page_num` in `--clean-text-metadata`:
- `clean_text` is taken directly from `override.clean_text`
- `page.extract_words` and `page.lines` for that page are not used to build `clean_text`

Otherwise, `clean_text` is built only from:
- words = page.extract_words(x_tolerance=1, y_tolerance=1)
- page.lines (only for block rules with `anchor.kind=horizontal_line`)

Each `word` must have at least: `text`, `top`, `x0`, `size`.
If `word.bottom` is missing, `bottom = top + size`.

## 5. Rules Metadata Schema (`profile_version=1`)
Top-level keys: profile_version, profile_name?, params, rules.
Other top-level keys are forbidden.

profile_version must be 1.

params required keys:
- y_tol, top_band_pct, bottom_band_pct, superscript, captions, footnotes, layout

params.layout required keys:
- mode: "single_column" | "two_column"
- column_split_x: number — required if and only if mode == "two_column"; forbidden otherwise

Validation:
- Unknown key in layout -> ERROR
- mode not in {"single_column", "two_column"} -> ERROR
- mode == "two_column" and column_split_x absent -> ERROR
- mode == "single_column" and column_split_x present -> ERROR
- column_split_x must be a number (int or float)

rules allowed keys:
- context?, line?, block?, text?

rules.context:
- page_to_chapter? : object mapping "page"(string) -> chapter(int)

rules.line: list of line rules
Each:
{
  name: str,
  type: "line_prefix"|"line_regex"|"line_equals",
  enabled: bool,
  scope: {band:"top"|"bottom"|"any"},
  type-specific fields...
}
type-specific:
- line_prefix: prefixes:[str...]
- line_regex: pattern:str, flags:""|"i"
- line_equals: value:str, normalize:"none"|"collapse_ws_lower"

Band:
top:    line_top < top_band_pct*page_height
bottom: line_top > bottom_band_pct*page_height
any:    always

rules.text: list of regex_sub rules
Each:
{name, type:"regex_sub", enabled, pattern, flags:""|"i", repl}

rules.block: list of `region_rule`
Each:
{
  name: str,
  type: "region_rule",
  enabled: bool,
  stage: "pre_line_rules"|"post_line_rules",
  target: "words",
  references?: [ {name, kind, fallback}, ... ],
  anchor: {...},
  candidate_region: {...},
  when?: {all|any|not},
  action: {type:"drop_region"}
}

Behavior:
- anchor miss => no-op
- select="all" => apply anchors in top-to-bottom order
- overlap => earlier deletion wins; later rules see already-deleted state

references:
- array; each has unique name (string)
- kind enum:
  - "median_gap"
  - "median_word_font_size_above_anchor"
- fallback: number
- reference usage: conditions refer to references by NAME (not enum)

anchor.kind:
A) text_line_regex:
{
  kind:"text_line_regex",
  where:{pattern:str, flags:""|"i"},
  select:"first"|"all"
}

B) horizontal_line:
{
  kind:"horizontal_line",
  source:"page.lines",
  where:{top_gte_pct:number, x0_lte:number, width_gte:number, width_lte:number, linewidth_lte:number},
  select:"lowest"
}
width := x1 - x0

candidate_region.kind:
A) lines_from_anchor_following_until:
{
  kind:"lines_from_anchor_following_until",
  max_lines:int,
  stop_when_any:[ {kind:"next_line_gap_gte_ratio", reference:<ref_name>, value:number} ]
}

B) region_below_anchor_to_page_bottom:
{
  kind:"region_below_anchor_to_page_bottom",
  offset:number
}

when:
supports:
- {"all":[expr...]}
- {"any":[expr...]}
- {"not": expr}
expr is either a logic node or a condition object.

Supported condition kinds:
- anchor_capture_int_eq_context:
  {kind, capture_group:int, context:"page_to_chapter"}

- candidate_line_count_gte:
  {kind, value:int}

- word_below_anchor_regex_at_index:
  {kind, pattern:str, word_index:int}

- word_below_anchor_size_lte_at_index:
  {kind, value:number, word_index:int}

- all_words_below_anchor_size_ratio_lte:
  {kind, reference:<ref_name>, value:number, ignore_first_word_if_matches:str}

## 6. Formal Definitions (Deterministic)
Column word split (two_column mode only):
- left_words  = {w ∈ words | w.x0 <  layout.column_split_x}
- right_words = {w ∈ words | w.x0 >= layout.column_split_x}
- Reading order: left column first, then right column.
- page_lines (horizontal lines) are passed to both column passes unchanged.

Line building:
- group words into lines if abs(top_i - top_j) <= y_tol
- sort lines by line_top ascending
- sort words inside line by x0 ascending
- line_top = min(word.top)
- line_bottom = max(word.bottom) (bottom defined as above)
- line_text = " ".join(word.text) with single spaces

Gap definition:
gap_i = next.line_top - curr.line_bottom; if negative => 0
median_gap = median(gap_i for gap_i>0), else fallback=11.0

Membership deletion:
- for line-based `candidate_region`: delete words belonging to candidate lines, NOT by y-range
- for below-anchor `candidate_region`: delete words with `word.top >= anchor.top + offset`

## 7. Known Terms Metadata Schema
Top-level keys:
- dictionary_name,
- version,
- description,
- entry_description,
- entries.
Other top-level keys are forbidden.

`entries` is a list of terms.
Each {
   word: str,
   split_variants: list[str]
  }
All `entries.word` values must be unique;
all values from all `entries[].split_variants` must be globally unique;
otherwise, that is an ERROR.
`split_variants` must be a non-empty `list[str]`
`entries` is required.
unknown field at any level -> ERROR

## 8. Known Terms Metadata
If `--terms-metadata` is provided, the extractor must replace in `clean_text`
each literal occurrence of each value from `entries[].split_variants`
with the corresponding `entries.word` value.
Replacement is applied after `rules.text`.

## 9. Final Clean Text Canonicalization (Strict)
`clean_text` in the output JSONL must be a single line.
Newline characters are not allowed in `clean_text`.
After all cleanup steps, the extractor must:
- replace any whitespace sequence, including `\n`, `\r`, and `\t`, with one space
- trim both sides

## 10. Pipeline Order (Contract)
For each page:
1) extract words + page.lines

If layout.mode == "single_column":
  1a) word set = all extracted words
  Run steps 2–9 once on word set → text.

If layout.mode == "two_column":
  1a) split words by column_split_x:
        left_words  = {w | w.x0 <  column_split_x}
        right_words = {w | w.x0 >= column_split_x}
  1b) run steps 2–9 on left_words  → left_text
  1c) run steps 2–9 on right_words → right_text
  1d) text = left_text + "\n" + right_text
  page_lines are passed unchanged to both 1b and 1c.

Steps 2–9 (applied per word set, as above):
2) superscript token filter (if enabled)
3) build lines + compute median_gap
4) apply block rules stage="pre_line_rules" in array order; after each deletion rebuild lines+median_gap
5) apply rules.line in array order
6) apply block rules stage="post_line_rules" in array order; after each deletion rebuild lines+median_gap
7) assemble text = "\n".join(line_text)
8) apply rules.text in array order
9) safe cleanup only:
   - CRLF->LF
   - remove NUL
   - collapse multiple spaces inside each line

10) if --terms-metadata exists, normalize known terms in the current clean_text, not including pages whose clean_text came from --clean-text-metadata overrides
11) final clean_text canonicalization:
   - replace any whitespace sequence (including \n, \r, \t) with one space
   - trim both sides
12) write JSONL row

Override pages skip extraction/rules/terms normalization, but still go through final clean_text canonicalization.
No other cleanup or normalization steps are allowed.

## 11. Self-Check Requirement
Before finalizing the code, do a self-check:
- Every field/enum used in rules_metadata.json is implemented exactly as described in this prompt.
- Any mismatch is a bug; fix it.
- Every field used in terms_metadata.json is implemented exactly as described in this prompt

No extra CLI args. No extra policy rules in code.
