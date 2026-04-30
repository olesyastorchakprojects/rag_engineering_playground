You are writing one Python script: `inheritance.py`.
This is a CLI test for the fixed-in-structural chunker. It verifies that every derived child chunk preserves the required parent metadata exactly.

The script must:
- use stdlib only;
- be deterministic;
- invoke the chunker through subprocess;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. Test Purpose
The test checks:
- that child chunks preserve parent `doc_id`;
- that child chunks preserve parent `url`;
- that child chunks preserve parent `document_title`;
- that child chunks preserve parent `section_title`;
- that child chunks preserve parent `section_path`;
- that child chunks preserve parent `tags`;
- that child chunks preserve coarse parent `page_start` and `page_end`;
- that a file containing multiple parent `doc_id` values keeps each child under the correct parent document identity.

This is a metadata-inheritance contract test.
This is not a sentence-boundary quality test.
This is not a token-budget quality test.

## 2. Inputs
CLI arguments:
- `--input` (`Path`) required
- `--config` (`Path`) required
- `--schema` (`Path`) required
- `--report-only` (`store_true`)
- `--max-errors` (`int`) default = `20`

The script must also define these constants:
- `SCRIPT_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = SCRIPT_DIR.parents[4]`
- `CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed_in_structural/chunker.py"`

File `--input`:
- JSONL input structural chunks;
- each non-empty line is a JSON object already conforming to the chunk schema.

File `--config`:
- fixed-in-structural chunker TOML config.

File `--schema`:
- chunk JSON Schema file;
- it is passed through to the chunker CLI.

## 3. Parent Index
Define:
`load_jsonl(path: Path)`
- reads JSONL;
- skips empty lines;
- returns rows.

Define:
`parent_index(rows) -> dict`

Logic:
- return a mapping keyed by this tuple:
  - `(doc_id, section_path tuple, page_start, page_end, url, document_title, tuple(tags))`
- value:
  - the full parent row

Meaning:
- parent identity for this test is the full inherited metadata footprint;
- exact parent `text` must not be part of the inheritance key.

## 4. Running the Chunker
Define:
`run_chunker(input_path: Path, config_path: Path, schema_path: Path, out_path: Path) -> None`

Logic:
- invoke exactly:

```python
subprocess.run(
    [
        "python3",
        str(CHUNKER),
        "--chunks",
        str(input_path),
        "--config",
        str(config_path),
        "--chunk-schema",
        str(schema_path),
        "--out",
        str(out_path),
    ],
    check=True,
    capture_output=True,
    text=True,
)
```

## 5. Main Checks
After running the chunker:
- load `parents = load_jsonl(args.input)`
- load `children = load_jsonl(out_path)`

If `children` is empty:
- print exactly `FAIL: no chunks in <out_path>`
- exit code 1

For each child:
- build the same inheritance key from the child row:
  - `(doc_id, tuple(section_path), page_start, page_end, url, document_title, tuple(tags))`
- if that key does not exist in the parent index:
  - this is a violation:
    - `kind = "unknown_parent_metadata"`
- otherwise it is valid inheritance.

Additionally verify:
- there is no child where `page_end < page_start`
- there is no child with empty `section_path` if the matched parent had non-empty `section_path`
- there is no child with a different `doc_id` from its matched parent

Important:
- do not compare `chunk_id`;
- do not compare `chunk_created_at`;
- do not compare `content_hash`;
- do not compare `text` against parent text;
- do not require one-to-one child-to-parent counts.

## 6. Output Format
Always print first:
- `parents=<P> children=<C> invalid=<K>`

Then always print:
- `violation_counts=<dict(sorted(...))>`

If there are examples:
- `Inheritance mismatch examples:`
- then lines of the form:
  - `  row=<i> kind=<kind> reason=<reason>`

## 7. Final Status
- if there is at least one violation and `--report-only` is not enabled:
  - `FAIL: inheritance validation failed`
- if there are violations and `--report-only` is enabled:
  - `WARN: inheritance validation failed (report-only)`
- if there are no violations:
  - `OK: child chunks preserve parent metadata`

## 8. Implementation Requirements
- Stdlib only.
- Use `argparse`, `json`, `subprocess`, `tempfile`, `Counter`, `Path`.
- Do not import chunker code directly.
- Keep the code straightforward.
- Do not make network requests.
- At the end include:
  - `if __name__ == "__main__":`
  - `    main()`
