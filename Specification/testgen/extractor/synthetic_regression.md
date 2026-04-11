You are writing a single Python script: `synthetic_regression.py`.
Goal: a regression suite over synthetic problematic inputs for the cleanup/extractor pipeline.
The script must be deterministic, use no external dependencies (stdlib only), and run as a CLI.

## 0. Test Codegen Policy
Hard constraints:
- Do not change semantics: for the same input, the output (lines) and exit code must stay identical.
- Do not change the order of summary lines, the format of FAIL/OK lines, fields, or key names in cases.
- Do not add new check types beyond those described below.
- Do not leave any “variant” implementation points in the specification (no A/B behavior).

Allowed changes (implementation only):
- Local variable names and function structure are up to you.
- CPU/memory optimizations are allowed if semantics stay unchanged.

## 1. Input File (Cases)
`--cases`: path to a JSON file.
File format: a JSON array (list) of objects (dicts).

Each case object MUST contain:
- `name`: str (non-empty after `strip`)
- `expected_clean_text`: str (may be empty)

Then each case object must be exactly one of two types:

1. text-only case:
- `raw_text`: str (may be empty)
- without the `words` field

2. explicit-geometry case:
- `words`: `list[dict]`
- without the `raw_text` field

Optional fields only for explicit-geometry case:
- `page_num`: int
- `page_height`: int|float
- `page_lines`: `list[dict]`

Allowed case object keys:
- `name`
- `expected_clean_text`
- `raw_text`
- `words`
- `page_num`
- `page_height`
- `page_lines`

Any deviation from the cases format is FAIL (a test data error): print a clear message and exit `1`.

FAIL conditions include:
- unknown key
- missing `name`
- missing `expected_clean_text`
- both `raw_text` and `words` are missing
- both `raw_text` and `words` are present at the same time
- invalid type for any field

## 2. CLI Flags
- `--cases` (`Path`) default = `DEFAULT_CASES`
- `--content-metadata` (`Path`) default = `DEFAULT_CONTENT_METADATA`
- `--verbose` (bool flag): print `OK   [name]` for each successful case
- `--show-diff` (bool flag): on FAIL, print additional diagnostics (see below)
- `--max-diff-tokens` (`int`) default = `30`

## 3. Pipeline Call
The test MUST call the real page cleanup/extraction pipeline.

IMPORTANT:
- The test must not implement its own header/caption/URL/footnote removal logic, etc.
- The test only feeds a synthetic page and metadata into the real pipeline and compares the result.
- The real pipeline must receive:
  - `words = SyntheticPage.extract_words()`
  - `page_height = SyntheticPage.height`
  - `page_num`
  - rules metadata
  - `page_lines = SyntheticPage.lines`
- The test is not allowed to modify explicit `words` or `page_lines` before calling the pipeline.

## 4. Normalization for Comparison
`normalize(s: str) = " ".join((s or "").split())`

A case is PASS if:
`normalize(actual) == normalize(expected)`

## 5. Required Implementation Details
5.1 `SyntheticPage` (mandatory)
Create a class `SyntheticPage` that:
- accepts a case object
- has field `raw_text: str`
- has field `height: float`
- has field `lines: list[dict]`
- implements `extract_words(**kwargs) -> list[dict]`

Behavior is strict:

A) text-only case
If the case contains `raw_text`:
- use `raw_text` as the source of synthetic text
- generate `words` deterministically from `raw_text`
- `lines = []`
- `height = 1000.0`

Every word dict in this mode must contain at least:
- `text: str`
- `top: float`
- `x0: float`
- `size: float`

Requirements for word generation in text-only mode:
- Deterministic: depends only on `raw_text`.
- Line-based splitting: split `raw_text` into lines by `"\n"`.
- For each line, apply `normalize_line` (imported from the project) and drop lines that become empty after `normalize_line`.
- For each non-empty line, build one or more word entries so that the pipeline can reconstruct the text.
  (Per-word or per-line generation is allowed, but it must be deterministic and identical across all cases.)
- Coordinate fields must be valid numbers. A simple scheme is acceptable:
  `top` increases by a fixed step for each line,
  `x0` is fixed (for example `0.0`),
  `size` is fixed (for example `10.0`).

B) explicit-geometry case
If the case contains `words`:
- `extract_words(**kwargs)` MUST return `words` unchanged
- `raw_text = ""`
- `lines = page_lines` if the field is provided, otherwise `[]`
- `height = page_height` if the field is provided, otherwise `1000.0`

5.1.1 words schema (strict)
For an explicit-geometry case the `words` field is required.

`words` must be a non-empty list.
Every item in `words` must be a dict with exactly these keys:
- `text`
- `top`
- `x0`
- `size`
- `bottom`

Types:
- `text`: str
- `top`: int|float
- `x0`: int|float
- `size`: int|float
- `bottom`: int|float

Any deviation is FAIL.

5.1.2 page_lines schema (strict)
If the `page_lines` field is provided:
- it must be a list

Every item in `page_lines` must be a dict with exactly these keys:
- `top`
- `x0`
- `x1`
- `linewidth`

Types:
- `top`: int|float
- `x0`: int|float
- `x1`: int|float
- `linewidth`: int|float

Any deviation is FAIL.

5.2 Metadata source / `page_num` (strict: book metadata only)
All data for:
- headers/chapter titles (for pipeline header leak rules),
- known figure captions / exceptions / manual pages,
must come only from `--content-metadata` (the book JSON metadata).
The test must not read any extra files for captions/headers.

If the case contains `page_num`:
- use it directly

Otherwise:
- for a text-only case, `infer_page_num(raw_text, content_metadata)` is allowed
- for an explicit-geometry case, use `page_num = 1`

## 6. Fail Diagnostics
On case FAIL, print exactly:

FAIL [<name>]
  expected: <expected!r>
  actual  : <actual!r>

If `--show-diff` is enabled:
- additionally print normalized versions:
  `expected_norm: <normalize(expected)!r>`
  `actual_norm  : <normalize(actual)!r>`
- print a simple token diff on normalized text:
  - `tokens_expected = normalize(expected).split(" ")`
  - `tokens_actual   = normalize(actual).split(" ")`
  - show up to `--max-diff-tokens` first differing pairs `(index, exp_token, act_token)`
  - if one list is shorter, show missing tokens as `"<EOF>"`

Do not use external diff libraries.

## 7. Output
For each case:
- if PASS and `--verbose`: print `OK   [<name>]`
- if FAIL: print the FAIL block (see above)

After all cases, print exactly one summary line:
`summary: total=<total> failed=<failed> passed=<passed>`
