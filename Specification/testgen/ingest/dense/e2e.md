# Dense Ingest End-to-End Tests

## 1. General Rules
Each test in this document must generate one standalone Python runner in the style of the other test runners in the repository.

General requirements:
- one executable Python file per test
- no external Python libraries
- use only stdlib modules, for example `json`, `tempfile`, `pathlib`, `sys`, `argparse`, `subprocess`, `time`, `uuid`, `shutil`
- do not use `pytest`
- do not use `unittest`
- avoid duplicating setup logic
- helper functions are allowed
- tests in this document use real services in containers
- tests in this document must not start fake/stub HTTP services instead of real services
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

## 5. Common Rules for Real Services
If a test uses real Qdrant or a real embedding service:
- the test runner must assume the containers are already running externally
- the test runner must not itself start `docker`, `docker compose`, or containers
- the test runner must accept `ENV_FILE_PATH` as a CLI parameter
- the test runner must use runtime endpoints from `ENV_FILE_PATH`
- the test runner must check required service availability before starting the main scenario
- if a service is unavailable, the case must end with `FAIL`

If a test uses both real Qdrant and a real embedding service:
- the Qdrant container must be reachable for the test
- the embedding service container must be reachable for the test
- if either service is unavailable, the case must end with `FAIL`

If a test mutates the state of real Qdrant:
- the test runner must use a unique collection name for each case
- the test runner must create a temporary copy of `CONFIG_PATH` if the case needs a different collection name
- after the case completes, the test runner must delete the temporary collection through the real Qdrant API
- cleanup of the temporary collection must run even if the case fails
- cleanup must not be skipped just because the main case assertion already failed

If a test uses a real embedding service:
- the test runner must not replace `OLLAMA_URL` with a fake endpoint
- the test runner must use the real requests issued by the ingest script to the embedding service

## 6. Common Rules for Black-Box Script Execution
If a test validates the ingest script as a black-box CLI:
- the script must be launched as a subprocess
- the subprocess must be launched as `sys.executable <SCRIPT_PATH> ...`
- the test runner must pass all required CLI arguments of the ingest script into the subprocess
- the test must not import internal functions from the ingest script under test
- the test must validate ingest-script behavior through:
  - `exit code`
  - stdout
  - stderr
  - side effects on the Qdrant collection
  - side effects in output logs

For the E2E tests in this document:
- the subprocess does not need to be terminated forcibly unless the specific test section requires otherwise
- the test runner must wait for the natural completion of the subprocess
- if the subprocess exits with an error, the case must fail
- on such failure, the test runner must print diagnostic information about the failure reason

## 7. Common Rules for Case Structure
Each test runner must use named cases.

Each case must define only the fields actually needed by the test subject.

If a test section uses derived expectations:
- derived expectations must be computed from config values and scenario constants
- derived expectations must not be hardcoded separately from the config values they are derived from

## 8. Common Rules for E2E Fixtures
If a test needs a temporary `CHUNKS_PATH`:
- the test runner must generate chunks locally
- generated chunks must be valid according to `CHUNK_SCHEMA_PATH`
- if the test runner generates `CHUNKS_PATH`, every chunk in it must be valid according to `CHUNK_SCHEMA_PATH`

If a test needs an existing point in Qdrant:
- the test runner must prepare that point through the real Qdrant API before launching the ingest script
- the point id must be computed according to the semantics of `CONFIG_PATH.qdrant.point_id.*`
- if the test checks `update`, `skip`, or `skip_and_log`, the payload of the preloaded point must be defined explicitly

If a test needs an existing collection:
- the test runner must prepare the collection through the real Qdrant API before launching the ingest script
- the collection vector config and metadata must be defined explicitly

