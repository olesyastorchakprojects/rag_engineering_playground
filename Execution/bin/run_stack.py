#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_RUNTIME_CONFIG = REPO_ROOT / "Execution" / "rag_runtime" / "rag_runtime.toml"
DEFAULT_EVAL_CONFIG = REPO_ROOT / "Execution" / "evals" / "eval_engine.toml"
QUERY_DATASETS_ROOT = REPO_ROOT / "Evidence" / "evals" / "datasets"
EVAL_RUNS_ROOT = REPO_ROOT / "Evidence" / "evals" / "runs"
DEFAULT_QUESTION_SET_ID = "default"
DEFAULT_QUERIES_FILE = QUERY_DATASETS_ROOT / DEFAULT_QUESTION_SET_ID / "questions.txt"
RAG_RUNTIME_MANIFEST = REPO_ROOT / "Execution" / "rag_runtime" / "Cargo.toml"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"

DENSE_INGEST_PROFILE_PATHS = {
    "fixed": REPO_ROOT / "Execution" / "ingest" / "dense" / "profiles" / "fixed.toml",
    "structural": REPO_ROOT / "Execution" / "ingest" / "dense" / "profiles" / "structural.toml",
}

HYBRID_INGEST_PROFILE_PATHS = {
    ("fixed", "bag_of_words"): REPO_ROOT
    / "Execution"
    / "ingest"
    / "hybrid"
    / "configs"
    / "fixed_bow.toml",
    ("fixed", "bm25_like"): REPO_ROOT
    / "Execution"
    / "ingest"
    / "hybrid"
    / "configs"
    / "fixed_bm25.toml",
    ("structural", "bag_of_words"): REPO_ROOT
    / "Execution"
    / "ingest"
    / "hybrid"
    / "configs"
    / "structural_bow.toml",
    ("structural", "bm25_like"): REPO_ROOT
    / "Execution"
    / "ingest"
    / "hybrid"
    / "configs"
    / "structural_bm25.toml",
}

EVAL_CHUNKS_PATHS = {
    "fixed": REPO_ROOT
    / "Evidence"
    / "parsing"
    / "understanding_distributed_systems"
    / "chunks"
    / "fixed_chunks.jsonl",
    "structural": REPO_ROOT
    / "Evidence"
    / "parsing"
    / "understanding_distributed_systems"
    / "chunks"
    / "chunks.jsonl",
}

GOLDEN_RETRIEVALS_PATHS = {
    "fixed": QUERY_DATASETS_ROOT / DEFAULT_QUESTION_SET_ID / "fixed_golden_retrievals.json",
    "structural": QUERY_DATASETS_ROOT / DEFAULT_QUESTION_SET_ID / "structural_golden_retrievals.json",
}

LAUNCHER_RUNTIME_MODEL_OPTIONS = (
    {
        "label": "local | qwen2.5:1.5b-instruct-ctx32k | http://localhost:11434",
        "transport_kind": "ollama",
        "model_name": "qwen2.5:1.5b-instruct-ctx32k",
        "provider_label": "local",
        "endpoint": "http://localhost:11434",
    },
    {
        "label": "together | openai/gpt-oss-20b | https://api.together.xyz",
        "transport_kind": "openai",
        "model_name": "openai/gpt-oss-20b",
        "provider_label": "together",
        "endpoint": "https://api.together.xyz",
    },
    {
        "label": "together | openai/gpt-oss-120b | https://api.together.xyz",
        "transport_kind": "openai",
        "model_name": "openai/gpt-oss-120b",
        "provider_label": "together",
        "endpoint": "https://api.together.xyz",
    },
)

LAUNCHER_JUDGE_MODEL_OPTIONS = (
    {
        "label": "local | qwen2.5:1.5b-instruct-ctx32k | http://localhost:11434",
        "provider": "ollama",
        "model_name": "qwen2.5:1.5b-instruct-ctx32k",
        "provider_label": "local",
        "endpoint": "http://localhost:11434",
    },
    {
        "label": "together | openai/gpt-oss-20b | https://api.together.xyz",
        "provider": "together",
        "model_name": "openai/gpt-oss-20b",
        "provider_label": "together",
        "endpoint": "https://api.together.xyz",
    },
    {
        "label": "together | openai/gpt-oss-120b | https://api.together.xyz",
        "provider": "together",
        "model_name": "openai/gpt-oss-120b",
        "provider_label": "together",
        "endpoint": "https://api.together.xyz",
    },
)

LAUNCHER_RUN_MODES = (
    ("runtime only", "runtime_only"),
    ("evals only", "evals_only"),
    ("runtime + evals", "runtime_and_evals"),
)

RERANKER_KIND_ALIASES = {
    "pass_through": "pass_through",
    "pass-through": "pass_through",
    "heuristic": "heuristic",
    "cross_encoder": "cross_encoder",
    "cross-encoder": "cross_encoder",
}

