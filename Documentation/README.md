# Project Documentation

This folder contains human-oriented project documentation for presentation,
onboarding, and architecture review.

These documents are intentionally narrative.
They complement the repository contracts and code-generation specs under
`Specification/`, but they do not replace them.

Recommended reading order:

1. `PROJECT_OVERVIEW.md`
2. `RUN_FROM_ZERO.md`
3. `ARCHITECTURE_OVERVIEW.md`
4. `SPECIFICATION_FIRST_APPROACH.md`
5. `REPOSITORY_MAP.md`
6. `KEY_TECHNICAL_DECISIONS.md`
7. `FEATURES_AND_CAPABILITIES.md`
8. `MCP_SERVERS_AND_TOOLS.md`
9. `AGENT_WORKFLOW_STORY.md`
10. `EVALUATION_STORY.md`
11. `OBSERVABILITY_STORY.md`

Document guide:

- `PROJECT_OVERVIEW.md`
  - what the project is, what problem it solves, and why it exists
- `RUN_FROM_ZERO.md`
  - the canonical onboarding path for bringing the local system up from a clean machine
- `ARCHITECTURE_OVERVIEW.md`
  - the end-to-end system shape and the role of each major subsystem
- `SPECIFICATION_FIRST_APPROACH.md`
  - how the project uses contracts, schemas, and specs as the source of truth
- `REPOSITORY_MAP.md`
  - how repository areas reflect the implementation/specification/measurement split
- `KEY_TECHNICAL_DECISIONS.md`
  - the most important engineering decisions and their rationale
- `FEATURES_AND_CAPABILITIES.md`
  - the functionality the project currently supports
- `MCP_SERVERS_AND_TOOLS.md`
  - how project-specific MCP servers expose repository-aware capabilities
- `AGENT_WORKFLOW_STORY.md`
  - how the repository supports multi-agent execution and workflow control
- `EVALUATION_STORY.md`
  - how request capture, eval runs, judge stages, and reports fit together
- `OBSERVABILITY_STORY.md`
  - how traces, metrics, dashboards, and local infra support engineering work

For executable contracts and implementation-level source-of-truth material,
see:

- `Specification/`
- `Execution/`
- `Measurement/`
- `Evidence/`
