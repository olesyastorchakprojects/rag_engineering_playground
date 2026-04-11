# Dense Ingest Tests Without Containers

## 1. General Rules
Each test in this document must generate one standalone Python runner in the style of the other test runners in the repository.

General requirements:
- one executable Python file per test
- no external Python libraries
- use `tomllib`, and if it is unavailable, `tomli` is allowed
- use only stdlib modules, for example `json`, `copy`, `tempfile`, `pathlib`, `sys`, `argparse`, `importlib`
- must not require containers
- must not modify project files
- create temporary files only inside a temporary directory
- temporary files and temporary directories must be automatically deleted after the test run completes
- do not use `pytest`
- do not use `unittest`
- output must be easy for a human to read
- test code must be readable and compact
- avoid duplicating mutation logic
- helper functions are allowed

## 2. Common CLI Format
All paths must come from CLI arguments.

There must be no default paths.

If the test uses an optional `VERBOSE` flag:
- `VERBOSE` = argument `--verbose`
- if `VERBOSE` is not provided, its default value is `False`

## 3. Common Output Format
For each case:
- print `OK [case_name]` or `FAIL [case_name]`

On failure:
- print the short diagnostic information explicitly required by the specific test section

At the end:
- print `cases=<N> failed=<K> passed=<M>`

If there is at least one failed case:
- exit code must be `1`

If all cases passed:
- exit code must be `0`

## 4. Common Verbose Format
If the test uses `VERBOSE`:
- when `VERBOSE = False`, do not print extra lines for `OK [case_name]`
- when `VERBOSE = False`, for a failed case print only the short diagnostic information explicitly required by the specific test section
- when `VERBOSE = True`, for a failed case you may additionally print:
  - `case_mutation=<short description>`
  - `expected_error_substring=<value>`, if set

## 5. Test: `config_validation.py`
You are writing one Python script named `config_validation.py`.

CLI
---
Arguments:
- `CONFIG_TEMPLATE_PATH` / `--config-template` (`Path`, required): canonical valid dense ingest TOML config
- `CONFIG_SCHEMA_PATH` / `--config-schema` (`Path`, required): JSON schema for parsed config validation
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `CONFIG_TEMPLATE_PATH`, `CONFIG_SCHEMA_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

Goal
----
The test must validate dense ingest config handling without starting containers.

The test must cover two layers:
- TOML parse
- schema validation

The test must run locally and finish with a project-style `OK/WARN/FAIL` summary.

Source Of Truth
---------------
Source of truth for config structure:
- `CONFIG_SCHEMA_PATH`

Canonical valid config:
- `CONFIG_TEMPLATE_PATH`

What the test must do
---------------------
- read the canonical valid config from `CONFIG_TEMPLATE_PATH`
- load the schema from `CONFIG_SCHEMA_PATH`
- implement schema validation inside the test
- build named test cases from the canonical valid config by applying controlled mutations on top of it
- verify which cases should pass and which should fail validation

Positive Cases
--------------
- the canonical config from `CONFIG_TEMPLATE_PATH` must be represented as a separate named positive case
- TOML from `CONFIG_TEMPLATE_PATH` parses successfully
- parsed config from `CONFIG_TEMPLATE_PATH` passes schema validation without errors

Negative Parse Cases
--------------------
- invalid TOML syntax

Negative Schema Cases
---------------------
- missing required top-level section
- missing required field inside a required section
- invalid scalar type
- empty string where the contract requires a non-empty string
- integer field `<= 0` where the contract requires a positive integer
- unsupported enum-like value:
  - `embedding.retry.backoff`
  - `qdrant.retry.backoff`
  - `qdrant.collection.vector_name`
  - `qdrant.point_id.strategy`
  - `qdrant.point_id.format`
  - `idempotency.strategy`
  - `idempotency.on_fingerprint_change`
  - `idempotency.on_metadata_change`
- empty `idempotency.fingerprint_fields`
- extra field inside a section, if the schema forbids it
- missing `qdrant.point_id.namespace_uuid`
- invalid UUID format in `qdrant.point_id.namespace_uuid`

Case Structure
--------------
Each case must define:
- `name`
- `kind`:
  - `positive`
  - `negative_parse`
  - `negative_schema`
- a mutation applied to the canonical config
- optional expected error substring

Each `negative_parse` and `negative_schema` case must be built from the canonical config through one targeted mutation or through a small set of related mutations.

For key negative cases, an expected error substring should be defined explicitly if that helps distinguish the correct failure reason from an accidental one.

Case Execution
--------------
For each case:
- create a separate mutated TOML config in a temporary directory
- perform parse
- perform schema validation

For a `positive` case:
- TOML parse must succeed
- schema validation must succeed

For a `negative_parse` case:
- TOML parse must fail
- schema validation is not executed after that

For a `negative_schema` case:
- TOML parse must succeed
- schema validation must fail

Runner Output
-------------
On failure print:
- `case_kind=<value>`
- `layer=<value>`
- `error=<message>`

Allowed `layer` values:
- `parse`
- `schema`
- `none`

## 6. Test: `env_validation.py`
You are writing one Python script named `env_validation.py`.

CLI
---
Arguments:
- `ENV_TEMPLATE_PATH` / `--env-template` (`Path`, required): canonical valid dense ingest env file
- `ENV_SCHEMA_PATH` / `--env-schema` (`Path`, required): JSON schema for parsed env validation
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `ENV_TEMPLATE_PATH`, `ENV_SCHEMA_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

