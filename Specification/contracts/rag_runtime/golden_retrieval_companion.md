# Golden Retrieval Companion Contract

## Purpose

This document defines the data contract for the unified golden retrieval companion file consumed by `rag_runtime`.

The companion file is the canonical runtime-owned input for per-request retrieval quality evaluation in batch mode.

It exists to provide one schema-driven source of truth for:

- question-to-golden lookup by raw batch question text;
- soft relevant chunk ids;
- strict relevant chunk ids;
- graded relevance labels used for ranking metrics.

This contract defines what the companion file means semantically.
Runtime loading and validation must follow this contract.

## Scope

This document defines:

- the semantic purpose of the companion file;
- the required top-level fields;
- the per-question record shape;
- field semantics;
- invariants.

This document does not define:

- CLI behavior;
- orchestration ownership;
- retrieval metric formulas;
- Rust module layout;
- observability attribute names.

## Required Top-Level Fields

The companion file contains the following required top-level fields:

- `version`
- `scenario`
- `questions`

## Top-Level Field Semantics

### `version`

- version of the companion-file contract;
- for the current version, the value must be `v1`.

### `scenario`

- scenario identifier for the companion file;
- for the current version, valid values are:
  - `fixed`
  - `structural`

### `questions`

- ordered list of per-question golden retrieval records;
- each item must follow the per-question record contract defined below.

## Per-Question Record Structure

Each item in `questions` contains:

- `question_id`
- `question`
- `soft_positive_chunk_ids`
- `strict_positive_chunk_ids`
- `graded_relevance`

## Per-Question Field Semantics

### `question_id`

- stable identifier for one question entry inside the companion file.

### `question`

- the exact raw question text used for runtime lookup in batch mode;
- runtime question-to-golden matching uses this field as the lookup key;
- the value is matched before runtime normalization;
- this value must be unique within one companion file.

### `soft_positive_chunk_ids`

- ordered list of chunk ids considered relevant under the soft relevance definition for this question;
- this list defines the gold set used by soft recall and soft reciprocal-rank style metrics.

### `strict_positive_chunk_ids`

- ordered list of chunk ids considered relevant under the strict relevance definition for this question;
- this list defines the gold set used by strict recall and strict reciprocal-rank style metrics.

### `graded_relevance`

- ordered list of graded relevance labels for this question;
- each item defines one `chunk_id` and its graded relevance score;
- this list is the gold source for graded ranking metrics such as nDCG-style metrics.

## Graded Relevance Item Structure

Each item in `graded_relevance` contains:

- `chunk_id`
- `score`

### `chunk_id`

- identifier of one chunk that has an explicit graded relevance label for this question.

### `score`

- graded relevance score for the corresponding chunk;
- for the current version, valid values are:
  - `0.0`
  - `0.5`
  - `1.0`

## Invariants

The companion file must satisfy all of the following invariants:

- `questions` must contain at least one item;
- `question` values must be unique within one file;
- `question_id` values must be unique within one file;
- `soft_positive_chunk_ids` must not contain duplicates within the same question entry;
- `strict_positive_chunk_ids` must not contain duplicates within the same question entry;
- `graded_relevance[*].chunk_id` values must be unique within the same question entry;
- every chunk id listed in `soft_positive_chunk_ids` must appear in `graded_relevance`;
- every chunk id listed in `strict_positive_chunk_ids` must appear in `graded_relevance`;
- every chunk id listed in `strict_positive_chunk_ids` must also appear in `soft_positive_chunk_ids`.

## Example Shape

```json
{
  "version": "v1",
  "scenario": "fixed",
  "questions": [
    {
      "question_id": "q1_tcp_reliable_over_ip",
      "question": "Why is TCP considered a layer that creates a reliable channel on top of unreliable IP, and what mechanisms does it use to compensate for packet loss, duplication, and reordering?",
      "soft_positive_chunk_ids": [
        "chunk-a",
        "chunk-b"
      ],
      "strict_positive_chunk_ids": [
        "chunk-a"
      ],
      "graded_relevance": [
        {
          "chunk_id": "chunk-a",
          "score": 1.0
        },
        {
          "chunk_id": "chunk-b",
          "score": 0.5
        },
        {
          "chunk_id": "chunk-c",
          "score": 0.0
        }
      ]
    }
  ]
}
```
