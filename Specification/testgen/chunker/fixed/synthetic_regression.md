You are writing one Python script: `synthetic_regression.py`.
This is a CLI test for the fixed chunker. It runs the fixed chunker on small synthetic inputs and verifies that the output matches the expected fixed chunking contract.

The script must:
- use stdlib only;
- be deterministic;
- invoke the fixed chunker through subprocess;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. Test Purpose
The test covers real fixed chunker scenarios:
- sentence-based packing;
- overshoot from the final full sentence;
- long sentence rule;
- duplicate pages;
- empty lines in `PAGES`;
- empty pages;
- marker-aware page coverage;
- `CONTENT_METADATA`-based section annotation;
- expected hard failures.

This is a regression test for fixed sentence-based chunk assembly.

## 2. Inputs
CLI arguments:
- `--cases` (`Path`) required
- `--report-only` (`store_true`)
- `--verbose` (`store_true`)

The script must also define these constants:
- `SCRIPT_DIR = Path(__file__).resolve().parent`
- `REPO_ROOT = SCRIPT_DIR.parents[2]`
- `CHUNKER = REPO_ROOT / "Execution/parsing/chunker/fixed/chunker.py"`

File `--cases`:
- JSON array;
- each element is a synthetic case object.

Each case must allow defining:
- `pages`
- `book_metadata`
- `content_metadata`
- `config`
- `expected_chunk_count`
- `expected_page_ranges`
- `expected_section_paths`
- `expected_text_contains`
- `expected_fail`

## 3. Main Checks
For each case the test must verify:
- expected chunk count;
- expected page ranges;
- expected `section_path`;
- expected text anchors;
- expected hard failure semantics for negative cases.

## 4. Output Format
For each case:
- `[OK] <name>`
or
- `[FAIL] <name>`

On failure print the list of reasons.

At the end:
- `cases=<N> failed=<K>`

## 5. Final Status
- if `failed > 0` and `--report-only` is not enabled:
  - `FAIL: synthetic regression failed`
- if `failed > 0` and `--report-only` is enabled:
  - `WARN: synthetic regression failed (report-only)`
- if `failed == 0`:
  - `OK: all synthetic regression cases passed`
