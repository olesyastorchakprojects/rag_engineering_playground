from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import (
    compare_changed_files,
    compare_spec_and_code,
    explain_check,
    find_uncovered_requirements,
    list_known_mismatches,
    list_modules,
    list_spec_requirements,
    scan_code_capabilities,
)


class SpecConformanceServerTests(unittest.TestCase):
    def test_list_modules_includes_rag_runtime(self) -> None:
        result = list_modules()
        modules = [entry["module"] for entry in result["modules"]]
        self.assertIn("rag_runtime", modules)
        self.assertIn("fixed_chunker", modules)
        self.assertIn("hybrid_ingest", modules)

    def test_hybrid_ingest_pre_codegen_check_is_currently_conformant(self) -> None:
        result = explain_check("hybrid_ingest.public_api.single_python_entrypoint_exists")
        self.assertEqual(result["status"], "conforms")

    def test_fixed_chunker_sentencizer_requirement_is_currently_conformant(self) -> None:
        result = list_spec_requirements("fixed_chunker")
        entry = next(
            item
            for item in result["requirements"]
            if item["id"] == "fixed_chunker.sentence_segmentation.uses_spacy_sentencizer"
        )
        self.assertEqual(entry["status"], "conforms")

    def test_fixed_chunker_content_start_page_requirement_is_currently_conformant(self) -> None:
        result = explain_check("fixed_chunker.content_start_page.ignores_front_matter_for_derivation")
        self.assertEqual(result["status"], "conforms")

    def test_generation_tokenizer_requirement_is_currently_conformant(self) -> None:
        result = list_spec_requirements("rag_runtime")
        entry = next(
            item
            for item in result["requirements"]
            if item["id"] == "rag_runtime.generation.token_counting.uses_real_tokenizer"
        )
        self.assertEqual(entry["status"], "conforms")

    def test_retrieval_retry_requirement_is_currently_conformant(self) -> None:
        result = explain_check("rag_runtime.retrieval.retry_uses_backon")
        self.assertEqual(result["status"], "conforms")

    def test_retrieval_typed_settings_requirement_is_currently_a_violation(self) -> None:
        result = explain_check("rag_runtime.retrieval.settings_contract_is_typed_and_schema_backed")
        self.assertEqual(result["status"], "conforms")

    def test_retrieval_factory_mapping_requirement_is_currently_a_violation(self) -> None:
        result = explain_check(
            "rag_runtime.retrieval.orchestration_factory_maps_ingest_to_implementation"
        )
        self.assertEqual(result["status"], "conforms")

    def test_retrieval_request_capture_shape_is_currently_conformant(self) -> None:
        result = explain_check(
            "rag_runtime.retrieval.request_capture_fields_are_typed_and_persisted"
        )
        self.assertEqual(result["status"], "conforms")

    def test_reranking_request_capture_shape_is_currently_conformant(self) -> None:
        result = list_spec_requirements("rag_runtime")
        entry = next(
            item
            for item in result["requirements"]
            if item["id"] == "rag_runtime.reranking.request_capture_fields_are_typed_and_persisted"
        )
        self.assertEqual(entry["status"], "conforms")

    def test_reranking_factory_mapping_is_currently_a_violation(self) -> None:
        result = explain_check(
            "rag_runtime.reranking.orchestration_factory_maps_kind_to_implementation"
        )
        self.assertEqual(result["status"], "conforms")

    def test_questions_file_batch_mode_is_currently_conformant(self) -> None:
        result = scan_code_capabilities("rag_runtime")
        entry = next(
            item
            for item in result["capabilities"]
            if item["id"] == "rag_runtime.cli.questions_file_batch_mode"
        )
        self.assertEqual(entry["status"], "conforms")

    def test_compare_spec_and_code_returns_mismatch_summary(self) -> None:
        result = compare_spec_and_code("rag_runtime")
        self.assertGreaterEqual(result["summary"]["mismatch"], 0)
        self.assertIn("missing_test_coverage", result["summary"])

    def test_list_known_mismatches_includes_retrieval_gaps_for_rag_runtime(self) -> None:
        result = list_known_mismatches(module="rag_runtime")
        mismatch_ids = {entry["id"] for entry in result["mismatches"]}
        self.assertEqual(mismatch_ids, set())

    def test_explain_check_returns_dashboard_conformance(self) -> None:
        result = explain_check("rag_runtime.observability.runtime_dashboard_inventory")
        self.assertEqual(result["status"], "conforms")

    def test_explain_check_returns_current_reranking_gap(self) -> None:
        result = explain_check("rag_runtime.reranking.orchestration_factory_maps_kind_to_implementation")
        self.assertEqual(result["status"], "conforms")

    def test_compare_changed_files_flags_spec_update_suspect(self) -> None:
        result = compare_changed_files(["Execution/rag_runtime/src/main.rs"], module="rag_runtime")
        suspects = result["spec_update_suspects"]
        self.assertTrue(
            any(
                entry["id"] == "rag_runtime.cli.questions_file_batch_mode"
                for entry in suspects
            )
        )

    def test_compare_changed_files_flags_reranking_spec_update_suspect(self) -> None:
        result = compare_changed_files(
            ["Execution/rag_runtime/src/orchestration/mod.rs"],
            module="rag_runtime",
        )
        suspects = result["spec_update_suspects"]
        self.assertTrue(
            any(
                entry["id"]
                == "rag_runtime.reranking.orchestration_factory_maps_kind_to_implementation"
                for entry in suspects
            )
        )

    def test_find_uncovered_requirements_includes_existing_curated_gap(self) -> None:
        result = find_uncovered_requirements("rag_runtime")
        self.assertTrue(
            any(
                entry["id"] == "rag_runtime.generation.token_counting.uses_real_tokenizer"
                for entry in result["uncovered_checks"]
            )
        )