RERANKER_TRANSPORT_ALIASES = {
    "mixedbread-ai": "mixedbread-ai",
    "mixedbread_ai": "mixedbread-ai",
    "voyageai": "voyageai",
}

RETRIEVER_KIND_ALIASES = {
    "dense": "dense",
    "hybrid": "hybrid",
}

SPARSE_STRATEGY_ALIASES = {
    "bag_of_words": "bag_of_words",
    "bm25_like": "bm25_like",
}

RAG_RUNTIME_SCENARIOS = {
    "fixed-cross-encoder": {
        "chunk_profile": "fixed",
        "reranker": "cross_encoder",
    },
    "fixed-heuristic": {
        "chunk_profile": "fixed",
        "reranker": "heuristic",
    },
    "fixed-pass-through": {
        "chunk_profile": "fixed",
        "reranker": "pass_through",
    },
    "structural-cross-encoder": {
        "chunk_profile": "structural",
        "reranker": "cross_encoder",
    },
    "structural-heuristic": {
        "chunk_profile": "structural",
        "reranker": "heuristic",
    },
    "structural-pass-through": {
        "chunk_profile": "structural",
        "reranker": "pass_through",
    },
}

EVAL_ENGINE_SCENARIOS = {
    "fixed": {
        "chunk_profile": "fixed",
    },
    "structural": {
        "chunk_profile": "structural",
    },
}


class LauncherError(RuntimeError):
    pass


class DatasetBundle(dict[str, Any]):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Thin launcher for rag_runtime and eval engine with profile-aware inputs."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved command and inputs without executing anything.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print expanded launcher/debug details such as fully resolved commands.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    launch = subparsers.add_parser(
        "launch",
        help="Interactive launcher that assembles effective runtime/eval configs and optionally runs them.",
    )
    launch.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    launch.add_argument("--eval-config", type=Path, default=DEFAULT_EVAL_CONFIG)

    rag = subparsers.add_parser("rag-runtime", help="Launch rag_runtime with resolved inputs.")
    rag.add_argument("--scenario", choices=sorted(RAG_RUNTIME_SCENARIOS))
    rag.add_argument("--chunk-profile", choices=sorted(DENSE_INGEST_PROFILE_PATHS), default="structural")
    rag.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    rag.add_argument(
        "--ingest-config",
        type=Path,
        help="Explicit ingest config path. Overrides --chunk-profile mapping.",
    )
    rag.add_argument(
        "--questions-file",
        type=Path,
        help="Explicit newline-delimited questions file.",
    )
    rag.add_argument(
        "--golden-retrievals-file",
        type=Path,
        help="Explicit golden retrievals JSON file. Overrides the default derived from --chunk-profile.",
    )
    rag.add_argument(
        "--reranker",
        choices=sorted(RERANKER_KIND_ALIASES),
        help="Override reranking.kind in a temporary rag_runtime config copy.",
    )
    rag.add_argument(
        "--reranker-transport",
        choices=sorted(RERANKER_TRANSPORT_ALIASES),
        help="Override reranking.cross_encoder.transport_kind in a temporary rag_runtime config copy.",
    )

    eval_engine = subparsers.add_parser(
        "eval-engine", help="Launch eval orchestrator with profile-aware chunks path."
    )
    eval_engine.add_argument("--scenario", choices=sorted(EVAL_ENGINE_SCENARIOS))
    eval_engine.add_argument("--chunk-profile", choices=sorted(EVAL_CHUNKS_PATHS), default="structural")
    eval_engine.add_argument(
        "--chunks-path",
        type=Path,
        help="Explicit chunks.jsonl path. Overrides --chunk-profile mapping.",
    )
    eval_engine.add_argument("--eval-config", type=Path, default=DEFAULT_EVAL_CONFIG)
    eval_engine.add_argument(
        "--run-type",
        choices=("continuous", "nightly", "experiment"),
        default="experiment",
    )
    eval_engine.add_argument("--postgres-url")
    eval_engine.add_argument("--tracing-endpoint")
    eval_engine.add_argument("--resume-run-id")
    eval_engine.add_argument(
        "--resume-failed-run",
        action="store_true",
        help="Select and resume one locally recorded failed eval run.",
    )

    show_config = subparsers.add_parser(
        "show-config",
        help="Print a saved effective runtime/eval config from Postgres by run id.",
    )
    show_config.add_argument("--postgres-url")
    show_group = show_config.add_mutually_exclusive_group(required=True)
    show_group.add_argument("--runtime-run-id")
    show_group.add_argument("--eval-run-id")

    try_enable_argcomplete(parser)
    return parser.parse_args()


def try_enable_argcomplete(parser: argparse.ArgumentParser) -> None:
    try:
        import argcomplete  # type: ignore
    except ModuleNotFoundError:
        return
    argcomplete.autocomplete(parser)


def main() -> int:
    args = parse_args()
    try:
        if args.command == "launch":
            return run_interactive_launch(args)
        if args.command == "rag-runtime":
            return run_rag_runtime(args)
        if args.command == "eval-engine":
            return run_eval_engine(args)
        if args.command == "show-config":
            return run_show_config(args)
        raise LauncherError(f"unsupported command: {args.command}")
    except LauncherError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


