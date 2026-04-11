# Project Structure

## Purpose

This file is the source of truth for repository layout.
It is written for code-generating models and coding agents.

Variant, shared, and profile naming policy is defined in:

- `Specification/architecture/module_variant_policy.md`

Use it to decide:

- where to read project context from;
- where to place newly generated code;
- where to place newly generated tests;
- where to place configs, schemas, contracts, prompts, and artifacts;
- which folders contain executable runtime logic vs specifications vs experimental evidence.
- how to represent implementation variants vs shared logic vs runtime profiles.

Do not invent alternative locations for files if a suitable location already exists in this structure.

## Core Repository Model

The repository is organized around six top-level areas:

- `Execution/`
- `Specification/`
- `Measurement/`
- `Evidence/`
- `AgentContext/`
- `Documentation/`

There is also:

- legacy references to an older repository layout may still appear in historical notes; treat them as background context, not as the target for new code
- `.env` in repository root — runtime environment file; it must stay in the repository root.

## Top-Level Directory Rules

### `Execution/`

`Execution/` contains everything needed to run the system or verify runnable behavior:

- production/runtime code;
- executable tests;
- runtime configs;
- runtime schemas;
- parsing resources used at runtime;
- thin entrypoints in `Execution/bin/`.

If you generate runnable code, it belongs in `Execution/`.

If you generate executable tests, they also belong in `Execution/`.

### `Specification/`

`Specification/` contains the specifications used to guide code generation, test generation, architecture decisions, and repository organization.

This includes:

- code-generation prompts;
- test-generation prompts;
- higher-level task prompts;
- human-readable contracts;
- architecture documents;
- test matrices.

If you generate a prompt/specification for a model, it belongs in `Specification/`, not in `Execution/`.

### `Measurement/`

`Measurement/` contains the rules and tooling used to evaluate variants.

Typical future contents:

- evaluation harnesses;
- scoring logic;
- benchmark definitions;
- cost/latency/quality metrics logic;
- dashboard definitions such as Grafana configs.

`Measurement/` defines how results are measured.
It does not store the results of concrete runs.

### `Evidence/`

`Evidence/` stores artifacts produced by running the system and experiments.

Typical contents:

- `pages.jsonl`, `chunks.jsonl`;
- ingest manifests;
- failed chunk logs;
- retrieval outputs;
- answer outputs;
- run metadata;
- benchmark outputs;
- generated reports;
- metric snapshots;
- exported dashboard data;
- experiment result tables.

`Evidence/` stores what happened during actual runs.

### `AgentContext/`

`AgentContext/` is reserved for agent-operating rules and conventions.

Typical future contents:

- `AGENTS.md`;
- repository conventions;
- workflow rules for coding agents;
- tool usage rules;
- review checklists.

Primary workflow-policy reference:

- `Specification/architecture/agent_workflow_policy.md`

### `Documentation/`

`Documentation/` is for human-oriented explanatory documentation and writeups.

Use `Documentation/` for narrative docs, not for executable specs.

## Detailed Layout

## `Execution/`

### `Execution/parsing/`

Contains offline parsing pipeline logic.

This area is responsible for:

- text extraction;
- chunking;
- metadata validation related to parsing;
- runtime schemas for parsing inputs and outputs.

Current structure:

- `Execution/parsing/extractor/`
- `Execution/parsing/chunker/fixed/`
- `Execution/parsing/chunker/structural/`
- `Execution/parsing/common/`
- `Execution/parsing/books/`
- `Execution/parsing/schemas/`

#### `Execution/parsing/extractor/`

Place extractor implementation here.

Current file:

- `Execution/parsing/extractor/extractor.py`

Rule:

- extractor-specific runtime code goes here;
- if only one extractor exists, keep files flat in this directory;
- do not create extra variant subfolders unless there are multiple extractor implementations.

#### `Execution/parsing/chunker/`

Place chunker implementations here.

Chunking has multiple variants, so each variant gets its own subfolder.

Current variant folders:

- `Execution/parsing/chunker/fixed/`
- `Execution/parsing/chunker/structural/`

Current file:

