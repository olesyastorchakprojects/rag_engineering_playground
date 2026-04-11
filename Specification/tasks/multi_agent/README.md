# Multi-Agent Tasks

This directory contains reusable role prompts for a project-specific multi-agent workflow.

Files:

- `coordinator.md`
- `code_writer_agent.md`
- `spec_conformance_agent.md`
- `code_review_agent.md`
- `test_writer_agent.md`
- `coverage_gaps_agent.md`
- `launchers.md`
- `handoff_packet.md`
- `launcher_examples.md`

Use these prompts together with:

- `AgentContext/AGENTS.md`
- `AgentContext/multi_agent_system.md`
- repository MCP servers configured in `~/.codex/config.toml`

Recommended startup pattern:

1. coordinator selects a pipeline
2. writer and test writer handle implementation and tests
3. conformance, review, and gap agents validate the result

Fastest way to start:

1. copy the right template from `launchers.md`
2. run `Coordinator`
3. pass the result forward using `handoff_packet.md`

If you want concrete examples first, start with `launcher_examples.md`.