## 9. Test: `qdrant_collection_metadata_roundtrip.py`
You are writing one Python script named `qdrant_collection_metadata_roundtrip.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

### Goal
The test must verify that the ingest script creates a collection in Qdrant with parameters taken from `CONFIG_PATH`.

### What the test must do
- create a temporary copy of `CONFIG_PATH`
- assign a unique collection name for the case
- before launching the ingest script, verify that no collection with that name exists
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- launch the ingest script as a black-box subprocess with that `CHUNKS_PATH`
- wait for the subprocess to complete
- issue `GET /collections/{name}` through the real Qdrant API
- verify that the response contains:
  - `result.config.metadata.embedding_model_name`
  - `result.config.params.vectors.size`
  - `result.config.params.vectors.distance`

### Checks
- the subprocess must complete successfully
- `embedding_model_name` must equal `CONFIG_PATH.embedding.model.name`
- `vectors.size` must equal `CONFIG_PATH.embedding.model.dimension`
- `vectors.distance` must equal `CONFIG_PATH.qdrant.collection.distance`
- only these contract fields are in scope for this test
- if the subprocess exits with an error, the case must fail
- even if the subprocess exits with an error, the test runner must still try to read the collection and include that result in the failure diagnostics

### Runner Output
On failure print:
- `error=<message>`
- `collection_name=<value>`
- `stdout=<value>`
- `stderr=<value>`
- `actual_metadata=<value>`
- `actual_vector_size=<value>`
- `actual_vector_distance=<value>`
- `cleanup_error=<value>`, if cleanup of the temporary collection fails

## 10. Test: `qdrant_collection_compatibility_e2e.py`
You are writing one Python script named `qdrant_collection_compatibility_e2e.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

### Goal
The test must validate fail-fast behavior for an existing incompatible collection.

### Cases
- `collection_metadata_missing`
- `embedding_model_name_mismatch`
- `vector_dimension_mismatch`
- `vector_distance_mismatch`

### What the test must do
- for each case, create a temporary copy of `CONFIG_PATH` with a unique collection name
- before launching the ingest script, verify that no collection with that name exists
- for each case, prepare the existing collection through the real Qdrant API before launching the ingest script
- the generated existing collection must use the collection name from the temporary copy of `CONFIG_PATH`
- generate a temporary `CHUNKS_PATH` with one chunk valid according to `CHUNK_SCHEMA_PATH`
- launch the ingest script as a black-box subprocess
- wait for the subprocess to complete
- after subprocess completion, delete the temporary collection through the real Qdrant API
- cleanup of the temporary collection must run even if the case fails

### Case Setup
Case `collection_metadata_missing`:
- the collection create request must not contain `metadata`
- the existing collection vector dimension must match `CONFIG_PATH.embedding.model.dimension`
- the existing collection vector distance must match `CONFIG_PATH.qdrant.collection.distance`
- expected error substring = `collection metadata missing`

Case `embedding_model_name_mismatch`:
- the existing collection must be created with metadata key `embedding_model_name`
- `embedding_model_name` in the existing collection must differ from `CONFIG_PATH.embedding.model.name`
- use a fixed mismatch value different from `CONFIG_PATH.embedding.model.name`
- the existing collection vector dimension must match `CONFIG_PATH.embedding.model.dimension`
- the existing collection vector distance must match `CONFIG_PATH.qdrant.collection.distance`
- expected error substring = `collection embedding_model_name mismatch`

Case `vector_dimension_mismatch`:
- the existing collection must be created with metadata key `embedding_model_name` equal to `CONFIG_PATH.embedding.model.name`
- the existing collection vector dimension must differ from `CONFIG_PATH.embedding.model.dimension`
- use a fixed integer mismatch value different from `CONFIG_PATH.embedding.model.dimension`
- the existing collection vector distance must match `CONFIG_PATH.qdrant.collection.distance`
- expected error substring = `collection vector dimension mismatch`

Case `vector_distance_mismatch`:
- the existing collection must be created with metadata key `embedding_model_name` equal to `CONFIG_PATH.embedding.model.name`
- the existing collection vector dimension must match `CONFIG_PATH.embedding.model.dimension`
- the existing collection vector distance must differ from `CONFIG_PATH.qdrant.collection.distance`
- use a fixed enum value different from `CONFIG_PATH.qdrant.collection.distance`
- expected error substring = `collection vector distance mismatch`

### Checks
- the subprocess must exit with `exit code = 1`
- after subprocess completion, the collection must still contain zero points
- the test runner must verify this through `result.points_count` in the response of `GET /collections/{name}`
- expected `result.points_count = 0`
- stdout or stderr must contain the expected error substring for the case
- cleanup of the temporary collection must complete successfully

### Chunk Fixture
- `CHUNKS_PATH` must contain exactly one valid chunk
- this chunk exists only to launch the ingest script in this test’s fail-fast scenario

### Runner Output
On failure print:
- `error=<message>`
- `case_name=<value>`
- `collection_name=<value>`
- `stdout=<value>`
- `stderr=<value>`
- `expected_error_substring=<value>`
- `cleanup_error=<value>`, if cleanup of the temporary collection fails

