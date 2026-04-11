# Local Observability And Eval Storage Stack

This directory defines the reproducible local observability and eval-storage stack for the project.
`Execution/docker/compose.yaml` defines the observability-and-eval storage stack.
`Execution/docker/rag.compose.yaml` defines the RAG-side stack for `qdrant`, `ollama`, and `mxbai-reranker`.

Services:
- PostgreSQL
- Phoenix
- Tempo
- OpenTelemetry Collector
- Prometheus
- Grafana
- Qdrant
- Ollama
- mxbai-reranker

The stack is wired to:

- repository observability artifacts under `Measurement/observability`
- PostgreSQL init SQL under `Execution/docker/postgres/init/`

## Why Phoenix Is Configured This Way

Phoenix is intentionally pinned to `arizephoenix/phoenix:version-13.14.0` and uses a persistent working directory volume.

This follows the official Phoenix Docker guidance:
- Phoenix should be version-pinned for stable self-hosted runs.
- SQLite-backed Phoenix should run with `PHOENIX_WORKING_DIR` attached to a persistent volume.

## Start

```bash
docker compose -f Execution/docker/compose.yaml up -d
```

To start the RAG-side services in the dedicated `rag` Compose project:

```bash
docker compose -f Execution/docker/rag.compose.yaml up -d
```

## Stop

```bash
docker compose -f Execution/docker/compose.yaml down
```

## Endpoints

- mxbai-rerank-base-v2 reranker: `http://localhost:8081`
- RAG runtime cross-encoder endpoint env: `RERANKER_ENDPOINT=http://localhost:8081`
- PostgreSQL: `postgres://postgres:postgres@localhost:5432/rag_eval`
- Grafana: `http://localhost:3001`
- Prometheus: `http://localhost:9090`
- Tempo: `http://localhost:3200`
- Phoenix UI: `http://localhost:6006`
- OTLP gRPC ingress: `http://localhost:4317`
- OTLP HTTP ingress: `http://localhost:4318`
- Phoenix OTLP gRPC host port: `http://localhost:4319`

## Notes

- PostgreSQL is the local evaluation-storage backend for request captures and later eval results, summaries, and aggregates.
- PostgreSQL initialization SQL is mounted from `Execution/docker/postgres/init/`.
- Qdrant and Ollama live in the separate `Execution/docker/rag.compose.yaml` compose project.
- The OpenTelemetry Collector is the only ingress point for traces and metrics.
- Collector routes traces to Tempo and Phoenix.
- Collector exposes Prometheus metrics on `:9464`.
- Tempo does not publish host port `4317` to avoid colliding with the collector ingress port.
- The reranker is isolated into `Execution/docker/rag.compose.yaml` so it does not appear inside the `observability` Compose group.
