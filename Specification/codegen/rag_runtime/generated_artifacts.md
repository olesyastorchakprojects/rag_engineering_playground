## 1) Purpose / Scope

This document defines the mandatory generated-artifact set for `rag_runtime`.

This document is the single source of truth for:
- required generated runtime artifacts;
- required generated unit-test artifacts;
- required generated observability artifacts;
- completion criteria for a finished `rag_runtime` generation pass.

Generation for `rag_runtime` is incomplete if any required artifact from this document is missing.

## 2) Required Runtime Artifacts

Generation must create or update the runtime crate under:

- `Execution/rag_runtime/`

Required runtime repository artifacts are:

- `Execution/rag_runtime/Cargo.toml`
- `Execution/rag_runtime/rag_runtime.toml`
- `Execution/rag_runtime/schemas/rag_runtime_config.schema.json`
- `Execution/rag_runtime/src/lib.rs`
- `Execution/rag_runtime/src/main.rs`
- `Execution/rag_runtime/src/config/mod.rs`
- `Execution/rag_runtime/src/input_validation/mod.rs`
- `Execution/rag_runtime/src/retrieval/mod.rs`
- `Execution/rag_runtime/src/reranking/mod.rs`
- `Execution/rag_runtime/src/generation/mod.rs`
- `Execution/rag_runtime/src/generation/transport.rs`
- `Execution/rag_runtime/src/generation/ollama.rs`
- `Execution/rag_runtime/src/generation/openai.rs`
- `Execution/rag_runtime/src/generation/tokenizer.rs`
- `Execution/rag_runtime/src/orchestration/mod.rs`
- `Execution/rag_runtime/src/request_capture_store/mod.rs`
- `Execution/rag_runtime/src/models/mod.rs`
- `Execution/rag_runtime/src/errors/mod.rs`
- `Execution/rag_runtime/src/observability/mod.rs`

If the generated implementation uses additional Rust source files inside the declared module folders, those files are allowed only as internal decomposition of the required crate structure above.

Retrieval decomposition rule:

- `Execution/rag_runtime/src/retrieval/mod.rs` remains the required retrieval module entrypoint;
- the generated implementation may decompose retrieval internals into additional files under `Execution/rag_runtime/src/retrieval/`, including separate dense and hybrid retriever implementations, as long as `Execution/rag_runtime/src/retrieval/mod.rs` remains present and owns the public retrieval module boundary.

Retrieval-metrics-helper decomposition rule:

- the retrieval metrics helper defined by `Specification/codegen/rag_runtime/retrieval_metrics.md` must be implemented in a dedicated internal Rust module file;
- executable Rust unit tests for that helper must live in the same helper module file under `#[cfg(test)]`;
- that helper module may live outside `Execution/rag_runtime/src/retrieval/` as long as it remains internal to the generated crate;
- helper-module tests complement, but do not replace, the required retrieval, reranking, orchestration, and observability test coverage defined by `Specification/codegen/rag_runtime/unit_tests.md`.

Generation decomposition rule:

- `Execution/rag_runtime/src/generation/mod.rs` remains the required `generation` module entrypoint;
- the generated implementation must decompose generation internals into dedicated internal files under `Execution/rag_runtime/src/generation/`;
- for the current version, the required internal generation files are:
  - `transport.rs`
  - `ollama.rs`
  - `openai.rs`
  - `tokenizer.rs`
- the generated implementation must not collapse generator logic, transport logic, and tokenizer-loading logic into one large `generation/mod.rs` file.

Internal test-only Rust source files under `Execution/rag_runtime/src/` are allowed when they are required by:

- `Specification/codegen/rag_runtime/unit_tests.md`

Generation must not omit any required runtime artifact listed in this section.

## 3) Required Unit-Test Artifacts

Generation must create or update unit tests for all modules required by:

- `Specification/codegen/rag_runtime/unit_tests.md`

Required generated unit-test artifacts are:

- unit tests inside `Execution/rag_runtime/src/input_validation/mod.rs`
- unit tests inside `Execution/rag_runtime/src/retrieval/mod.rs`
- unit tests inside `Execution/rag_runtime/src/reranking/mod.rs`
- unit tests inside `Execution/rag_runtime/src/generation/mod.rs`
- unit tests inside `Execution/rag_runtime/src/orchestration/mod.rs`
- unit tests inside `Execution/rag_runtime/src/request_capture_store/mod.rs`
- unit tests inside `Execution/rag_runtime/src/config/mod.rs`
- unit tests inside `Execution/rag_runtime/src/lib.rs`
- unit tests inside `Execution/rag_runtime/src/observability/mod.rs`
- unit tests inside `Execution/rag_runtime/src/errors/mod.rs`

Required generated unit-test artifact rules are:

- every required module test set must exist as executable Rust tests in the required module file;
- the dedicated retrieval-metrics-helper test set required by `Specification/codegen/rag_runtime/unit_tests.md` must exist as executable Rust tests in the dedicated helper module file required by the retrieval-metrics-helper decomposition rule above;
- required module test sets must not be replaced by comments, TODO markers, prose checklists, pseudo-tests, placeholder test functions without assertions, or empty test modules;
- the generated crate must include enough executable Rust tests to satisfy the minimum executable test counts defined in `Specification/codegen/rag_runtime/unit_tests.md`;
- tests marked `#[ignore]` do not satisfy the required minimum executable test counts defined in `Specification/codegen/rag_runtime/unit_tests.md`, and required tests must not be moved out of compliance by marking them ignored.

`Execution/rag_runtime/src/main.rs` is outside the mandatory unit-test artifact set.

Coverage measurement support required by `Specification/codegen/rag_runtime/unit_tests.md` is part of the mandatory generated testing contract.

Dedicated internal test-only helper files under `Execution/rag_runtime/src/` are part of the allowed generated testing contract when they are required by `Specification/codegen/rag_runtime/unit_tests.md`.

Retrieval test decomposition rule:

- if retrieval is decomposed into additional files under `Execution/rag_runtime/src/retrieval/`, executable Rust tests may live in those retrieval-internal files as part of the required retrieval module test set;
- those retrieval-internal tests complement, but do not replace, the required retrieval test coverage defined by `Specification/codegen/rag_runtime/unit_tests.md`.

Generation test decomposition rule:

- if generation is decomposed into additional files under `Execution/rag_runtime/src/generation/`, executable Rust tests may live in those generation-internal files as part of the required generation module test set;
- those generation-internal tests complement, but do not replace, the required generation test coverage defined by `Specification/codegen/rag_runtime/unit_tests.md`;
- `Execution/rag_runtime/src/generation/mod.rs` must still contain executable Rust tests as part of the required generation module test set.

## 4) Required Observability Artifacts

Generation must create or update observability repository artifacts under:

- `Measurement/observability/`

Required generated observability artifacts are:

- `Measurement/observability/grafana/dashboards/request_overview.json`
- `Measurement/observability/grafana/dashboards/ai_overview.json`
- `Measurement/observability/grafana/provisioning/dashboards/dashboards.yml`
- `Measurement/observability/grafana/provisioning/datasources/prometheus.yml`
- `Measurement/observability/grafana/provisioning/datasources/tempo.yml`
- `Measurement/observability/tempo/tempo.yaml`

Generation must not create alternative observability artifact filenames in place of the required filenames listed in this section.

## 5) Non-Required Post-Generation Artifacts

The following are not mandatory generated repository artifacts for `rag_runtime`:

- runtime-produced outputs under `Evidence/`
- coverage HTML output
- coverage text output
- temporary debug files
- smoke-run outputs
- benchmark outputs

Those artifacts are run outputs or local measurement outputs.
They are not part of the required repository artifact set for code generation completion.

## 6) Generation Completion Rule

Generation for `rag_runtime` is complete only when all of the following conditions are true:

- every required runtime artifact from section `2)` exists;
- every required unit-test artifact from section `3)` exists;
- every required observability artifact from section `4)` exists;
- the generated unit tests satisfy the contract in `Specification/codegen/rag_runtime/unit_tests.md`;
- no required module test set has been replaced by comments, TODO markers, prose, pseudo-tests, placeholder test functions without assertions, or empty test modules;
- the generated crate satisfies the minimum executable test counts defined in `Specification/codegen/rag_runtime/unit_tests.md`.
