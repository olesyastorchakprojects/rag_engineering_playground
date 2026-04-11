You are writing one Python script: `overlap.py`.
This is a CLI test for the fixed chunker. It verifies that overlap between adjacent chunks conforms to the fixed chunker contract.

The script must:
- use stdlib only;
- be deterministic;
- not import chunker code;
- work only as a CLI;
- print a short fixed-format report;
- exit using the rules below.

## 1. Test Purpose
The test checks:
- that overlap is correct for every adjacent chunk pair;
- that overlap is formed only from whole sentence units;
- that overlap is computed as a suffix of the previous chunk and a prefix of the next chunk;
- that `overlap_ratio = 0` produces no pairwise overlap;
- that overlap does not break progress;
- that the same chunk is not emitted repeatedly.

This is a fixed-specific overlap contract test.
The main validation unit is:
- the adjacent pair `chunk_i`, `chunk_{i+1}`

This is not an aggregate duplication test over the full corpus.

## 2. Inputs
CLI arguments:
- `--chunks` (`Path`) required
- `--config` (`Path`) required
- `--report-only` (`store_true`)
- `--max-errors` (`int`) default = `20`

File `--chunks`:
- JSONL chunk payloads

File `--config`:
- fixed chunker TOML config

## 3. Main Checks
The test must verify:
- that adjacent chunks are the primary validation unit;
- that when `overlap_ratio = 0`, the pair `chunk_i`, `chunk_{i+1}` has no valid suffix/prefix overlap;
- that when `overlap_ratio > 0`, overlap is checked only for the pair `chunk_i`, `chunk_{i+1}`;
- that overlap follows suffix semantics, not arbitrary duplication;
- that overlap is a prefix of the next chunk, not just a generic text intersection;
- that the next chunk is not equal to the previous chunk by `text`;
- that the chunk sequence makes progress;
- that a long-sentence chunk does not cause infinite self-overlap.

Aggregate corpus-level overlap metrics:
- may be computed as additional observability/debugging information;
- are not the primary contract invariant of this test.

## 4. Output Format
First:
- `chunks=<N> checked_pairs=<K> invalid=<M>`

Then:
- `violation_counts=<dict(sorted(...))>`

If there are examples:
- `Overlap mismatch examples:`
- then lines of the form:
  - `  pair=<i,j> kind=<kind> reason=<reason>`

## 5. Final Status
- if there is at least one violation and `--report-only` is not enabled:
  - `FAIL: overlap validation failed`
- if there are violations and `--report-only` is enabled:
  - `WARN: overlap validation failed (report-only)`
- if there are no violations:
  - `OK: overlap contract is valid`
