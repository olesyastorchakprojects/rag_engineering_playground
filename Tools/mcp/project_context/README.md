# Project Context MCP

This MCP server exposes the repository's operating context.

It is the place to ask about:

- service roles and responsibilities
- launcher entrypoints under `Execution/bin`
- provider topology for generation, reranking, and eval judging
- high-level data flow
- hybrid ingest and workflow control-plane roles
- debugging defaults
- language ownership boundaries
- routing policy for other MCP servers
- storage ownership in the operational sense

It complements, but does not replace, formal specifications.

## Tool Surface

- `get_project_context()`
- `get_system_roles()`
- `get_operational_defaults()`
- `get_data_flow()`
- `get_debugging_defaults()`
- `get_language_boundaries()`
- `get_storage_owner(name)`
- `get_routing_policy()`

## When To Use It

Use this server when you need to understand how the project currently works operationally, not when you need formal contracts or live runtime truth.

Good examples:

- "who owns `request_captures`?"
- "what is the default local observability stack?"
- "what does `run_stack.py` launch and what inputs does it resolve?"
- "which generation provider is active right now?"
- "how does hybrid ingest fit into the project flow?"
- "what should we consult first for a storage or routing question?"

`get_storage_owner(...)` returns the operational owner or writer-side owner for a concern.
It does not necessarily return the physical backend system.

Example:

- `request_captures` -> `rag_runtime` as the operational writer
- PostgreSQL remains the physical backend for that table

## Files

- `context.yaml` - human-edited project context source of truth
- `routing_policy.md` - when to consult this MCP first
- `server.py` - MCP server implementation
- `validators.py` - lightweight validation for `context.yaml`
- `tests/` - smoke tests for context loading

## Local Run

```bash
./.venv/bin/python Tools/mcp/project_context/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.