- `Execution/parsing/chunker/structural/chunker.py`

Rules:

- each chunking strategy gets its own subfolder;
- the main implementation file for a strategy can be named `chunker.py`;
- chunker-specific configs may live alongside the implementation if needed.

#### `Execution/parsing/common/`

Place parsing-shared helpers here.

Current file:

- `Execution/parsing/common/book_metadata_validation.py`

Rules:

- shared parsing utilities used by multiple parsing modules and parsing tests belong here;
- do not place generic repository-wide helpers here unless they are truly parsing-specific.

#### `Execution/parsing/books/`

Contains document-specific parsing resources.

Each source document or book gets its own folder.

Current book folder:

- `Execution/parsing/books/understanding_distributed_systems/`

Inside each book folder use:

- `source/` for source assets and structural metadata;
- `cleanup/` for extraction/cleanup rules and overrides.

Current example:

- `Execution/parsing/books/understanding_distributed_systems/source/book_content_metadata.json`
- `Execution/parsing/books/understanding_distributed_systems/source/Understanding-Distributed-Systems-2nd-Edition.pdf`
- `Execution/parsing/books/understanding_distributed_systems/cleanup/rules_metadata.json`
- `Execution/parsing/books/understanding_distributed_systems/cleanup/terms_dictionary.json`
- `Execution/parsing/books/understanding_distributed_systems/cleanup/clean_text_overrides_metadata.json`

Rules:

- structural metadata for the source goes in `source/`;
- cleanup/extraction rules and manual overrides go in `cleanup/`;
- if a new book is added, create a new sibling folder under `Execution/parsing/books/`.

#### `Execution/parsing/schemas/`

Contains runtime-used schemas for parsing-specific inputs and outputs.

Rule:

- machine-readable schemas that are specific to parsing belong here.

#### `Execution/schemas/`

Contains runtime-used schemas shared across multiple execution stages.

Current file:

- `Execution/schemas/chunk.schema.json`

Rule:

- machine-readable schemas shared by parsing, ingest, retrieval, or other runtime stages belong here.

### `Execution/ingest/`

Contains offline indexing/ingest logic.

Current structure:

- `Execution/ingest/dense/`
- `Execution/ingest/hybrid/`
- `Execution/ingest/schemas/`

#### `Execution/ingest/dense/`

Place dense ingest runtime code and its runnable config here.

Current files:

- `Execution/ingest/dense/ingest.py`
- `Execution/ingest/dense/ingest.toml`

Rules:

- `dense` is an ingest implementation variant;
- if dense ingest needs chunk-source-specific presets such as `fixed` or `structural`,
  place them in `Execution/ingest/dense/profiles/`;
- do not express chunk-source profiles as sibling files like `ingest_fixed.toml`
  when `profiles/<profile>.toml` would represent the axis more clearly.

#### `Execution/ingest/hybrid/`

Reserved for hybrid ingest runtime code, config, and chunk-source profiles.

Current files:

- `Execution/ingest/hybrid/ingest.toml`
- `Execution/ingest/hybrid/profiles/fixed.toml`
- `Execution/ingest/hybrid/profiles/structural.toml`
- `Execution/ingest/hybrid/examples/bm25_like.toml`

Rules:

- use the same pattern as dense ingest;
- place implementation as `ingest.py` and runtime config as `ingest.toml` unless there is a strong reason not to.
- if hybrid ingest needs chunk-source-specific presets, place them under `profiles/`
  rather than encoding the profile in the filename.
- if hybrid ingest needs strategy-oriented example configs that are not canonical
  runtime defaults, place them under `examples/`.
- if hybrid ingest creates sparse-point exports, corpus-level sparse stats, or
  run manifests, those generated artifacts belong in runtime output locations
  such as `Evidence/`, not inside `Execution/ingest/hybrid/`.
- the current source-of-truth codegen spec for this variant is
  `Specification/codegen/ingest/hybrid.md`.

#### `Execution/ingest/schemas/`

Contains runtime-used schemas for ingest configuration and environment contracts.

Current files:

- `Execution/ingest/schemas/dense_ingest_config.schema.json`
- `Execution/ingest/schemas/dense_ingest_env.schema.json`
- `Execution/ingest/schemas/hybrid_ingest_config.schema.json`
- `Execution/ingest/schemas/common/sparse_vocabulary.schema.json`
- `Execution/ingest/schemas/hybrid_ingest_manifest.schema.json`

Future hybrid ingest schemas should also go here.

### `Execution/rag_runtime/`

Contains the unified Rust runtime crate for online RAG execution.

This crate should contain:

- retrieval;
- reranking;
- generation;
- orchestration;
- shared runtime models and helpers.

Current structure:

- `Execution/rag_runtime/`

Rules:

- online RAG runtime code belongs here;
- do not assume a fixed internal module folder layout until the runtime specification is finalized;
- Rust crate manifest belongs at `Execution/rag_runtime/Cargo.toml`.

### `Execution/tests/`

Contains executable tests and runtime test fixtures.

Current structure:

- `Execution/tests/parsing/`
- `Execution/tests/ingest/`
- `Execution/tests/orchestration/`
- `Execution/tests/fixtures/`

Rules:

- place executable tests under the stage they verify;
- place reusable fixtures under `Execution/tests/fixtures/`;
- do not hide fixtures deep inside a single test directory if they are reusable.
- when code under test has `common/` and variant-specific structure, mirror that
  structure in tests and fixtures.

#### `Execution/tests/parsing/`

Contains extractor and chunker tests.

Current structure:

- `Execution/tests/parsing/extractor/`
- `Execution/tests/parsing/chunker/`

#### `Execution/tests/ingest/`

Contains ingest tests organized first by ingest implementation and then by
optional profile-specific scope.

Current structure:

- `Execution/tests/ingest/dense/`

Rule:

- place dense ingest engine tests flat in `Execution/tests/ingest/dense/`
- introduce `fixed/` or `structural/` under ingest tests only when assertions
  genuinely depend on chunk-source-specific semantics such as fixed overlap
  behavior or structural hierarchy semantics.

#### `Execution/tests/fixtures/`

Contains shared test fixtures.

Current fixtures:

- `Execution/tests/fixtures/parsing/chunker/fixed/synthetic_chunking_cases.json`
- `Execution/tests/fixtures/parsing/chunker/structural/synthetic_chunking_cases.json`
- `Execution/tests/fixtures/parsing/extractor/synthetic_cleanup_cases.json`

Rule:

- if a fixture is used by tests, place it here rather than next to a single test script.

### `Execution/bin/`

Contains thin executable entrypoints and launch scripts.

Rules:

- keep these thin;
- business logic belongs in the appropriate runtime folders, not directly in `Execution/bin/`.

## `Specification/`

### `Specification/architecture/`

Contains repository architecture docs and structure docs.

Current file:

- `Specification/architecture/project_structure.md`

Use this area for stable structural guidance.

### `Specification/IncidentReports/`

Contains incident reports from failed or degraded generation attempts.

Use this area to document:

- generation-time mistakes that led to incorrect code or false debugging conclusions;
- environment and infrastructure failures that affected validation;
- observability pitfalls;
- specification violations that caused regressions;
- concrete guardrails for the next generation attempt.

Rules:

- create one dated Markdown file per incident or repair session;
- incident reports must be written so that a later code-generating model can avoid repeating the same mistakes;
- if a generation session exposed traps in validation, observability, runtime config, container setup, or spec adherence, they must be recorded here;
- before the next generation of the same component, models must read the relevant incident reports in this folder carefully.

### `Specification/codegen/`

Contains component specifications used to drive later code generation.

Current structure:

- `Specification/codegen/extractor/`
- `Specification/codegen/chunker/`
- `Specification/codegen/ingest/`
- `Specification/codegen/rag_runtime/`

Current examples:

- `Specification/codegen/extractor/extractor.md`
- `Specification/codegen/chunker/structural.md`
- `Specification/codegen/ingest/dense.md`
- `Specification/codegen/rag_runtime/generated_artifacts.md`
- `Specification/codegen/rag_runtime/prompts.json`
- `Specification/codegen/rag_runtime/rag_runtime.md`
- `Specification/codegen/rag_runtime/unit_tests.md`

