You are writing one Python script: `schema_validation.py`.
This is a CLI test for the chunker. It verifies that every record in `chunks.jsonl` conforms to `Execution/schemas/chunk.schema.json`.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- that every `chunks.jsonl` row is valid against the JSON Schema;
- that no required fields are missing;
- that there are no extra top-level or nested fields when `additionalProperties = false`;
- that types and basic value constraints are satisfied;
- that `page_end >= page_start`.

This is a contract / schema validation test.
This is not a quality test.
This is not a span test.

## 2. INPUTS
CLI arguments:
- `--chunks` (`Path`) required
- `--schema` (`Path`) required
- `--report-only` (`store_true`)
- `--max-errors` (`int`) default = `10`

Important:
- `--chunks` and `--schema` must not have default paths;
- the script must not try to auto-fill paths;
- if `--chunks` is not provided, the CLI must fail with an argument error;
- if `--schema` is not provided, the CLI must fail with an argument error.

File `--chunks`:
- JSONL;
- each non-empty line is a JSON object.

File `--schema`:
- JSON object;
- it is JSON Schema draft 2020-12;
- for this task it is enough to support the subset of schema features actually used by `chunk_schema.json`.

If `--chunks` contains no rows:
- print exactly `FAIL: no chunks in <path>`
- exit code 1

## 3. HELPER FUNCTIONS
Required helper functions:

`load_json(path: Path)`
- reads the full JSON file through `json.load`.

`load_jsonl(path: Path)`
- reads JSONL;
- skips empty lines;
- returns a list of rows.

`check_type(value, expected: str) -> bool`
- must support:
  - `object`
  - `array`
  - `string`
  - `integer`
  - `null`
- for `integer`, bool must not count as int.

`validate_datetime(value: str) -> bool`
- must validate ISO 8601 datetime through `datetime.fromisoformat(value.replace("Z", "+00:00"))`
- if parsing fails, return `False`.

## 4. JSON SCHEMA SUBSET
Define:
`validate_instance(instance, schema, path, errors) -> None`

Support only these schema keywords:
- `type`
- `required`
- `properties`
- `additionalProperties`
- `items`
- `minLength`
- `minimum`
- `format`

Logic:
- if `type` is a string:
  - the instance must match exactly that type;
- if `type` is a list:
  - the instance must match at least one type from the list;
- on type mismatch add:
  - `{"kind": "type_error", "path": path, "reason": "..."}`

Object validation:
- if instance is a dict:
  - check `required`
  - for each missing required field add:
    - `{"kind": "missing_required", "path": path, "reason": "missing required field '<field>'"}`
  - if `additionalProperties == false`:
    - any key not listed in `properties` is an error:
      - `{"kind": "additional_property", "path": f"{path}.{key}", "reason": "unexpected property"}`
  - for each key in `properties`, if it exists in the instance:
    - recursively call `validate_instance(...)`

Array validation:
- if instance is a list and `items` is present:
  - validate each element recursively
  - the path must look like:
    - `$.section_path[0]`

String validation:
- if `minLength` exists:
  - strings shorter than the threshold -> `value_error`
- if `format == "date-time"`:
  - use `validate_datetime`
  - invalid format -> `value_error`

Integer validation:
- if `minimum` exists:
  - values below the threshold -> `value_error`

## 5. BUSINESS RULE
Define:
`validate_chunk(chunk, schema) -> list[dict]`

Logic:
- first call `validate_instance(chunk, schema, "$", errors)`
- then separately check:
  - if `page_start` and `page_end` are both ints and `page_end < page_start`:
    - add:
      - `{"kind": "value_error", "path": "$.page_end", "reason": "page_end < page_start"}`
- return the list of errors.

## 6. MAIN LOGIC
In `main()`:
- parse CLI args;
- load `rows = load_jsonl(args.chunks)`
- load `schema = load_json(args.schema)`
- if `rows` is empty:
  - print `FAIL: no chunks in <path>`
  - exit code 1

Then:
- `invalid_rows = 0`
- `violation_counts = Counter()`
- `examples = []`

For each row:
- `errors = validate_chunk(row, schema)`
- if `errors` is empty:
  - continue
- otherwise:
  - `invalid_rows += 1`
  - for each error increment `violation_counts[error["kind"]]`
  - while `len(examples) < max_errors`, store examples as:
    - `{"row": str(idx), "path": error["path"], "reason": error["reason"]}`

## 7. OUTPUT FORMAT
Always print first:
- `chunks=<len(rows)> invalid=<invalid_rows>`

Then always print:
- `violation_counts=<dict(sorted(violation_counts.items()))>`

If `examples` is not empty:
- print:
  - `Schema mismatch examples:`
- then for each example:
  - `  row=<row> path=<path> reason=<reason>`

If `examples` is empty:
- do not print the examples block.

## 8. FINAL STATUS AND EXIT CODE
If `invalid_rows > 0`:
- if `report_only == True`:
  - print `WARN: chunk schema validation failed (report-only)`
  - exit code 0
- otherwise:
  - print `FAIL: chunk schema validation failed`
  - exit code 1

If `invalid_rows == 0`:
- print `OK: all chunks satisfy the schema`
- exit code 0

## 9. IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Use `argparse`, `json`, `sys`, `Counter`, `datetime`, `Path`.
- Do not use the external `jsonschema` package.
- Do not make network requests.
- Do not import the chunker.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
