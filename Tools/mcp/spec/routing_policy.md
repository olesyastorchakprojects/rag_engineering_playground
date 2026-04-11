# Spec MCP Routing Policy

Consult `Spec MCP` first when the question is about:

- formal contracts
- machine-readable schemas
- storage markdown contracts
- SQL table definitions used as storage schemas
- prompt specifications used by generation or evaluation
- code generation requirements
- module behavior defined by repository specs
- validation requirements defined by repository specs
- validation risks defined by repository specs
- which topic is the primary source of truth for one entity or module
- which topics are related to one another in the curated spec graph
- which documents are primary for generation of one topic
- which documents are primary for validation of one topic
- which curated documents belong to one spec topic
- which references are strong runtime references versus secondary implementation references

Use `Spec MCP` especially for:

- `get_topic_sources(topic)` when you need the full curated source set for a known topic
- `find_source_of_truth(name)` when you know the entity or module name but not the exact document path
- `get_generation_context(topic)` when implementing code from a spec topic
- `get_validation_context(topic)` when validating generated output against spec expectations
- `list_documents_by_kind(kind)` when you need all docs of one curated kind across topics

Prefer `Spec MCP` over raw repository search when:

- the answer depends on curated source-of-truth priority
- the answer depends on separating data contracts from config/env/storage contracts
- the answer depends on separating formal specs from implementation references
- the answer depends on knowing which documents are required for generation or validation rather than merely related by keyword search

Do not consult `Spec MCP` first when the question is primarily about:

- current operational topology
- service roles
- runtime data flow
- debugging defaults
- language ownership boundaries

For those questions, consult `Project Context MCP` first.

Do not consult `Spec MCP` first when the question is primarily about:

- current retrieval/index state in Qdrant
- current eval/request rows in Postgres
- traces, dashboards, and runtime telemetry

For those questions, consult the corresponding runtime-truth MCP first:

- `Qdrant MCP`
- `Postgres MCP`
- `Observability MCP`
