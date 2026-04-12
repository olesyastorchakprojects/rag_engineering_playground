# Backlog

## Observability

- Revisit runtime latency dashboards for local sparse traffic.
  The current `histogram_quantile(rate(..._bucket[window]))` panels on classic histograms become misleading when requests arrive intermittently: while traffic is continuous they look plausible, but after pauses they can jump to bucket boundaries such as `2500ms`. This appears to be a known limitation of classic histogram quantiles on sparse/intermittent traffic rather than a straightforward instrumentation bug. Consider separate strategies for local CLI debugging versus long-lived production-like runtime dashboards.

- Add small set of span attributes to Tempo config for indexing

## Runtime Hardening

- Propagate chunker type into eval manifests consistently.
  `chunking_strategy` is already present in `run_report.md`, but the manifest path is not yet consistent. Eval artifacts should expose the chunker identity (for example `structural` vs `fixed`) in a way that downstream tooling can read without inferring it indirectly from file paths or collection names.

- Configure a larger default context window for the local `ollama` runner.
  The model advertises `context length = 32768`, but the live runner currently starts with `KvSize/n_ctx = 4096`, which can silently undercut `rag_runtime` generation and cause long `/api/chat` failures on retrieval-augmented prompts.

## Deployment Surface

- Add a real deployment surface only if the project moves beyond local RAG experimentation.
  The current repository already proves the intended goal: local parsing, ingest, runtime execution, evaluation, and comparative analysis for RAG experimentation. A stronger deployment surface can be added later as a separate track, likely with dedicated workload containers for ingest and `rag_runtime`, clearer compose-based application entrypoints, and a more reproducible public execution model. For the current release, this is intentionally deferred rather than treated as unfinished core work.

## Parsing / Chunking

- Refactor the structural chunker to use the new metadata split.
  At minimum it should stop depending on document-level fields embedded inside `book_content_metadata.json` and instead read `book_metadata.json` for document-level payload fields while continuing to use `book_content_metadata.json` for structure and annotation. This follow-up should preserve current structural-chunker behavior where required, but align its inputs with the new metadata contracts introduced for the fixed chunker.

- Add a chunker that splits structural chunks into fixed-size chunks.
  This should preserve the structural chunker as the upstream structure-aware stage, then introduce a follow-up chunking step that breaks those structural chunks into fixed-size segments. The goal is to support experiments where structure-aware boundaries are preserved first, but final retrieval units are normalized to a fixed size.

## Ingest

- Sync dense ingest parser with the ingest config contract.
  `dense_ingest_config.schema.json` and `rag_runtime` expect `pipeline.corpus_version`, but the current Python dense-ingest parser rejects that field as unexpected. The parser should accept the full contract so one ingest config can be used consistently by both ingest and `rag_runtime`.

- Add vector reindexing support for embedding-relevant ingest changes.
  The current ingest path detects embedding-relevant fingerprint changes but logs and skips rather than rebuilding affected points. Add an explicit reindexing path so collection state can be updated when embedding model, vector settings, or other index-relevant inputs change.
