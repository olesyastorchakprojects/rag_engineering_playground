You are writing one Python script: `synthetic_regression.py`.
This is a CLI test for the fixed-in-structural chunker. It runs the chunker on small synthetic structural-chunk inputs and verifies that the output matches the expected chunk-splitting contract.

The script must:
- use stdlib only;
- be deterministic;
- invoke the chunker through subprocess;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. Test Purpose
The test covers real fixed-in-structural scenarios:
- sentence-based packing inside one parent structural chunk;
- overshoot from the final full sentence;
- long sentence rule;
- overlap behavior within one parent chunk;
- no output chunk crossing parent structural chunk boundaries;
- empty parent text producing no output chunks;
- preservation of parent `section_path`;
- preservation of coarse parent `page_start` and `page_end`;
- support for multiple `doc_id` values in one input file;
- expected hard failures.

This is a regression test for fixed-size chunk assembly over structural chunk input.

## 2. Inputs
CLI arguments:
- `--cases` (`Path`) required
- `--report-only` (`store_true`)
- `--verbose` (`store_true`)

The script must also define these constants:
- `SCRIPT_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = SCRIPT_DIR.parents[4]`
- `CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed_in_structural/chunker.py"`
- `CHUNK_SCHEMA = REPO_ROOT / "Execution/schemas/chunk.schema.json"`

File `--cases`:
- JSON array;
- each element is a synthetic case object.

Each case must allow defining:
- `name`
- `chunks`
- `config`
- `expected_chunk_count`
- `expected_doc_ids`
- `expected_page_ranges`
- `expected_section_paths`
- `expected_text_contains`
- `forbid_cross_parent_text_pairs`
- `expected_fail`

`chunks` format:
- array of input structural chunk records;
- each record is already a chunk-schema-shaped object;
- test cases may mix different `doc_id` values in the same input file.

`forbid_cross_parent_text_pairs` format:
- array of objects;
- each object contains:
  - `left_anchor` (str) required
  - `right_anchor` (str) required
- meaning:
  - no single output chunk text may contain both anchors together.

## 3. Main Checks
For each case the test must verify:
- expected chunk count;
- expected `doc_id` sequence;
- expected page ranges;
- expected `section_path` sequence;
- expected text anchors;
- that forbidden anchor pairs are never merged into one output chunk;
- expected hard failure semantics for negative cases.

## 4. Case Preparation
Required helper functions:

`write_jsonl(path: Path, rows)`
- writes JSONL with one object per line;
- uses `json.dumps(..., ensure_ascii=False)`;
- ends the file with a final newline.

`write_toml_text(path: Path, text: str)`
- writes the config text as UTF-8 exactly as provided.

`load_jsonl(path: Path)`
- reads JSONL;
- skips empty lines;
- returns a list of rows.

## 5. Running One Case
Define:
`run_case(case: dict, verbose: bool = False) -> list[str]`

Logic:
- take `name = case["name"]`
- create `TemporaryDirectory(prefix=f"chunk_fis_{name}_")`
- inside it create:
  - `input_chunks.jsonl`
  - `config.toml`
  - `out_chunks.jsonl`
- write inputs using the helper functions

Run the chunker:

```python
subprocess.run(
    [
        "python3",
        str(CHUNKER),
        "--chunks",
        str(input_chunks_path),
        "--config",
        str(config_path),
        "--chunk-schema",
        str(CHUNK_SCHEMA),
        "--out",
        str(out_chunks_path),
    ],
    check=True,
    capture_output=not verbose,
    text=True,
)
```

Then:
- `rows = load_jsonl(out_chunks_path)`
- `errs = []`

Negative cases:
- if `case.get("expected_fail")` is true:
  - the chunker must fail;
  - if it succeeds, add:
    - `f"expected failure but chunker succeeded"`
- if `expected_fail` is false or absent:
  - the chunker must succeed;
  - if it fails, add:
    - `f"unexpected failure: <stderr_or_exception_summary>"`

## 6. Case Checks
If the chunker succeeded:

Compute:
- `actual_doc_ids = [row.get("doc_id") for row in rows]`
- `actual_page_ranges = [(row.get("page_start"), row.get("page_end")) for row in rows]`
- `actual_section_paths = [row.get("section_path", []) for row in rows]`
- `texts = [str(row.get("text", "")) for row in rows]`

If the case contains `expected_chunk_count`:
- compare with `len(rows)`

If the case contains `expected_doc_ids`:
- compare by strict list equality

If the case contains `expected_page_ranges`:
- compare by strict list equality

If the case contains `expected_section_paths`:
- compare by strict list equality

If the case contains `expected_text_contains`:
- it is an array of strings;
- for each string, at least one output chunk text must contain it;
- otherwise add:
  - `f"missing expected text anchor: {anchor!r}"`

If the case contains `forbid_cross_parent_text_pairs`:
- for each pair object:
  - if any single output chunk text contains both anchors:
    - add:
      - `f"forbidden text merge detected: left={left!r} right={right!r}"`

Important:
- do not check exact chunk text equality;
- do not check `chunk_id`;
- do not check `chunk_created_at`;
- do not require exact token counts in the report;
- the synthetic test validates behavioral contract, not exact serialization.

## 7. Output Format
For each case:
- `[OK] <name>`
or
- `[FAIL] <name>`

On failure print the list of reasons.

At the end:
- `cases=<N> failed=<K>`

## 8. Final Status
- if `failed > 0` and `--report-only` is not enabled:
  - `FAIL: synthetic regression failed`
- if `failed > 0` and `--report-only` is enabled:
  - `WARN: synthetic regression failed (report-only)`
- if `failed == 0`:
  - `OK: all synthetic regression cases passed`

## 9. Implementation Requirements
- Stdlib only.
- Use `argparse`, `json`, `subprocess`, `tempfile`, `Path`.
- Keep the code short and straightforward.
- Do not import chunker code directly.
- The test must invoke the real CLI chunker.
- Do not add parallelism.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
