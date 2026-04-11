# Handoff Packet

Use this packet when passing work from one agent to the next.

Copy the template and fill only the fields you know.

## Template

```text
task: <task summary>
mode: <implement-change | review-change | spec-driven>
module: <module or subsystem>

changed_files:
- <file 1>
- <file 2>

changed_test_files:
- <test file 1>
- <test file 2>

spec_docs_used:
- <doc 1>
- <doc 2>

mcps_consulted:
- <mcp 1>
- <mcp 2>

commands_run:
- <command 1>
- <command 2>

findings:
- <finding 1>
- <finding 2>

known_limitations:
- <limitation 1>
- <limitation 2>

open_risks:
- <risk 1>
- <risk 2>

recommended_next_agent: <agent name>
```

## Minimum Version

Use this when you want the smallest possible handoff:

```text
task: <task summary>
module: <module>
changed_files:
- <file 1>
spec_docs_used:
- <doc 1>
commands_run:
- <command 1>
open_risks:
- <risk 1>
recommended_next_agent: <agent name>
```

## Notes

- `Code Writer Agent` should usually populate `changed_files`, `commands_run`, and `assumptions` in prose near `known_limitations`.
- `Spec Conformance Agent` should populate `findings` with clear buckets:
  - code must change
  - spec must change
  - MCP metadata is stale
- `Code Review Agent` should keep `findings` ordered by severity.
- `Coverage & Gaps Agent` should treat uncovered areas as gaps, not as code defects by default.