def run_rag_runtime(args: argparse.Namespace) -> int:
    scenario = RAG_RUNTIME_SCENARIOS.get(args.scenario, {})
    effective_chunk_profile = scenario.get("chunk_profile", args.chunk_profile)
    runtime_config = resolve_existing_path(args.runtime_config, "runtime config")
    ingest_config = resolve_existing_path(
        args.ingest_config or DENSE_INGEST_PROFILE_PATHS[effective_chunk_profile],
        "ingest config",
    )
    questions_path = resolve_existing_path(
        args.questions_file or DEFAULT_QUERIES_FILE,
        "questions file",
    )
    golden_retrievals_path = resolve_existing_path(
        args.golden_retrievals_file or GOLDEN_RETRIEVALS_PATHS[effective_chunk_profile],
        "golden retrievals file",
    )
    reranker_raw = args.reranker or scenario.get("reranker")
    reranker_kind = normalize_reranker_kind(reranker_raw) if reranker_raw else None
    reranker_transport = (
        normalize_reranker_transport(args.reranker_transport) if args.reranker_transport else None
    )

    if reranker_kind is None:
        command = build_rag_runtime_command(runtime_config, ingest_config, questions_path, golden_retrievals_path)
        print_rag_runtime_plan(
            runtime_config,
            ingest_config,
            questions_path,
            golden_retrievals_path,
            None,
            None,
            command,
            scenario_name=args.scenario,
        )
        return maybe_run(command, args.dry_run)

    runtime_data = load_toml(runtime_config)
    runtime_data.setdefault("reranking", {})
    reranking = require_dict(runtime_data["reranking"], "reranking")
    reranking["kind"] = reranker_kind
    if reranker_kind == "cross_encoder" and "cross_encoder" not in reranking:
        raise LauncherError(
            "reranking.kind=cross_encoder requires the [reranking.cross_encoder] subtree "
            f"in {runtime_config}"
        )
    if reranker_kind != "cross_encoder" and reranker_transport is not None:
        raise LauncherError("--reranker-transport is only valid with --reranker cross_encoder")
    if reranker_kind == "cross_encoder" and reranker_transport is not None:
        cross_encoder = require_dict(reranking["cross_encoder"], "reranking.cross_encoder")
        cross_encoder["transport_kind"] = reranker_transport

    with tempfile.TemporaryDirectory(prefix="run_stack_rag_runtime_") as tmp_dir:
        temp_runtime_config = Path(tmp_dir) / "rag_runtime.override.toml"
        temp_runtime_config.write_text(dump_toml_document(runtime_data), encoding="utf-8")
        command = build_rag_runtime_command(temp_runtime_config, ingest_config, questions_path, golden_retrievals_path)
        print_rag_runtime_plan(
            runtime_config,
            ingest_config,
            questions_path,
            golden_retrievals_path,
            reranker_kind,
            reranker_transport,
            command,
            temp_runtime_config=temp_runtime_config,
            scenario_name=args.scenario,
        )
        return maybe_run(command, args.dry_run)


