You are writing one Python script: `chunker.py`.
This is a CLI chunker for a book. It must build fixed-size chunks from `PAGES`, `BOOK_METADATA`, and `CONTENT_METADATA`.

The script must:
- be `document-stream based`;
- use sentence-preserving chunk boundaries;
- use token-based chunk sizing;
- use `BOOK_METADATA` only for document-level payload fields;
- use `CONTENT_METADATA` to determine the chunking start page and for annotation;
- operate only as a CLI;
- write one JSONL output file.

The script must not:
- reconstruct book structure heuristically;
- use `CONTENT_METADATA` to determine chunk boundaries;
- split sentences in half;
- write auxiliary `.txt` files.

## 1. Processing Pipeline
The high-level fixed chunker pipeline must be:

1. Validate `PAGES`, `BOOK_METADATA`, `CONTENT_METADATA`, and `CONFIG`.
2. Determine the chunking start page from `CONTENT_METADATA`.
3. Build an internal document stream from filtered `PAGES`.
4. Perform sentence segmentation over the document stream.
5. Convert the sentence segmentation results into a stream of `SentenceUnit`.
6. Build a stream of chunks from the stream of `SentenceUnit`.
7. Compute `page_start` and `page_end` for each chunk.
8. Assign `section_title` and `section_path` through `CONTENT_METADATA`.
9. Form chunk payload objects using `BOOK_METADATA` and `CONFIG`.
10. Write `OUT` as JSONL.

## 2. CLI
Required arguments:
- `--pages` (`Path`)
- `--book-metadata` (`Path`)
- `--content-metadata` (`Path`)
- `--config` (`Path`)
- `--out` (`Path`)

There must be no default paths.

Argument descriptions:
- `--pages`: input page-level JSONL
- `--book-metadata`: book-level metadata JSON
- `--content-metadata`: content metadata JSON
- `--config`: fixed chunker TOML config file
- `--out`: output chunks JSONL

In the rest of this specification:
- `PAGES` means the file passed via `--pages`
- `BOOK_METADATA` means the file passed via `--book-metadata`
- `CONTENT_METADATA` means the file passed via `--content-metadata`
- `CONFIG` means the file passed via `--config`
- `OUT` means the file passed via `--out`

## 3. Inputs
The `PAGES` file:
- JSONL;
- blank lines in the file are allowed and must be ignored;
- each non-blank line must conform to the schema file:
  - [page_record.schema.json](/home/olesia/code/prompt_gen_proj/Execution/parsing/schemas/page_record.schema.json)

Pages must:
- be sorted by `page`;
- be processed in sorted order;
- preserve the original `page` values from `PAGES`;
- allow duplicate `page` values;
- preserve the original record order from `PAGES` when `page` is the same;
- not be fixed or deduplicated by the fixed chunker.

If `PAGES` is missing or any JSONL record does not pass validation:
- the chunker must fail.

The `BOOK_METADATA` file:
- a JSON object;
- must conform to the schema file:
  - [book_metadata.schema.json](/home/olesia/code/prompt_gen_proj/Execution/parsing/schemas/book_metadata.schema.json)

If `BOOK_METADATA` is missing or does not pass validation:
- the chunker must fail.

The `CONTENT_METADATA` file:
- a JSON object;
- must conform to the schema file:
  - [book_content_metadata.schema.json](/home/olesia/code/prompt_gen_proj/Execution/parsing/schemas/book_content_metadata.schema.json)

If `CONTENT_METADATA` is missing or does not pass validation:
- the chunker must fail.

The following must be derived from `CONTENT_METADATA`:
- `content_start_page`
- section annotation data

`content_start_page` must be determined as follows:
- collect all valid `ranges.pdf.start` values from:
  - `parts`
  - `chapters`
  - `sections`
  - `subsections`
- `front_matter` must not participate in the `content_start_page` calculation;
- `content_start_page = min(all_collected_starts)`;
- if no valid start exists at those levels, the chunker must fail.

