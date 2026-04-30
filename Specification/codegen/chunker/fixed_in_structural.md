You are writing one Python script: `chunker.py`.
This is a CLI chunker for a collection of structural chunks. It must build fixed-size chunks from `STRUCTURAL_CHUNKS` and `CONFIG`.

The script must:
- be `chunk-stream based`;
- use sentence-preserving chunk boundaries;
- use token-based chunk sizing;
- reuse parent chunk metadata exactly as provided in `STRUCTURAL_CHUNKS`;
- validate both input chunks and output chunks through the schema passed via CLI;
- operate only as a CLI;
- write one JSONL output file.

The script must not:
- reconstruct book structure heuristically;
- read page-level extractor output;
- read `CONTENT_METADATA`;
- split sentences in half;
- write auxiliary `.txt` files.

## 1. Processing Pipeline
The high-level fixed-in-structural chunker pipeline must be:

1. Validate `STRUCTURAL_CHUNKS`, `CONFIG`, and `CHUNK_SCHEMA`.
2. Build an internal chunk stream from `STRUCTURAL_CHUNKS`.
3. Perform sentence segmentation over each parent chunk text independently.
4. Convert the sentence segmentation results into a stream of `SentenceUnit`.
5. Build a stream of fixed-size child chunks from the stream of `SentenceUnit`.
6. Assign inherited metadata from the parent structural chunk.
7. Form output chunk payload objects using inherited metadata and `CONFIG`.
8. Validate each output chunk against `CHUNK_SCHEMA`.
9. Write `OUT` as JSONL.

## 2. CLI
Required arguments:
- `--chunks` (`Path`)
- `--config` (`Path`)
- `--chunk-schema` (`Path`)
- `--out` (`Path`)

There must be no default paths.

Argument descriptions:
- `--chunks`: input structural chunks JSONL
- `--config`: fixed-in-structural chunker TOML config file
- `--chunk-schema`: JSON Schema for validating both input and output chunk records
- `--out`: output chunks JSONL

In the rest of this specification:
- `STRUCTURAL_CHUNKS` means the file passed via `--chunks`
- `CONFIG` means the file passed via `--config`
- `CHUNK_SCHEMA` means the file passed via `--chunk-schema`
- `OUT` means the file passed via `--out`

## 3. Inputs
The `STRUCTURAL_CHUNKS` file:
- JSONL;
- blank lines in the file are allowed and must be ignored;
- each non-blank line must be a separate JSON object;
- each non-blank line must conform to `CHUNK_SCHEMA`.

Input chunks must:
- be processed in input order;
- preserve the original record order from `STRUCTURAL_CHUNKS`;
- be allowed to contain different `doc_id` values in the same file;
- be handled independently from one another for sentence segmentation and chunk building.

If `STRUCTURAL_CHUNKS` is missing or any JSONL record does not pass validation:
- the chunker must fail.

The following fields must be read from each input structural chunk:
- `doc_id`
- `url`
- `document_title`
- `section_title`
- `section_path`
- `page_start`
- `page_end`
- `tags`
- `text`

The following fields must be treated as inherited parent metadata for all derived child chunks:
- `doc_id`
- `url`
- `document_title`
- `section_title`
- `section_path`
- `page_start`
- `page_end`
- `tags`

The `CONFIG` file:
- must be the source of truth for fixed-in-structural chunker behavior;
- must be a TOML config file;
- must conform to the same config contract as the fixed chunker.

Canonical config path for the current fixed chunker version:
- [chunker.toml](/home/olesia/code/prompt_gen_proj/Execution/parsing/chunker/fixed/chunker.toml)

If `CONFIG` is missing or does not pass validation:
- the chunker must fail.

The following must be read from `CONFIG`:
- `chunking.target_tokens`
- `chunking.overlap_ratio`
- `chunking.chunking_version`
- `sentence_segmentation.library`
- `sentence_segmentation.library_version`
- `sentence_segmentation.language`
- `tokenizer.library`
- `tokenizer.source`
- `tokenizer.revision`, if the field is present

