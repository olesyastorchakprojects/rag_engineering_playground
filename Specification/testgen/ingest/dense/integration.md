# Dense Ingest Integration Tests

## 1. General Rules
Each test in this document must generate one standalone Python runner in the style of the other test runners in the repository.

General requirements:
- one executable Python file per test
- no external Python libraries
- use only stdlib modules, for example `json`, `tempfile`, `pathlib`, `sys`, `argparse`, `subprocess`, `threading`, `http.server`, `socketserver`, `time`
- do not use `pytest`
- do not use `unittest`
- avoid duplicating setup logic
- helper functions are allowed
- tests in this document must not require containers
- tests in this document may start local stub/fake HTTP services inside the test runner itself
- temporary files and temporary directories must be automatically deleted after the test run completes

## 2. Common CLI Format
All paths must come from CLI arguments.

There must be no default paths.

If a test uses an optional `VERBOSE` flag:
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
If a test uses `VERBOSE`:
- when `VERBOSE = False`, do not print extra lines for `OK [case_name]`
- when `VERBOSE = False`, for a failed case print only the short diagnostic information explicitly required by the specific test section
- when `VERBOSE = True`, for a failed case you may additionally print:
  - `case_setup=<short description>`
  - `case_mutation=<short description>`
  - `expected_error_substring=<value>`, if set

## 5. Common Rules for Stub Services
If a test starts a local stub service:
- the stub service must be started inside the test runner
- the stub service must listen only on a local address
- the stub service must use a random free port
- every such test must accept `ENV_FILE_PATH` as a CLI parameter
- the test runner must create a temporary copy of `ENV_FILE_PATH`
- in that temporary copy, the URL of the corresponding external service must be replaced with the URL of the local stub service
- that temporary copy of `ENV_FILE_PATH` must be the one passed to the ingest script under test
- the test runner must explicitly wait for stub-service readiness before launching the tested scenario
- the stub service must automatically stop after the test run completes

If the test needs to validate HTTP interactions:
- the test runner must explicitly record:
  - which requests arrived
  - in which order they arrived, if order matters
  - which request bodies arrived, if request bodies are part of the test subject

## 6. Common Section: Stub Embedding Service
This section is mandatory for any test in this document that starts a stub embedding service.

The stub embedding service must implement exactly one ingest-script endpoint:
- `POST /api/embed`

For endpoint `POST /api/embed`, the stub embedding service must support both response modes:
- HTTP `500`
- HTTP `200` with the success payload described below

For every received request, the stub embedding service must:
- record the HTTP method
- record the request path
- record the raw request body
- parse the request body as a JSON object
- store the parsed JSON body in observed requests

For endpoint `POST /api/embed`, the stub embedding service must expect a request body with this shape:
- JSON object
- field `model`
- field `input`
- `model` must be a string
- `input` must be a JSON array

For endpoint `POST /api/embed`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `embeddings`
- `embeddings` must be a JSON array
- the number of elements in `embeddings` must equal the number of elements in request-body field `input`
- each element in `embeddings` must be a JSON array of length `CONFIG_PATH.embedding.model.dimension`
- every element in every embedding must be a JSON number

Unless a specific test defines different values, the success payload for each embedding must consist only of `0.0`.

Therefore:
- if request-body `input` contains `N` strings, the success response must contain `N` embeddings
- if `N = 1`, the success response must contain exactly one embedding
- if `N = 2`, the success response must contain exactly two embeddings

For endpoint `POST /api/embed`, the failure response must have exactly this structure:
- HTTP status `500`
- header `Content-Type: application/json`
- JSON object
- field `error` with a string value

Inside the test runner, stub-embedding behavior must be configured explicitly and deterministically:
- either fixed behavior for all requests to `POST /api/embed`
- or rule-based behavior driven by observed request attributes explicitly named in the test
- rule selection must not depend on randomness

If the test cares about the number of requests or the order of requests:
- observed requests to `POST /api/embed` must be stored in arrival order
- every observed request must expose the parsed JSON body

## 7. Common Section: Stub Qdrant Service
This section is mandatory for any test in this document that starts a stub Qdrant service.

The stub Qdrant service must implement these Qdrant endpoints:
- `GET /collections/{collection_name}`
- `PUT /collections/{collection_name}`
- `GET /collections/{collection_name}/points/{point_id}`
- `PUT /collections/{collection_name}/points`
- `PUT /collections/{collection_name}/points/payload`

