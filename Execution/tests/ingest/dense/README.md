# Dense Ingest Test Layout

This directory contains dense ingest executable tests.

Current repository rule:

- keep dense ingest tests flat in this directory
- do not add an extra `common/` layer

Use future `fixed/` or `structural/` subdirectories only if a test genuinely
depends on chunk-source-specific semantics.
