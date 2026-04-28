# Spec: synthetic_regression.py — Two-Column Extension

## Context

`synthetic_regression.py` tests `clean_page_text` with controlled synthetic inputs.
Originally it hardcodes `rules_metadata` from `data/rules/rules_metadata.json`.
This spec extends it with a `--rules-metadata` CLI argument so the same script can
be run with different profiles (e.g. two-column).

---

## 1. CLI Change

Add one optional argument to `parse_args()`:

```
--rules-metadata <path>   Path to rules_metadata.json.
                          Default: data/rules/rules_metadata.json
```

The constant `DEFAULT_RULES_METADATA = Path("data/rules/rules_metadata.json")` becomes
the default value for the argument. Existing behaviour is unchanged when the flag is absent.

---

## 2. Two-Column Fixture File

File: `Execution/tests/fixtures/parsing/extractor/two_column_synthetic_cleanup_cases.json`

Format: same JSON array as `synthetic_cleanup_cases.json`.
Each case uses the `words` variant (explicit word geometry) — `raw_text` is not suitable
because it carries no x0 information for column splitting.

Required fields per case: `name`, `words`, `expected_clean_text`.
Optional: `page_height` (default 1000.0), `page_num` (default 1), `page_lines`.

The fixture is run against a minimal two-column rules profile
(`two_column_rules_metadata.json`, see §3) that has:
- `layout.mode = "two_column"`, `column_split_x = 300.0`
- `y_tol = 2.0`, `top_band_pct = 0.10`, `bottom_band_pct = 0.90`
- `superscript.enabled = false`
- one line rule: `footer_page_number` — drops `^\d{1,2}$` in bottom band
- one block rule: `footnote_hrule` — `post_line_rules`, horizontal_line anchor
  (`top_gte_pct=0.70`, `x0_lte=90`, `width_gte=60`, `width_lte=150`, `linewidth_lte=1.0`,
  `select=lowest`), `when: all_words_below_anchor_size_ratio_lte` reference=`body_median_font`
  value=`0.85`, `ignore_first_word_if_matches=^\d{1,2}$`

---

## 3. Minimal Rules Metadata Fixture

File: `Execution/tests/fixtures/parsing/extractor/two_column_rules_metadata.json`

```json
{
  "profile_version": 1,
  "profile_name": "two-column-synthetic-test",
  "params": {
    "y_tol": 2.0,
    "top_band_pct": 0.10,
    "bottom_band_pct": 0.90,
    "superscript": { "enabled": false, "max_digits": 2, "size_ratio": 0.75 },
    "captions": {
      "enabled": false,
      "start_pattern": "^Figure\\s+\\d+",
      "flags": "i",
      "chapter_aware": false,
      "max_cont_lines": 2,
      "max_line_len": 150,
      "empty_lines_required": 1
    },
    "footnotes": {
      "enabled": false,
      "start_y_pct": 0.80,
      "size_ratio": 0.85,
      "marker_patterns": ["^\\d{1,2}$"]
    },
    "layout": { "mode": "two_column", "column_split_x": 300.0 }
  },
  "rules": {
    "line": [
      {
        "name": "footer_page_number",
        "type": "line_regex",
        "enabled": true,
        "scope": { "band": "bottom" },
        "pattern": "^\\d{1,2}$",
        "flags": ""
      }
    ],
    "block": [
      {
        "name": "footnote_hrule",
        "type": "region_rule",
        "enabled": true,
        "stage": "post_line_rules",
        "target": "words",
        "references": [
          { "name": "body_median_font", "kind": "median_word_font_size_above_anchor", "fallback": 0.0 }
        ],
        "anchor": {
          "kind": "horizontal_line",
          "source": "page.lines",
          "where": {
            "top_gte_pct": 0.70,
            "x0_lte": 90.0,
            "width_gte": 60.0,
            "width_lte": 150.0,
            "linewidth_lte": 1.0
          },
          "select": "lowest"
        },
        "candidate_region": {
          "kind": "region_below_anchor_to_page_bottom",
          "offset": 2.0
        },
        "when": {
          "all": [
            {
              "kind": "all_words_below_anchor_size_ratio_lte",
              "reference": "body_median_font",
              "value": 0.85,
              "ignore_first_word_if_matches": "^\\d{1,2}$"
            }
          ]
        },
        "action": { "type": "drop_region" }
      }
    ],
    "text": []
  }
}
```

---

## 4. Test Cases

### 4.1 `two_column_left_before_right`

**What it tests:** left column content appears before right column content in output,
even when words from both columns share the same `top` coordinate.

- Left col (x0 < 300): "Alpha Beta" at top=100
- Right col (x0 ≥ 300): "Gamma Delta" at top=100
- Expected: `"Alpha Beta Gamma Delta"`

### 4.2 `two_column_line_rule_per_column`

**What it tests:** the page-number line rule fires independently in each column's
bottom band and removes the footer from both.

- Left col: body text at top=100 + word "8" at top=910 (bottom band: 910 > 0.90×1000=900)
- Right col: body text at top=100 + word "8" at top=910
- Expected: body text only, no "8"

### 4.3 `two_column_footnote_removed_in_left_preserved_in_right`

**What it tests:** the hrule block rule fires for the left column (footnote-sized text
below anchor) but does NOT fire for the right column (body-sized text below the same anchor).

Setup (`page_height=1000`):
- `page_lines`: one hrule at `top=720` (`> 0.70×1000=700` ✓),
  `x0=72`, `x1=132` (width=60), `linewidth=0.5`
- Left col: "BodyLeft" at top=200 (size=10.0) + "Footnote" at top=730 (size=7.5)
- Right col: "BodyRight" at top=200 (size=10.0) + "BodyBelow" at top=730 (size=10.0)

body_median above anchor for left col = 10.0; 7.5 / 10.0 = 0.75 ≤ 0.85 → drop.
body_median above anchor for right col = 10.0; 10.0 / 10.0 = 1.0 > 0.85 → keep.

- Expected: `"BodyLeft BodyRight BodyBelow"`

### 4.4 `two_column_text_split_at_column_boundary`

**What it tests:** text logically split across columns (end of left col + start of right col)
is joined correctly in the output with a space separator.

- Left col: "result = {" at top=500 (bottom of left col)
- Right col: "value: 42}" at top=100 (top of right col — different vertical position, correct)
- Expected: `"result = { value: 42}"`

---

## 5. How to Run

```
cd Execution/tests/parsing/extractor
python3 synthetic_regression.py \
  --rules-metadata ../../fixtures/parsing/extractor/two_column_rules_metadata.json \
  --cases ../../fixtures/parsing/extractor/two_column_synthetic_cleanup_cases.json \
  --content-metadata data/content/book_content_metadata.json \
  --verbose
```
