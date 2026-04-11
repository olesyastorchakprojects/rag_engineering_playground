# Run From Zero

## Purpose

This is the canonical public onboarding path for bringing the project up from a clean machine.

It is intentionally not a demo script.
It is the shortest practical path that proves a new engineer can:

- start the local infrastructure
- run one ingest pipeline
- run one runtime scenario
- inspect the resulting system surfaces

This guide is verified against the current repository entrypoints, compose files,
launcher flags, profile paths, dataset paths, and local endpoint defaults.

It is not a separate deployment stack and does not guarantee a frictionless start on every clean machine.
Its goal is narrower and practical: provide a repository-native path with enough concrete commands, paths, and expected surfaces for an engineer to bring the system up locally and debug environment-specific issues if they appear.

## What This Path Uses

This guide uses the simplest stable local path:

- chunking: `fixed`
- retrieval: `dense`
- reranking: `heuristic`
- generation: local Ollama chat model
- dataset for runtime questions: `Evidence/evals/datasets/default`

Why this path:

- it avoids external generation providers
- it avoids remote reranker dependencies
- it uses current first-class repository paths
- it proves the main end-to-end flow without requiring the full experiment matrix

## Prerequisites

Install these on the machine first:

- Docker with the Compose plugin
- Python 3
- Rust + Cargo
- network access for first-time model/image pulls

This path does not require a prebuilt Python environment for the core ingest and runtime steps.

## Required Local Environment

The repository root `.env` must contain at least these local values:

```dotenv
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
POSTGRES_URL=postgres://postgres:postgres@localhost:5432/rag_eval
TRACING_ENDPOINT=http://localhost:4317
METRICS_ENDPOINT=http://localhost:4317
RUST_LOG=rag_runtime=debug,info
```

Notes:

- `QDRANT_URL` and `OLLAMA_URL` are used by dense ingest and runtime
- `POSTGRES_URL`, `TRACING_ENDPOINT`, `METRICS_ENDPOINT`, and `RUST_LOG` are required by the current runtime environment contract
- this guide does not require external API keys

## Step 1. Create The Shared Docker Network

Both compose projects expect the external Docker network `axum_net`.

```bash
docker network create axum_net
```

If the network already exists, Docker will report that and nothing else is required.

The RAG-side compose project also expects two external Docker volumes that may not exist on a clean machine yet:

```bash
docker volume create ollama
docker volume create sys_design_agent_qdrant_data
```

If they already exist, Docker will report that and reuse them.

## Step 2. Build The Local Reranker Image

The RAG-side compose file references a local image name for the reranker service.
Build it once before starting the stack:

```bash
docker build -t observability-mxbai-reranker:latest Execution/docker/mxbai_reranker
```

Even though the canonical runtime path in this guide uses heuristic reranking,
building the image keeps the compose project consistent and prevents startup failure.

## Step 3. Start The Local Stack

Start the RAG-side services:

```bash
docker compose -f Execution/docker/rag.compose.yaml up -d
```

Start the observability and eval-storage services:

```bash
docker compose -f Execution/docker/compose.yaml up -d
```

After startup, the main local surfaces are:

- Qdrant: `http://localhost:6333`
- Ollama: `http://localhost:11434`
- Phoenix: `http://localhost:6006`
- Grafana: `http://localhost:3001` with `admin/admin`
- Prometheus: `http://localhost:9090`
- OTLP collector: `http://localhost:4317`

## Step 4. Pull The Local Models

The fixed dense ingest profile uses the embedding model `qwen3-embedding:0.6b`.
The local runtime path in this guide uses the chat model `qwen2.5:1.5b-instruct-ctx32k`.

Pull both into the local Ollama instance:

```bash
docker exec rag-ollama ollama pull qwen3-embedding:0.6b
docker exec rag-ollama ollama pull qwen2.5:1.5b-instruct-ctx32k
```

You can verify that Ollama sees them:

```bash
curl -sf http://localhost:11434/api/tags
```

## Step 5. Run Dense Fixed Ingest

Use the fixed chunk set and the fixed dense ingest profile:

```bash
python3 Execution/ingest/dense/ingest.py \
  --chunks Evidence/parsing/understanding_distributed_systems/chunks/fixed_chunks.jsonl \
  --config Execution/ingest/dense/profiles/fixed.toml \
  --env-file .env
```

What this should do:

- read fixed chunks from `Evidence/parsing/understanding_distributed_systems/chunks/fixed_chunks.jsonl`
- create embeddings with Ollama
- create or reuse the Qdrant collection `chunks_dense_qwen3_fixed`
- write failed/skipped ingest logs into `out/` only if needed

What success looks like:

- the command exits with code `0`
- it prints the normal ingest summary
- Qdrant now contains the fixed dense collection

Optional quick check:

```bash
curl -sf http://localhost:6333/collections/chunks_dense_qwen3_fixed
```

## Step 6. Run One Runtime Scenario

Use the launcher because it is the current repository-aware entrypoint for runtime execution.

Run:

```bash
python3 Execution/bin/run_stack.py launch
```

Choose the following path in the interactive launcher:

1. `Run mode` -> `runtime only`
2. `Chunking strategy` -> `fixed`
3. `Retriever` -> `dense`
4. `Reranker` -> `heuristic`
5. `Chat model config` -> `local | qwen2.5:1.5b-instruct-ctx32k | http://localhost:11434`
6. `Question set` -> `default | Distributed Systems Basics | 5 questions`
7. `Action` -> `launch`

Why this exact path:

- it matches the collection created in Step 5
- it uses the maintained launcher instead of hand-editing configs
- it keeps the run local-first

What success looks like:

- the launcher prints the resolved runtime plan
- `cargo run` starts the Rust runtime
- the runtime answers the question set from `Evidence/evals/datasets/default/questions.txt`
- request-level outputs become visible in traces, metrics, and capture storage

## Step 7. Inspect The Result

After the runtime run, inspect at least these surfaces.

### Runtime Trace

Open Phoenix:

- `http://localhost:6006`

Look for the recent `rag.request` trace and confirm that you can see:

- request input
- retrieval stage
- reranking stage
- generation stage

### Metrics Dashboard

Open Grafana:

- `http://localhost:3001`

Use:

- username: `admin`
- password: `admin`

Confirm that runtime traffic is visible on the provisioned dashboards.

### Collection Check

Confirm that the dense fixed collection exists in Qdrant:

```bash
curl -sf http://localhost:6333/collections/chunks_dense_qwen3_fixed
```

## Optional Step 8. Run Eval On Top Of Existing Captures

This is not required for the minimal from-zero proof, but it is the next canonical extension once runtime requests exist.

Unlike the core ingest/runtime path above, this optional eval path assumes the repository Python environment is available at `.venv/bin/python`, because the launcher delegates to `Execution.evals.eval_orchestrator` through that interpreter.

Use the launcher entrypoint:

```bash
python3 Execution/bin/run_stack.py launch
```

Choose the following path in the interactive launcher:

1. `Run mode` -> `evals only`
2. `Chunking strategy` -> `fixed`
3. `Judge model config` -> the currently configured judge path you want to use
4. `Eval run mode` -> `new run`
5. `Action` -> `launch`

This step still depends on the current eval judge configuration:

- the checked-in default `Execution/evals/eval_engine.toml` points to the Together judge provider
- if you want to stay local-first, select the local judge option in the launcher
- if you keep the Together-backed judge, additional provider configuration is required beyond the local-only runtime path above

## Shutdown

Stop the observability and eval-storage stack:

```bash
docker compose -f Execution/docker/compose.yaml down
```

Stop the RAG-side stack:

```bash
docker compose -f Execution/docker/rag.compose.yaml down
```

## What This Guide Proves

If all steps above succeed, a new engineer has demonstrated that this repository can:

- start its local infra from repository-owned compose files
- ingest a real chunk corpus into Qdrant
- run the Rust runtime against that local corpus
- produce observable traces and metrics
- expose a reproducible, repository-aware runtime entrypoint

That is the minimum public proof that the project can be run end to end from the repository itself.