Goal
----
The test must validate dense ingest env handling without starting containers.

The test must cover two layers:
- env parse
- schema validation

The test must run locally and finish with a project-style `OK/WARN/FAIL` summary.

Source Of Truth
---------------
Source of truth for parsed env structure:
- `ENV_SCHEMA_PATH`

Canonical valid env:
- `ENV_TEMPLATE_PATH`

What the test must do
---------------------
- read the canonical valid env file from `ENV_TEMPLATE_PATH`
- load the schema from `ENV_SCHEMA_PATH`
- implement env parsing inside the test
- implement schema validation inside the test
- build named test cases from the canonical valid env by applying controlled mutations on top of it
- verify which cases should pass and which should fail validation

Positive Cases
--------------
- the canonical env from `ENV_TEMPLATE_PATH` must be represented as a separate named positive case
- the env file from `ENV_TEMPLATE_PATH` parses successfully
- parsed env from `ENV_TEMPLATE_PATH` passes schema validation without errors

Negative Parse Cases
--------------------
- a line without `=`
- an empty key to the left of `=`

Negative Schema Cases
---------------------
- missing required key `QDRANT_URL`
- missing required key `OLLAMA_URL`
- empty value for `QDRANT_URL`
- empty value for `OLLAMA_URL`
- extra comment lines and empty lines must not make the env invalid on their own

Case Structure
--------------
Each case must define:
- `name`
- `kind`:
  - `positive`
  - `negative_parse`
  - `negative_schema`
- a mutation applied to the canonical env
- optional expected error substring

Each `negative_parse` and `negative_schema` case must be built from the canonical env through one targeted mutation or through a small set of related mutations.

For key negative cases, an expected error substring should be defined explicitly if that helps distinguish the correct failure reason from an accidental one.

Case Execution
--------------
For each case:
- create a separate mutated env file in a temporary directory
- perform env parse
- perform schema validation

For a `positive` case:
- env parse must succeed
- schema validation must succeed

For a `negative_parse` case:
- env parse must fail
- schema validation is not executed after that

For a `negative_schema` case:
- env parse must succeed
- schema validation must fail

Runner Output
-------------
On failure print:
- `case_kind=<value>`
- `layer=<value>`
- `error=<message>`

Allowed `layer` values:
- `parse`
- `schema`
- `none`

## 7. Test: `chunks_input_validation.py`
You are writing one Python script named `chunks_input_validation.py`.