For each endpoint above, the stub Qdrant service must support both response modes:
- HTTP `500`
- HTTP `200` with the success payload described below

For endpoints where the ingest contract uses `404` as the normal “entity missing” result, the stub Qdrant service must additionally support:
- HTTP `404` for `GET /collections/{collection_name}`
- HTTP `404` for `GET /collections/{collection_name}/points/{point_id}`

For every received request, the stub Qdrant service must:
- record the HTTP method
- record the request path
- record the raw request body
- if the body is non-empty, parse it as a JSON object
- store the parsed JSON body in observed requests for the corresponding endpoint

For endpoint `GET /collections/{collection_name}`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `ok`
- field `result`
- `result` must be a JSON object
- `result` must contain field `config`
- `result.config` must be a JSON object
- `result.config` must contain field `params`
- `result.config.params` must be a JSON object
- `result.config.params` must contain field `vectors`
- `result.config.params.vectors` must be a JSON object
- `result.config.params.vectors.size` must be an integer equal to `CONFIG_PATH.embedding.model.dimension`
- `result.config.params.vectors.distance` must be a string equal to `CONFIG_PATH.qdrant.collection.distance`
- `result.config` must contain field `metadata`
- `result.config.metadata` must be a JSON object
- `result.config.metadata.embedding_model_name` must be a string equal to `CONFIG_PATH.embedding.model.name`
- `result` must contain field `payload_schema`
- `result.payload_schema` must be a JSON object

For endpoint `PUT /collections/{collection_name}`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `ok`
- field `result`
- `result` must be a JSON object
- `result.status` must be `acknowledged`
- `result.operation_id` must be an integer

For endpoint `GET /collections/{collection_name}/points/{point_id}`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `ok`
- field `result`
- `result` must be a JSON object
- `result` must contain field `id`
- `result` must contain field `payload`
- `result.payload` must be a JSON object

For endpoint `PUT /collections/{collection_name}/points`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `ok`
- field `result`
- `result` must be a JSON object
- `result.status` must be `acknowledged`
- `result.operation_id` must be an integer

For endpoint `PUT /collections/{collection_name}/points/payload`, the success response must have exactly this structure:
- HTTP status `200`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `ok`
- field `result`
- `result` must be a JSON object
- `result.status` must be `acknowledged`
- `result.operation_id` must be an integer

For endpoint `PUT /collections/{collection_name}`, the stub Qdrant service must expect a request body with this shape:
- JSON object
- field `vectors`
- `vectors` must be a JSON object
- `vectors.size` must be an integer
- `vectors.distance` must be a string
- field `metadata`
- `metadata` must be a JSON object
- `metadata.embedding_model_name` must be a string

For endpoint `PUT /collections/{collection_name}/points`, the stub Qdrant service must expect a request body with this shape:
- JSON object
- field `points`
- `points` must be a JSON array
- every element in `points` must be a JSON object
- every point must contain fields `id`, `vector`, and `payload`

For endpoint `PUT /collections/{collection_name}/points/payload`, the stub Qdrant service must expect a request body with this shape:
- JSON object
- field `payload`
- `payload` must be a JSON object
- field `points`
- `points` must be a JSON array
- `points` must contain exactly one `point_id`

For every endpoint, the failure response must have exactly this structure:
- HTTP status `500`
- header `Content-Type: application/json`
- JSON object
- field `status` with value `error`
- field `error` with a string value

Inside the test runner, stub-Qdrant behavior must be configured explicitly and deterministically for each endpoint:
- either fixed behavior for all requests to that endpoint
- or rule-based behavior driven by observed request attributes explicitly named in the test
- rule selection must not depend on randomness

If the test cares about counts, bodies, or request order:
- observed requests must be stored separately by endpoint
- within each endpoint, observed requests must be stored in arrival order
- for each observed request, parsed JSON body must be available if the request has a body

## 8. Common Rules for Black-Box Script Execution
If a test validates the ingest script as a black-box CLI:
- the script must be launched as a subprocess
- the subprocess must be launched as `sys.executable <SCRIPT_PATH> ...`
- the test runner must pass all required CLI arguments of the ingest script into the subprocess
- the test must not import internal functions from the ingest script under test
- the test must validate ingest-script behavior through:
  - `exit code`
  - stdout
  - stderr
  - side effects on temporary files
  - observed requests in stub services

## 9. Common Rules for Case Structure
Each test runner must use named cases.