Rules:

- if a component has multiple variants, use one file per variant;
- use names like `dense.md`, `hybrid.md`, `fixed.md`, `structural.md`, or a component-level file like `rag_runtime.md` when the component is specified as a unified runtime;
- if a component has only one implementation, a descriptive single file like `extractor.md` is acceptable;
- companion specification files that define shared generation constraints for a component belong next to the main component specification, for example `Specification/codegen/rag_runtime/unit_tests.md`;
- companion specification files that define completion criteria or required generated repository artifacts for a component also belong next to the main component specification, for example `Specification/codegen/rag_runtime/generated_artifacts.md`;
- machine-readable companion files that define prompt templates or prompt-construction inputs for a component also belong next to the main component specification, for example `Specification/codegen/rag_runtime/prompts.json`;
- these files should first define a detailed, unambiguous implementation specification;
- code generation should happen only after the specification is complete enough to be the source of truth for implementation placement in `Execution/`.

### `Specification/testgen/`

Contains prompts/specs used to generate executable tests.

Current structure:

- `Specification/testgen/extractor/`
- `Specification/testgen/chunker/`
- `Specification/testgen/ingest/`
- `Specification/testgen/orchestrator/`

Current examples:

- `Specification/testgen/extractor/sanity.md`
- `Specification/testgen/chunker/structure.md`
- `Specification/testgen/ingest/dense/e2e.md`
- `Specification/testgen/ingest/hybrid/e2e.md`

Rule:

- keep dense ingest testgen specs flat in `Specification/testgen/ingest/dense/`
- keep hybrid ingest testgen specs flat in `Specification/testgen/ingest/hybrid/`
- introduce `fixed/` or `structural/` subdirectories under ingest testgen only
  when those specs require profile-specific chunk semantics.

Rules:

- these files describe how to generate tests, not the tests themselves;
- generated executable tests belong in `Execution/tests/...`;
- keep prompt organization parallel to the system organization where practical.

### `Specification/tasks/`

Contains high-level orchestration prompts for agents.

These are higher-level than `codegen/` and `testgen/`.

They may instruct the model to:

- generate code;
- generate tests;
- run repair loops until tests pass;
- consult architecture files and contracts;
- place outputs in the proper repository locations.

Rules:

- use `Specification/tasks/` for prompts similar to direct chat instructions;
- tasks may reference files from `Specification/codegen/`, `Specification/testgen/`, `Specification/contracts/`, and `Specification/architecture/`.

### `Specification/contracts/`

Contains human-readable contracts.

Current structure:

- `Specification/contracts/chunk/`
- `Specification/contracts/ingest/`
- `Specification/contracts/retrieval/`

Current examples:

- `Specification/contracts/chunk/spec.md`
- `Specification/contracts/ingest/dense_config.md`
- `Specification/contracts/ingest/dense_env.md`

Rule:

- human-readable contract descriptions go here;
- machine-readable runtime schemas go in `Execution/.../schemas/`.

### `Specification/tests/`

Contains human-readable test matrices and test-plan documents.

Current files:

- `Specification/tests/TESTS_MATRIX.md`
- `Specification/tests/dense_ingest_TESTS_MATRIX.md`
- `Specification/tests/hybrid_ingest_TESTS_MATRIX.md`

Rules:

- place test strategy and test coverage matrices here;
- place executable tests in `Execution/tests/`.

## `Measurement/`

`Measurement/` is currently a reserved area.

Use it for:

- evaluation code;
- benchmark definitions;
- score aggregation;
- dashboard configuration;
- comparison tooling;
- cost/latency/quality measurement logic.

Do not place raw run outputs here.

## `Evidence/`

`Evidence/` stores outputs from real runs.

Organize it by stage and, when relevant, by experiment.

Current areas:

- `Evidence/parsing/`
- `Evidence/ingest/`
- `Evidence/retrieval/`
- `Evidence/orchestration/`
- `Evidence/experiments/`
- `Evidence/debug/`

### `Evidence/parsing/`

Contains outputs of parsing runs.

Current example:

- `Evidence/parsing/understanding_distributed_systems/pages/pages.jsonl`
- `Evidence/parsing/understanding_distributed_systems/chunks/chunks.jsonl`

Rule:

- store actual produced parsing artifacts here, grouped by source.

### `Evidence/ingest/`

Contains outputs of ingest runs, including failed chunks and manifests.

Current example:

- `Evidence/ingest/dense/understanding_distributed_systems/failed_chunks/ingest_failed_chunks.jsonl`

### `Evidence/retrieval/`

Contains retrieval run outputs and logs for each retrieval strategy.

### `Evidence/orchestration/`

Contains online answer-generation outputs.

Use it for:

- answer outputs;
- orchestration run metadata;
- orchestration logs.

### `Evidence/experiments/`

Contains aggregated comparison evidence for experiments.

Current experiment folders:

- `Evidence/experiments/fixed_vs_structural/`
- `Evidence/experiments/dense_vs_hybrid/`

Rules:

- raw comparison runs go in `runs/`;
- summarized outputs go in `reports/`.

### `Evidence/debug/`

Contains debug-only evidence that does not belong to normal stage outputs.

Current example:

- `Evidence/debug/parsing/understanding_distributed_systems/contract/`

Use this for:

- contract debugging outputs;
- temporary or low-level forensic artifacts;
- artifacts useful for debugging but not part of normal pipeline outputs.

## Generation Placement Rules

When generating new files, use the following placement rules:

- production extractor code -> `Execution/parsing/extractor/`
- production chunker code -> `Execution/parsing/chunker/<variant>/`
- parsing shared helper -> `Execution/parsing/common/`
- book-specific parsing resources -> `Execution/parsing/books/<book_id>/source/` or `cleanup/`
- runtime parsing schema -> `Execution/parsing/schemas/`
- shared runtime schema -> `Execution/schemas/`
- ingest code -> `Execution/ingest/<variant>/`
- ingest runtime schemas -> `Execution/ingest/schemas/`
- RAG runtime code -> `Execution/rag_runtime/`
- executable tests -> `Execution/tests/<stage>/...`
- shared test fixtures -> `Execution/tests/fixtures/<stage>/...`
- code-generation prompt -> `Specification/codegen/<component>/...`
- test-generation prompt -> `Specification/testgen/<component>/...`
- high-level task prompt -> `Specification/tasks/<component>/...`
- human-readable contract -> `Specification/contracts/...`
- architecture guidance -> `Specification/architecture/`
- generation incident report -> `Specification/IncidentReports/`
- test matrix -> `Specification/tests/`
- measurement logic -> `Measurement/...`
- run artifacts -> `Evidence/...`

## Read-First Guidance For Code-Generating Models

Before generating code for a component, read in this order:

1. `Specification/architecture/project_structure.md`
2. relevant file in `Specification/codegen/...`
3. relevant incident reports in `Specification/IncidentReports/`, especially reports for the same component or the same observability stack
4. companion generation-constraint files in the same component folder, for example `Specification/codegen/rag_runtime/unit_tests.md`, when they exist
5. companion generated-artifact files in the same component folder, for example `Specification/codegen/rag_runtime/generated_artifacts.md`, when they exist
6. companion machine-readable prompt-template files in the same component folder, for example `Specification/codegen/rag_runtime/prompts.json`, when they exist
7. relevant file in `Specification/testgen/...` if tests must also be generated
8. relevant files in `Specification/contracts/...`
9. relevant runtime schemas in `Execution/.../schemas/`
10. neighboring implementations in `Execution/...`
11. neighboring executable tests in `Execution/tests/...`

Before generating a high-level task workflow, read:

1. `Specification/architecture/project_structure.md`
2. relevant files in `Specification/tasks/...`
3. supporting prompts in `Specification/codegen/...` and `Specification/testgen/...`

## Legacy Material

Some historical notes may still refer to a previous repository layout that is no longer part of the active tree.

Rules:

- do not treat legacy path names as valid write targets;
- use them only as historical reference when interpreting older notes or migration-oriented material;
- prefer the current structure for all newly generated code, tests, specs, and artifacts.
