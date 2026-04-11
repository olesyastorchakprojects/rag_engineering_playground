# OTEL Runtime Smoke

This crate is the canonical runtime-shaped observability smoke for `rag_runtime`.

It validates all of the following in one short-lived process:
- effective `RUST_LOG`
- OTLP endpoint wiring
- tracing-only root span flow
- stage and dependency spans shaped like the runtime pipeline
- post-request export window for batch traces and periodic metrics

## Canonical Launch

From `Execution/otel_runtime_smoke`:

```bash
RUST_LOG='rag_runtime=debug,opentelemetry=debug,opentelemetry_sdk=debug,opentelemetry_otlp=debug,tracing_opentelemetry=debug,tonic=debug,h2=info,hyper=info,info' cargo run -- --endpoint http://localhost:4317
```

## Successful Validation

The run is considered healthy when:
- the process prints the effective environment diagnostics
- the process completes without exporter initialization errors
- a `rag.request` trace tree appears in Tempo/Phoenix
- the tree contains:
  - `rag.request`
  - `input_validation`
  - `retrieval.embedding`
  - `retrieval.vector_search`
  - `generation.chat`

## Notes

- This smoke intentionally uses tracing-based spans only.
- This smoke intentionally keeps the process alive after request completion so batch export has time to run.
- This smoke is a runtime-shape reference, not a direct copy of the full `rag_runtime` business pipeline.