The `CONFIG` file:
- must be the source of truth for fixed chunker behavior;
- must be a TOML config file;
- must conform to the schema file:
  - [fixed_chunker_config.schema.json](/home/olesia/code/prompt_gen_proj/Execution/parsing/schemas/fixed_chunker_config.schema.json)

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

## 4. Output Contract
`OUT` must be a JSONL output file.
Each non-blank line in `OUT` must be a separate JSON object.
`OUT` must end with a final newline.
Blank lines between output objects are not allowed.

Each output object must conform to:
- [chunk.schema.json](/home/olesia/code/prompt_gen_proj/Execution/schemas/chunk.schema.json)
- [chunk spec](/home/olesia/code/prompt_gen_proj/Specification/contracts/chunk/spec.md)

The fixed chunker must populate all required fields from the chunk payload contract and all supported annotation fields that are described in those documents.

`content_hash` must be computed from `text` exactly as stored.

Rules for populating the remaining schema-required fields:
- `document_title` must come from `BOOK_METADATA.document_title`
- `url` must come from `BOOK_METADATA.url`
- `tags` must come from `BOOK_METADATA.tags`
- `schema_version = 1`
- `chunking_version` must come from `CONFIG.chunking.chunking_version`
- `chunk_created_at` must be computed as `START_TS + timedelta(minutes=chunk_index)`, where `START_TS = 2026-02-17T09:00:00Z`
- `doc_id` must be created once per chunker run as `str(uuid.uuid4())` and shared by all chunks of that run
- `chunk_id` must be created for each output chunk as `str(uuid.uuid4())`

Important:
- the fixed chunker intentionally uses these same rules even though `doc_id` and `chunk_id` remain run-volatile;
- chunker determinism for testing must be checked against a stable projection payload rather than `doc_id`, `chunk_id`, and `chunk_created_at`.

The stable projection payload for the fixed chunker must contain only:
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
- apply `strip()` to page text;
- collapse repeated whitespace through the regex replacement `\s+ -> " "`.

Allowed:
- replacing `\u00a0` with a normal space;
- collapsing repeated whitespace;
- applying `strip()` at the page text boundaries.

Not allowed:
- fixing extraction artifacts;
- joining split words;
- changing punctuation;
- changing the text semantically.

## 6. Document Stream
The chunker must build one internal document stream only from document pages starting at `content_start_page`.

For each page, the stream must include a unique machine-readable marker in the format:
- `<<<PAGE:{page}>>>`

Document stream construction rules:
- first, filter `PAGES` to keep only records where `page >= content_start_page`;
- if no pages remain after that, the chunker must fail;
- the stream is built in page order;
- for each page, the stream must contain:
  - the page marker;
  - a newline;
  - the normalized page `clean_text`;
- between adjacent pages, insert exactly `\n\n`.

Empty pages:
- are not removed from the page sequence;
- receive their own marker in the stream;
- do not produce a `SentenceUnit` if the page text is empty after normalization;
- must still participate in `CONTENT_METADATA` lookup by page ranges.

Markers:
- are used only inside the chunker;
- must not appear in `SentenceUnit.sentence_text`;
- must not appear in output `text`;
- must not participate in `content_hash`.

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

The sentence splitter must operate on the internal document stream, but markers must be treated as hard separators:
- a marker is not part of a sentence;
- a marker must not appear inside `sentence_text`;
- markers must be used to compute page coverage for each sentence span.

Post-processing rule:
- `spaCy` must receive the internal document stream together with markers;
- markers do not have to form a separate sentence span;
- the implementation must perform marker-aware post-processing on top of the sentence segmentation results;
- for each sentence span, the implementation must:
  - find all markers inside the sentence span;
  - determine `page_start` as the page of the first marker covered by the sentence span;
  - determine `page_end` as the page of the last marker covered by the sentence span;
  - remove all markers from the text of that sentence span;
  - apply `strip() + whitespace collapse` to the remaining text;
  - not create a `SentenceUnit` if the text becomes empty after marker removal and `strip()`;
  - create `SentenceUnit` only from the remaining non-empty text.

The result of sentence segmentation must be an ordered list of `SentenceUnit`.

