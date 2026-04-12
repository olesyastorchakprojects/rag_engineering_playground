# Key Technical Decisions

## What this document covers

This document summarizes the main engineering decisions that shape the repository.

It is not a full architecture description and not a replacement for the specifications. Its role is narrower: to explain why several important design choices were made and what problems they solve.

For full system shape, see `ARCHITECTURE_OVERVIEW.md`.
For evaluation workflow, see `EVALUATION_STORY.md`.
For observability design, see `OBSERVABILITY_STORY.md`.
For the generation workflow behind contracts and code, see `SPECIFICATION_FIRST_APPROACH.md`.

---

## 1. Rust for runtime, Python for preparation workflows

The repository uses two implementation environments on purpose.

- **Python** is used for extraction, chunking, ingest, and related preparation workflows.
- **Rust** is used for the runtime pipeline, orchestration, and stricter stage boundaries.

This split reflects different engineering needs rather than language preference alone. Preparation workflows benefit from flexible document-processing iteration. Runtime and orchestration benefit from stronger typed boundaries, explicit stage I/O, and tighter control over contracts.

The decision keeps each side of the system in the environment where it is easiest to make the important constraints explicit.

---

## 2. Parsing is split into extractor and chunker

Knowledge preparation is not treated as one opaque preprocessing step.

Instead, it is split into:

- **extractor** — produces page-level artifacts
- **chunker** — produces chunk-level artifacts from prepared pages
- **ingest** — turns chunk artifacts into retrieval-ready storage

This separation matters because page extraction and chunk construction have different inputs, different contracts, and different failure modes. It also makes the preparation pipeline easier to validate, easier to test, and easier to change without collapsing all document preparation behavior into one monolithic component.

---

## 3. Intermediate artifacts are explicit, schema-bound data products

Page-level and chunk-level outputs are not treated as hidden internal state.

They exist as explicit artifacts with paired schemas and validation rules. The same general pattern also appears in request capture, eval tables, report contracts, and observability surfaces.

This decision serves two purposes:

- it makes pipeline boundaries explicit and machine-checkable
- it reduces ambiguity when code and tests are generated from specifications

The repository prefers stable intermediate artifacts over implicit handoffs between stages.

---

## 4. Dense and hybrid retrieval are first-class indexed variants

The project supports both dense and hybrid retrieval as explicit retrieval families rather than as one-off experiments around a single baseline.

Hybrid indexing currently supports two sparse retrieval strategies:

- **bag-of-words**
- **BM25-like**

Treating these as first-class indexed variants makes retrieval comparison part of the system design rather than an ad hoc extension. It allows chunking, ingest, retrieval, reranking, and evaluation to be compared across different retrieval substrates under a stable workflow.

---

## 5. Retrieval uses ingest-derived settings to prevent runtime/index drift

Runtime retrieval does not define its view of the index independently from ingest.

Instead, retrieval receives ingest-derived configuration so that query-time retrieval uses the same retrieval-relevant fields that were used during indexing. This includes collection and vector naming, embedding-related settings, and hybrid sparse-side settings.

This decision reduces the risk that indexed data and runtime retrieval silently diverge. It keeps retrieval aligned with the shape of the built index rather than relying on duplicated configuration logic.

---

## 6. Request capture is the canonical bridge into offline evaluation

Request capture is not a debug log and not just a convenience persistence step.

It is a contract-bound handoff artifact between online runtime and offline analysis. The runtime assembles `RequestCapture`, validates it, and persists it so that eval runs start from captured request evidence rather than from live replay.

This decision is central to the project because it separates:

- serving the request now
- studying that request later

Without that separation, evaluation would depend too heavily on the live state of the system at analysis time.

---

## 7. Retrieval, reranking, and generation stay as separate stage boundaries

The runtime pipeline intentionally keeps retrieval, reranking, and generation as distinct stages.

This allows the system to ask better engineering questions:

- Did retrieval improve?
- Did reranking change ordering meaningfully?
- Did answer quality improve, or did generation merely compensate?
- What reached the final generation context?

If these stages were collapsed into one implementation unit, many of the comparisons that matter in RAG work would become much harder to observe and evaluate.

---

## 8. Pass-through reranking is still represented as an explicit stage

Even when no actual reranking model is used, pass-through remains an explicit reranking stage rather than a pipeline bypass.

This decision keeps the runtime pipeline structurally comparable across variants. It means “no reranking” is still represented inside the same pipeline shape and can be reasoned about as one member of the reranking design space, not as a special-case execution mode.

That consistency simplifies evaluation, observability, and comparison.

---

## 9. Evaluation runs use frozen scope and resumable state

Offline evaluation is implemented as a stateful workflow coordinated by `eval_orchestrator`.

A run has:

