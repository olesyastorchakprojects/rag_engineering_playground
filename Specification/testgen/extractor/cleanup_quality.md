You are writing a single Python script: `cleanup_quality.py`.
This is a CLI test that reads JSONL with pages after cleanup and prints “garbage leakage” metrics for `clean_text`.

## 1. Output (Strict)
Print lines in exactly this order and format:

pages=<N>
header_leak: <count> samples=<samples_pages>
url_leak: <count> samples=<samples_pages>
inline_footnote_ref: <count> samples=<samples_pages>
math_glyph_leak: <count> samples=<samples_pages>
long_word_merge_leak: <count> (len><LONG_WORD_THRESHOLD>) samples=<samples_words>
<final_status_line>

Where:
- `<N>` = the number of parsed JSON lines (after skipping empty lines).
- `samples_pages` = a list of page numbers: `samples=[p1,p2,...]`, at most 10 elements; if there are more, append `",..."` after the 10th.
- `samples_words` = a list of suspicious words: `samples=[w1,w2,...]`, at most 10 elements; if there are more, append `",..."` after the 10th.
- If `N==0`: print exactly `FAIL: no rows` and exit code `1` (print nothing else).

`final_status_line`:
- if `total_violations == 0`: `OK: cleanup quality checks passed` and exit `0`
- if `total_violations > 0` and `--report-only`: `WARN: cleanup quality violations found (report-only)` and exit `0`
- if `total_violations > 0` and not `--report-only`: `FAIL: cleanup quality violations found` and exit `1`

## 2. Input
`--input`: JSONL, each non-empty line is a JSON object.
Use only these fields:
- `page` (int)
- `clean_text` (str)

Skip empty file lines (`line.strip() == ""`).

## 3. CLI Flags
- `--input` (`Path`) default = `DEFAULT_PAGES`
- `--content-metadata` (`Path`) default = `DEFAULT_CONTENT_METADATA`
- `--max-examples` (`int`) default = `0`
- `--long-word-threshold` (`int`) default = `20`
- `--report-only` (bool flag)
- `--verbose` (bool flag)

## 4. Metrics
For each metric, collect a list of hits. Every hit must contain at least:
- `page`
- `match` (the matched string)

4.1 `header_leak` (exact, for this specific book)
Load the JSON object from `--content-metadata` and read the chapter list:
`payload["chapters"]` (if missing, file missing, or invalid JSON, use an empty list).
Each chapter is a dict with fields:
- `chapter` (int)
- `title` (str)

For each chapter build the string:
`H = "Chapter {chapter}. {title_stripped}"`
where `title_stripped = title.strip()`.

For the page:
`T = clean_text` (string, if `None` -> `""`)
If `lstrip(T).startswith(H) == True` for any chapter:
- add one hit to `header_leak` for this page (`match` may be `H` or the text prefix),
- and stop checking `header_leak` for this page.

4.2 `url_leak` (regex must be exactly this, with exactly these flags)
`pattern = r"https?://|www\."`
`flags = re.I`
Compile exactly as: `re.compile(pattern, flags)`

If the regex finds a match in `clean_text`:
- add a hit (`match` = matched substring).

4.3 `inline_footnote_ref` (regex must be exactly this)
`regex_footnote = r"\[\d{1,3}(?:\s*,\s*\d{1,3})*\]"`
If `regex_footnote` finds a match in `clean_text`:
- add a hit (`match` = matched substring).

4.4 `math_glyph_leak` (regex must be exactly this)
`regex_math = r"[\U0001D400-\U0001D7FF]"`
If `regex_math` finds a match in `clean_text`:
- add a hit (`match` = matched substring).

4.5 `long_word_merge_leak`
This is a heuristic for merged words.
First build `english_words` only from the rows corpus:
- take all `[a-z]{2,20}` from `lower(clean_text)` for every page and add them to a set.

Then for each page:
- find all tokens with regex:
  `[A-Za-z0-9][A-Za-z0-9'/-]*`
- keep only tokens where `len(token) > LONG_WORD_THRESHOLD`.

For each such token candidate:
- lowercase it and strip outer whitespace.
- skip it if the token does not match `[a-z]+` (Latin letters only).
- skip it if `token ∈ english_words`.
- otherwise try to check whether the token can be segmented into 2+ consecutive parts where every part:
  - has length `2..20`,
  - belongs to `english_words`,
  - and short parts of length `2` are allowed only if the part is in `{"as","to","in","on","of","by","if","is","it","an","or","at","we"}`.
If the token is segmentable, this is one hit:
- add a hit to `long_word_merge_leak` (`match` = original token).

Important:
- samples for `long_word_merge_leak` are words (`match`), not page numbers.

## 5. Samples and Counts
For each metric:
- `count = len(hits[metric])`.

`samples_pages`:
- the first 10 `page` values from hits in insertion order.

`samples_words`:
- the first 10 `match` values from `long_word_merge_leak` hits in insertion order.

## 6. Verbose
If `--verbose` and `--max-examples > 0`:
after the metric line print up to `max_examples` hit examples for that metric in the form:
  `page=<page> match=<python_repr_of_match>`

Print no other lines.

## 7. Exit Logic
`total_violations` = the sum of `count` across all 5 metrics.
Then follow the `final_status_line` rules from the OUTPUT section.

## 8. Structure
- Only one file.
- End with: `if __name__ == "__main__": main()`
