You are writing one Python script: `dense_ingest.py`.
This is a CLI ingest pipeline for dense vector ingestion into Qdrant. It must read chunk records from `CHUNKS_PATH`, create embeddings through a local embedding service, and upsert points into Qdrant.

## 1. CLI
Named parameters:
- `CHUNKS_PATH` = argument `--chunks`
- `CONFIG_PATH` = argument `--config`
- `ENV_FILE_PATH` = argument `--env-file`
- `REPORT_ONLY` = argument `--report-only`

Required arguments:
- `CHUNKS_PATH` / `--chunks` (`Path`)
- `CONFIG_PATH` / `--config` (`Path`)
- `ENV_FILE_PATH` / `--env-file` (`Path`)

Optional arguments:
- `REPORT_ONLY` / `--report-only` (`store_true`)

Description:
- `CHUNKS_PATH`: chunks JSONL file
- `CONFIG_PATH`: ingest pipeline TOML config
- `ENV_FILE_PATH`: dotenv-style environment settings file
- `REPORT_ONLY`: boolean flag; if provided, do not fail on failed chunks, but print a WARN summary

Further references in this file to `CHUNKS_PATH`, `CONFIG_PATH`, `ENV_FILE_PATH`, and `REPORT_ONLY` refer specifically to these CLI arguments.

When this prompt says "read `CHUNKS_PATH`", "read `CONFIG_PATH`", "read `ENV_FILE_PATH`", or use `REPORT_ONLY`, it means to work with the value obtained from the corresponding command-line CLI argument.

There must be no default paths for `CHUNKS_PATH`, `CONFIG_PATH`, or `ENV_FILE_PATH`.
If `REPORT_ONLY` is not provided, its default value = `False`.

## 2. Format of `CONFIG_PATH`
The `CONFIG_PATH` file is an ingest pipeline config TOML file.
`CONFIG_PATH` is the source of truth for pipeline behavior.

The structure of `CONFIG_PATH` must be validated against:
- `Execution/ingest/schemas/dense_ingest_config.schema.json`

The format and semantics of `CONFIG_PATH` are defined in:
- `Specification/contracts/ingest/dense_config.md`

The implementation must use these contract files as the source of truth for the structure and semantics of `CONFIG_PATH`.
If this prompt and the contract files for `CONFIG_PATH` appear contradictory, the source of truth for `CONFIG_PATH` is the contract files.

Invalid `CONFIG_PATH`:
- `CONFIG_PATH` is considered invalid if TOML does not parse, if the parsed config does not conform to the schema, or if a value violates contract semantics
- it is considered a whole-run error
- ingest must terminate immediately
- such errors do not belong in the failed chunk log

Notation such as `CONFIG_PATH.some.section.field` in this document means the corresponding field in the ingest config.

## 3. Format of `ENV_FILE_PATH`
The `ENV_FILE_PATH` file is a dotenv-like text file.
`ENV_FILE_PATH` is the source of truth for runtime endpoints and secret-like connection settings.

The structure of parsed env values must be validated against:
- `Execution/ingest/schemas/dense_ingest_env.schema.json`

The format and semantics of `ENV_FILE_PATH` are defined in:
- `Specification/contracts/ingest/dense_env.md`

The implementation must use these contract files as the source of truth for the structure and semantics of `ENV_FILE_PATH`.
If this prompt and the contract files for `ENV_FILE_PATH` appear contradictory, the source of truth for `ENV_FILE_PATH` is the contract files.

Invalid `ENV_FILE_PATH`:
- `ENV_FILE_PATH` is considered invalid if the file cannot be read, if env parsing violates the contract format, if parsed env values do not conform to the schema, or if a value violates contract semantics
- it is considered a whole-run error
- ingest must terminate immediately
- such errors do not belong in the failed chunk log

Notation such as `ENV_FILE_PATH.SOME_KEY` in this document means the corresponding field in the env contract.

## 4. Format of `CHUNKS_PATH`
The `CHUNKS_PATH` file:
- JSONL;
- each non-empty line is a JSON object chunk;
- each chunk must conform to `Execution/schemas/chunk.schema.json`;

