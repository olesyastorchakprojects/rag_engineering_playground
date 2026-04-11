# Features And Capabilities

## Current Feature Set

The project currently provides an end-to-end RAG platform with both runtime and
evaluation capabilities.

## Corpus Preparation

The system supports:

- document extraction and cleanup
- chunk generation from source corpus artifacts
- multiple chunking strategies

Current chunking strategies:

- fixed chunking
- structural chunking

## Retrieval

The system supports two retrieval families:

- dense retrieval
- hybrid retrieval

Hybrid retrieval includes dense and sparse representations and is designed for
retrieval strategy comparison rather than only one fixed production path.

## Reranking

The runtime supports multiple reranking strategies:

- `PassThrough`
- `Heuristic`
- `CrossEncoder`

Cross-encoder reranking currently supports multiple transport-backed provider
implementations and includes:

- batching
- retry policy
- token accounting
- provider-specific response normalization

## Generation

The generation layer supports multiple transport styles, including local and
OpenAI-compatible chat backends.

The runtime tracks:

- prompt tokens
- completion tokens
- total tokens
- cost metadata used by downstream reporting

## Request Capture

The runtime writes one canonical `RequestCapture` per successful request.

Captured information includes:

- request identity and trace linkage
- validated query inputs
- retrieval outputs
- reranker configuration snapshots
- generation token usage
- retrieval-stage metrics
- reranking-stage metrics

## Retrieval And Reranking Metrics

The runtime computes request-level ranking quality metrics against golden
retrieval targets.

Current metrics include:

- Recall@k
- Reciprocal Rank@k
- nDCG@k
- first relevant rank
- relevant counts

The same metric model is used across retrieval and reranking stages.

## Evaluation

The project includes a resumable eval engine that can:

- bootstrap run scope from captured requests
- freeze run identity and request scope
- resume failed runs safely
- judge generation quality
- judge retrieval quality
- build request-level summaries
- write run artifacts

Current run artifacts include:

- `run_manifest.json`
- `run_report.md`

## Observability

The project provides end-to-end observability for runtime and eval workflows.

Available signals include:

- traces
- stage spans
- dependency histograms
- retry counters
- token usage
- latency metrics

The observability stack supports:

- Tempo
- Phoenix
- Prometheus
- Grafana

## Dashboards And Reporting

The repository includes dashboards and report generation for:

- runtime latency and reliability
- request-level inspection
- evaluation usage and run comparisons
- token and cost summaries

## Launch And Local Operation

The project includes thin launchers and local stack definitions that make it
possible to:

- run RAG scenarios locally
- launch eval scenarios
- resume failed eval runs
- operate the observability stack locally
- use consistent dataset and golden-retrieval bundles

## Engineering Strengths

Beyond feature checklists, the project is strong in:

- reproducibility
- experiment comparison
- clear contracts
- traceability from request to report
- operational visibility into latency, retries, tokens, and costs