def run_interactive_launch(args: argparse.Namespace) -> int:
    runtime_config = resolve_existing_path(args.runtime_config, "runtime config")
    eval_config = resolve_existing_path(args.eval_config, "eval config")
    run_mode_label, run_mode = prompt_choice_pairs("Run mode", LAUNCHER_RUN_MODES)
    chunk_profile = prompt_choice(
        "Chunking strategy",
        ["structural", "fixed"],
    )
    retriever_kind: str | None = None
    sparse_strategy: str | None = None
    reranker_kind: str | None = None
    reranker_transport: str | None = None
    runtime_model: dict[str, str] | None = None
    judge_model: dict[str, str] | None = None
    question_set: str | None = None
    question_set_title: str | None = None
    question_count: int | None = None

    if run_mode in ("runtime_only", "runtime_and_evals"):
        retriever_kind = prompt_choice("Retriever", ["dense", "hybrid"])
        if retriever_kind == "hybrid":
            sparse_strategy = prompt_choice("Sparse strategy", ["bag_of_words", "bm25_like"])
        reranker_kind = prompt_choice(
            "Reranker",
            ["pass_through", "heuristic", "cross_encoder"],
        )
        if reranker_kind == "cross_encoder":
            reranker_transport = prompt_choice(
                "Cross-encoder transport",
                ["mixedbread-ai", "voyageai"],
            )
        runtime_model = prompt_option_dict("Chat model config", LAUNCHER_RUNTIME_MODEL_OPTIONS)
        dataset_bundle = prompt_dataset_bundle("Question set")
        question_set = str(dataset_bundle["id"])
        question_set_title = str(dataset_bundle["title"])
        question_count = int(dataset_bundle["question_count"])

    if run_mode in ("evals_only", "runtime_and_evals"):
        judge_model = prompt_option_dict("Judge model config", LAUNCHER_JUDGE_MODEL_OPTIONS)
    resume_run_id: str | None = None
    if run_mode in ("evals_only", "runtime_and_evals"):
        eval_run_mode = prompt_choice_pairs(
            "Eval run mode",
            (
                ("new run", "new"),
                ("resume failed run", "resume_failed"),
            ),
        )[1]
        if eval_run_mode == "resume_failed":
            resume_selection = prompt_failed_eval_run("Failed eval run", list_failed_eval_runs())
            resume_run_id = str(resume_selection["run_id"])

    ingest_config: Path | None = None
    collection_name: str | None = None
    if retriever_kind == "dense":
        ingest_config = resolve_existing_path(DENSE_INGEST_PROFILE_PATHS[chunk_profile], "ingest config")
    elif retriever_kind == "hybrid":
        assert sparse_strategy is not None
        ingest_config = resolve_existing_path(
            HYBRID_INGEST_PROFILE_PATHS[(chunk_profile, sparse_strategy)],
            "ingest config",
        )
    if ingest_config is not None:
        ingest_data = load_toml(ingest_config)
        qdrant = require_dict(ingest_data.get("qdrant"), "qdrant")
        collection = require_dict(qdrant.get("collection"), "qdrant.collection")
        collection_name = str(collection.get("name")) if collection.get("name") is not None else None

    chunks_path = resolve_existing_path(EVAL_CHUNKS_PATHS[chunk_profile], "chunks path")
    if question_set is not None:
        golden_retrievals_path = resolve_existing_path(
            dataset_golden_retrievals_path(question_set, chunk_profile),
            "golden retrievals file",
        )
    else:
        golden_retrievals_path = resolve_existing_path(
            GOLDEN_RETRIEVALS_PATHS[chunk_profile],
            "golden retrievals file",
        )
    questions_path: Path | None = None
    if question_set is not None:
        questions_path = resolve_existing_path(
            dataset_questions_path(question_set),
            "questions file",
        )

    runtime_data: dict[str, Any] | None = None
    if run_mode in ("runtime_only", "runtime_and_evals"):
        assert reranker_kind is not None
        assert runtime_model is not None
        assert retriever_kind is not None
        runtime_data = load_toml(runtime_config)
        retrieval = require_dict(runtime_data.setdefault("retrieval", {}), "retrieval")
        retrieval["kind"] = retriever_kind
        reranking = require_dict(runtime_data.setdefault("reranking", {}), "reranking")
        reranking["kind"] = reranker_kind
        if reranker_kind == "cross_encoder":
            cross_encoder = require_dict(
                reranking.setdefault("cross_encoder", {}),
                "reranking.cross_encoder",
            )
            cross_encoder["transport_kind"] = reranker_transport or "mixedbread-ai"
        generation = require_dict(runtime_data.setdefault("generation", {}), "generation")
        generation["transport_kind"] = runtime_model["transport_kind"]
        ollama_generation = require_dict(generation.setdefault("ollama", {}), "generation.ollama")
        openai_generation = require_dict(generation.setdefault("openai", {}), "generation.openai")
        if runtime_model["transport_kind"] == "ollama":
            ollama_generation["model_name"] = runtime_model["model_name"]
        else:
            openai_generation["model_name"] = runtime_model["model_name"]

    eval_data: dict[str, Any] | None = None
    if run_mode in ("evals_only", "runtime_and_evals"):
        assert judge_model is not None
        eval_data = load_toml(eval_config)
        judge = require_dict(eval_data.setdefault("judge", {}), "judge")
        judge["provider"] = judge_model["provider"]
        judge["model_name"] = judge_model["model_name"]

    artifact_dir = create_launcher_artifact_dir()
    effective_runtime_config = artifact_dir / "effective_rag_runtime.toml"
    effective_eval_config = artifact_dir / "effective_eval_engine.toml"
    if runtime_data is not None:
        effective_runtime_config.write_text(dump_toml_document(runtime_data), encoding="utf-8")
    if eval_data is not None:
        effective_eval_config.write_text(dump_toml_document(eval_data), encoding="utf-8")

    runtime_command: list[str] | None = None
    if run_mode in ("runtime_only", "runtime_and_evals"):
        assert ingest_config is not None
        runtime_command = build_rag_runtime_command(
            effective_runtime_config,
            ingest_config,
            questions_path,
            golden_retrievals_path,
        )
    env_values = load_dotenv(ROOT_ENV_PATH)
    eval_command: list[str] | None = None
    if run_mode in ("evals_only", "runtime_and_evals"):
        postgres_url = require_env_value(env_values, "POSTGRES_URL")
        tracing_endpoint = require_env_value(env_values, "TRACING_ENDPOINT")
        eval_command = [
            str(VENV_PYTHON),
            "-m",
            "Execution.evals.eval_orchestrator",
            "--postgres-url",
            postgres_url,
            "--run-type",
            "experiment",
            "--chunks-path",
            str(chunks_path),
            "--tracing-endpoint",
            tracing_endpoint,
            "--eval-config",
            str(effective_eval_config),
        ]

    print_launcher_summary(
        run_mode=run_mode_label,
        chunk_profile=chunk_profile,
        ingest_config=ingest_config,
        chunks_path=chunks_path,
        golden_retrievals_path=golden_retrievals_path,
        collection_name=collection_name,
        reranker_kind=reranker_kind,
        reranker_transport=reranker_transport,
        retriever_kind=retriever_kind,
        sparse_strategy=sparse_strategy,
        runtime_model=runtime_model["label"] if runtime_model is not None else None,
        judge_model=judge_model["label"] if judge_model is not None else None,
        question_set=question_set,
        question_set_title=question_set_title,
        question_count=question_count,
        questions_path=questions_path,
        effective_runtime_config=effective_runtime_config,
        effective_eval_config=effective_eval_config,
        runtime_command=runtime_command,
        eval_command=eval_command,
        verbose=args.verbose,
    )

    final_action = prompt_choice_pairs("Action", (("launch", "launch"), ("cancel", "cancel")))[1]
    if final_action == "cancel":
        print("launch canceled", file=sys.stderr)
        return 0
    if args.dry_run:
        return 0

    if run_mode in ("runtime_only", "runtime_and_evals"):
        assert runtime_command is not None
        runtime_result = maybe_run(runtime_command, False)
        if runtime_result != 0:
            return runtime_result
    if run_mode in ("evals_only", "runtime_and_evals"):
        assert eval_command is not None
        if resume_run_id:
            eval_command.extend(["--resume-run-id", resume_run_id])
        eval_result = maybe_run(eval_command, False)
        if eval_result != 0:
            return eval_result
    return 0


