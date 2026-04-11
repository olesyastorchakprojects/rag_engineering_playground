# Spec MCP

This MCP server exposes the repository's canonical specification and schema trees.

Its purpose is to give the agent structured access to:

- architecture docs
- contracts
- codegen specs
- test and verification specs
- machine-readable schemas
- curated implementation references
- incident-backed reference areas when they materially improve generation quality

This server does not replace `Project Context MCP`.

- `Project Context MCP` answers how the project works operationally
- `Spec MCP` answers what the formal repository specs currently say

## Tool Surface

- `get_spec_roots()`
- `get_topic_index()`
- `list_spec_documents(prefix="")`
- `read_spec_document(path)`
- `get_topic_sources(topic)`
- `find_source_of_truth(name)`
- `find_related_docs(topic)`
- `list_documents_by_kind(kind)`
- `get_generation_context(topic)`
- `get_validation_context(topic)`
- `search_spec_documents(query, limit=20)`

## When To Use It

Use this server when the question depends on the repository's formal contracts, schemas, or curated topic graph.

Good examples:

- "what is the source of truth for `rag_runtime`?"
- "which documents should I use when generating code for this topic?"
- "what are the validation references for this area?"

The curated topic index may include semantic layers such as:

- `primary_source_of_truth`
- `architecture`
- `codegen`
- `related_topics`
- `data_contracts`
- `storage_contracts`
- `config_contracts`
- `env_contracts`
- `external_service_contracts`
- `prompt_specs`
- `data_schemas`
- `storage_schemas`
- `config_schemas`
- `env_schemas`
- `runtime_metadata`
- `validators`
- `strong_references`
- `secondary_references`
- `implementation_references`
- `incident_reports`
- `dashboard_roles`
- `validation_risks`

Routing guidance lives in:

- [routing_policy.md](routing_policy.md)

## Local Run

```bash
./.venv/bin/python Tools/mcp/spec/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.