`SentenceUnit` must contain:
- `sentence_text: str`
- `page_start: int`
- `page_end: int`
- `token_count: int`

Requirements for `SentenceUnit`:
- `sentence_text` must be non-empty after `strip()`;
- `page_start` and `page_end` must define the page range covered by the sentence span;
- `page_start <= page_end`;
- `token_count` is computed with the normative tokenizer specified in this spec.

A chunk boundary may only occur between `SentenceUnit`.
Splitting a single sentence into two parts is forbidden.

If sentence segmentation produces no `SentenceUnit`:
- the chunker must fail.

## 8. Token Counting
Chunk size must be measured in tokens.

Normative tokenizer:
- a Hugging Face compatible tokenizer loaded through the `tokenizers` library

The chunker must use one fixed tokenizer artifact for:
- `SentenceUnit.token_count`
- deciding when `CONFIG.chunking.target_tokens` has been reached
- computing overlap

The normative tokenizer must be read from `CONFIG`:
- tokenizer settings must be read from `CONFIG.tokenizer`
- tokenizer source must come from `CONFIG.tokenizer.source`
- tokenizer revision must come from `CONFIG.tokenizer.revision`, if the field is present
- if `CONFIG.tokenizer.revision` is absent, the implementation must resolve the latest/default upstream revision

The implementation must:
- initialize one tokenizer instance from `CONFIG.tokenizer`
- load tokenizer artifacts from `CONFIG.tokenizer.source`
- use `CONFIG.tokenizer.revision` when resolving tokenizer artifacts, if the field is present
- reuse the same tokenizer instance throughout the entire chunking run

Failure to load tokenizer artifacts:
- is a whole-run error
- must cause immediate chunker failure

This tokenizer must be used for:
- `SentenceUnit.token_count`
- chunk sizing
- overlap sizing

## 9. Chunk Assembly
The chunker must walk through `SentenceUnit` from left to right and build chunks only from consecutive sentences.

Algorithm:
1. Start a new chunk with the current `SentenceUnit`.
2. Add following `SentenceUnit` until the total chunk `token_count` becomes `>= CONFIG.chunking.target_tokens`.
3. After reaching `CONFIG.chunking.target_tokens`, the chunk must stop.

Constraints:
- sentence order inside a chunk must not change;
- sentences must not be skipped;
- non-consecutive sentences must not be included.

## 10. Overshoot
Overshoot is allowed.

Overshoot rule:
- if adding the last full sentence makes the chunk larger than `CONFIG.chunking.target_tokens`, that chunk remains valid;
- overshoot is unlimited if it is caused by the last full sentence.

The chunker must not:
- remove the last already-added sentence only to satisfy the limit;
- split a sentence to hit `CONFIG.chunking.target_tokens` exactly.

## 11. Long Sentence Rule
If a single `SentenceUnit` has `token_count > CONFIG.chunking.target_tokens`, it must form its own chunk.

Such a chunk:
- is valid;
- is not split;
- may be larger than `CONFIG.chunking.target_tokens`.

## 12. Overlap
Overlap is required and is defined by `CONFIG.chunking.overlap_ratio`.

For a completed previous chunk:
- `target_overlap_tokens = ceil(previous_chunk_token_count * CONFIG.chunking.overlap_ratio)`

The next chunk must not start from the first new sentence, but from a suffix of the previous chunk.

Rule for choosing the overlap suffix:
- walk backward from the end of the previous chunk over its sentences;
- accumulate sentences until their total `token_count` becomes `>= target_overlap_tokens`;
- the selected suffix is the overlap of the next chunk.

After the overlap suffix is selected:
- the new chunk starts from the first sentence of the selected suffix;
- the chunk is then grown forward again using the normal `CONFIG.chunking.target_tokens + final sentence overshoot` rule.

Progress rule:
- each next chunk must end strictly to the right of the previous chunk in the `SentenceUnit` sequence;
- the chunker must not emit the same set of sentences again;
- if the overlap suffix is equal to the entire previous chunk and would not allow progress, the next chunk must start from the first new sentence after the previous chunk start.