def run_eval_engine(args: argparse.Namespace) -> int:
    scenario = EVAL_ENGINE_SCENARIOS.get(args.scenario, {})
    effective_chunk_profile = scenario.get("chunk_profile", args.chunk_profile)
    env_values = load_dotenv(ROOT_ENV_PATH)
    if args.resume_run_id and args.resume_failed_run:
        raise LauncherError("--resume-run-id and --resume-failed-run are mutually exclusive")
    chunks_path = resolve_existing_path(
        args.chunks_path or EVAL_CHUNKS_PATHS[effective_chunk_profile],
        "chunks path",
    )
    eval_config = resolve_existing_path(args.eval_config, "eval config")

    postgres_url = args.postgres_url or require_env_value(env_values, "POSTGRES_URL")
    tracing_endpoint = args.tracing_endpoint or require_env_value(env_values, "TRACING_ENDPOINT")
    judge_provider, judge_base_url, judge_model = resolve_judge_runtime(eval_config, env_values)
    resume_run_id = args.resume_run_id
    if args.resume_failed_run:
        resume_selection = prompt_failed_eval_run("Failed eval run", list_failed_eval_runs())
        resume_run_id = str(resume_selection["run_id"])

    command = [
        str(VENV_PYTHON),
        "-m",
        "Execution.evals.eval_orchestrator",
        "--postgres-url",
        postgres_url,
        "--run-type",
        args.run_type,
        "--chunks-path",
        str(chunks_path),
        "--tracing-endpoint",
        tracing_endpoint,
        "--eval-config",
        str(eval_config),
    ]
    if resume_run_id:
        command.extend(["--resume-run-id", resume_run_id])

    print_eval_engine_plan(
        chunks_path=chunks_path,
        chunk_profile=effective_chunk_profile,
        scenario_name=args.scenario,
        postgres_url=postgres_url,
        tracing_endpoint=tracing_endpoint,
        judge_provider=judge_provider,
        judge_base_url=judge_base_url,
        judge_model=judge_model,
        run_type=args.run_type,
        resume_run_id=resume_run_id,
        command=command,
    )
    return maybe_run(command, args.dry_run)


