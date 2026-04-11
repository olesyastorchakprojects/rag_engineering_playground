You are writing one Python script: `determinism.py`.
This is a CLI test for the chunker. It runs the chunker twice on the same input and checks that the stable output fields match exactly.

The script must:
- use stdlib only;
- be deterministic;
- invoke the chunker through subprocess;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. TEST PURPOSE
The test checks:
- that the chunker produces the same number of chunks on repeated runs;
- that stable chunk fields do not change between run 1 and run 2;
- that nondeterministic serialization fields are excluded from comparison.

This is a stability/regression test, not a quality test.

## 2. INPUTS
CLI arguments:
- `--pages` (`Path`) required
- `--metadata` (`Path`) required
- `--report-only` (`store_true`)
- `--max-errors` (`int`) default = `10`

The script must also define these constants:
- `SCRIPT_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = SCRIPT_DIR.parents[1]`
- `CHUNKER = REPO_ROOT / "Execution/parsing/chunker/structural/chunker.py"`

Behavior for missing arguments:
- if `--pages` is not provided, the CLI must fail with an argument error;
- if `--metadata` is not provided, the CLI must fail with an argument error.

If `args.pages.exists() == False`:
- print exactly `FAIL: pages file not found: <path>`
- exit code 1

If `args.metadata.exists() == False`:
- print exactly `FAIL: metadata file not found: <path>`
- exit code 1

## 3. HELPER FUNCTIONS
Required helper functions:

`load_jsonl(path: Path)`
- reads JSONL;
- each non-empty line is a JSON object;
- skips empty lines;
- returns a list of rows.

`stable_projection(rows)`
- sorts rows by `int(row.get("chunk_index", 0))`
- returns a new `list[dict]` where each row keeps only:
  - `chunk_index = int(row.get("chunk_index", 0))`
  - `page_start = int(row.get("page_start", 0))`
  - `page_end = int(row.get("page_end", 0))`
  - `section_path = list(row.get("section_path", []) or [])`
  - `text = (row.get("text", "") or "").strip()`

Important:
- no other fields may participate in the comparison;
- specifically do not compare:
  - `doc_id`
  - `chunk_id`
  - `chunk_created_at`
  - `document_title`
  - `tags`
  - `url`
  - `content_hash`
  - `chunking_version`

`run_once(pages: Path, metadata: Path, out_jsonl: Path)`
- invokes the chunker using exactly this command:

```python
subprocess.run(
    [
        "python3",
        str(CHUNKER),
        "--pages",
        str(pages),
        "--metadata",
        str(metadata),
        "--out",
        str(out_jsonl),
    ],
    check=True,
    capture_output=True,
    text=True,
)
```

## 4. MAIN LOGIC
In `main()`:
- parse CLI args;
- verify `args.pages.exists()` and `args.metadata.exists()`;
- create `TemporaryDirectory(prefix="chunk_determinism_")`;
- inside it create:
  - `chunks_run1.jsonl`
  - `chunks_run2.jsonl`

Run:
- `run_once(args.pages, args.metadata, out1)`
- `run_once(args.pages, args.metadata, out2)`

Then:
- `a = stable_projection(load_jsonl(out1))`
- `b = stable_projection(load_jsonl(out2))`

## 5. RUN COMPARISON
If `len(a) != len(b)`:
- print exactly:
  - `FAIL: chunk count differs between runs: run1=<len(a)> run2=<len(b)>`
- exit code 1

Otherwise:
- create:
  - `mismatches = []`
  - `field_mismatch_counts = {"chunk_index": 0, "page_start": 0, "page_end": 0, "section_path": 0, "text": 0}`

Compare pairwise:
- `for i, (ra, rb) in enumerate(zip(a, b), start=1):`
  - if `ra != rb`:
    - for each key in `field_mismatch_counts`:
      - if `ra.get(key) != rb.get(key)`, increment the corresponding counter
    - append mismatch:
      - `(i, ra, rb)`
    - if `len(mismatches) >= args.max_errors`, stop the loop

## 6. OUTPUT FORMAT
Always print first:
- `chunks=<len(a)> mismatches=<len(mismatches)>`

If `any(field_mismatch_counts.values())`:
- print:
  - `field_mismatch_counts=<field_mismatch_counts>`

If `mismatches` is not empty:
- print:
  - `Determinism mismatch examples:`
- then for each mismatch in `mismatches[: args.max_errors]`:
  - `  row=<i> run1=<ra>`
  - `         run2=<rb>`

If `mismatches` is empty:
- do not print any example block.

## 7. FINAL STATUS AND EXIT CODE
If `mismatches` is not empty:
- if `report_only == True`:
  - print `WARN: determinism test failed (report-only)`
  - exit code 0
- otherwise:
  - print `FAIL: determinism test failed`
  - exit code 1

If `mismatches` is empty:
- print `OK: chunker output is deterministic for stable fields`
- exit code 0

## 8. REPORT SHAPE EXAMPLE
```text
chunks=157 mismatches=0
OK: chunker output is deterministic for stable fields
```

Example failing shape:

```text
chunks=157 mismatches=2
field_mismatch_counts={'chunk_index': 0, 'page_start': 1, 'page_end': 0, 'section_path': 0, 'text': 2}
Determinism mismatch examples:
  row=14 run1={'chunk_index': 14, 'page_start': 41, 'page_end': 41, 'section_path': ['Communication', 'Reliable Links'], 'text': '...'}
         run2={'chunk_index': 14, 'page_start': 42, 'page_end': 42, 'section_path': ['Communication', 'Reliable Links'], 'text': '...'}
FAIL: determinism test failed
```

## 9. IMPLEMENTATION REQUIREMENTS
- Stdlib only.
- Use `argparse`, `json`, `subprocess`, `sys`, `tempfile`, `Path`.
- Keep the code straightforward.
- Do not import chunker code directly.
- Do not add alternative sorting modes.
- Comparison must use only the stable projection.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