If there is not a single non-empty line in `CHUNKS_PATH`:
- print exactly `FAIL: no chunks in <path>`
- `<path>` = the value of `CHUNKS_PATH`
- exit code 1

## 5. Semantics of Config Values
The semantics of config values are defined in:
- `Specification/contracts/ingest/dense_config.md`

When this document uses references such as:
- `CONFIG_PATH.qdrant.point_id.strategy`
- `CONFIG_PATH.idempotency.fingerprint_fields`
- `CONFIG_PATH.qdrant.collection.distance`

they must be interpreted according to the contract semantics from
`Specification/contracts/ingest/dense_config.md`.

Rule for field references in config:
- if a config field reference points to a `chunk` field, it must use the explicit root `chunk`
- examples of valid field references:
  - `chunk.text`
  - `chunk.content_hash`
  - `chunk.ingest.ingested_at`
- when resolving such a field reference, the implementation must treat `chunk` as the name of the root entity
- the implementation must not interpret the `chunk` prefix as a literal key that must be searched inside the already loaded chunk payload

## 6. Terms
`chunk` in this document means the JSON object read from one non-empty line of the `CHUNKS_PATH` file.

`point` in this document means a record in a Qdrant collection consisting of `point_id`, a dense vector, and payload.

`embedding` in this document means the dense vector created by the embedding generation service for a `chunk`.

`fingerprint` in this document means a computed value used to compare a `point` and a chunk.
- a fingerprint may be computed both for a chunk and for a point
- the fields used to compute the fingerprint are defined in `CONFIG_PATH.idempotency.fingerprint_fields` and always mean paths inside the `chunk` payload
- the fingerprint generation algorithm is defined by `CONFIG_PATH.idempotency.strategy`
- fingerprint is not intended to detect collection-level migration events

`ingest_status` in this document means the ingest decision for a `chunk`.
- allowed values: `insert`, `update`, `skip`, `skip_and_log`

`metadata` means the fields of a `chunk` or a `point`, except for the fields listed in
`CONFIG_PATH.idempotency.fingerprint_fields`

## 7. Implementation Restrictions
Requirements for implementation structure:
- do not make one huge function for the entire ingest flow;
- separate parsing / config loading, validation, HTTP I/O, diff logic, and summary reporting;
- avoid long functions with mixed responsibility;
- the final deliverable must still remain one file: `dense_ingest.py`;
- for HTTP requests to the embedding service and to Qdrant, use a standard-library HTTP client;
- do not use external Python libraries;
- exception: for TOML reading on Python without `tomllib`, `tomli` may be used;
- small local helper functions, dataclass structures, and helper types are allowed if they simplify the code;
- structure the implementation by failure domains, not only by happy-path steps;
- any potentially failing operation must run inside the error-handling scope at the level where its error is contractually supposed to be handled;
- preparatory computations must not be moved outside `try` if they depend on data from a specific entity and can raise an error that contractually must stay localized to that entity level;
- if processing has multiple levels, for example run-level, batch-level, and item-level, the `try/except` boundaries must preserve the same hierarchy of failure domains;
- a fallback path must not widen the failure domain compared with the path it replaces;
- errors in validation, field resolution, serialization, normalization, request-body assembly, and other preparatory steps must fall into the same error-handling branch as the main operation they support.

## 8. Chunk Validation
Validation of each chunk must happen before any requests to the embedding generation service and to Qdrant.

Additional rule on top of the schema:
- `chunk.page_end >= chunk.page_start`

Chunk validation must be deterministic and fail-fast at the level of the specific chunk:
- no requests to the embedding generation service or to Qdrant may be executed for an invalid chunk;
- it must be written to the failed chunk log;
- the overall ingest may continue for the remaining chunks.

## 9. Fingerprint Comparison
`fingerprint` is used to compare a `chunk` and a `point`.

The fields for fingerprint computation for both `chunk` and `point` are defined in `CONFIG_PATH.idempotency.fingerprint_fields`.
These fields are always interpreted as paths inside the `chunk` payload; when computing a fingerprint for a `point`, the same paths are applied to the payload of that `point`.
The algorithm for computing the fingerprint for both `chunk` and `point` is defined by `CONFIG_PATH.idempotency.strategy`.