def run_show_config(args: argparse.Namespace) -> int:
    env_values = load_dotenv(ROOT_ENV_PATH)
    postgres_url = args.postgres_url or require_env_value(env_values, "POSTGRES_URL")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError:
        if os.environ.get("RUN_STACK_SHOW_CONFIG_RERUN") != "1" and VENV_PYTHON.exists():
            completed = subprocess.run(
                [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
                cwd=REPO_ROOT,
                env={
                    **os.environ,
                    **env_values,
                    "RUN_STACK_SHOW_CONFIG_RERUN": "1",
                },
            )
            return completed.returncode
        raise LauncherError("psycopg is not available in the current Python environment")

    table_name: str
    id_field: str
    config_field: str
    run_id: str
    if args.runtime_run_id:
        table_name = "runtime_run_configs"
        id_field = "runtime_run_id"
        config_field = "runtime_config_json"
        run_id = args.runtime_run_id
    else:
        table_name = "eval_run_configs"
        id_field = "eval_run_id"
        config_field = "eval_config_json"
        run_id = args.eval_run_id

    with psycopg.Connection.connect(postgres_url, row_factory=dict_row) as connection:
        row = connection.execute(
            f"""
            select {id_field}, created_at, config_version, {config_field}
            from {table_name}
            where {id_field} = %s
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        raise LauncherError(f"no saved config found for {id_field}={run_id}")

    payload = {
        "kind": "runtime" if args.runtime_run_id else "eval",
        id_field: row[id_field],
        "created_at": str(row["created_at"]),
        "config_version": row["config_version"],
        "config": row[config_field],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def build_rag_runtime_command(
    runtime_config: Path,
    ingest_config: Path,
    questions_path: Path | None,
    golden_retrievals_path: Path | None,
) -> list[str]:
    command = [
        "cargo",
        "run",
        "--manifest-path",
        str(RAG_RUNTIME_MANIFEST),
        "--",
        "--config",
        str(runtime_config),
        "--ingest-config",
        str(ingest_config),
    ]
    if questions_path is not None:
        command.extend(["--questions-file", str(questions_path)])
    if golden_retrievals_path is not None:
        command.extend(["--golden-retrievals-file", str(golden_retrievals_path)])
    return command


def maybe_run(command: list[str], dry_run: bool) -> int:
    if dry_run:
        return 0
    child_env = os.environ.copy()
    child_env.update(load_dotenv(ROOT_ENV_PATH))
    completed = subprocess.run(command, cwd=REPO_ROOT, env=child_env)
    return completed.returncode


def print_launcher_summary(
    *,
    run_mode: str,
    chunk_profile: str,
    ingest_config: Path | None,
    chunks_path: Path,
    golden_retrievals_path: Path,
    collection_name: str | None,
    reranker_kind: str | None,
    reranker_transport: str | None,
    retriever_kind: str | None,
    sparse_strategy: str | None,
    runtime_model: str | None,
    judge_model: str | None,
    question_set: str | None,
    question_set_title: str | None,
    question_count: int | None,
    questions_path: Path | None,
    effective_runtime_config: Path,
    effective_eval_config: Path,
    runtime_command: list[str] | None,
    eval_command: list[str] | None,
    verbose: bool,
) -> None:
    print("", file=sys.stderr)
    print("Launch Summary", file=sys.stderr)
    print("--------------", file=sys.stderr)
    print("Parameters", file=sys.stderr)
    print("----------", file=sys.stderr)
    print(f"run_mode={run_mode}", file=sys.stderr)
    print(f"chunking_strategy={chunk_profile}", file=sys.stderr)
    if retriever_kind is not None:
        print(f"retriever={retriever_kind}", file=sys.stderr)
    if collection_name is not None:
        print(f"collection_name={collection_name}", file=sys.stderr)
    if sparse_strategy is not None:
        print(f"sparse_strategy={sparse_strategy}", file=sys.stderr)
    if reranker_kind is not None:
        print(f"reranker={reranker_kind}", file=sys.stderr)
    if reranker_transport is not None:
        print(f"reranker_transport={reranker_transport}", file=sys.stderr)
    if runtime_model is not None:
        print(f"runtime_model={runtime_model}", file=sys.stderr)
    if judge_model is not None:
        print(f"judge_model={judge_model}", file=sys.stderr)
    if question_set is not None:
        print(f"question_set={question_set}", file=sys.stderr)
    if question_set_title is not None:
        print(f"question_set_title={question_set_title}", file=sys.stderr)
    if question_count is not None:
        print(f"question_count={question_count}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Paths", file=sys.stderr)
    print("-----", file=sys.stderr)
    if ingest_config is not None:
        print(f"ingest_config={display_path(ingest_config)}", file=sys.stderr)
    if run_mode in ("evals only", "runtime + evals"):
        print(f"eval_chunks_path={display_path(chunks_path)}", file=sys.stderr)
    if run_mode in ("runtime only", "runtime + evals"):
        print(
            f"golden_retrievals_path={display_path(golden_retrievals_path)}",
            file=sys.stderr,
        )
    if questions_path is not None:
        print(f"questions_path={display_path(questions_path)}", file=sys.stderr)
    if verbose:
        print("", file=sys.stderr)
        print("Commands", file=sys.stderr)
        print("--------", file=sys.stderr)
        if runtime_command is not None:
            print(f"runtime_command={shell_join(runtime_command)}", file=sys.stderr)
        if eval_command is not None:
            print(f"eval_command={shell_join(eval_command)}", file=sys.stderr)
    print("", file=sys.stderr)


def print_rag_runtime_plan(
    runtime_config: Path,
    ingest_config: Path,
    questions_path: Path | None,
    golden_retrievals_path: Path | None,
    reranker_kind: str | None,
    reranker_transport: str | None,
    command: list[str],
    temp_runtime_config: Path | None = None,
    scenario_name: str | None = None,
) -> None:
    print("mode=rag-runtime", file=sys.stderr)
    print(f"repo_root={REPO_ROOT}", file=sys.stderr)
    print(f"scenario={scenario_name or '<none>'}", file=sys.stderr)
    print(f"runtime_config_base={runtime_config}", file=sys.stderr)
    if temp_runtime_config is not None:
        print(f"runtime_config_effective={temp_runtime_config}", file=sys.stderr)
    print(f"ingest_config={ingest_config}", file=sys.stderr)
    print(f"questions_file={questions_path or '<interactive stdin>'}", file=sys.stderr)
    print(f"golden_retrievals_file={golden_retrievals_path or '<none>'}", file=sys.stderr)
    print(f"reranker_kind={reranker_kind or '<unchanged>'}", file=sys.stderr)
    print(f"reranker_transport={reranker_transport or '<unchanged>'}", file=sys.stderr)
    print(f"command={shell_join(command)}", file=sys.stderr)


def print_eval_engine_plan(
    *,
    chunks_path: Path,
    chunk_profile: str,
    scenario_name: str | None,
    postgres_url: str,
    tracing_endpoint: str,
    judge_provider: str,
    judge_base_url: str,
    judge_model: str,
    run_type: str,
    resume_run_id: str | None,
    command: list[str],
) -> None:
    print("mode=eval-engine", file=sys.stderr)
    print(f"repo_root={REPO_ROOT}", file=sys.stderr)
    print(f"scenario={scenario_name or '<none>'}", file=sys.stderr)
    print(f"chunk_profile={chunk_profile}", file=sys.stderr)
    print(f"chunks_path={chunks_path}", file=sys.stderr)
    print(f"run_type={run_type}", file=sys.stderr)
    print(f"postgres_url={postgres_url}", file=sys.stderr)
    print(f"tracing_endpoint={tracing_endpoint}", file=sys.stderr)
    print(f"judge_provider={judge_provider}", file=sys.stderr)
    print(f"judge_base_url={judge_base_url}", file=sys.stderr)
    print(f"judge_model={judge_model}", file=sys.stderr)
    print(f"resume_run_id={resume_run_id or '<none>'}", file=sys.stderr)
    print(f"command={shell_join(command)}", file=sys.stderr)


def create_launcher_artifact_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    artifact_dir = REPO_ROOT / "tmp" / "run_stack_launcher" / timestamp
    artifact_dir.mkdir(parents=True, exist_ok=True)
    return artifact_dir


def prompt_choice(title: str, options: list[str]) -> str:
    index = prompt_choice_index(title, [option.replace("_", "-") for option in options], allow_passthrough=False)
    return options[index]


def prompt_choice_pairs(title: str, options: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    labels = [label for label, _value in options]
    index = prompt_choice_index(title, labels, allow_passthrough=False)
    return options[index]


def prompt_option_dict(title: str, options: tuple[dict[str, str], ...]) -> dict[str, str]:
    labels = [option["label"] for option in options]
    index = prompt_choice_index(title, labels, allow_passthrough=True)
    return options[index]


def prompt_dataset_bundle(title: str) -> dict[str, Any]:
    datasets = list_dataset_bundles()
    labels = [dataset["label"] for dataset in datasets]
    index = prompt_choice_index(title, labels, allow_passthrough=False)
    return datasets[index]


def prompt_failed_eval_run(title: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [run["label"] for run in runs]
    index = prompt_choice_index(title, labels, allow_passthrough=False)
    return runs[index]


def prompt_choice_index(title: str, labels: list[str], allow_passthrough: bool) -> int:
    while True:
        print("", file=sys.stderr)
        print(f"{title}", file=sys.stderr)
        for idx, label in enumerate(labels, start=1):
            print(f"{idx}. {label}", file=sys.stderr)
        response = input("> ").strip()
        if response.isdigit():
            selected = int(response)
            if 1 <= selected <= len(labels):
                return selected - 1
        if allow_passthrough:
            normalized = response.lower()
            for idx, label in enumerate(labels):
                if normalized == label.lower():
                    return idx
        print("Please enter one of the listed numbers.", file=sys.stderr)


def list_dataset_bundles() -> list[dict[str, Any]]:
    if not QUERY_DATASETS_ROOT.exists():
        raise LauncherError(f"dataset root does not exist: {QUERY_DATASETS_ROOT}")

    bundles: list[dict[str, Any]] = []
    for dataset_dir in sorted(path for path in QUERY_DATASETS_ROOT.iterdir() if path.is_dir()):
        metadata_path = dataset_dir / "metadata.json"
        questions_path = dataset_dir / "questions.txt"
        if not metadata_path.exists() or not questions_path.exists():
            continue
        metadata = load_json(metadata_path)
        dataset_id = require_non_empty_string(metadata.get("id"), f"{metadata_path}.id")
        title = require_non_empty_string(metadata.get("title"), f"{metadata_path}.title")
        question_count = require_positive_int(
            metadata.get("question_count"),
            f"{metadata_path}.question_count",
        )
        bundles.append(
            {
                "id": dataset_id,
                "title": title,
                "question_count": question_count,
                "label": f"{dataset_id} | {title} | {question_count} questions",
            }
        )

    if not bundles:
        raise LauncherError(f"no dataset bundles found under {QUERY_DATASETS_ROOT}")
    return bundles


def dataset_questions_path(dataset_id: str) -> Path:
    return QUERY_DATASETS_ROOT / dataset_id / "questions.txt"


def dataset_golden_retrievals_path(dataset_id: str, chunk_profile: str) -> Path:
    return QUERY_DATASETS_ROOT / dataset_id / f"{chunk_profile}_golden_retrievals.json"


def list_failed_eval_runs() -> list[dict[str, Any]]:
    if not EVAL_RUNS_ROOT.exists():
        raise LauncherError(f"eval runs root does not exist: {EVAL_RUNS_ROOT}")

    runs: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in EVAL_RUNS_ROOT.iterdir() if path.is_dir()):
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = load_json(manifest_path)
        status = manifest.get("status")
        run_id = manifest.get("run_id")
        if status != "failed" or not isinstance(run_id, str) or not run_id.strip():
            continue
        started_at = manifest.get("started_at")
        run_type = manifest.get("run_type")
        last_error = manifest.get("last_error")
        label = f"{run_id} | {run_type or 'unknown'} | {started_at or 'unknown'}"
        if isinstance(last_error, str) and last_error.strip():
            short_error = last_error.strip().replace("\n", " ")
            if len(short_error) > 100:
                short_error = short_error[:97] + "..."
            label += f" | {short_error}"
        runs.append(
            {
                "run_id": run_id,
                "status": status,
                "started_at": started_at,
                "run_type": run_type,
                "last_error": last_error,
                "label": label,
            }
        )

    runs.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
    if not runs:
        raise LauncherError(f"no failed eval runs found under {EVAL_RUNS_ROOT}")
    return runs


def resolve_existing_path(path: Path, label: str) -> Path:
    resolved = path if path.is_absolute() else (REPO_ROOT / path).resolve()
    if not resolved.exists():
        raise LauncherError(f"{label} does not exist: {resolved}")
    return resolved


def normalize_reranker_kind(value: str) -> str:
    try:
        return RERANKER_KIND_ALIASES[value]
    except KeyError as exc:
        raise LauncherError(f"unsupported reranker kind: {value}") from exc


def normalize_reranker_transport(value: str) -> str:
    try:
        return RERANKER_TRANSPORT_ALIASES[value]
    except KeyError as exc:
        raise LauncherError(f"unsupported reranker transport: {value}") from exc


def resolve_judge_runtime(eval_config: Path, env_values: dict[str, str]) -> tuple[str, str, str]:
    from Execution.evals.judge_transport import JudgeConfigError, load_judge_settings

    try:
        settings = load_judge_settings(eval_config, env_values)
    except JudgeConfigError as error:
        raise LauncherError(str(error)) from error
    return settings.provider, settings.base_url, settings.model_name


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        values[key.strip()] = normalized_value
    return values


def require_env_value(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None or value.strip() == "":
        raise LauncherError(f"missing required {key} in {ROOT_ENV_PATH}")
    return value


def load_toml(path: Path) -> dict[str, Any]:
    try:
        import tomllib as parser  # type: ignore
    except ModuleNotFoundError:
        import tomli as parser  # type: ignore
    with path.open("rb") as handle:
        data = parser.load(handle)
    if not isinstance(data, dict):
        raise LauncherError(f"TOML root must be an object: {path}")
    return data


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LauncherError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise LauncherError(f"JSON root must be an object: {path}")
    return data


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LauncherError(f"{label} must be a table/object")
    return value


def require_non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LauncherError(f"{label} must be a non-empty string")
    return value.strip()


def require_positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise LauncherError(f"{label} must be an integer >= 1")
    return value


def dump_toml_value(value: Any, indent: str = "") -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        parts = ["["]
        for item in value:
            parts.append(f"{indent}  {dump_toml_value(item, indent + '  ')},")
        parts.append(f"{indent}]")
        return "\n".join(parts)
    raise LauncherError(f"unsupported TOML value type: {type(value).__name__}")


def dump_toml_document(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def emit_table(path_parts: list[str], table: dict[str, Any]) -> None:
        if path_parts:
            lines.append(f"[{'.'.join(path_parts)}]")
        scalar_items: list[tuple[str, Any]] = []
        nested_items: list[tuple[str, dict[str, Any]]] = []
        for key, value in table.items():
            if isinstance(value, dict):
                nested_items.append((key, value))
            else:
                scalar_items.append((key, value))
        for key, value in scalar_items:
            lines.append(f"{key} = {dump_toml_value(value)}")
        if scalar_items and nested_items:
            lines.append("")
        for index, (key, value) in enumerate(nested_items):
            emit_table(path_parts + [key], value)
            if index != len(nested_items) - 1:
                lines.append("")

    emit_table([], data)
    return "\n".join(lines) + "\n"


def shell_join(command: list[str]) -> str:
    return " ".join(subprocess.list2cmdline([part]) for part in command)


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