- its own `run_id`
- a frozen request scope
- stage-local progress
- resumable state
- run artifacts such as `run_manifest.json` and `run_report.md`

The frozen run scope is especially important: once a run begins, new captured requests must not silently enter that run. Resume must continue the same run, not mutate its membership.

This decision makes runs stable enough to compare and review as real units of analysis.

---

## 10. Evaluation materializes normalized tables, not only reports

The eval pipeline does not stop at judge calls or markdown reporting.

It materializes normalized result tables and request summaries that can be queried, aggregated, reused, and fed into Grafana dashboards. That means evaluation outputs exist in two complementary forms:

- **report artifacts** for human interpretation
- **dashboard-ready tabular data** for browsing, comparison, and operational review across runs

This decision makes eval results more useful than a one-off textual artifact.

---

## 11. Observability is contract-driven, not implementation-defined

Observability is specified through separate contracts for:

- OTEL spans
- metrics
- OpenInference semantic spans
- Grafana-facing dashboard artifacts

This is a deliberate design choice. The project does not want observability behavior to emerge implicitly from scattered instrumentation. It wants telemetry structure to be stable enough that emitted data, trace interpretation, and dashboards stay aligned.

This also makes observability generation less ambiguous when code and provisioning artifacts are generated from specs.

---

## 12. Phoenix gets a semantic OpenInference slice inside the same trace

The project supports a Phoenix-facing OpenInference view, but it does not emit a second parallel trace.

Instead, a fixed subset of spans inside the same OTEL trace is annotated semantically for Phoenix. This keeps:

- the full engineering trace for detailed runtime diagnosis
- the compact semantic chain / retriever / reranker / LLM view for model-oriented inspection

This decision avoids duplicating trace systems while still giving Phoenix a clean semantic surface.

---

## 13. Telemetry flows through an OpenTelemetry Collector layer

The application does not export telemetry directly to every observability backend.

Instead, telemetry is sent to an OpenTelemetry Collector, which sits between the app and downstream backends. This gives the system an intermediate routing layer and keeps runtime telemetry export less tightly coupled to any one backend.

That decision matters because the project needs multiple observability surfaces without turning each backend into a direct runtime integration concern.

---

## 14. Launcher layer controls variability without exploding config files

The launcher layer in `Execution/bin` is not only a convenience wrapper.

It is an execution control layer that helps materialize one concrete experiment scenario from a larger supported capability space. Instead of keeping a dedicated static config file for every combination of:

- chunking strategy
- retrieval variant
- reranker
- generation backend
- new run vs resumed run

the launcher guides the user through selecting a valid combination and assembles a temporary config from those choices.

This prevents configuration sprawl and keeps the system’s variability manageable.

---

## 15. The launcher also supports resuming unfinished eval runs

The launcher is also used to resume failed or unfinished eval runs.

This is important because evals are stateful and run-scoped. Restarting such a run should not require manually reconstructing the right configuration and run identity.

By surfacing resumable runs and materializing the correct restart configuration, the launcher acts as part of the operational control surface of the eval system.

---

## 16. Specification is the source of truth for code and test generation

One of the most important decisions in the repository is that generated code is not treated as the design authority.

The source of truth is the specification.

In practice, that means:

- I define the contracts, types, rules, interfaces, and boundaries first
- the model generates code and tests from those specs
- generated code is reviewed against the specification, not treated as the place where design intent originates

This decision exists to reduce ambiguity, improve reproducibility, and make model-assisted generation easier to direct and easier to audit.

---

## 17. Evidence stays separate from execution

The repository keeps execution, evidence, measurement, specification, and documentation as distinct surfaces.

That separation is intentional. It allows the project to preserve:

- runnable implementation
- explicit design contracts
- telemetry and dashboards
- captured request and eval artifacts
- human-readable documentation

as related but different engineering layers.

This prevents the project from collapsing everything into “the codebase” and makes it easier to inspect and compare what the system does, what it was designed to do, and what evidence it produced.

---

## 18. Local Dockerized infrastructure is treated as part of reproducibility

The local stack is not treated as a disposable dev-only convenience.

It is part of how the project preserves reproducible operating conditions across runtime, eval, and observability work. Local Qdrant, PostgreSQL, Grafana, Tempo, Phoenix, model-serving backends, and collector-layer infrastructure make the system testable as a composed environment rather than only as isolated components.

This decision helps keep architecture, evaluation, and observability work grounded in a repeatable local setup.

---

## Summary

The project’s key technical decisions are mostly decisions about **clarity under variability**.

They aim to keep:

- stage boundaries explicit
- artifacts contract-bound
- runtime and eval paths comparable
- observability aligned with emitted telemetry
- model-assisted generation grounded in specifications rather than improvisation

Together, these decisions make the repository easier to evolve as an engineering system rather than only as a collection of experiments.