## 11. Test: `full_ingest_e2e.py`
You are writing one Python script named `full_ingest_e2e.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

### Goal
The test must validate the full happy-path ingest flow through real Qdrant and a real embedding service.

### Source Of Truth
Source of truth for collection contract fields:
- `CONFIG_PATH.embedding.model.name`
- `CONFIG_PATH.embedding.model.dimension`
- `CONFIG_PATH.qdrant.collection.distance`
- `CONFIG_PATH.qdrant.collection.name`

Source of truth for chunk payload:
- `CHUNK_SCHEMA_PATH`
- the generated chunk JSON object written into temporary `CHUNKS_PATH`
- expected stored Qdrant payload:
  - the generated chunk JSON object
  - plus the `ingest` object added by `dense_ingest.py`

### What the test must do
- create a temporary copy of `CONFIG_PATH`
- assign a unique collection name for the case
- before launching the ingest script, verify that no collection with that name exists
- for this pre-check use endpoint `GET /collections/{name}`
- expect HTTP `404` for this pre-check
- generate a temporary `CHUNKS_PATH` with exactly one chunk valid according to `CHUNK_SCHEMA_PATH`
- launch the ingest script as a black-box subprocess with that `CHUNKS_PATH`
- wait for the subprocess to complete
- after subprocess completion, issue `GET /collections/{name}` through the real Qdrant API
- after subprocess completion, issue `GET /collections/{name}/points/{point_id}` through the real Qdrant API
- after all checks, delete the temporary collection through the real Qdrant API
- cleanup of the temporary collection must run even if the case fails

### Real Service Availability Checks
- before launching the ingest script, the test runner must verify Qdrant availability through `GET /collections`
- the Qdrant availability check must expect HTTP `200`
- before launching the ingest script, the test runner must verify embedding service availability through `POST /api/embed`
- the embedding availability request body must be:
  - `model = CONFIG_PATH.embedding.model.name`
  - `input = ["availability probe"]`
- the embedding availability check must expect HTTP `200`
- the embedding availability response must be a JSON object
- the embedding availability response must contain field `embeddings`, which must be a JSON array

### Config Fixture
- the test runner must use the existing working valid `CONFIG_PATH`
- the test runner must create a temporary copy of that valid config file
- in the temporary copy, the test runner must change only `CONFIG_PATH.qdrant.collection.name`
- all other config values must remain unchanged

### Chunk Fixture
- `CHUNKS_PATH` must contain exactly one valid chunk
- the generated chunk must be a JSON object valid according to `CHUNK_SCHEMA_PATH`
- the generated chunk must be the source of truth for the expected stored Qdrant payload
- the expected stored Qdrant payload must equal:
  - all fields of the generated chunk
  - plus an `ingest` object with the following fields:
    - `embedding_model = CONFIG_PATH.embedding.model.name`
    - `embedding_model_dimension = CONFIG_PATH.embedding.model.dimension`
    - `ingest_config_version = CONFIG_PATH.pipeline.ingest_config_version`
    - `ingested_at = runtime UTC timestamp string` generated by the ingest script
- the expected stored Qdrant payload must not contain extra top-level keys beyond:
  - all keys of the generated chunk
  - `ingest`
- object `ingest` must not contain extra keys beyond:
  - `embedding_model`
  - `embedding_model_dimension`
  - `ingest_config_version`
  - `ingested_at`

### Collection Checks
The test must call endpoint:
- `GET /collections/{name}`

The test must verify only these fields from the endpoint response:
- `result.config.metadata.embedding_model_name`
- `result.config.params.vectors.size`
- `result.config.params.vectors.distance`
- `result.points_count`

### Point Checks
- the test runner must compute the expected `point_id` according to the semantics of `CONFIG_PATH.qdrant.point_id.*`
- short point-id rule:
  - take `generated_chunk["chunk_id"]`
  - take the namespace UUID from `CONFIG_PATH.qdrant.point_id.namespace_uuid`
  - compute `uuid5(namespace_uuid, generated_chunk["chunk_id"])`
  - use the canonical UUID string as expected `point_id`
- the test must call endpoint:
  - `GET /collections/{name}/points/{point_id}`
- the test must verify only these fields from the endpoint response:
  - `result.id`
  - `result.payload`
- `result.id` must equal the expected `point_id`
- `result.payload` must equal the expected stored Qdrant payload after JSON deserialization
- equality between `result.payload` and expected stored Qdrant payload must be exact JSON-object equality by keys and values
- the test runner must separately verify that the set of top-level keys in `result.payload` equals:
  - all keys of the generated chunk
  - plus `ingest`
- the test runner must separately verify that the set of keys in `result.payload.ingest` equals:
  - `embedding_model`
  - `embedding_model_dimension`
  - `ingest_config_version`
  - `ingested_at`
- `result.payload.ingest.ingested_at` must be validated as a runtime-generated UTC timestamp string

### Checks
- the subprocess must complete successfully
- stdout must contain a summary with `created=1`
- the collection must exist after subprocess completion
- the response of `GET /collections/{name}` must have:
  - HTTP `200`
  - `status = "ok"`
  - `result.config.metadata.embedding_model_name = CONFIG_PATH.embedding.model.name`
  - `result.config.params.vectors.size = CONFIG_PATH.embedding.model.dimension`
  - `result.config.params.vectors.distance = CONFIG_PATH.qdrant.collection.distance`
  - `result.points_count = 1`
- the response of `GET /collections/{name}/points/{point_id}` must have:
  - HTTP `200`
  - `status = "ok"`
  - `result` not equal to `null`
  - `result.id = expected_point_id`
  - `result.payload` contains all fields of the generated chunk unchanged
  - `result.payload.ingest.embedding_model = CONFIG_PATH.embedding.model.name`
  - `result.payload.ingest.embedding_model_dimension = CONFIG_PATH.embedding.model.dimension`
  - `result.payload.ingest.ingest_config_version = CONFIG_PATH.pipeline.ingest_config_version`
  - `result.payload.ingest.ingested_at` is a valid UTC timestamp string
- cleanup of the temporary collection must complete successfully
- if cleanup of the temporary collection fails, the case must be considered failed

### Runner Output
On failure print:
- `error=<message>`
- `collection_name=<value>`
- `stdout=<value>`
- `stderr=<value>`
- `actual_metadata=<value>`
- `actual_vector_size=<value>`
- `actual_vector_distance=<value>`
- `actual_points_count=<value>`
- `actual_point_id=<value>`
- `actual_payload=<value>`
- `cleanup_error=<value>`, if cleanup of the temporary collection fails

### Endpoint Summary
This test must use the following real Qdrant endpoints:
- `GET /collections/{name}` before ingest starts, to verify collection absence via HTTP `404`
- `GET /collections/{name}` to verify collection metadata, vector config, and `points_count`
- `GET /collections/{name}/points/{point_id}` to verify stored point id and stored point payload
- `DELETE /collections/{name}` to clean up the temporary collection

## 12. Test: `ingest_status.py`
You are writing one Python script named `ingest_status.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

