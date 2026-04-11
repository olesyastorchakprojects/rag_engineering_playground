# Routing Policy

Consult `Eval Experiments MCP` first when you need to:

- look at recent eval runs
- summarize one run as an experiment unit
- compare two runs
- build a request-level coverage matrix for one run
- find regression candidates between two runs
- check artifact health for one run
- understand which runs included a particular `request_id`
- compare one request across two runs

Do not start with `Eval Experiments MCP` when you need to:

- read raw table rows or inspect PostgreSQL schema
  - start with `Postgres MCP`
- find the formal spec, manifest contract, or report contract
  - start with `Spec MCP`
- understand the broader eval pipeline flow
  - start with `Project Context MCP`

Useful distinction:

- `Postgres MCP` answers what is in the tables
- `Eval Experiments MCP` answers how those rows fit into runs, experiments, and comparisons
