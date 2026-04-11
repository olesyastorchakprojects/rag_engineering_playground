#!/usr/bin/env python3
import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
import _hybrid_testlib as lib  # noqa: E402


def load_schema(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_schema_shape(parsed: dict, schema: dict) -> None:
    require(schema.get("type") == "object", "config schema must be object")
    require("properties" in schema, "config schema missing properties")
    required_top = schema.get("required", [])
    for key in required_top:
        require(key in parsed, f"schema-required top-level section missing {key}")


def validate_contract(parsed: dict) -> None:
    kind = parsed["sparse"]["strategy"]["kind"]
    version = parsed["sparse"]["strategy"]["version"]
    require(kind in {"bag_of_words", "bm25_like"}, "unsupported sparse.strategy.kind")
    require(version == "v1", "unsupported sparse.strategy.version")
    lib.validate_base_collection_name(parsed["qdrant"]["collection"]["name"])
    require(
        parsed["qdrant"]["collection"]["dense_vector_name"] != parsed["qdrant"]["collection"]["sparse_vector_name"],
        "dense_vector_name must differ from sparse_vector_name",
    )
    has_bow = "bag_of_words" in parsed["sparse"]
    has_bm25 = "bm25_like" in parsed["sparse"]
    require(not (has_bow and has_bm25), "strategy blocks must be mutually exclusive")
    if kind == "bag_of_words":
        require(has_bow, "selected bag_of_words but sparse.bag_of_words missing")
        require(parsed["sparse"]["bag_of_words"]["document"] == "term_frequency", "invalid sparse.bag_of_words.document")
        require(parsed["sparse"]["bag_of_words"]["query"] == "binary_presence", "invalid sparse.bag_of_words.query")
    if kind == "bm25_like":
        require(has_bm25, "selected bm25_like but sparse.bm25_like missing")
        block = parsed["sparse"]["bm25_like"]
        require(block["document"] == "bm25_document_weight", "invalid sparse.bm25_like.document")
        require(block["query"] == "bm25_query_weight", "invalid sparse.bm25_like.query")
        require(block["k1"] > 0.0, "bm25_like.k1 must be positive")
        require(0.0 <= block["b"] <= 1.0, "bm25_like.b must be in [0,1]")


def run_case(case: dict, canonical_text: str, canonical_config: dict, schema: dict):
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        config_path = Path(tmp_dir_str) / "config.toml"
        if case["kind"] == "negative_parse":
            config_path.write_text(case["raw_text"], encoding="utf-8")
        else:
            mutated = copy.deepcopy(canonical_config)
            case["mutate"](mutated)
            config_path.write_text(lib.dump_toml_document(mutated), encoding="utf-8")
        layer = "none"
        try:
            try:
                parsed = lib.load_toml(config_path)
            except Exception as exc:
                if case["kind"] == "negative_parse":
                    return True, {"layer": "parse", "error": str(exc)}
                return False, {"layer": "parse", "error": str(exc)}
            layer = "schema"
            validate_schema_shape(parsed, schema)
            validate_contract(parsed)
            if case["kind"] == "positive":
                return True, {"layer": "none", "error": ""}
            return False, {"layer": layer, "error": "expected validation failure but case passed"}
        except Exception as exc:
            if case["kind"] == "negative_schema":
                return True, {"layer": layer, "error": str(exc)}
            return False, {"layer": layer, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-template", type=Path, required=True)
    parser.add_argument("--config-schema", type=Path, required=True)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    canonical_text = args.config_template.read_text(encoding="utf-8")
    canonical_config = lib.load_toml(args.config_template)
    schema = load_schema(args.config_schema)

    cases = [
        {"name": "canonical_config", "kind": "positive", "mutate": lambda cfg: None},
        {"name": "broken_toml_syntax", "kind": "negative_parse", "raw_text": canonical_text + "[broken\n"},
        {
            "name": "missing_sparse_strategy",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["sparse"].pop("strategy"),
        },
        {
            "name": "unsupported_sparse_strategy_kind",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["sparse"]["strategy"].__setitem__("kind", "unknown_strategy"),
        },
        {
            "name": "both_strategy_blocks_present",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["sparse"].__setitem__(
                "bm25_like",
                {
                    "document": "bm25_document_weight",
                    "query": "bm25_query_weight",
                    "k1": 1.2,
                    "b": 0.75,
                    "idf_smoothing": "default",
                },
            ),
        },
        {
            "name": "missing_selected_bow_block",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["sparse"].pop("bag_of_words"),
        },
        {
            "name": "missing_selected_bm25_block",
            "kind": "negative_schema",
            "mutate": lambda cfg: (
                cfg["sparse"]["strategy"].__setitem__("kind", "bm25_like"),
                cfg["sparse"].pop("bag_of_words"),
            ),
        },
        {
            "name": "base_name_ends_with_bow",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["qdrant"]["collection"].__setitem__("name", "chunks_hybrid_bow"),
        },
        {
            "name": "base_name_ends_with_bm25",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["qdrant"]["collection"].__setitem__("name", "chunks_hybrid_bm25"),
        },
        {
            "name": "base_name_ends_with_underscore",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["qdrant"]["collection"].__setitem__("name", "chunks_hybrid_"),
        },
        {
            "name": "vector_names_equal",
            "kind": "negative_schema",
            "mutate": lambda cfg: cfg["qdrant"]["collection"].__setitem__("sparse_vector_name", cfg["qdrant"]["collection"]["dense_vector_name"]),
        },
    ]

    failed = 0
    passed = 0
    for case in cases:
        ok, details = run_case(case, canonical_text, canonical_config, schema)
        if ok:
            passed += 1
            print(f"OK [{case['name']}]")
        else:
            failed += 1
            print(f"FAIL [{case['name']}]")
            print(f"case_kind={case['kind']}")
            print(f"layer={details['layer']}")
            print(f"error={details['error']}")
    print(f"cases={len(cases)} failed={failed} passed={passed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