### Goal
The test must validate real `insert`, `update`, `skip`, and `skip_and_log` outcomes within one controlled E2E scenario.

### Scenario
The test must use one case with two sequential ingest runs.

### Config Preconditions
- the test runner must use the existing working valid `CONFIG_PATH`
- the test runner must create a temporary copy of that config file
- in the temporary copy, the test runner must modify only:
  - `CONFIG_PATH.qdrant.collection.name`
  - `CONFIG_PATH.logging.failed_chunk_log_path`
  - `CONFIG_PATH.logging.skipped_chunk_log_path`
- all other config values must remain unchanged

### Chunk Fixtures
- the test runner must generate 4 valid chunks according to `CHUNK_SCHEMA_PATH`
- all 4 chunks must have different `chunk_id`
- the first ingest run must use only the first 3 chunks
- the second ingest run must use all 4 chunks:
  - the same first 3 chunks unchanged
  - plus one new fourth chunk
- the incoming chunk for expected outcome `skip` must be the same JSON object in both runs without any changes
- the test runner must precompute `point_id` for all 4 chunks according to the semantics of `CONFIG_PATH.qdrant.point_id.*`

### Initial Run
- the test runner must launch the ingest script the first time with 3 chunks
- after the first run, the subprocess must complete successfully
- after the first run, the collection must contain exactly 3 points
- after the first run, the test runner must read all 3 points through the real Qdrant API and save their payload snapshots

### API Mutations Between Runs
After the first run, the test runner must modify the existing points through the real Qdrant API:
- for the first existing point, change field `section_title`
- for the second existing point, change field `content_hash`
- leave the third existing point unchanged
- for mutation `section_title`, use literal value `"Mutated Section Title"`
- for mutation `content_hash`, use literal value `"sha256:mutated-content-hash"`

