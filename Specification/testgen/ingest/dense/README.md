# Dense Ingest Testgen Layout

This directory mirrors the structure of dense ingest executable tests.

Current repository rule:

- keep dense ingest test-generation specs flat in this directory
- do not add an extra `common/` layer

Use future `fixed/` or `structural/` subdirectories only if generated tests
must assert on profile-specific semantics.
