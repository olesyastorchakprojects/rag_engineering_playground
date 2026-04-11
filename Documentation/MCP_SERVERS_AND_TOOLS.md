# MCP Servers And Tools

## Why MCP Exists In This Project

The repository includes a project-specific MCP layer so that agents do not need
to treat the codebase, storage, observability stack, and experiment artifacts as
opaque external systems.

Instead, the project exposes curated server interfaces for the things that
matter most during engineering work:

- repository context
- specifications and contracts
- conformance checks
- observability
- PostgreSQL state
- Qdrant state
- eval experiment artifacts
- workflow orchestration

This turns the repository into a tool-aware environment rather than a folder
tree that agents must interpret from scratch every time.

## Where The MCP Servers Live

The project-specific servers live under:

- `Tools/mcp/`

Current server families include:

- `agent_orchestrator`
- `eval_experiments`
- `observability`
- `postgres`
- `project_context`
- `qdrant`
- `spec`
- `spec_conformance`

## At A Glance

| Server | Main Use | Notable Tools |
| --- | --- | --- |
| `project_context` | operational topology, storage ownership, and routing policy | `get_project_context`, `get_storage_owner`, `get_routing_policy` |
| `spec` | formal specs, schemas, topic graph, generation and validation context | `get_topic_sources`, `get_generation_context`, `get_validation_context`, `search_spec_documents` |
| `spec_conformance` | curated drift checks between spec and implementation | `list_modules`, `compare_spec_and_code`, `compare_changed_files`, `find_uncovered_requirements` |
| `observability` | repo-backed observability assets and live local stack inspection | `get_dashboard_catalog`, `get_live_stack_status`, `get_tempo_trace`, `find_trace_by_attribute` |
| `postgres` | eval truth, request captures, processing state, and run results | `get_request_capture`, `get_request_eval_bundle`, `get_eval_stage_summary`, `get_run_results` |
| `qdrant` | live retrieval truth and ingest compatibility checks | `get_collection_compatibility`, `get_point_by_chunk_id`, `get_retrieval_payload_health` |
| `eval_experiments` | run-level eval summaries, comparisons, regressions, and health checks | `summarize_run`, `compare_runs`, `compare_request_across_runs`, `get_run_artifact_health` |
| `agent_orchestrator` | workflow planning, structured handoffs, status, and fix cycles | `plan_task`, `run_workflow`, `submit_and_continue`, `get_workflow_report` |

Each server has its own:

- implementation
- README
- tests
- routing policy
- and, where needed, schemas or policy files

## What These Servers Do

### `project_context`

This server provides repository-aware operating context.

It answers questions such as:

- what are the important subsystem boundaries?
- which storage backend owns a given concept?
- what are the default runtime assumptions?
- how should debugging start for a given class of problem?

### `spec`

This server exposes the specification layer as a queryable system.

It helps agents find:

- source-of-truth documents
- spec roots
- generation context
- validation context
- related docs for a topic

### `spec_conformance`

This server focuses on the gap between declared contracts and implementation.

It answers questions such as:

- which requirements are currently covered?
- what mismatches are known?
- which touched files affect which conformance checks?

The current curated coverage focuses on `hybrid_ingest`, `fixed_chunker`, and `rag_runtime`.

### `observability`

This server provides repository-aware access to the local observability stack.

It helps with:

- checking stack health
- discovering dashboards
- reading dashboard definitions
- inspecting collector wiring
- finding traces

### `postgres`

This server gives safe, curated access to the evaluation and request-capture
storage model.

It supports questions such as:

- what request captures exist?
- what eval stage is a request in?
- what did one run write into storage?

### `qdrant`

This server provides visibility into the retrieval store.

It supports:

- collection inspection
- point lookup
- compatibility checks
- payload health checks

### `eval_experiments`

This server supports run-oriented eval inspection and comparison.

It answers questions like:

- what runs exist?
- what artifacts are present for a run?
- what changed between two runs?
- where are the likely regressions?

It complements the run manifest and run report artifacts.

### `agent_orchestrator`

This server is the control-plane component for the repository's multi-agent
workflow.

It plans the workflow, persists state, and returns structured assignments for
the external runner that actually executes specialist agents.

It manages:

- task planning
- workflow state
- step routing
- completion rules
- step result submission
- workflow status and report generation

It does not spawn specialist agents itself.

## Why This Matters Architecturally

The MCP layer is important because it gives agents structured access to the same
engineering surfaces that humans care about:

- specs
- storage
- observability
- experiments
- workflow state

That reduces ambiguity, improves routing, and makes the repository more
operable as a complex engineering system.

## What This Enables

Because the MCP layer exists, agents can work in a way that is much closer to
how a human teammate would work in this repository:

- find source-of-truth docs before changing code
- inspect database state without inventing new tooling
- inspect traces and dashboards as part of debugging
- compare eval runs directly
- route workflow steps through an explicit orchestration layer

That makes the project not only specification-first, but also tool-aware.

## Why This Is Worth Showing In A Presentation

The MCP layer demonstrates that the project is designed not only to run, but to
support disciplined engineering workflows on top of itself.

It shows that:

- repository knowledge is encoded
- critical operational surfaces are queryable
- agent work can be structured instead of improvised

That is a strong differentiator compared with repositories that only contain
runtime code and some dashboards.