### Mutation Rules
- the metadata-only mutation must change exactly field `section_title`
- the new `section_title` value must equal `"Mutated Section Title"`
- the incoming chunk in the second run for expected outcome `update` must contain the original `section_title`, different from `"Mutated Section Title"`
- the `content_hash` mutation must change the value of `content_hash` to literal value `"sha256:mutated-content-hash"`
- the incoming chunk in the second run for expected outcome `skip_and_log` must contain the original `content_hash`, different from `"sha256:mutated-content-hash"`
- both mutated points must retain the same `point_id`
- for each mutation via `PUT /collections/{name}/points/payload`, the test runner must:
  - take the existing point payload snapshot after the first run
  - modify only the one target field in that payload snapshot
  - send the full merged payload object to Qdrant
  - do not send only a partial payload fragment with the changed field

### Second Run
- the test runner must launch the ingest script the second time with 4 chunks:
  - the 3 original chunks
  - 1 new chunk
- the second subprocess must complete successfully

### Expected Outcomes
For the second ingest run, the expected outcomes must be:
- one chunk -> `update`
- one chunk -> `skip_and_log`
- one chunk -> `skip`
- one chunk -> `insert`

### Outcome Mapping
- the chunk with the metadata-only mutation must produce `update`
- the chunk whose existing point has a changed `content_hash` must produce `skip_and_log`
- the unchanged chunk must produce `skip`
- the new fourth chunk must produce `insert`

### Post-Run Checks
After the second ingest run, the test runner must verify through the real Qdrant API:
- the collection contains exactly 4 points
- the point for `insert` exists
- the payload of the `update` point has `section_title` equal to the `section_title` value from the incoming chunk of the second run
- the payload of the `update` point must have `content_hash` equal to the `content_hash` value from the incoming chunk of the second run
- the payload of the `update` point must have `text` equal to the `text` value from the incoming chunk of the second run
- the payload of the `update` point must contain an `ingest` object updated with values from the second ingest run
- the payload of the `skip` point after the second run must be exactly equal to that point’s payload snapshot after the first run
- the payload of the `skip_and_log` point after the second run must have `content_hash` equal to the mutated `content_hash` written through the API mutation between runs
- the payload of the `skip_and_log` point after the second run must not be overwritten by the incoming chunk of the second run in field `content_hash`
- all post-run checks must be tied to the precomputed `point_id` values

### Summary Checks
- stdout of the second ingest run must contain:
  - `created=1`
  - `updated=1`
  - `unchanged=1`
  - `skipped=1`
  - `failed=0`

### Skipped Log Checks
- `CONFIG_PATH.logging.skipped_chunk_log_path` after the second run must exist
- the skipped log must contain exactly one JSONL entry
- that entry must correspond to the chunk with expected outcome `skip_and_log`
- the skipped-log entry must contain:
  - `chunk_index`
  - `chunk_id`
  - `reason = "fingerprint_changed"`
- `skipped_log_entry.chunk_id` must equal the `chunk_id` of the incoming chunk with expected outcome `skip_and_log`

### Forbidden Outcomes
- the second ingest run must not write failed-chunk log entries
- the failed chunk log file must either be absent or exist and contain exactly `0` JSONL entries
- the `skip_and_log` chunk must not cause a payload update
- the `skip` chunk must not cause a payload update
- the `update` chunk must not create a second point for the same semantic chunk
- cleanup of the temporary collection must run even if the case fails

### Endpoint Summary
This test must use the following real Qdrant endpoints:
- `GET /collections/{name}` to check `points_count`
- `GET /collections/{name}/points/{point_id}` to read payload snapshots after the first run and for post-run checks after the second run
- `PUT /collections/{name}/points/payload` for the `section_title` mutation and `content_hash` mutation between runs
- `DELETE /collections/{name}` to clean up the temporary collection

### Runner Output
On failure print:
- `error=<message>`
- `collection_name=<value>`
- `first_run_stdout=<value>`
- `first_run_stderr=<value>`
- `second_run_stdout=<value>`
- `second_run_stderr=<value>`
- `actual_points_count=<value>`
- `actual_skipped_log_entries=<value>`
- `cleanup_error=<value>`, if cleanup of the temporary collection fails

## 13. Test: `failed_chunk_log_e2e.py`
You are writing one Python script named `failed_chunk_log_e2e.py`.

### CLI
Arguments:
- `SCRIPT_PATH` / `--script` (`Path`, required): path to dense ingest script
- `CHUNK_SCHEMA_PATH` / `--chunk-schema` (`Path`, required): chunk schema JSON file
- `CONFIG_PATH` / `--config` (`Path`, required): valid dense ingest config file
- `ENV_FILE_PATH` / `--env-file` (`Path`, required): valid dense ingest env file
- `VERBOSE` / `--verbose` (`store_true`, optional): print extra diagnostics for failed cases