The goal of the comparison is to determine whether a `point` may be updated without recreating the embedding.
If the `fingerprint` of the `chunk` and the `point` is the same, the `point` may be updated without recreating the embedding.
If the `fingerprint` of the `chunk` and the `point` is different, the `point` may not be updated without recreating the embedding.
A change of embedding model or vector dimension is a collection-level migration and must not be expressed through a fingerprint mismatch of an individual `chunk`.

Rule for metadata-only comparison:
- when deciding between `ingest_status = update` and `ingest_status = skip`, the runtime field `ingest.ingested_at` must not be counted as a metadata difference
- `chunk.ingest.ingested_at` and `point.payload.ingest.ingested_at` may differ between ingest runs without causing `update`
- a difference only in `ingest.ingested_at` must lead to `ingest_status = skip`, not to `ingest_status = update`

## 10. Embedding Service Contract
The base embedding service contract is defined in:
- `Specification/contracts/external/embedding_service.md`

Ingest-specific usage:
- `OLLAMA_URL` is taken from `ENV_FILE_PATH.OLLAMA_URL`
- request `model` is taken from `CONFIG_PATH.embedding.model.name`
- request `input` is the current batch of chunk texts selected for embedding
- the number of returned embeddings must equal the number of strings in `request.input`
- the length of each returned embedding must equal `CONFIG_PATH.embedding.model.dimension`

Retry:
- for requests to the embedding generation service, use `CONFIG_PATH.embedding.retry.max_attempts` and `CONFIG_PATH.embedding.retry.backoff` for retry logic

Fallback on failed embedding batch:
- if an embedding batch failed after all retry attempts, ingest must not silently drop the whole batch;
- ingest must degrade to per-chunk processing inside that batch;
- each chunk from the failed batch must be reprocessed separately;
- a failed embedding batch includes a transport error, a non-`2xx` HTTP status, and an invalid response;
- if an individual chunk still does not receive a valid embedding response, it must be written to the failed chunk log;
- the remaining chunks from that same batch must still have a chance to complete successfully;
- per-chunk processing after batch fallback must also use the same retry policy.

## 11. Qdrant Contract
The base HTTP contract of Qdrant is defined by the official Qdrant API specification:
- https://api.qdrant.tech/

The official Qdrant API defines the base HTTP contract, and this document defines which endpoints and restrictions must be used in this implementation.

Checking collection existence
-----------------------------
- endpoint: `GET /collections/{CONFIG_PATH.qdrant.collection.name}`
- used to check collection existence and to read collection config
- request mode: single request
- `404` means the collection does not exist
- a successful Qdrant response means the collection exists
- from a successful response, the following must be read:
  - collection metadata from `result.config.metadata`
  - collection vector config, including vector dimension and vector distance

Creating the collection
-----------------------
- endpoint: `PUT /collections/{CONFIG_PATH.qdrant.collection.name}`
- used to create the collection
- request mode: single request
- the request body must describe exactly one vector config:
  - `vectors.size` = `CONFIG_PATH.embedding.model.dimension`
  - `vectors.distance` = `CONFIG_PATH.qdrant.collection.distance`
- the request body must include collection metadata:
  - `embedding_model_name` = `CONFIG_PATH.embedding.model.name`
  - `chunking_strategy` = `CONFIG_PATH.pipeline.chunking_strategy`
- the operation is considered successful only on a successful Qdrant response

Getting a point by `point_id`
-----------------------------
- endpoint: `GET /collections/{CONFIG_PATH.qdrant.collection.name}/points/{point_id}`
- used to get a point by `point_id`
- request mode: single request
- `404` means the point does not exist
- a successful Qdrant response means the point was found
- with HTTP status `200`, the response must parse as a JSON object
- with HTTP status `200`, the response body must contain the `point` object
- with HTTP status `200`, the `point` must contain `payload`, and `payload` must be a JSON object

Upsert points
-------------
- endpoint: `PUT /collections/{CONFIG_PATH.qdrant.collection.name}/points`
- used for batch upsert of points
- request mode: batch request
- each upsert point must contain `id`, `vector`, and `payload`
- the operation is considered successful only on a successful Qdrant response

