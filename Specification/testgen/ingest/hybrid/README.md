# Hybrid Ingest Testgen Layout

This directory mirrors the structure of hybrid ingest executable tests.

Current repository rule:

- keep hybrid ingest test-generation specs flat in this directory
- do not add an extra `common/` layer

Use future `fixed/` or `structural/` subdirectories only if generated tests
must assert on profile-specific semantics.
