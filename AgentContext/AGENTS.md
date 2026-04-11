# AGENTS

## Purpose

This file is the operational entrypoint for coding agents working in this repository.

Read this file first.
Then read the project structure files referenced below before generating or moving code.

## Read Order

Before making code changes, read in this order:

1. `Specification/architecture/project_structure.md`
2. `Specification/architecture/project_structure.json`
3. relevant file in `Specification/codegen/`
4. relevant file in `Specification/testgen/` if tests must also be created or updated
5. relevant file in `Specification/contracts/`
6. neighboring runtime code in `Execution/`
7. neighboring executable tests in `Execution/tests/`

Before executing a higher-level generation task, also read:

1. relevant file in `Specification/tasks/`

## Repository Model

The repository is organized into these top-level areas:

- `Execution/` — runnable code, executable tests, runtime configs, runtime schemas, runtime resources
- `Specification/` — specifications used to guide code generation, test generation, architecture decisions, and repository organization
- `Measurement/` — evaluation and comparison logic
- `Evidence/` — run artifacts and experiment outputs
- `AgentContext/` — agent instructions and workflow conventions
- `Documentation/` — human-oriented documentation

## Mandatory Placement Rules

- New runnable code must go into `Execution/`
- New executable tests must go into `Execution/tests/`
- Shared test fixtures must go into `Execution/tests/fixtures/`
- New code-generation prompts must go into `Specification/codegen/`
- New test-generation prompts must go into `Specification/testgen/`
- New high-level agent task prompts must go into `Specification/tasks/`
- Human-readable contracts must go into `Specification/contracts/`
- Runtime schemas must go into the relevant `Execution/.../schemas/` directory
- Run outputs, logs, reports, and other artifacts must go into `Evidence/`

## Parsing Rules

- Extractor code belongs in `Execution/parsing/extractor/`
- Chunker code belongs in `Execution/parsing/chunker/<variant>/`
- Parsing-shared helpers belong in `Execution/parsing/common/`
- Book-specific parsing inputs belong in `Execution/parsing/books/<book_id>/source/`
- Book-specific cleanup rules and overrides belong in `Execution/parsing/books/<book_id>/cleanup/`

## Ingest Rules

- Dense ingest code belongs in `Execution/ingest/dense/`
- Hybrid ingest code belongs in `Execution/ingest/hybrid/`
- Ingest runtime schemas belong in `Execution/ingest/schemas/`

## Retrieval And Orchestration Rules

- Retrieval runtime code belongs in `Execution/retrieval/`
- Orchestration runtime code belongs in `Execution/orchestration/`
- Keep `Execution/bin/` thin; do not move core logic there

## Specs And Prompt Rules

- `Specification/architecture/` contains stable structure and architecture guidance
- `Specification/codegen/` contains prompts for generating production code
- `Specification/testgen/` contains prompts for generating executable tests
- `Specification/tasks/` contains high-level orchestration prompts similar to direct user instructions

## Evidence Rules

- Parsing outputs such as `pages.jsonl` and `chunks.jsonl` belong in `Evidence/parsing/`
- Ingest outputs belong in `Evidence/ingest/`
- Retrieval outputs belong in `Evidence/retrieval/`
- Orchestration outputs belong in `Evidence/orchestration/`
- Cross-variant experiment outputs belong in `Evidence/experiments/`
- Debug-only artifacts belong in `Evidence/debug/`

## Legacy Rules

- The repository previously used an older layout that is no longer part of the active tree
- If older path names appear in historical notes or prompts, treat them as legacy references rather than valid write targets
- Prefer neighboring files in the current structure over similarly named files mentioned in older material

## Final Check Before Writing Files

Before creating a new file, verify:

1. whether a matching folder already exists in the new structure;
2. whether a neighboring implementation or test already defines the local pattern;
3. whether the file should be runtime code, executable test, prompt/spec, measurement logic, or evidence;
4. whether the target should be in `Execution/`, `Specification/`, `Measurement/`, or `Evidence/`.