Update payload fields
---------------------
- endpoint: `PUT /collections/{CONFIG_PATH.qdrant.collection.name}/points/payload`
- used to update payload fields of one point
- request mode: single request
- in the request:
  - `payload` must be a JSON object
  - `payload` must be the full merged payload object of the target point after update
  - `payload` must not be a partial fragment containing only changed fields
  - ingest must first read the existing point payload, then apply metadata changes on top of it, and send the full merged payload
  - `points` must be an array of `point_id`
  - `points` must contain exactly one `point_id`
- the operation is considered successful only on a successful Qdrant response

Retry:
- use `CONFIG_PATH.qdrant.retry.max_attempts` and `CONFIG_PATH.qdrant.retry.backoff` for all requests to Qdrant

Fallback on failed upsert batch:
- if a batch upsert failed after all retry attempts, ingest must not silently drop the whole batch;
- ingest must degrade to per-point processing inside that batch;
- each point from the failed batch must be reprocessed separately;
- if the response for an individual point remains invalid, it must be written to the failed chunk log;
- the remaining points from that same batch must still have a chance to complete successfully;
- per-point processing after batch fallback must also use the same retry policy.

## 12. Defining `ingest_status`
This section defines how `ingest_status` is determined for a `chunk`.

If the collection was created during the current ingest run:
- for each `chunk`, assign `ingest_status = insert`
- in this branch, point lookup and fingerprint comparison must not be executed

If the collection already existed at the start of the ingest run:
1. perform point lookup for the `point_id` computed from the `chunk`
  - `point_id` must be computed from `chunk["chunk_id"]` according to the rules in `CONFIG_PATH.qdrant.point_id.strategy` and `CONFIG_PATH.qdrant.point_id.format`
  - to look up the `point` by `point_id`, use the endpoint `GET /collections/{CONFIG_PATH.qdrant.collection.name}/points/{point_id}` described in `11) Qdrant Contract`
2. if no `point` is found for `point_id`, assign `ingest_status = insert`
3. if the `point` is found:
  - if the `fingerprint` of the `chunk` and the `point` is different, assign `ingest_status = skip_and_log`
  - if the `fingerprint` of the `chunk` and the `point` is the same and the `metadata` of the `chunk` and the `point` is different, assign `ingest_status = update`
  - in this metadata comparison, a difference only in `ingest.ingested_at` must be ignored
  - otherwise, assign `ingest_status = skip`

## 13. Embedding Batching
- only `chunk` objects with `ingest_status = insert` participate in embedding batching
- the list of chunks must be split into batches of size at most `CONFIG_PATH.embedding.transport.max_batch_size`
- the last batch may be smaller than `CONFIG_PATH.embedding.transport.max_batch_size`
- for each batch, take from each chunk the value of the field specified in `CONFIG_PATH.embedding.input.text_source`
- from these values, build the array of strings for the `input` field in the request body
- for each batch, use the endpoint `POST ENV_FILE_PATH.OLLAMA_URL/api/embed` described in `10) Embedding Service Contract`
- one string in `input` must correspond to one chunk
- the order of strings in `input` must correspond to the order of chunks in the batch
- one embedding in the response must correspond to one chunk
- the order of embeddings in the response must correspond to the order of strings in `input`
- after receiving the response, for each `chunk` in the batch, build an element of the internal structure `chunk + embedding`

## 14. Point Ingest Batching
- only `chunk + embedding` elements obtained for `chunk` with `ingest_status = insert` participate in point ingest batching
- the list of `chunk + embedding` elements must be split into upsert batches of size at most `CONFIG_PATH.qdrant.transport.upsert_batch_size`
- the last batch may be smaller than `CONFIG_PATH.qdrant.transport.upsert_batch_size`
- for each `chunk + embedding` element, build a `point` for upsert:
  - `point.id` = `point_id`, computed according to the rules in `CONFIG_PATH.qdrant.point_id.strategy` and `CONFIG_PATH.qdrant.point_id.format`
  - `point.vector` = `embedding`
  - `point.payload` = `chunk`
- for each batch, use the endpoint `PUT /collections/{CONFIG_PATH.qdrant.collection.name}/points` described in `11) Qdrant Contract`
- each `point` in such a batch must correspond to one `chunk + embedding` element

## 15. Overall Algorithm
The overall ingest flow must be:

