# Chunker Testgen

This folder is split by chunker test type:

- `common/`
  - tests that apply to any chunker variant
- `structural/`
  - tests specific to the metadata-driven structural chunker
- `fixed/`
  - tests specific to the fixed sentence-based chunker

Current layout:

- `common/truth_consistency.md`
- `common/sanitation.md`
- `common/determinism.md`
- `common/schema_validation.md`
- `structural/span_quality.md`
- `structural/structure.md`
- `structural/synthetic_regression.md`
- `fixed/page_mapping.md`
- `fixed/overlap.md`
- `fixed/synthetic_regression.md`