### Goal
The test must verify that on a hard failure during status assignment, the ingest script writes an entry to `failed_chunk_log_path`.

### Scenario
The test must use one case with two sequential ingest runs.

### Config Preconditions
- the test runner must use the existing working valid `CONFIG_PATH`
- the test runner must create a temporary copy of that config file
- in the temporary copy, the test runner must modify only:
  - `CONFIG_PATH.qdrant.collection.name`
  - `CONFIG_PATH.logging.failed_chunk_log_path`
  - `CONFIG_PATH.logging.skipped_chunk_log_path`
- all other config values must remain unchanged

### Chunk Fixture
- the test runner must generate exactly one valid chunk according to `CHUNK_SCHEMA_PATH`
- the test runner must precompute the `point_id` of that chunk according to the semantics of `CONFIG_PATH.qdrant.point_id.*`
- the first and second ingest runs must use the same JSON object for that chunk unchanged

### Initial Run
- the test runner must launch the ingest script the first time with one chunk
- after the first run, the subprocess must complete successfully
- after the first run, the collection must contain exactly one point
- after the first run, the test runner must read the payload of that point through the real Qdrant API and save the payload snapshot
- after the first run, `CONFIG_PATH.logging.failed_chunk_log_path` and `CONFIG_PATH.logging.skipped_chunk_log_path` must either be absent or contain exactly `0` JSONL entries

### API Mutation Between Runs
After the first run, the test runner must modify the existing point through the real Qdrant API so that `content_hash` is absent from the payload.

### Mutation Rules
- the mutation must use endpoint `PUT /collections/{name}/points/payload`
- the test runner must:
  - take the existing point payload snapshot after the first run
  - delete the top-level key `content_hash` from it
  - not replace `content_hash` with `null`
  - leave all other payload fields unchanged
  - send the full merged payload object to Qdrant without field `content_hash`
- the existing point `point_id` must remain the same

### Second Run
- the test runner must launch the ingest script the second time with the same chunk
- the second subprocess must exit with `exit code = 1`

### Expected Failure
In the second ingest run, status assignment must end in a hard failure for this chunk, because the existing point payload no longer contains `content_hash`.

### Summary Checks
- stdout of the second ingest run must contain:
  - `created=0`
  - `updated=0`
  - `unchanged=0`
  - `skipped=0`
  - `failed=1`
- stdout of the second ingest run must contain `FAIL: dense ingest failed`

### Failed Log Checks
- `CONFIG_PATH.logging.failed_chunk_log_path` after the second run must exist
- the failed log must contain exactly one JSONL entry
- the failed-log entry must contain:
  - `chunk_id`
  - `chunk_index`
  - `stage = "qdrant"`
  - `error`
- `failed_log_entry.chunk_id` must equal the `chunk_id` of the incoming chunk
- `failed_log_entry.error` must contain substring `missing field path: content_hash`

### Skipped Log Checks
- `CONFIG_PATH.logging.skipped_chunk_log_path` after the second run must either be absent or contain exactly `0` JSONL entries

### Post-Run Checks
After the second ingest run, the test runner must verify through the real Qdrant API:
- the collection still contains exactly one point
- `GET /collections/{name}/points/{point_id}` after the second run must return HTTP `200`
- the test runner must keep the payload snapshot immediately after the destructive mutation between runs
- the existing point payload after the second run must be exactly equal to the payload snapshot after the destructive mutation between runs
- the ingest script must not restore the missing `content_hash`

### Endpoint Summary
This test must use the following real Qdrant endpoints:
- `GET /collections/{name}` to check `points_count`
- `GET /collections/{name}/points/{point_id}` to read the payload snapshot after the first run and for post-run checks after the second run
- `PUT /collections/{name}/points/payload` for the destructive mutation of the existing point payload between runs
- `DELETE /collections/{name}` to clean up the temporary collection

### Runner Output
On failure print:
- `error=<message>`
- `collection_name=<value>`
- `first_run_stdout=<value>`
- `first_run_stderr=<value>`
- `second_run_stdout=<value>`
- `second_run_stderr=<value>`
- `actual_points_count=<value>`
- `actual_failed_log_entries=<value>`
- `cleanup_error=<value>`, if cleanup of the temporary collection fails
- cleanup of the temporary collection must run even if the case fails