Each case must define only the fields actually needed by the test subject.

If the test subject needs both positive and negative scenarios:
- case categories must be named explicitly
- do not use abstract category names if they can be named operationally

If a case is built from canonical valid input:
- the negative case must be derived from canonical input through one targeted mutation or through a small set of related mutations

## 10. Common Rules for Retry/Fallback Expectations
If a test section uses `max_attempts`:
- the section must define the interpretation of `max_attempts` explicitly for that test
- the interpretation of `max_attempts` must not be left implicit

If a test section validates sequence-based behavior:
- the section must explicitly separate:
  - fixed scenario constants
  - derived expectations
  - observed values
- derived expectations must be computed from config values and scenario constants
- if an expected sequence is derived from config values, it must not be hardcoded separately from those config values

If a test section uses derived expectations:
- derived expectations must have explicit names
- allowed example names:
  - `initial_batch_item_count`
  - `failed_batch_chunk_count`
  - `failed_batch_point_count`
  - `expected_input_lengths_sequence`
  - `expected_points_lengths_sequence`
  - `expected_request_count`

If a test section validates a retry cycle and a fallback phase at the same time:
- the section must explicitly separate requests that belong to the retry cycle from requests that belong to the fallback phase
- the section must explicitly describe which requests are added by the fallback phase

If a test validates only a prefix sequence control flow:
- the test runner must stop the subprocess immediately after the expected observed condition is reached
- requests after that stop must not be part of the validation subject
- the test runner must not wait for natural subprocess completion if the test subject is already fully observed

## 11. Test: `embedding_retry.py`
You are writing one Python script named `embedding_retry.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `SCRIPT_PATH`, `CHUNK_SCHEMA_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

### Goal
The test must validate retry behavior for requests to the embedding service without starting containers.

The test must validate black-box ingest-script behavior under temporary and final embedding-service failures.

### Source Of Truth
Source of truth for retry semantics:
- `CONFIG_PATH.embedding.retry.max_attempts`
- `CONFIG_PATH.embedding.retry.backoff`

Interpretation of request count in this test:
- `CONFIG_PATH.embedding.retry.max_attempts` defines the number of requests inside one embedding attempt cycle
- if the initial batch request fails after all requests in that retry cycle, ingest must switch to per-chunk fallback for each item in the initial batch
- each item from the initial batch must produce exactly one additional request in per-chunk fallback, if the test forcibly stops the subprocess immediately after the expected request count is reached
- therefore the expected request count in this test must be:
  - `CONFIG_PATH.embedding.retry.max_attempts + initial_batch_item_count`
- in this test, `initial_batch_item_count = 1`, because the initial batch contains exactly one chunk

Source of truth for chunk structure:
- `CHUNK_SCHEMA_PATH`

### What the test must do
- launch the ingest script as a black-box CLI subprocess against local stub services
- use the stub embedding service from section `6`
- use the stub Qdrant service from section `7`
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- validate retry behavior for embedding-service requests only by counting HTTP requests received by the stub embedding service
- in this test, retry must be triggered only by HTTP `500` responses from the stub embedding service
- this test must not use timeouts, connection drops, connection resets, or other transport-level failure modes

### Cases
- the stub embedding service always returns HTTP `500`
- the ingest script must retry requests to the embedding service until the retry limit is reached

### Case Structure
Each case must define:
- `name`
- stub embedding-service config from section `6`: fixed `HTTP 500` behavior for endpoint `POST /api/embed`
- stub Qdrant-service config from section `7`: `GET /collections/{collection_name}` -> `404`, `PUT /collections/{collection_name}` -> `200`
- expected request count

### Case Execution
For each case:
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- create a temporary copy of `ENV_FILE_PATH`
- replace `QDRANT_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub Qdrant service
- replace `OLLAMA_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub embedding service
- create a stub Qdrant service instance according to section `7` and configure it for this case:
  - `GET /collections/{collection_name}` -> `404`
  - `PUT /collections/{collection_name}` -> `200`
- create a stub embedding service instance according to section `6` and configure it for this case:
  - `POST /api/embed` -> fixed `500`
- start both configured stub services
- launch the subprocess as `sys.executable <SCRIPT_PATH> --chunks <generated_chunks_path> --config <CONFIG_PATH> --env-file <mutated_env_path>`
- wait until the stub embedding service receives `expected request count` requests
- after that, forcibly stop the subprocess
- collect observed requests from the stub embedding service

