# Spec Conformance MCP

This MCP server exposes curated spec/code drift checks.

Its purpose is to answer two different questions:

- does the code still conform to the repository spec?
- has the code moved ahead of the spec without the spec being updated?

This server does not replace:

- `Spec MCP` for reading source-of-truth documents
- `Project Context MCP` for operational ownership

Instead, it compares a small curated set of high-signal requirements and capabilities.

The current version is intentionally deterministic and conservative:

- it uses explicit checkers
- it uses a manifest-driven `checks.yaml` rather than hardcoded Python-only rules
- it currently covers `hybrid_ingest`, `fixed_chunker`, and `rag_runtime`
- it returns `conforms`, `violates_spec`, `undocumented_code`, or `needs_review`

Routing guidance lives in:

- [routing_policy.md](routing_policy.md)

## Tool Surface

- `list_modules()`
- `list_spec_requirements(module)`
- `scan_code_capabilities(module)`
- `compare_spec_and_code(module)`
- `list_known_mismatches(module="")`
- `explain_check(check_id)`
- `compare_changed_files(changed_files, module="")`
- `find_uncovered_requirements(module)`

## When To Use It

Use this server when you need a compact, deterministic read on spec/code drift.

Good examples:

- "what modules are currently covered?"
- "does this module have known mismatches?"
- "what changed files might require a spec update?"
- "where is test coverage still missing for this curated check?"

## Notes

- the checker set is intentionally small and curated
- the server is conservative by design
- `compare_changed_files(...)` is the fastest way to review a concrete patch
- `find_uncovered_requirements(...)` highlights checks without mapped coverage
- `list_known_mismatches(...)` is useful for backlog-style drift review

## Local Run

```bash
./.venv/bin/python Tools/mcp/spec_conformance/server.py
```

## Expected MCP Registration

This server is intended to be registered as a local stdio MCP server in the local Codex configuration.