CLI
---
Arguments:
- `CHUNKS_TEMPLATE_PATH` / `--chunks-template` (`Path`, required): canonical valid dense ingest chunks JSONL file
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `INGEST_SCRIPT_PATH` / `--ingest-script` (`Path`, required): path to the dense ingest script
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `CHUNKS_TEMPLATE_PATH`, `CHUNK_SCHEMA_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, `INGEST_SCRIPT_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

Goal
----
The test must validate `CHUNKS_PATH` input without starting containers.

The test must cover four layers:
- JSONL parse
- object-level input validation
- schema validation
- validation through `INGEST_SCRIPT_PATH`

The test must run locally and finish with a project-style `OK/WARN/FAIL` summary.

Source Of Truth
---------------
Source of truth for chunk structure:
- `CHUNK_SCHEMA_PATH`

Reference implementation for additional chunk validation rules on top of schema:
- `INGEST_SCRIPT_PATH`

Canonical valid chunks input:
- `CHUNKS_TEMPLATE_PATH`

What the test must do
---------------------
- read the canonical valid chunks file from `CHUNKS_TEMPLATE_PATH`
- load the schema from `CHUNK_SCHEMA_PATH`
- implement JSONL parsing inside the test
- implement object-level input validation inside the test
- implement schema validation inside the test
- use `INGEST_SCRIPT_PATH` as a black-box reference implementation for additional chunk validation rules on top of schema
- build named test cases from the canonical valid chunks input by applying controlled mutations on top of it
- verify which cases should pass and which should fail validation

Object-level input validation in this test means:
- every non-empty line must parse as JSON
- every non-empty line after parse must be a JSON object

Positive Cases
--------------
- the canonical chunks input from `CHUNKS_TEMPLATE_PATH` must be represented as a separate named positive case
- JSONL from `CHUNKS_TEMPLATE_PATH` parses successfully
- every non-empty line in `CHUNKS_TEMPLATE_PATH` parses as a JSON object
- all chunk records in `CHUNKS_TEMPLATE_PATH` pass schema validation without errors
- all chunk records in `CHUNKS_TEMPLATE_PATH` satisfy `chunk.page_end >= chunk.page_start`
- validation through `INGEST_SCRIPT_PATH` accepts all chunk records in `CHUNKS_TEMPLATE_PATH` without errors

Negative Parse Cases
--------------------
- invalid JSON line
- a line contains a JSON value that is not an object

Negative Schema Cases
---------------------
- missing required field
- extra field is present, if the schema forbids it
- invalid scalar type
- invalid array item type
- empty string where the contract requires a non-empty string
- invalid `schema_version`
- invalid `chunk_id`
- invalid `doc_id`
- invalid `content_hash`
- invalid `chunk_created_at`
- invalid `ingest.ingested_at`, if the field is present
- `chunk.page_end < chunk.page_start`

Negative Runtime Validation Cases
---------------------------------
- `chunk.page_end < chunk.page_start`

Case Structure
--------------
Each case must define:
- `name`
- `kind`:
  - `positive`
  - `negative_parse`
  - `negative_schema`
  - `negative_runtime_validation`
- a mutation applied to the canonical chunks input
- optional expected error substring

Each `negative_parse`, `negative_schema`, and `negative_runtime_validation` case must be built from the canonical chunks input through one targeted mutation or through a small set of related mutations.

For key negative cases, an expected error substring should be defined explicitly if that helps distinguish the correct failure reason from an accidental one.

Case Execution
--------------
For each case:
- create a separate mutated JSONL file in a temporary directory
- perform JSONL parse
- perform object-level input validation
- perform schema validation
- perform validation through `INGEST_SCRIPT_PATH` by launching the ingest script as a subprocess

Subprocess execution through `INGEST_SCRIPT_PATH`:
- launch the subprocess as `sys.executable <INGEST_SCRIPT_PATH> ...`
- pass these arguments into the subprocess:
  - `--chunks <mutated_chunks_path>`
  - `--config <CONFIG_PATH>`
  - `--env-file <ENV_FILE_PATH>`
