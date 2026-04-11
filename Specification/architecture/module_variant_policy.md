# Module Variant Policy

## Purpose

This document defines the canonical naming and placement policy for modules that
have:

- multiple implementation variants;
- shared logic across variants;
- profile-like runtime inputs that are not separate implementations.

Use this file together with:

- `Specification/architecture/project_structure.md`

If these two documents appear to conflict, use this policy to decide how to
represent variant, common, and profile axes inside an existing stage layout.

## Problem This Policy Solves

The repository currently expresses module variability in more than one way:

- sometimes through directory structure;
- sometimes through filename prefixes or suffixes;
- sometimes through partially parallel test/spec layouts.

This creates ambiguity when new variants are added, especially for:

- fixed vs structural chunking;
- dense vs hybrid ingest or retrieval;
- configs that describe input profiles rather than distinct runtimes.

The goal of this policy is to keep each axis visible in one consistent place.

## Canonical Rule

Use the filesystem path to represent the implementation axis.

Use the filename to represent the file's role.

Use a dedicated `common/` directory for shared assets.

Use a dedicated `profiles/` directory for profile-like runtime inputs that are
consumed by the same implementation.

Do not encode an implementation variant in both the path and the filename unless
there is a very strong compatibility reason.

## Definitions

### Implementation Variant

An implementation variant is a different runtime strategy or subsystem shape.

Examples:

- chunker `fixed` vs `structural`
- ingest `dense` vs `hybrid`
- retrieval `dense` vs `hybrid`

Implementation variants belong in the path.

Examples:

- `Execution/parsing/chunker/fixed/`
- `Execution/parsing/chunker/structural/`
- `Execution/ingest/dense/`
- `Execution/ingest/hybrid/`

### Shared Logic

Shared logic is reusable logic that is valid across multiple variants of the
same module family.

Shared logic belongs in `common/`.

Examples:

- `Execution/parsing/chunker/common/`
- `Execution/tests/parsing/chunker/common/`
- `Specification/testgen/chunker/common/`

### Profile

A profile is a runtime input shape or configuration preset consumed by the same
implementation. A profile is not a separate implementation.

Examples:

- dense ingest over chunks produced by the `fixed` chunker
- dense ingest over chunks produced by the `structural` chunker

Profiles belong in `profiles/` under the implementation variant that consumes
them.

Examples:

- `Execution/ingest/dense/profiles/fixed.toml`
- `Execution/ingest/dense/profiles/structural.toml`

## Naming Rules

### Directories

Use short lowercase directory names for module families and variants.

Preferred variant names:

- `fixed`
- `structural`
- `dense`
- `hybrid`
- `common`
- `profiles`

Avoid synonyms for the same axis such as mixing:

- `shared/` and `common/`
- `preset/` and `profile/`
- `fixed_chunker/` and `fixed/`

### Files

File names should describe role, not re-state the variant already encoded by the
directory.

Preferred file names:

- implementation entrypoint: `chunker.py`, `ingest.py`
- canonical runtime config in a variant directory: `chunker.toml`, `ingest.toml`
- profile config in a `profiles/` directory: `fixed.toml`, `structural.toml`
- variant-specific codegen spec: `fixed.md`, `structural.md`, `dense.md`, `hybrid.md`

Avoid names like:

- `ingest_fixed.toml` inside `Execution/ingest/dense/`
- `fixed_chunker.toml` inside `Execution/parsing/chunker/fixed/` when the folder
  already says `fixed`
- `dense_ingest.py` inside `Execution/ingest/dense/`

Those names duplicate the axis already present in the path.

## Stage-Specific Policy

### Parsing

Chunker implementations are variant-based and should remain path-oriented.

Preferred layout:

```text
Execution/parsing/chunker/
  common/
  fixed/
    chunker.py
    chunker.toml
  structural/
    chunker.py
    chunker.toml
```

Rules:

- `fixed` and `structural` are implementation variants;
- chunker configs live next to the implementation they configure;
- shared chunker helpers belong in `common/`.

### Ingest

`dense` and `hybrid` are ingest implementation variants.

`fixed` and `structural` are chunk-source profiles consumed by an ingest
implementation. They are not ingest implementations.

Preferred layout:

```text
Execution/ingest/
  dense/
    ingest.py
    ingest.toml
    profiles/
      fixed.toml
      structural.toml
  hybrid/
    ingest.py
    ingest.toml
    profiles/
      fixed.toml
      structural.toml
```

Rules:

- keep the ingest engine in the variant directory;
- use `profiles/` for chunk-source-specific config presets;
- do not create `Execution/ingest/fixed/` unless fixed becomes a real ingest
  implementation rather than an input profile.

### Retrieval

When hybrid retrieval is added, follow the same axis split as ingest.

If retrieval remains a unified runtime crate, keep the crate unified and express
variant-specific implementation modules below `src/retrieval/`.

Preferred direction:

```text
Execution/rag_runtime/src/retrieval/
  common/
  dense/
  hybrid/
```

Rules:

- use directories for retrieval implementations;
- keep shared mapping, retry, and payload helpers in `common/`;
- avoid filename-only encoding such as `hybrid_retrieval.rs` next to
  `dense_retrieval.rs` when a variant directory would be clearer.

### Executable Tests

Executable tests should mirror the same variant structure used by the code they
verify.

Preferred layout:

```text
Execution/tests/
  parsing/
    chunker/
      common/
      fixed/
      structural/
  ingest/
    dense/
      common/
      fixed/
      structural/
    hybrid/
      common/
      fixed/
      structural/
```

