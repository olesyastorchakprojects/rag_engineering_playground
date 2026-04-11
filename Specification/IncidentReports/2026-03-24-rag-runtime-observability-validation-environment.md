# Incident Report: `rag_runtime` Observability Validation Environment

Date: `2026-03-24`

## Purpose

This report records what went wrong during same-day validation of `rag_runtime` observability after the runtime and backend stack were already close to working.

The main failure was not a broken observability implementation.
The main failure was a broken validation process.

This report must be read before any future trace-validation session for:

- `Execution/rag_runtime/`
- `Execution/otel_smoke/`
- `Execution/otel_runtime_smoke/`
- `Execution/docker/compose.yaml`

## Summary

Multiple additional hours were lost because a tool-run false negative was treated as proof that `rag_runtime` tracing was still broken.

The critical mistake was repeating the exact class of error already documented in the earlier incident report:

- not checking the effective `RUST_LOG` first;
- treating the agent execution environment as equivalent to the user's terminal;
- continuing to patch code after the validation environment was already untrustworthy.

By the end of the session, the decisive fact was clear:

- the user-facing CLI run was able to emit traces correctly;
- the agent run was suppressing traces because its inherited environment had `RUST_LOG=warn`.

## What Went Wrong

### 1. The effective `RUST_LOG` was not checked before drawing conclusions

The agent shell environment inherited:

- `RUST_LOG=warn`

But the runtime instrumentation used `INFO` spans and `INFO` events.

That meant the agent's validation environment filtered out:

- `info_span!(...)`
- `#[tracing::instrument]` default spans
- `tracing::info!(...)`

Consequences:

- traces appeared absent in the agent session;
- valid tracing code was treated as broken;
- hours were spent debugging the wrong layer.

This was a direct repeat of the guardrail already written in:

- `Specification/IncidentReports/2026-03-24-rag-runtime-observability-generation.md`

### 2. Tool-run absence of traces was treated as proof of runtime failure

The agent environment and the user's terminal environment were not equivalent.

Important differences included:

- different effective `RUST_LOG`;
- different launch style;
- different stdin/process behavior;
- different confidence level in backend reachability and env loading.

The user ran the CLI in the normal way:

```bash
cd ~/code/prompt_gen_proj/Execution/rag_runtime
cargo run -- --config rag_runtime.toml --ingest-config ../ingest/dense/ingest.toml
```

That user-facing run produced traces.

The agent used other run styles during debugging, including non-equivalent tool-run launches.

Consequences:

- the wrong execution environment became the source of truth;
- valid user-observed telemetry was temporarily discounted;
- the debugging process looped around false negatives.

### 3. Endpoint repair was real, but it was over-attributed

During the session, `.env` was corrected so that:

- `TRACING_ENDPOINT=http://localhost:4317`
- `METRICS_ENDPOINT=http://localhost:4317`

This change mattered.
It aligned the CLI with the live collector ingress used by the working observability stack.

However, this was not enough by itself to explain the entire story.

After the endpoint correction:

- metrics clearly started flowing;
- agent-side trace validation still appeared broken;
- later it became clear that the remaining negative signal was polluted by `RUST_LOG=warn`.

Rule for future runs:

- do not attribute success or failure to a single fix until the validation environment is known-good.

### 4. Diagnostic code was added while the environment was still invalid

Once the agent believed traces were still missing, several code-path hypotheses were explored:

- root span activation style;
- smoke-like trace init path;
- literal insertion of a known-good diagnostic span block from `otel_current_exact`;
- temporary diagnostic spans in `main.rs`.

Some of those changes may be harmless or even useful, but the timing was wrong.

They were introduced while the validation environment was still lying.

Consequences:

- it became harder to tell which changes were truly necessary;
- real fixes and diagnostic noise became interleaved;
- rollback/ablation analysis became more expensive.

Rule for future runs:

- do not patch tracing code while `RUST_LOG` or launch parity is still unknown.

### 5. A working backend stack was almost re-diagnosed as broken

By the time the later validation happened, the observability stack was already in a good state:

- `Execution/docker/compose.yaml` stack was up;
- `phoenix`, `tempo`, `otel-collector`, `prometheus`, and `grafana` were alive;
- `Execution/otel_smoke` was working;
- `Execution/otel_runtime_smoke` was working.

That should have shifted the burden of proof onto the validation environment.

Instead, the session continued to suspect broad tracing failure in `rag_runtime`.

Rule for future runs:

- once backend health and smoke references are confirmed, check environment parity before touching runtime code.

## What Was Confirmed To Work

By the end of the session, the following were confirmed:

- the observability Docker stack was healthy;
- `Execution/otel_smoke` emitted traces successfully;
- `Execution/otel_runtime_smoke` emitted runtime-shaped traces successfully;
- `rag_runtime` CLI emitted traces in the user's normal terminal run;
- `rag_runtime` CLI also emitted traces in the agent environment once `RUST_LOG` was explicitly set to a compatible debug-friendly value.

This means the primary blocker was validation-environment mismatch, not a total tracing implementation failure.

## Root Cause

The root cause of the wasted debugging cycle was:

- failure to validate the effective environment before trusting observability results.

More specifically:

- the agent inherited `RUST_LOG=warn`;
- `dotenv`-loaded project settings did not override that inherited value;
- agent-side runs therefore filtered out the very spans being validated;
- the session kept debugging tracing code instead of first correcting the validation environment.

## Required Guardrails For Future Validation

Before any future claim that `rag_runtime` traces are missing, the validating agent must:

1. Print the effective `RUST_LOG`.
2. Confirm that the effective filter is compatible with `INFO` spans.
3. Confirm the effective tracing and metrics endpoints.
4. State whether the run is:
   - user-terminal run
   - agent tool-run
   - smoke run
5. Refuse to draw code-level conclusions from a tool-run negative result unless the environment matches the user-facing run.
6. Re-read both incident reports before changing observability code.

## Required Validation Order

The required order for future sessions is:

1. Confirm backend health.
2. Confirm smoke references.
3. Print effective environment:
   - `RUST_LOG`
   - tracing endpoint
   - metrics endpoint
4. Reproduce with the user's normal CLI launch shape.
5. Only then inspect runtime code if traces are still absent.

## Short Checklist

Use this checklist before changing any tracing code:

- Is `RUST_LOG` explicitly known?
- Is the effective value compatible with `INFO` spans?
- Is the run happening in the same style as the user's real CLI run?
- Is the collector endpoint live and correct?
- Do the smoke apps already prove the backend path is healthy?
- Are we about to patch code before environment parity is proven?

If any answer is `no` or `unknown`, stop debugging code and fix validation first.
