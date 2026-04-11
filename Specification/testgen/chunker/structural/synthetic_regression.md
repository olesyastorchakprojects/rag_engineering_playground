You are writing one Python script: `synthetic_regression.py`.
This is a CLI test for the new metadata-driven chunker. It runs the chunker on small synthetic inputs and verifies that output paths and chunk contents satisfy the expected contract.

The script must:
- use stdlib only;
- be deterministic;
- invoke the chunker through subprocess;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. TEST PURPOSE
The test covers real scenarios for the new chunker:
- intro chunks for `part` and `chapter`;
- wrapper chunks for `section` before subsections;
- leaf chunks for subsections;
- no false parent midstream chunk;
- trailing residual chunks for `chapter` and `part`;
- correct behavior for same-page siblings;
- correct behavior when an empty page appears inside a metadata range;
- the special case for the `Introduction` branch when a chapter does not belong to a part.

This is a regression test for metadata-driven chunk assembly.

## 2. INPUTS
CLI arguments:
- `--cases` (`Path`) default = `Execution/tests/fixtures/parsing/chunker/structural/synthetic_chunking_cases.json`
- `--report-only` (`store_true`)
- `--verbose` (`store_true`)

The script must also define these constants:
- `SCRIPT_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = SCRIPT_DIR.parents[4]`
- `DEFAULT_CASES = REPO_ROOT / "Execution/tests/fixtures/parsing/chunker/structural/synthetic_chunking_cases.json"`
- `CHUNKER = REPO_ROOT / "Execution/parsing/chunker/structural/chunker.py"`

File `--cases`:
- JSON array;
- each element is a JSON object case;
- all cases can be assumed valid;
- do not design separate behavior for broken JSON or invalid case structure.

One case has this shape:
- `name` (str) required
- `metadata` (object) required
- `pages` (array) required
- `expected_chunk_count` (int) optional
- `expected_paths` (array[array[str]]) optional
- `forbidden_paths` (array[array[str]]) optional
- `checks` (array[object]) optional

`pages` format:
- each element is an object with:
  - `page` (int)
  - `clean_text` (str)

`checks` format:
- each element is an object with:
  - `section_path` (array[str]) required
  - `first_anchor` (str) optional
  - `last_anchor` (str) optional

`metadata` from each case must be passed to the chunker as a separate temporary JSON file.

## 3. CASE PREPARATION
Required helper functions:

`load_cases(path: Path)`
- reads JSON and returns the case array.

`write_pages_jsonl(path: Path, pages)`
- writes JSONL;
- for each page writes an object with:
  - `page`
  - `clean_text`

`write_metadata_json(path: Path, metadata: dict)`
- writes metadata as JSON using `ensure_ascii=False`, `indent=2`
- a trailing `"\n"` is allowed

`load_chunks(path: Path)`
- reads the chunker output JSONL;
- returns a list of rows;
- skips empty lines.

## 4. RUNNING ONE CASE
Define:
`run_case(case: dict, verbose: bool = False) -> list[str]`

Logic:
- take `name = case["name"]`
- create `TemporaryDirectory(prefix=f"chunk_synth_{name}_")`
- inside it create:
  - `pages.jsonl`
  - `metadata.json`
  - `chunks.jsonl`
- write pages and metadata using helper functions

Run the chunker:

```python
subprocess.run(
    [
        "python3",
        str(CHUNKER),
        "--pages",
        str(pages_path),
        "--metadata",
        str(metadata_path),
        "--out",
        str(chunks_path),
    ],
    check=True,
    capture_output=not verbose,
    text=True,
)
```

Then:
- `chunks = load_chunks(chunks_path)`
- `errs = []`

## 5. CASE CHECKS
First compute:
- `actual_paths = [chunk.get("section_path", []) for chunk in chunks]`

If the case contains `expected_paths`:
- compare by strict list equality:
  - order must match;
  - length must match;
  - each path must match as a list of segments.
- if it does not match, add:
  - `f"unexpected path sequence: expected={expected_paths!r} actual={actual_paths!r}"`

If the case contains `expected_chunk_count`:
- compare with `len(chunks)`
- if it does not match, add:
  - `f"unexpected chunk count: expected={expected_count} actual={len(chunks)}"`

If the case contains `forbidden_paths`:
- for each forbidden path:
  - if it exists in `actual_paths`, add:
    - `f"forbidden path emitted: {forbidden}"`

Build:
- `by_path = {section_path: [chunk1, chunk2, ...]}`

For each check in `checks`:
- `path = check["section_path"]`
- `a1 = check.get("first_anchor", "")`
- `a2 = check.get("last_anchor", "")`
- `candidates = by_path.get(path) or []`
- if `candidates` is empty:
  - add `f"missing chunk for section_path: {path}"`
  - continue
- among `candidates`, find the first chunk where:
  - either `a1` is empty or `a1 in chunk["text"]`
  - and either `a2` is empty or `a2 in chunk["text"]`
- if no such chunk exists:
  - add `f"no chunk instance for {path} matches requested anchors"`

Important:
- do not check exact chunk text equality;
- do not check page numbers;
- do not check chunk ids;
- if the same `section_path` appears multiple times, that is allowed;
- in that case checks for this path should match any one instance that contains all requested anchors;
- the synthetic test must not require `section_path` uniqueness unless the case explicitly enforces it through `expected_paths` or `expected_chunk_count`;
- the synthetic test validates behavioral contract, not exact serialization.

## 6. OVERALL LOOP
In `main()`:
- parse CLI args
- load cases
- `total = len(cases)`
- `failed = 0`

For each case in order:
- `name = case.get("name", f"case_{i}")`
- `errs = run_case(case, verbose=args.verbose)`
- if `errs` is not empty:
  - `failed += 1`
  - print:
    - `[FAIL] {name}`
  - then for each error:
    - `  - {error}`
- otherwise print:
  - `[OK]   {name}`

After the loop print:
- `cases=<total> failed=<failed>`

## 7. FINAL STATUS AND EXIT CODE
After the line `cases=<total> failed=<failed>`:
- if `failed > 0` and `report_only == False`:
  - `raise SystemExit("FAIL: synthetic chunking tests failed")`
- if `failed > 0` and `report_only == True`:
  - print `WARN: synthetic chunking regressions (report-only)`
  - exit code 0
- if `failed == 0`:
  - print `OK: synthetic chunking tests passed`
  - exit code 0

## 8. OUTPUT FORMAT
The format is strictly fixed:
- one line per case:
  - `[OK]   <name>`
  - or `[FAIL] <name>`
- after `[FAIL]`, print a flat list of errors, each prefixed with `  - `
- at the end always print:
  - `cases=<total> failed=<failed>`
- then one final status line

Do not print extra output:
- do not print chunker stdout/stderr if `--verbose` is not enabled;
- do not print temporary paths;
- do not print chunk diffs;
- do not print metadata dumps.

## 9. REPORT SHAPE EXAMPLE
```text
[OK]   chapter_intro_then_sections
[OK]   subsections_emit_leaf_chunks_only
[FAIL] same_page_sibling_sections
  - unexpected path sequence: expected=['Communication/Reliable Links', 'Communication/Reliable Links/Reliability'] actual=['Communication', 'Communication/Reliable Links', 'Communication/Reliable Links/Reliability']
cases=3 failed=1
FAIL: synthetic chunking tests failed
```

## 10. IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Use `argparse`, `json`, `subprocess`, `tempfile`, `Path`.
- Keep the code short and straightforward.
- Do not import chunker code directly.
- The test must invoke the real CLI chunker.
- Do not add parallelism.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
