# Incident Report: `rag_runtime` Observability Generation

Date: `2026-03-24`

## Purpose

This report records what went wrong during the `rag_runtime` observability generation and repair cycle so that the next generation does not repeat the same failures.

This report must be read before any future regeneration of:

- `Execution/rag_runtime/`
- `Measurement/observability/`
- `Specification/codegen/rag_runtime/observability/...`

## Summary

Multiple hours were lost because working code was repeatedly treated as broken.

The main failure pattern was not one single code bug.
It was a compound failure across:

- observability container setup;
- validation environment assumptions;
- tracing filter configuration;
- deviation from the root-span contract already present in the specification;
- overconfident debugging conclusions drawn from incomplete evidence.

## What Went Wrong

### 1. Phoenix container drifted because `latest` was used

The Phoenix image tag was left as `latest`.

That led to an unstable situation where the container behavior changed and was debugged as if the application code had broken.

Observed problems included:

- Phoenix container behavior diverged from previously working runs;
- the container was not aligned with the documented startup pattern;
- time was spent debugging application traces before first stabilizing the backend.

### 2. Phoenix container was not created in a documented, validated way

The Phoenix container setup did not initially match the documented runtime expectations.

Important details that mattered:

- documented Phoenix startup pattern uses a specific container style;
- using an arbitrary compose shape without validating it against Phoenix docs created false negatives during trace validation;
- backend misconfiguration was mistaken for runtime instrumentation failure.

### 3. The container chain itself was broken

The observability backend was not consistently healthy.

Issues that occurred during the session:

- `tempo` had startup and permission problems;
- collector forwarding assumptions were wrong at different points;
- Phoenix connectivity was broken in parts of the session;
- traces were debugged before the collector/backend path was definitively revalidated.

Rule for future runs:

- first prove that the backend path is healthy;
- only then debug application instrumentation.

### 4. `RUST_LOG` filtered out the spans

This was one of the most expensive false-debug causes.

The execution environment used:

- `RUST_LOG=warn`

But the generated tracing spans were created at `INFO`.

That meant:

- `info_span!`
- `#[tracing::instrument]` default info spans
- `info!(...)` events

were filtered out before they reached the OTEL layer.

Consequences:

- traces looked absent;
- direct OTEL spans appeared to work while tracing-based spans looked broken;
- code was blamed when the real issue was filtering.

Rule for future runs:

- never conclude that tracing instrumentation is broken before checking the effective `RUST_LOG`;
- for validation, use the specified fallback or an explicitly compatible filter.

### 5. The generation deviated from the root-span requirement already written in the spec

The specification already required the correct root request span pattern:

- create root span at request entrypoint;
- enter root span before awaiting downstream execution;
- keep it active across the full request path.

This rule was not followed consistently during generation.

Consequences:

- trace trees were malformed;
- child spans were orphaned or inconsistently attached;
- debugging effort went into symptoms that were caused by ignoring an existing spec rule.

Rule for future runs:

- do not improvise around root-span ownership;
- implement the root request scope exactly as specified before debugging anything else.

### 6. Tool-run environment was treated as equivalent to the user's terminal when it was not

Repeated conclusions were drawn from runs executed in a restricted or otherwise different execution environment.

Important mismatches included:

- sandbox vs non-sandbox execution;
- different effective `RUST_LOG`;
- different validation assumptions about backend reachability;
- different confidence in what “no trace appeared” actually meant.

Rule for future runs:

- do not treat tool-run absence of traces as proof that code is broken;
- explicitly validate the execution environment first.

### 7. Direct OTEL diagnostic spans were mixed into tracing-path debugging

During debugging, direct OTEL spans were used as diagnostics.

That was useful for backend sanity-checking, but it also created confusion:

- direct OTEL success does not prove `tracing -> tracing-opentelemetry` success;
- direct OTEL failure does not isolate root-span lifecycle issues;
- mixed validation paths made interpretation noisy.

Rule for future runs:

- keep backend sanity checks separate from tracing-path validation;
- do not let direct OTEL diagnostics redefine the runtime contract.

### 8. The wrong things were blamed before checking the basics

Several hypotheses were explored too early:

- span complexity;
- semantic attribute shape;
- Phoenix UI issues;
- OTEL exporter internals;
- library version mismatch.

Some of these mattered less than:

- backend health;
- `RUST_LOG`;
- root span lifetime.

Rule for future runs:

- check the simple invariants first:
  - backend healthy;
  - correct log filter;
  - root span active across request;
  - trace observed in backend;
- only then debug deeper telemetry shape issues.

### 9. Query-token observability drifted from the intended ownership model

At one point:

- `input_validation` emitted query token count as an event;
- `retrieval.embedding` also emitted a token count attribute;
- the retrieval value was even computed incorrectly with `split_whitespace()`.

This created conflicting numbers and confused trace reading.

The corrected model is:

- `input_validation.token_count` owns `input_token_count` as a span attribute;
- `retrieval.embedding` must not duplicate it.

Rule for future runs:

- token count ownership must stay single-source;
- do not duplicate semantic facts across unrelated spans.

## What Was Confirmed To Work

By the end of the session, the following were confirmed:

- `rag_runtime` CLI can emit a correct trace tree to Phoenix;
- `rag.request` can act as the root span when explicitly entered and kept alive across the full request path;
- `retrieval.embedding`, `retrieval.vector_search`, and `generation.chat` semantic spans can appear correctly in Phoenix;
- `Execution/otel_smoke` can validate tracing-tree behavior when run in a correct environment;
- the main “missing traces” diagnosis was largely caused by validation/setup issues, not by total failure of the application code.

## Required Guardrails For The Next Generation

Before the next generation attempt, the model must:

1. Read this incident report.
2. Read `Specification/architecture/project_structure.md`.
3. Re-read the `observability/implementation.md` root-span requirements carefully.
4. Validate the backend stack before debugging application traces.
5. Validate the effective `RUST_LOG` before concluding that tracing spans are missing.
6. Preserve the tracing-only contract unless the specification explicitly says otherwise.
7. Avoid introducing direct OTEL spans as a runtime workaround when the spec requires tracing-based instrumentation.
8. Keep token-count ownership consistent:
   - `input_validation.token_count` owns `input_token_count`
   - `retrieval.embedding` must not duplicate it

## Short Checklist

Use this checklist before trusting any future observability validation result:

- Is Phoenix pinned to a known-good image tag instead of `latest`?
- Is the collector/Tempo/Phoenix chain healthy right now?
- Does the launch environment use an appropriate `RUST_LOG`?
- Is the request root span explicitly entered before downstream awaits?
- Is the observed failure reproduced in the same environment as the user-facing run?
- Are semantic attrs being checked on the correct semantic spans?
- Are stage spans being mistaken for semantic spans?

If any answer is “no” or “unknown”, do not conclude that the generated code is broken.
