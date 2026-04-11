# Embedding Service Contract

This document defines the reusable external contract for the embedding service used by ingest and retrieval.

## Request

- method: `POST`
- url = `<OLLAMA_URL>` + `/api/embed`
- body format: JSON object

Required request fields:

- `model`
- `input`

Request semantics:

- `model` must be a non-empty string
- `input` must be a non-empty array of strings

## Response

Successful response:

- HTTP status `2xx`
- body must parse as JSON object
- body must contain field `embeddings`
- `embeddings` must be an array
- each element of `embeddings` must be an array of JSON numbers

Invalid response:

- HTTP status is not `2xx`
- body does not parse as JSON object
- `embeddings` is missing
- `embeddings` is not an array
- any embedding item is not an array of JSON numbers

## Response Shape Validation

The caller must validate:

- the number of returned embeddings matches the number of input strings
- the dimension of each returned embedding matches the expected embedding dimension for the current caller

These validations are caller-specific because the expected embedding dimension and request cardinality come from the caller's own configuration and request context.