Special cases:
- if `CONFIG.chunking.overlap_ratio = 0`, there is no overlap;
- overlap is chosen only on sentence boundaries;
- overlap never cuts a sentence.

## 13. Text Construction
`chunk.text` must be built only from the `sentence_text` values of the sentences included in the chunk.

Rules:
- sentences are concatenated with a single space;
- the resulting `text` must be non-empty;
- `content_hash` is computed from the final `text` exactly as stored.

## 14. Page Range
`page_start` and `page_end` must be derived only from the page ranges of the sentences included in the chunk.

Rules:
- `page_start = min(sentence.page_start for sentence in chunk)`
- `page_end = max(sentence.page_end for sentence in chunk)`

If all sentences in a chunk belong to the same page:
- `page_start == page_end`

If a chunk covers sentences from multiple pages:
- `page_start` and `page_end` must define the full range of those pages;
- pages without a `SentenceUnit` that lie between `page_start` and `page_end` are considered part of the coverage range.

## 15. Section Annotation
Metadata does not affect chunk boundaries.
Metadata is used:
- to determine `content_start_page`;
- for annotation.

For the fixed chunker, `section_title` and `section_path` must be determined from `CONTENT_METADATA` based on page ranges.

Annotation sources:
- `front_matter`
- `parts`
- `chapters`
- `sections`
- `subsections`

Leaf annotation selection rule:
- a chunk is annotated by its `page_start`
- the leaf section is chosen as the deepest node from `CONTENT_METADATA` whose range covers `page_start`
- depth priority:
  - `subsection`
  - `section`
  - `chapter`
  - `part`
  - `front_matter`

`section_path` selection rule:
- `section_path` must be an ordered path from the highest available level down to the leaf node;
- the path must be built from `CONTENT_METADATA` titles, not from chunk text;
- for the same `page_start`, the same path from `CONTENT_METADATA` must be reproduced deterministically.

If there is no subsection for `page_start`:
- use section;
If there is no section:
- use chapter;
If there is no chapter:
- use part or front matter title.

Path construction rules:
- `section_path` must be built top-down;
- each next path level must be selected only within the already selected parent node;
- if `page_start` falls into `front_matter`, `section_path` must contain only the title of the front matter item;
- if `page_start` falls into a chapter without a `part`, the path must start with the chapter title;
- if `page_start` falls into a chapter inside a `part`, the path must include `part title`, then `chapter title`, then deeper levels when present;
- if `CONTENT_METADATA` ranges overlap at the same level, the implementation must choose the earliest matching node in `CONTENT_METADATA` source order;
- if no match exists at some level, deeper levels without a parent match must not be included in the path;
- if no match is found for `page_start` at any level, that is a hard error and the chunker must fail.

## 16. Determinism
Identical:
- `PAGES`
- `BOOK_METADATA`
- `CONTENT_METADATA`
- `CONFIG.chunking.target_tokens`
- `CONFIG.chunking.overlap_ratio`
- `CONFIG.chunking.chunking_version`
- `CONFIG.sentence_segmentation.library`
- `CONFIG.sentence_segmentation.library_version`
- `CONFIG.sentence_segmentation.language`
- `CONFIG.tokenizer.library`
- `CONFIG.tokenizer.source`
- `CONFIG.tokenizer.revision`, if the field is present

must produce identical:
- sequence of chunks
- `text`
- `page_start/page_end`
- `section_title`
- `section_path`
- `content_hash`

## 17. Versioning
`schema_version` refers to the payload contract.
`chunking_version` refers to fixed chunker behavior.

Changing `chunking_version` is mandatory for any change to:
- sentence segmentation rules;
- tokenizer artifact;
- normalization rules;
- document stream construction;
- overlap rules;
- chunk assembly rules;
- section annotation rules.

## 18. Non-Goals
The fixed chunker must not:
- reconstruct book structure from text;
- attempt to semantic-merge adjacent chunks;
- apply heuristic title extraction from chunk text;
- remove extraction artifacts beyond the normalization policy;
- force chunk boundaries to match `CONTENT_METADATA` section boundaries;