The `CHUNK_SCHEMA` file:
- must be a JSON Schema file;
- must define the chunk payload contract used by both input and output chunk records.

Canonical schema path for the current chunk payload version:
- [chunk.schema.json](/home/olesia/code/prompt_gen_proj/Execution/schemas/chunk.schema.json)

Canonical output filename for the current fixed-in-structural chunker version:
- `fixed_in_structural_chunks.jsonl`

If `CHUNK_SCHEMA` is missing or invalid:
- the chunker must fail.

## 4. Output Contract
`OUT` must be a JSONL output file.
Each non-blank line in `OUT` must be a separate JSON object.
`OUT` must end with a final newline.
Blank lines between output objects are not allowed.

Each output object must conform to:
- `CHUNK_SCHEMA`
- [chunk spec](/home/olesia/code/prompt_gen_proj/Specification/contracts/chunk/spec.md)

The fixed-in-structural chunker must populate all required fields from the chunk payload contract and all supported annotation fields that are described in those documents.

`content_hash` must be computed from `text` exactly as stored.

Rules for populating schema-required and inherited fields:
- `doc_id` must be inherited from the parent structural chunk;
- `url` must be inherited from the parent structural chunk;
- `document_title` must be inherited from the parent structural chunk;
- `section_title` must be inherited from the parent structural chunk;
- `section_path` must be inherited from the parent structural chunk;
- `page_start` must be inherited from the parent structural chunk;
- `page_end` must be inherited from the parent structural chunk;
- `tags` must be inherited from the parent structural chunk;
- `schema_version = 1`
- `chunking_version` must come from `CONFIG.chunking.chunking_version`
- `chunk_created_at` must be computed as `START_TS + timedelta(minutes=chunk_index)`, where `START_TS = 2026-02-17T09:00:00Z`
- `chunk_id` must be created for each output chunk as `str(uuid.uuid4())`

Important:
- the fixed-in-structural chunker must preserve parent `doc_id` values exactly, even when one input file contains chunks from multiple documents;
- `page_start` and `page_end` for derived child chunks are intentionally coarse provenance inherited from the parent structural chunk rather than exact subchunk page coverage.

The stable projection payload for the fixed-in-structural chunker must contain only:
- `doc_id`
- `chunk_index`
- `page_start`
- `page_end`
- `section_title`
- `section_path`
- `text`
- `content_hash`
- `chunking_version`

## 5. Normalization
The whitespace normalization policy must be:
- replace `\u00a0` with a normal space;
- apply `strip()` to parent chunk text;
- collapse repeated whitespace through the regex replacement `\s+ -> " "`.

Allowed:
- replacing `\u00a0` with a normal space;
- collapsing repeated whitespace;
- applying `strip()` at the parent chunk text boundaries.

Not allowed:
- fixing extraction artifacts;
- joining split words;
- changing punctuation;
- changing the text semantically.

## 6. Chunk Stream
The chunker must build one internal chunk stream from `STRUCTURAL_CHUNKS`.

Chunk stream construction rules:
- process parent structural chunks strictly in input order;
- sentence segmentation and chunk building must reset at every new parent structural chunk;
- no output chunk may contain text from more than one parent structural chunk;
- if a parent structural chunk has empty text after normalization, it must produce no output chunks.

## 7. Sentence Segmentation
Sentence segmentation is a required intermediate stage.

Normative sentence splitter:
- `spaCy sentencizer`

Normative initialization:
- sentence segmentation settings must be read from `CONFIG.sentence_segmentation`;
- the pipeline must be initialized according to `CONFIG.sentence_segmentation`;
- the implementation must:
  - create `nlp` via `spacy.blank(CONFIG.sentence_segmentation.language)`
  - add `sentencizer` via `nlp.add_pipe("sentencizer")`