1. Load config and env.
2. Validate runtime settings.
3. Read input chunks JSONL.
4. Validate each chunk against `Execution/schemas/chunk.schema.json`.
5. Check whether the collection exists in Qdrant and create it if necessary, as described in `11) Qdrant Contract`.
   - if the collection is missing and `CONFIG_PATH.qdrant.collection.create_if_missing = false`, ingest must terminate before processing chunks
   - if the collection is created during the current ingest run, it must be created with collection metadata:
     - `embedding_model_name` = `CONFIG_PATH.embedding.model.name`
     - `chunking_strategy` = `CONFIG_PATH.pipeline.chunking_strategy`
   - if the collection already existed at the start of the ingest run, ingest must, through the same request `GET /collections/{CONFIG_PATH.qdrant.collection.name}`, read collection metadata and vector config
6. If the collection already existed at the start of the ingest run, check compatibility of that collection with the current ingest config:
   - ingest must check that the collection metadata key `embedding_model_name` is present
   - ingest must compare collection metadata `embedding_model_name` with `CONFIG_PATH.embedding.model.name`
   - ingest must compare collection metadata `chunking_strategy` with `CONFIG_PATH.pipeline.chunking_strategy`
   - ingest must compare collection vector dimension with `CONFIG_PATH.embedding.model.dimension`
   - ingest must compare collection vector distance with `CONFIG_PATH.qdrant.collection.distance`
   - all checks must be executed before finishing ingest; there must be no early exit after the first mismatch
   - if collection metadata is missing or the key `embedding_model_name` is missing, ingest must terminate with a whole-run error
   - if `embedding_model_name` does not match, ingest must terminate with a whole-run error
   - if `chunking_strategy` is missing or does not match, ingest must terminate with a whole-run error
   - if vector dimension does not match, ingest must terminate with a whole-run error
   - if vector distance does not match, ingest must terminate with a whole-run error
   - these errors must terminate ingest before chunk processing
7. Populate `chunk.ingest` fields with values from the current ingest run:
   - `chunk.ingest.embedding_model` = `CONFIG_PATH.embedding.model.name`
   - `chunk.ingest.embedding_model_dimension` = `CONFIG_PATH.embedding.model.dimension`
   - `chunk.ingest.ingest_config_version` = `CONFIG_PATH.pipeline.ingest_config_version`
   - `chunk.ingest.ingested_at` = runtime timestamp of the current ingest run
8. For each `chunk`, determine `ingest_status` as described in `12) Defining ingest_status`.
9. Perform embedding batching for `chunk` with `ingest_status = insert`, as described in `13) Embedding Batching`.
10. Perform point ingest batching for `chunk + embedding` elements obtained for `chunk` with `ingest_status = insert`, as described in `14) Point Ingest Batching`.
11. Perform single update requests for `chunk` with `ingest_status = update`, using the endpoint `PUT /collections/{CONFIG_PATH.qdrant.collection.name}/points/payload` described in `11) Qdrant Contract`.
   - for each `update`, ingest must:
     - read the existing point payload
     - build the full merged payload object
     - preserve all fields from the existing point payload that are not changed by this update
     - replace only payload fields that really changed and are allowed for the update path
     - send to Qdrant the full merged payload object, not a partial payload fragment
12. Write `chunk` with `ingest_status = skip_and_log` to the skipped chunk log, as described in `18) Skipped Chunk Log`.
13. Write all hard failures to the failed chunk log, as described in `17) Failed Chunk Log`.
14. At the end, print the fixed summary, as described in `19) Summary Output`.

## 16. Logging Contract
Runtime logging is mandatory in this implementation.

General rules:
- runtime logs must be written to `stderr`
- runtime log format: plain text
- each runtime log line must start with the prefix `[dense_ingest]`
- runtime logging is meant for observability of the ingest flow and for error diagnostics
- runtime logs do not replace the failed chunk log and the skipped chunk log
- absence of runtime logging for important flow transitions is considered a contract violation

What must be logged:
- run start
- config, env, and chunks loading
- chunk validation result
- collection existence check
- collection creation
- collection compatibility check
- final status assignment
- embedding batch start and result
- transition from embedding batch processing to per-chunk fallback
- Qdrant upsert batch start and result
- transition from Qdrant upsert batch processing to per-point fallback
- update path start and result
- exit code