- the test must not import internal functions from `INGEST_SCRIPT_PATH`
- the test must validate `INGEST_SCRIPT_PATH` as a black-box CLI
- for subprocess runs in `positive` and `negative_runtime_validation` cases, use the original valid `CONFIG_PATH` and `ENV_FILE_PATH` without mutations

For a `positive` case:
- JSONL parse must succeed
- object-level input validation must succeed
- schema validation must succeed
- subprocess run through `INGEST_SCRIPT_PATH` must exit with `exit code = 0`

For a `negative_parse` case:
- JSONL parse or object-level input validation must fail
- schema validation is not executed after that
- subprocess run through `INGEST_SCRIPT_PATH` is not executed after that

For a `negative_schema` case:
- JSONL parse must succeed
- object-level input validation must succeed
- schema validation must fail
- subprocess run through `INGEST_SCRIPT_PATH` is not executed after that

For a `negative_runtime_validation` case:
- JSONL parse must succeed
- object-level input validation must succeed
- schema validation must succeed
- subprocess run through `INGEST_SCRIPT_PATH` must exit with `exit code = 1`

Runner Output
-------------
On failure print:
- `case_kind=<value>`
- `layer=<value>`
- `error=<message>`

Allowed `layer` values:
- `parse`
- `schema`
- `runtime_validation`
- `none`

## 8. Test: `point_id_determinism.py`
You are writing one Python script named `point_id_determinism.py`.

CLI
---
Arguments:
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `CONFIG_CONTRACT_PATH` / `--config-contract` (`Path`, required): config contract markdown file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `CONFIG_PATH`, `CONFIG_CONTRACT_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

Goal
----
The test must validate deterministic point-id behavior for dense ingest without starting containers.

The test must verify:
- the same `chunk_id` always produces the same `point_id`
- different `chunk_id` values produce different `point_id` values
- `point_id` matches the canonical UUID string format
- `point_id` is computed according to the contract semantics from `CONFIG_PATH.qdrant.point_id.*`

The test must run locally and finish with a project-style `OK/WARN/FAIL` summary.

Source Of Truth
---------------
Source of truth for config values:
- `CONFIG_PATH`

Source of truth for point-id semantics:
- `CONFIG_CONTRACT_PATH`

What the test must do
---------------------
- read config from `CONFIG_PATH`
- use `CONFIG_CONTRACT_PATH` as the source of truth for the semantics of `CONFIG_PATH.qdrant.point_id.strategy`, `CONFIG_PATH.qdrant.point_id.namespace_uuid`, and `CONFIG_PATH.qdrant.point_id.format`
- the test must not parse `CONFIG_CONTRACT_PATH` programmatically; it is used as the source of truth for meaning when implementing the test logic
- implement point-id computation inside the test according to the semantics of `CONFIG_PATH.qdrant.point_id.strategy`, `CONFIG_PATH.qdrant.point_id.namespace_uuid`, and `CONFIG_PATH.qdrant.point_id.format`
- build named test cases from controlled synthetic chunk inputs
- verify that point-id behavior is deterministic and matches contract expectations

Positive Cases
--------------
- the same `chunk_id` in two computations produces the same `point_id`
- different `chunk_id` values produce different `point_id`
- the result parses successfully as a UUID
- the string representation of the result matches the canonical lowercase UUID string

Case Structure
--------------
Each case must define:
- `name`
- synthetic chunk data needed for the case
- expected outcome:
  - `same_point_id`
  - `different_point_id`
  - `canonical_uuid_format`

Case Execution
--------------
For each case:
- generate the synthetic chunk data needed for the case
- compute `point_id`
- point-id computation must succeed
- the result must match the case expectation

Runner Output
-------------
On failure print:
- `error=<message>`

If a case compares multiple computations, additionally print:
- `point_id_1=<value>`
- `point_id_2=<value>`