### Stub-Service Usage
- success/failure payloads must be generated by the stub-service implementations from sections `6` and `7`
- the test must not redefine success payload shapes manually
- no extra requests to the stub Qdrant service are expected in this test

### Checks
- observed request count must equal expected request count
- expected request count must equal `CONFIG_PATH.embedding.retry.max_attempts + initial_batch_item_count`
- in this test, `initial_batch_item_count` must be computed from the number of items in the initial batch request to the embedding service
- request order does not need to be checked
- subprocess exit code does not need to be checked

### Runner Output
On failure print:
- `error=<message>`
- `observed_request_count=<value>`
- `expected_request_count=<value>`

## 12. Test: `qdrant_retry.py`
You are writing one Python script named `qdrant_retry.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `SCRIPT_PATH`, `CHUNK_SCHEMA_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

### Goal
The test must validate retry behavior for `GET /collections/{name}` requests to Qdrant without starting containers.

The test must validate black-box ingest-script behavior under repeated failed `GET /collections/{name}` requests to Qdrant.

### Source Of Truth
Source of truth for retry semantics:
- `CONFIG_PATH.qdrant.retry.max_attempts`
- `CONFIG_PATH.qdrant.retry.backoff`

Interpretation of `CONFIG_PATH.qdrant.retry.max_attempts` in this test:
- `max_attempts` = total number of `GET /collections/{name}` requests inside the retry cycle
- in this test, no additional fallback path for `GET /collections/{name}` should add extra requests

### What the test must do
- launch the ingest script as a black-box CLI subprocess against local stub services
- use the stub Qdrant service from section `7`
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- validate retry behavior for `GET /collections/{name}` requests to Qdrant only by counting HTTP requests received by the stub Qdrant service
- in this test, retry must be triggered only by HTTP `500` responses from the stub Qdrant service on `GET /collections/{name}`
- this test must not use timeouts, connection drops, connection resets, or other transport-level failure modes

### Cases
- the stub Qdrant service from section `7` always returns HTTP `500` on endpoint `GET /collections/{collection_name}`
- the ingest script must retry `GET /collections/{name}` requests to Qdrant until the retry limit is reached