- other pipeline components are not allowed.

Sentence segmentation rules:
- segmentation must be performed on each parent structural chunk `text` independently;
- the parent chunk `text` must be normalized according to this specification before sentence segmentation;
- each resulting sentence must be normalized with `strip() + whitespace collapse`;
- no `SentenceUnit` may be created from an empty sentence after normalization.

The result of sentence segmentation for each parent chunk must be an ordered list of `SentenceUnit`.

`SentenceUnit` must contain:
- `sentence_text: str`
- `page_start: int`
- `page_end: int`
- `token_count: int`

Requirements for `SentenceUnit`:
- `sentence_text` must be non-empty after `strip()`;
- `page_start` must equal the parent structural chunk `page_start`;
- `page_end` must equal the parent structural chunk `page_end`;
- `page_start <= page_end`;
- `token_count` is computed with the normative tokenizer specified in this spec.

A chunk boundary may only occur between `SentenceUnit`.
Splitting a single sentence into two parts is forbidden.

If sentence segmentation produces no `SentenceUnit` for a given parent structural chunk:
- that parent structural chunk must produce no output chunks;
- the chunker must continue processing the remaining parent structural chunks.

## 8. Tokenization
The normative tokenizer must be initialized from `CONFIG.tokenizer`.

Rules:
- token counts used for chunk sizing must come from this tokenizer;
- token counting must be applied to normalized sentence text;
- token counting must be deterministic for the same config and input text.

## 9. Fixed-Size Chunk Building
The chunking algorithm must reuse the same sentence-window packing semantics as the fixed chunker.

The algorithm must:
- process the ordered `SentenceUnit` list of one parent structural chunk at a time;
- build one chunk window by appending complete `SentenceUnit` items until the total token count reaches or exceeds `chunking.target_tokens`;
- use overlap according to `chunking.overlap_ratio`;
- never cross parent structural chunk boundaries.

The overlap rules must be:
- if `overlap_ratio <= 0`, the next chunk starts immediately after the previous chunk;
- otherwise, compute overlap from the realized token count of the current chunk;
- the next chunk start must be chosen by walking backward over whole `SentenceUnit` items until the overlap target is met or exceeded;
- if the overlap walk would not advance, the implementation must still make forward progress.

If one sentence alone exceeds `chunking.target_tokens`:
- that sentence must still remain whole in one output chunk;
- splitting the sentence is forbidden.

## 10. Metadata Inheritance
All derived child chunks must inherit the following values from their parent structural chunk exactly as provided:
- `doc_id`
- `url`
- `document_title`
- `section_title`
- `section_path`
- `page_start`
- `page_end`
- `tags`

The implementation must not:
- recompute `section_title`;
- recompute `section_path`;
- inspect `CONTENT_METADATA`;
- attempt exact page remapping inside the parent structural chunk.

## 11. Output Materialization
For each output chunk window, the chunker must:
- join `SentenceUnit.sentence_text` with exactly one space between adjacent sentences;
- normalize the joined text with the normalization policy from this specification;
- compute `content_hash` from the final stored text exactly as stored;
- assign `chunk_index` globally across the full output stream, starting from `0`.

`chunk_index` rules:
- indexing must be global across all output chunks written to `OUT`;
- indexing must not reset per parent structural chunk;
- output order must preserve parent chunk input order and child chunk order within each parent.

## 12. Validation
The implementation must validate:
- each input structural chunk against `CHUNK_SCHEMA`;
- each output chunk against `CHUNK_SCHEMA`.

If any input or output record fails validation:
- the chunker must fail.

The implementation should reuse existing shared schema-validation helpers if they already exist in the codebase.

## 13. JSONL Output
The chunker must write validated output records to `OUT` in output order.

Rules:
- use UTF-8;
- write one JSON object per line;
- do not write blank lines;
- ensure the file ends with `\n`.

The script may print a short success message to stdout after writing the file.
