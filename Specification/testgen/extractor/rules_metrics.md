You are writing a single Python script: `rules_metrics.py`.
This is a CLI diagnostics tool that computes simple text-observable metrics from the enabled rules in `rules_metadata`.

The script must be deterministic, use no external dependencies (stdlib only), and run as a CLI.

## 0. Test Codegen Policy
Hard constraints:
- Do not change semantics: for the same input, the output (lines) and exit code must stay identical.
- Do not change the order of output lines.
- Do not add new metrics, new rule sections, or a new mode classification.
- Do not leave any variable or ambiguous places in the specification.

Allowed changes (implementation only):
- Local variable names and function structure are up to you.
- CPU/memory optimizations are allowed if semantics stay unchanged.

## 1. Inputs
1.1 `--input`
JSONL file.
Each non-empty line must be a JSON object.

Used row fields:
- `page`
- `raw_text`
- `clean_text`

Skip empty lines.

If `row["page"]` is missing or cannot be interpreted as `int`:
- print `FAIL: invalid page field`
- exit `1`

If the file does not exist:
- print `FAIL: input not found: <path>`
- exit `1`

If the JSONL is invalid:
- print `FAIL: invalid JSONL: <json_error>`
- exit `1`

If no records remain after skipping empty lines:
- print `FAIL: JSONL is empty`
- exit `1`

1.2 `--rules-metadata`
JSON file with rules metadata.

If the file does not exist:
- print `FAIL: rules-metadata not found: <path>`
- exit `1`

If the JSON is invalid:
- print `FAIL: invalid rules-metadata JSON: <json_error>`
- exit `1`

If the root is not an object:
- print `FAIL: rules-metadata root must be an object`
- exit `1`

If `payload["rules"]` is missing or is not an object:
- print `FAIL: rules-metadata.rules must be an object`
- exit `1`

## 2. CLI Flags
Create argparse flags:
- `--input` (`Path`) default = `DEFAULT_INPUT`
- `--rules-metadata` (`Path`) default = `DEFAULT_RULES`
- `--field` choices=`["clean_text","raw_text"]` default=`"clean_text"`
- `--max-samples` (`int`) default=`10`
- `--show-mode` (bool flag)

No other CLI args.

## 3. Output
Print lines in exactly this order:

pages=<N>
field=<field_value>
<rule_metric_line_1>
<rule_metric_line_2>
...

Where:
- `<N>` = the number of parsed JSONL rows after skipping empty lines
- `<field_value>` = the value of `--field`

For each rule metric line:

`<rule_name>: <matches> samples=[...]`

If `--show-mode` is enabled:

`<rule_name>: <matches> samples=[...] mode=<mode>`

`samples` format:
- at most `--max-samples` elements
- if there are more, append `,...` after the last shown item
- the format must be exactly `samples=[v1,v2,...]`
- for an empty list: `samples=[]`

Do not print any final OK/WARN/FAIL lines.
If there is no input error, exit code is always `0`.

## 4. Which Rules to Count
Use only enabled rules from sections:
- `rules.line`
- `rules.block`
- `rules.text`

Iterate sections strictly in this order:
1. `line`
2. `block`
3. `text`

Iterate rules inside each section in the original array order.

A rule must be included in the output only if:
- the rule is a dict
- `rule["name"]` is a `str`
- `rule["enabled"] is True`

Additionally, exclude a rule from the output if `rule["name"]` is one of:
- `footer_page_number`
- `bottom_footnotes_after_separator_hrule`

Do not exclude any other rule names.

## 5. Metric Semantics
For every selected rule compute:
- total matches across all pages
- sample pages where matches occurred
- mode

For each page:
- `page = int(row["page"])`
- `text = row.get(args.field)`
- if `text` is not a string, skip this page for this rule

`matches` for a rule = the sum of `page_matches` across all pages.

If `page_matches > 0` on a page:
- append the page number to `sample_pages` exactly `page_matches` times
- i.e. sample pages are not deduplicated

Example:
- if 3 matches are found on `page=10`, then `10,10,10` are added to `samples`

## 6. Helper Definitions
6.1 `collapse_ws_lower`
Function:

`collapse_ws_lower(text) = " ".join((text or "").split()).lower()`

6.2 lines for line/block metrics
For line/block text matching:
- `lines = text.splitlines()`
- if `splitlines()` returns an empty list, use `[text]`

## 7. Line Rule Metrics
For `section == "line"` the mode is always:
- `line_rule`

7.1 `line_prefix`
For each line:
- `stripped = line.lstrip()`
- if `stripped.startswith(prefix)` is true for at least one prefix in `rule["prefixes"]`, this is `+1` match

7.2 `line_regex`
Compile regex:
- `flags = re.I` if `rule["flags"] == "i"`, otherwise `0`
- `pattern = rule["pattern"]`

For each line:
- if `regex.search(line) != None`, this is `+1` match

7.3 `line_equals`
If `rule["normalize"] == "collapse_ws_lower"`:
- compare `collapse_ws_lower(line)` to `collapse_ws_lower(rule["value"])`

Otherwise:
- compare `line == rule["value"]`

A matching line gives `+1` match.

7.4 unknown line rule type
If `rule["type"]` is not one of:
- `line_prefix`
- `line_regex`
- `line_equals`

then:
- `page_matches = 0`
- `mode = "line_rule"`

## 8. Text Rule Metrics
For `section == "text"` the mode is always:
- `regex`

Compile regex:
- `flags = re.I` if `rule["flags"] == "i"`, otherwise `0`
- `pattern = rule["pattern"]`

For the whole page text:
- `page_matches = number of matches returned by regex.finditer(text)`

## 9. Block Rule Metrics
For `section == "block"` the default mode is:
- `unsupported`

Only one supported anchor form exists in this test:
- `rule["anchor"]` must be a dict
- `rule["anchor"]["kind"] == "text_line_regex"`
- `rule["anchor"]["where"]` must be a dict
- `rule["anchor"]["where"]["pattern"]` must be a string
- `rule["anchor"]["where"]["flags"]` must be a string

If all these conditions hold:
- compile regex from `anchor.where.pattern`
- use `re.I` if `anchor.where.flags == "i"`, otherwise `0`
- split text into lines using the helper rule from section 6.2
- `page_matches = number of lines where regex.search(line) != None`
- `mode = "anchor_regex"`

If the anchor shape is unsupported:
- `page_matches = 0`
- `mode = "unsupported"`

## 10. Mode Rules
Mode values are:
- `line_rule`
- `regex`
- `anchor_regex`
- `unsupported`

Mode selection rules:
- `line` section -> `line_rule`
- `text` section -> `regex`
- `block` section with supported `text_line_regex` anchor -> `anchor_regex`
- everything else -> `unsupported`

If a rule produces `0` matches on all pages but has a supported implementation path, its mode must still be the supported mode, not `unsupported`.

## 11. Sample Format
Use the first `max_samples` values from `sample_pages` in insertion order.

Formatting:
- `samples=[1,2,3]`
- if the list is longer than `max_samples`, append `,...`
- example: `samples=[10,10,12,...]`

## 12. Structure
- Only one file.
- Stdlib only.
- End with: `if __name__ == "__main__": main()`