Runtime log detail level:
- run-level events must always be logged
- batch-level events must always be logged
- item-level events must be logged for fallback processing, `skip_and_log`, fail, and update
- item-level success logs are not needed for normal happy-path batch processing
- any branch that changes control flow because of an error, retry exhaustion, fallback, or early exit must emit a diagnostic runtime log before leaving that branch

Runtime log structure:
- if a log refers to a batch, it must include batch index and batch size
- if a log refers to a specific chunk, it must include `chunk_index`
- if a log refers to a collection-level check, it must explicitly state which exact check is being performed
- if a log refers to a fail-fast condition, it must explicitly state the reason for terminating the run

Collection compatibility logging:
- ingest must log the result of checking presence of the collection metadata key `embedding_model_name`
- ingest must log the result of comparing collection metadata `embedding_model_name` with `CONFIG_PATH.embedding.model.name`
- ingest must log the result of comparing collection metadata `chunking_strategy` with `CONFIG_PATH.pipeline.chunking_strategy`
- ingest must log the result of comparing collection vector dimension with `CONFIG_PATH.embedding.model.dimension`
- ingest must log the result of comparing collection vector distance with `CONFIG_PATH.qdrant.collection.distance`
- on mismatch, the log line must contain `expected=<value>` and `actual=<value>`
- if metadata is missing, the log line must explicitly contain `collection metadata missing`

Logging external service errors:
- on an unsuccessful HTTP response, the diagnostic message must include the HTTP status code
- if the response body has JSON format, the diagnostic message must include the values of the fields `error`, `message`, `status`, `details`, if such fields are present
- if the response body is not JSON, the diagnostic message must include the response body text
- if the response body is missing or cannot be read, the diagnostic message must include the literal text `detailed error body unavailable`
- it is not allowed to reduce an external service error only to a status code if the service response contains a body

Restrictions:
- do not log full chunk texts
- do not log embeddings
- do not log secrets or secret-like values from env/config
- do not print a traceback for normal contract data errors if the error is already represented by a short diagnostic message

## 17. Failed Chunk Log
All hard failures must be written as JSONL:
- path = `logging.failed_chunk_log_path`
- `chunk` with `ingest_status = skip` and `chunk` with `ingest_status = skip_and_log` must not be written to this log

Format of one record:
```json
{
  "chunk_id": "...",
  "chunk_index": 0,
  "stage": "validate|embed|qdrant",
  "error": "..."
}
```

`error` must contain a short string description of the hard failure reason.

The log file must be appended to line by line and created automatically together with parent directories.

## 18. Skipped Chunk Log
Only `chunk` with `ingest_status = skip_and_log` must be written as JSONL:
- path = `logging.skipped_chunk_log_path`

Format of one record:
```json
{
  "chunk_id": "...",
  "chunk_index": 0,
  "reason": "fingerprint_changed"
}
```

The log file must be appended to line by line and created automatically together with parent directories.

`ingest_status = skip_and_log`:
- is not a hard failure;
- must not be written to the failed chunk log;
- must be written to the skipped chunk log;
- must increment `skipped` in the summary.

## 19. Summary Output
Early exit summary:
If the collection is missing and `CONFIG_PATH.qdrant.collection.create_if_missing = false`:
- print `SKIP: collection does not exist and create_if_missing=false`
- exit code 0
- do not print the normal summary line

Normal run summary:
- `updated` = the number of `chunk` with `ingest_status = update` successfully processed by update requests
- `unchanged` = the number of `chunk` with `ingest_status = skip`
- `skipped` = the number of `chunk` with `ingest_status = skip_and_log`

At the end of a normal run, always print:
- `chunks=<total> created=<created> updated=<updated> unchanged=<unchanged> skipped=<skipped> failed=<failed>`

If `failed > 0`:
- if `REPORT_ONLY`:
  - print `WARN: dense ingest completed with failures`
  - exit code 0
- otherwise:
  - print `FAIL: dense ingest failed`
  - exit code 1

If `failed == 0`:
- print `OK: dense ingest completed`
- exit code 0

At the end, the file must contain:
- `if __name__ == "__main__":`
- `main()`