### Case Execution
For each case:
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- create a temporary copy of `ENV_FILE_PATH`
- replace `QDRANT_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub Qdrant service
- create a stub Qdrant service instance according to section `7` and configure it for this case:
  - `GET /collections/{collection_name}` -> fixed `500`
- start the configured stub Qdrant service
- launch the subprocess as `sys.executable <SCRIPT_PATH> --chunks <generated_chunks_path> --config <CONFIG_PATH> --env-file <mutated_env_path>`
- wait until the stub Qdrant service receives `expected request count` requests to `GET /collections/{name}`
- if the subprocess exits before reaching `expected request count`, the case must fail
- if `expected request count` is not reached within `TIMEOUT_SEC = 10`, the case must fail
- after that, forcibly stop the subprocess
- collect observed requests from the stub Qdrant service

### Stub-Service Usage
- the failure payload for `GET /collections/{collection_name}` must be generated by the stub Qdrant service implementation from section `7`
- no other requests to the stub Qdrant service are expected in this test

### Checks
- observed request count must equal expected request count
- expected request count must equal `CONFIG_PATH.qdrant.retry.max_attempts`
- request order does not need to be checked
- subprocess exit code does not need to be checked

### Runner Output
On failure print:
- `error=<message>`
- `observed_request_count=<value>`
- `expected_request_count=<value>`

## 13. Test: `embedding_batch_fallback.py`
You are writing one Python script named `embedding_batch_fallback.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `SCRIPT_PATH`, `CHUNK_SCHEMA_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

### Goal
The test must validate fallback behavior after a failed batch request to the embedding service without starting containers.

The test must validate black-box ingest-script behavior when switching from batch processing to per-chunk processing.

### Source Of Truth
Source of truth for embedding batch size:
- `CONFIG_PATH.embedding.transport.max_batch_size`
- `CONFIG_PATH.embedding.retry.max_attempts`

Interpretation of request sequence in this test:
- `CONFIG_PATH.embedding.retry.max_attempts` defines the number of requests inside one embedding attempt cycle
- the initial batch request must be retried exactly `CONFIG_PATH.embedding.retry.max_attempts` times before fallback
- after the initial batch retry budget is exhausted, ingest must switch to per-chunk fallback inside the same batch
- each chunk from the failed batch must produce its own single-item request sequence
- if a single-item request succeeds on the first attempt, its sequence consists of one element `1`
- the expected input-lengths sequence in this test must be computed as:
  - first, `initial_batch_item_count` repeated `CONFIG_PATH.embedding.retry.max_attempts` times
  - then one element `1` for each chunk in the failed batch
- in this test:
  - `initial_batch_item_count = 2`
  - `failed_batch_chunk_count = 2`
  - therefore the expected input-lengths sequence must be:
    - `2`, repeated `CONFIG_PATH.embedding.retry.max_attempts` times
    - then `1`, `1`

Source of truth for chunk structure:
- `CHUNK_SCHEMA_PATH`

### What the test must do
- launch the ingest script as a black-box CLI subprocess against local stub services
- use the stub embedding service from section `6`
- use the stub Qdrant service from section `7`
- generate a temporary `CHUNKS_PATH` with exactly two chunks valid according to `CHUNK_SCHEMA_PATH`
- create a temporary copy of `CONFIG_PATH` and set `CONFIG_PATH.embedding.transport.max_batch_size = 2`
- validate fallback behavior only by the sequence of HTTP requests received by the stub embedding service
- in this test, the failed batch must be triggered only through HTTP `500` returned by the stub embedding service
- after a failed batch request and exhausted batch retry, the script must switch to per-chunk requests inside the same batch

### Scenario
- the batch request with two strings receives HTTP `500`
- after that, the ingest script must switch to two separate single-item requests
- the expected input-lengths sequence must be computed from the formula in `Source Of Truth`, not hardcoded independently of `CONFIG_PATH.embedding.retry.max_attempts`

### Execution
- generate a temporary `CHUNKS_PATH` with exactly two chunks valid according to `CHUNK_SCHEMA_PATH`
- create a temporary copy of `CONFIG_PATH`
- set `CONFIG_PATH.embedding.transport.max_batch_size = 2` in the temporary copy
- create a temporary copy of `ENV_FILE_PATH`
- replace `QDRANT_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub Qdrant service
- replace `OLLAMA_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub embedding service
- create a stub Qdrant service instance according to section `7` and configure it for this test:
  - `GET /collections/{collection_name}` -> `404`
  - `PUT /collections/{collection_name}` -> `200`
- create a stub embedding service instance according to section `6` and configure it for this test:
  - if `POST /api/embed` receives a request body where `input` has length `2`, return `500`
  - if `POST /api/embed` receives a request body where `input` has length `1`, return `200`
- start both configured stub services
- launch the subprocess as `sys.executable <SCRIPT_PATH> --chunks <generated_chunks_path> --config <mutated_config_path> --env-file <mutated_env_path>`
- compute the expected input-lengths sequence from the formula in `Source Of Truth`
- wait until the stub embedding service receives the expected input-lengths sequence
- validate the expected input-lengths sequence in arrival order
- if the subprocess exits before the sequence is observed, the test must fail
- if the sequence is not observed within `TIMEOUT_SEC = 10`, the test must fail
- after that, forcibly stop the subprocess
- collect observed requests from the stub embedding service

### Stub-Service Usage
- the success payload for `POST /api/embed` with `input` length `1` must be generated by the stub embedding service implementation from section `6`
- the success payload must contain exactly one embedding made of `0.0`
- success/failure payloads for Qdrant must be generated by the stub Qdrant service implementation from section `7`
- after `GET /collections/{collection_name}` and `PUT /collections/{collection_name}`, no additional requests to the stub Qdrant service are expected in this test

### Checks
- observed request count must equal the length of the expected input-lengths sequence
- observed input-lengths sequence must equal the expected input-lengths sequence
- request order must be checked
- subprocess exit code does not need to be checked

### Runner Output
On failure print:
- `error=<message>`
- `observed_request_count=<value>`
- `observed_input_lengths=<value>`

## 14. Test: `upsert_batch_fallback.py`
You are writing one Python script named `upsert_batch_fallback.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

