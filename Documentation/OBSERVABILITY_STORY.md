# Observability Story

## Why Observability Is Central Here

This project is designed around the idea that a RAG system should not only
produce answers, but also explain how it produced them.

Observability is therefore not an optional layer added after the fact.
It is part of the project contract.

The repository treats traces, metrics, dashboards, and request-level storage as
core engineering tools.

## What The Project Makes Visible

The system exposes behavior at multiple levels:

- whole-request execution
- stage execution
- dependency latency
- retries
- token usage
- cost signals
- request captures
- eval runs

This layered visibility matters because no single artifact is enough on its
own.

For example:

- traces are excellent for temporal execution flow
- metrics are excellent for aggregate operational behavior
- request captures are excellent for stable request-level provenance
- run reports are excellent for experiment review

The project uses all of them together.

## Runtime Observability

The runtime emits telemetry for the major stages of the RAG pipeline:

- input validation
- retrieval
- reranking
- generation

It also emits dependency-level metrics for external interactions such as:

- embedding calls
- vector search
- chat generation
- reranker transport calls

This allows latency investigation at two levels:

- stage-level latency
- dependency-level latency

That distinction is useful because “the request was slow” and “the reranker
transport was slow” are different engineering conclusions.

## OpenTelemetry And Local Stack

The observability stack uses:

- OpenTelemetry
- Tempo
- Phoenix
- Prometheus
- Grafana

Each piece has a distinct role:

- OpenTelemetry provides the instrumentation layer
- Tempo stores traces
- Phoenix gives an LLM-oriented trace inspection surface
- Prometheus stores metrics
- Grafana turns the metrics and eval aggregates into dashboards

This local stack is part of the repository's working model, not just a support
tool for debugging.

## Why Traces Matter

Traces make the request path inspectable as a sequence of real operations.

For a single request, they can show:

- which stages ran
- how long each stage took
- which dependency calls were made
- where retries happened
- what request-local quality attributes were attached

That makes traces especially useful for:

- debugging latency spikes
- understanding reranking and retrieval behavior
- validating that the system emitted the expected spans
- demoing the system live

## Why Metrics Matter

Metrics serve a different purpose from traces.

Instead of telling the story of one request, they show patterns across many
requests.

This project uses metrics to observe:

- request counts
- latency distributions
- retry activity
- token usage
- cost signals
- dependency failure behavior

These metrics are what let the team answer questions like:

- did latency regress after a change?
- is reranking making the runtime slower?
- which dependency is driving tail latency?
- how much are we spending over a time range?

## Why Dashboards Matter

Dashboards turn raw metrics and stored eval aggregates into operational views.

They make it easy to compare:

- runtime latency
- dependency behavior
- eval run usage
- token and cost summaries
- run-specific metadata

This is especially helpful because the project is built for experimentation.
When retrieval strategy, reranker choice, model choice, and chunking strategy
can all vary, dashboards become part of the comparison interface.

## Why Observability Complements Request Capture

Observability and request capture solve related but different problems.

Observability answers:

- what happened during execution?
- when did it happen?
- how long did it take?
- which dependency failed?

Request capture answers:

- what exact request data was produced?
- what chunks were retrieved?
- what rerank order was selected?
- what config snapshot was active?

Together they let the project support both operational debugging and
experimental reproducibility.

## Why This Is Important For Presentation

Observability is one of the clearest ways to show that the project is serious
engineering work rather than a narrow demo.

During a presentation, the observability story lets you show:

- the answer
- the retrieval path
- the reranking path
- the dependency timings
- the captured request record
- the resulting eval artifacts

That creates a stronger story than “we asked a model a question and got a
response.”

## What This Enables

Because observability is built into the project, the team can:

- debug runtime issues faster
- compare variants more confidently
- understand cost and latency tradeoffs
- validate end-to-end behavior against real signals
- make demos more concrete and credible

This is one of the reasons the repository already feels mature: the system is
not only implemented, it is inspectable.