Rules:

- put cross-variant checks in `common/`;
- put implementation-specific checks in the corresponding variant directory;
- if a test targets a profile consumed by an implementation, place it under the
  implementation variant and then under the profile name.

### Fixtures

Fixtures should mirror the same stage and variant layout used by executable
tests.

Preferred layout:

```text
Execution/tests/fixtures/
  parsing/chunker/common/
  parsing/chunker/fixed/
  parsing/chunker/structural/
  ingest/dense/fixed/
  ingest/dense/structural/
```

### Specifications

Keep spec organization parallel to the execution layout, but continue to use a
single file per variant where the spec is file-oriented.

Preferred layout:

```text
Specification/codegen/chunker/
  fixed.md
  structural.md

Specification/testgen/chunker/
  common/
  fixed/
  structural/

Specification/testgen/ingest/
  dense/
    common/
    fixed/
    structural/
```

## Migration Guidance For Current Repository

This section translates the policy into concrete next steps for the current
tree.

### Current Canonicalized Paths

The first cleanup wave converges on:

1. Parsing config:
   - `Execution/parsing/chunker/fixed/chunker.toml`

2. Dense ingest profiles:
   - `Execution/ingest/dense/profiles/fixed.toml`
   - `Execution/ingest/dense/profiles/structural.toml`

3. Dense ingest canonical config entrypoint:
   - `Execution/ingest/dense/ingest.toml`
   - this file may remain as the engine-level default while profile-specific
     presets live in `profiles/`

### Test Layout Cleanup

Move current chunker tests into explicit `common/` and `structural/` folders.

Canonical mapping:

- `Execution/tests/parsing/chunker/determinism.py`
  -> `Execution/tests/parsing/chunker/common/determinism.py`
- `Execution/tests/parsing/chunker/sanitation.py`
  -> `Execution/tests/parsing/chunker/common/sanitation.py`
- `Execution/tests/parsing/chunker/schema_validation.py`
  -> `Execution/tests/parsing/chunker/common/schema_validation.py`
- `Execution/tests/parsing/chunker/structure.py`
  -> `Execution/tests/parsing/chunker/structural/structure.py`
- `Execution/tests/parsing/chunker/span_quality.py`
  -> `Execution/tests/parsing/chunker/structural/span_quality.py`
- `Execution/tests/parsing/chunker/truth_consistency.py`
  -> `Execution/tests/parsing/chunker/structural/truth_consistency.py`
- `Execution/tests/parsing/chunker/synthetic_regression.py`
  -> `Execution/tests/parsing/chunker/structural/synthetic_regression.py`

Canonical fixture paths:

- `Execution/tests/fixtures/parsing/chunker/structural/synthetic_chunking_cases.json`
- `Execution/tests/fixtures/parsing/chunker/fixed/synthetic_chunking_cases.json`

### Dense Ingest Testgen Cleanup

Current dense ingest test-generation specs should live under:

- `Specification/testgen/ingest/dense/e2e.md`
- `Specification/testgen/ingest/dense/integration.md`
- `Specification/testgen/ingest/dense/without_containers.md`

Current dense ingest executable tests should live under:

- `Execution/tests/ingest/dense/`

Future profile-specific dense ingest tests may be added under:

- `Execution/tests/ingest/dense/fixed/`
- `Execution/tests/ingest/dense/structural/`
- `Specification/testgen/ingest/dense/fixed/`
- `Specification/testgen/ingest/dense/structural/`

### Dense Ingest Semantic Classification

Dense ingest tests belong flat under `Execution/tests/ingest/dense/` when they
verify behavior of the dense ingest engine regardless of which chunker profile
produced the input chunks.

Keep a dense ingest test flat in `Execution/tests/ingest/dense/` if it
primarily checks:

- config or env validation;
- embedding request construction;
- embedding retry limits;
- embedding batch fallback behavior;
- Qdrant retry limits;
- collection creation metadata;
- collection compatibility checks;
- point id generation semantics that depend only on stable chunk contract fields;
- idempotency behavior based on generic chunk payload fields such as
  `content_hash`;
- failed chunk logging mechanics;
- full-ingest success for a minimal valid chunk set.

Move or create a dense ingest test under `fixed/` or `structural/` only when
the test expectation depends on chunker-specific payload shape or semantics.

Examples of profile-specific dense ingest tests:

- logic that depends on fixed-chunker overlap behavior;
- assertions that depend on structural heading hierarchy or metadata-derived
  section paths;
- profile-specific collection partitioning or naming conventions, if those are
  introduced later;
- ingestion rules that are enabled only for one chunk-source profile.

Current interpretation for the repository:

- all existing dense ingest executable tests belong in
  `Execution/tests/ingest/dense/`
- all existing dense ingest test-generation specs belong in
  `Specification/testgen/ingest/dense/`
- `fixed/` and `structural/` under dense ingest should not be created until a
  test genuinely depends on those profile semantics

### Follow-Up Retrieval Layout

Before adding hybrid retrieval, define the retrieval variant structure first and
then place code, tests, and specs into it. Do not let the first hybrid files
establish a filename-suffix convention by accident.

## Decision Summary

Use one axis per structural layer:

- stage in the top-level path;
- implementation variant in the next path segment;
- shared logic in `common/`;
- profile presets in `profiles/`;
- file role in the filename.

This keeps future additions composable without introducing filenames such as:

- `hybrid_ingest_fixed_v2.toml`
- `dense_retrieval_hybrid.rs`
- `fixed_chunker_config_structural_override.toml`
