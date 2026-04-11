# Dense Ingest Env Contract

This document defines the contract for `ENV_FILE_PATH` used by `dense_ingest.py`.

## Format

`ENV_FILE_PATH` is a dotenv-like text file with `KEY=value` format.
`ENV_FILE_PATH` is the source of truth for runtime endpoints and secret-like connection settings.

Expected fields:
- `QDRANT_URL`: base URL of Qdrant HTTP API
- `OLLAMA_URL`: base URL of the Ollama HTTP API

Rules:
- empty lines are allowed
- comment lines are allowed
- a line without `=` is an env file format error

Invalid `ENV_FILE_PATH`:
- `ENV_FILE_PATH` is invalid if the file cannot be read, if a line violates `KEY=value` format, or if a required key is missing
- this is a whole-run error
- ingest must exit immediately
- such errors do not belong in failed chunk log
