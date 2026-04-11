# Spec Conformance MCP Routing Policy

Use this MCP when the task is about drift between repository specs and implementation.

Prefer this server when you need to know:

- which spec requirements are currently violated by code
- which code capabilities exist but are not yet documented in spec
- whether a recent code change needs a spec update
- which known mismatches already have deterministic evidence

Do not use this MCP as the first stop for:

- reading the raw specification text
- exploring runtime observability or dashboards
- understanding project ownership or operational defaults

In those cases, use:

- `Spec MCP`
- `Observability MCP`
- `Project Context MCP`

Use the tools in this order:

1. `list_modules()` to see current coverage
2. `compare_spec_and_code(module)` for the main overview
3. `list_known_mismatches(module="")` for backlog-style drift review
4. `explain_check(check_id)` when you need the specific evidence
5. `compare_changed_files(changed_files, module="")` when reviewing a concrete patch
6. `find_uncovered_requirements(module)` when checking test-awareness around known checks
