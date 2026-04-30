# Chunker Test Layout

This directory is organized by chunker variant scope:

- `common/`
- `fixed/`
- `structural/`
- `fixed_in_structural/`

## What Goes In `common/`

Place a chunker executable test in `common/` when it should hold for every
chunker variant that emits the shared chunk contract.

Examples:

- determinism;
- sanitation;
- schema validation.

These tests should avoid assumptions that only one chunker strategy can satisfy.

## What Goes In `fixed/`

Place a test in `fixed/` when it depends on fixed sentence-based chunker
semantics.

Examples:

- page mapping behavior for overlapped sentence-packed chunks;
- fixed-specific synthetic regression cases;
- overlap-sensitive expectations.

Associated fixtures should live under:

- `Execution/tests/fixtures/parsing/chunker/fixed/`

## What Goes In `structural/`

Place a test in `structural/` when it depends on metadata-driven structural
chunking semantics.

Examples:

- heading structure validation;
- span quality against metadata-driven section boundaries;
- truth consistency tied to structural hierarchy;
- structural synthetic regression cases.

Associated fixtures should live under:

- `Execution/tests/fixtures/parsing/chunker/structural/`

## What Goes In `fixed_in_structural/`

Place a test in `fixed_in_structural/` when it depends on sentence-based fixed
repacking over structural chunk input.

Examples:

- child chunk inheritance from parent structural chunks;
- no cross-parent chunk merging;
- fixed-size splitting behavior over chunk input rather than page input.

Associated fixtures should live under:

- `Execution/tests/fixtures/parsing/chunker/fixed_in_structural/`

## Current Repository Rule

The current executable layout is:

- `common/determinism.py`
- `common/sanitation.py`
- `common/schema_validation.py`
- `fixed/page_mapping.py`
- `fixed/synthetic_regression.py`
- `fixed_in_structural/inheritance.py`
- `fixed_in_structural/overlap.py`
- `fixed_in_structural/synthetic_regression.py`
- `structural/span_quality.py`
- `structural/structure.py`
- `structural/synthetic_regression.py`
- `structural/truth_consistency.py`

If a new test could reasonably apply to both chunker variants, start by putting
it in `common/`. Move it into `fixed/` or `structural/` only when its
assertions truly depend on one chunker strategy.