In the rest of this section, references to `SCRIPT_PATH`, `CHUNK_SCHEMA_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, and `VERBOSE` refer exactly to these CLI arguments.

### Goal
The test must validate fallback behavior after a failed batch upsert request to Qdrant without starting containers.

The test must validate black-box ingest-script behavior when switching from batch upsert processing to per-point processing.

### Source Of Truth
Source of truth for upsert batch size:
- `CONFIG_PATH.qdrant.transport.upsert_batch_size`
- `CONFIG_PATH.qdrant.retry.max_attempts`

Interpretation of request sequence in this test:
- `CONFIG_PATH.qdrant.retry.max_attempts` defines the number of requests inside one upsert attempt cycle
- the initial batch upsert request must be retried exactly `CONFIG_PATH.qdrant.retry.max_attempts` times before fallback
- after the initial batch retry budget is exhausted, ingest must switch to per-point fallback inside the same batch
- each point from the failed batch must produce its own single-point upsert request sequence
- if a single-point upsert succeeds on the first attempt, its sequence consists of one element `1`
- the expected points-lengths sequence in this test must be computed as:
  - first, `initial_batch_item_count` repeated `CONFIG_PATH.qdrant.retry.max_attempts` times
  - then one element `1` for each point from the failed batch
- in this test:
  - `initial_batch_item_count = 2`
  - `failed_batch_point_count = 2`
  - therefore the expected points-lengths sequence must be:
    - `2`, repeated `CONFIG_PATH.qdrant.retry.max_attempts` times
    - then `1`, `1`

Source of truth for embedding batch size:
- `CONFIG_PATH.embedding.transport.max_batch_size`

Source of truth for chunk structure:
- `CHUNK_SCHEMA_PATH`

### What the test must do
- launch the ingest script as a black-box CLI subprocess against local stub services
- use the stub embedding service from section `6`
- use the stub Qdrant service from section `7`

### Scenario
- the batch upsert request with two points receives HTTP `500`
- after that, the ingest script must switch to two separate single-point upsert requests
- after the failed batch upsert request and exhausted batch retry, the script must switch to per-point upsert requests inside the same batch
- the expected points-lengths sequence must be computed from the formula in `Source Of Truth`, not hardcoded independently of `CONFIG_PATH.qdrant.retry.max_attempts`

### Execution
- generate a temporary `CHUNKS_PATH` with exactly two chunks valid according to `CHUNK_SCHEMA_PATH`
- create a temporary copy of `CONFIG_PATH`
- set `CONFIG_PATH.embedding.transport.max_batch_size = 2` in the temporary copy
- set `CONFIG_PATH.qdrant.transport.upsert_batch_size = 2` in the temporary copy
- create a temporary copy of `ENV_FILE_PATH`
- replace `QDRANT_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub Qdrant service
- replace `OLLAMA_URL` in the temporary copy of `ENV_FILE_PATH` with the URL of the local stub embedding service
- create a stub embedding service instance according to section `6` and configure it for this test:
  - `POST /api/embed` -> `200`
- create a stub Qdrant service instance according to section `7` and configure it for this test:
  - `GET /collections/{collection_name}` -> `404`
  - `PUT /collections/{collection_name}` -> `200`
  - if `PUT /collections/{collection_name}/points` receives a request body where `points` has length `2`, return `500`
  - if `PUT /collections/{collection_name}/points` receives a request body where `points` has length `1`, return `200`
- start both configured stub services
- launch the subprocess as `sys.executable <SCRIPT_PATH> --chunks <generated_chunks_path> --config <mutated_config_path> --env-file <mutated_env_path>`
- compute the expected points-lengths sequence from the formula in `Source Of Truth`
- wait until the stub Qdrant service receives the expected points-lengths sequence
- validate the expected points-lengths sequence in arrival order of `PUT /collections/{name}/points` requests by the length of field `points` in the JSON request body
- if the subprocess exits before the sequence is observed, the test must fail
- if the sequence is not observed within `TIMEOUT_SEC = 10`, the test must fail
- after that, forcibly stop the subprocess
- collect observed upsert requests from the stub Qdrant service

### Stub-Service Usage
- the success payload for `POST /api/embed` must be generated by the stub embedding service implementation from section `6`
- the success payload for `POST /api/embed` must contain exactly two embeddings made of `0.0`
- the success payload for `PUT /collections/{collection_name}/points` must be generated by the stub Qdrant service implementation from section `7`
- success/failure payloads for the remaining Qdrant endpoints must be generated by the stub Qdrant service implementation from section `7`

### Checks
- observed upsert request count must equal the length of the expected points-lengths sequence
- observed points-lengths sequence must equal the expected points-lengths sequence
- request order must be checked
- subprocess exit code does not need to be checked

### Runner Output
On failure print:
- `error=<message>`
- `observed_request_count=<value>`
- `observed_points_lengths=<value>`
