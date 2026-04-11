import ast
import json
import math
import os
from typing import Any

import pandas as pd
from openai import OpenAI
from phoenix.client import Client


PHOENIX_ENDPOINT = os.getenv("PHOENIX_ENDPOINT", "http://localhost:6006")
PHOENIX_PROJECT_NAME = os.getenv("PHOENIX_PROJECT_NAME", "default")
JUDGE_BASE_URL = os.getenv("PHOENIX_JUDGE_BASE_URL", "http://localhost:11434/v1")
JUDGE_MODEL = os.getenv("PHOENIX_JUDGE_MODEL", "qwen2.5:7b-instruct-q4_K_M")
JUDGE_API_KEY = os.getenv("PHOENIX_JUDGE_API_KEY", "ollama")
CHUNKS_PATH = os.getenv(
    "PHOENIX_CHUNKS_PATH",
    "/home/olesia/code/prompt_gen_proj/Evidence/parsing/understanding_distributed_systems/chunks/chunks.jsonl",
)

MEAN_ANNOTATION_NAME = "retrieval_relevance_mean_topk"
WEIGHTED_ANNOTATION_NAME = "retrieval_relevance_weighted_topk"

LABEL_TO_SCORE = {
    "relevant": 1.0,
    "partial": 0.5,
    "irrelevant": 0.0,
}

SYSTEM_PROMPT = """You are evaluating retrieval relevance for a RAG system.

You must judge whether a retrieved chunk is relevant to answering the user's question.
You must be conservative and consistent.

Label definitions:
- relevant:
  The chunk contains information that clearly helps answer the question.
- partial:
  The chunk is somewhat related and may help indirectly, but it is incomplete, weakly connected, or only partially useful.
- irrelevant:
  The chunk does not meaningfully help answer the question.

Decision rules:
- If you are uncertain between relevant and partial, choose partial.
- If you are uncertain between partial and irrelevant, choose irrelevant.
- Do not reward topic similarity alone.
- Judge only whether this chunk is useful for answering the question.

Return valid JSON with exactly these keys:
{"label": "relevant|partial|irrelevant", "explanation": "short explanation"}
Do not return any other text.
"""


def require_columns(dataframe: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        print("The dataframe is missing expected columns:")
        print(missing)
        print("Available columns:")
        print(list(dataframe.columns))
        raise SystemExit(1)


def parse_maybe_serialized_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
    return []


def parse_maybe_serialized_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, SyntaxError):
            pass
    return {}


def load_chunk_index(path: str) -> dict[str, dict[str, Any]]:
    chunk_index: dict[str, dict[str, Any]] = {}
    with open(path, encoding="utf-8") as file:
        for line in file:
            record = json.loads(line)
            chunk_index[record["chunk_id"]] = record
    return chunk_index


def build_eval_dataframe(spans_df: pd.DataFrame) -> pd.DataFrame:
    trace_id_column = "context.trace_id"
    span_id_column = "context.span_id"
    span_name_column = "name"
    input_column = "attributes.input.value"
    retriever_column = "attributes.retriever"

    require_columns(
        spans_df,
        [trace_id_column, span_id_column, span_name_column, retriever_column, input_column],
    )

    retrieval_spans = spans_df[
        (spans_df[span_name_column] == "retrieval.vector_search")
    ][[trace_id_column, span_id_column, retriever_column, input_column]].copy()
    retrieval_spans = retrieval_spans.drop_duplicates(subset=[trace_id_column], keep="last")

    retrieval_spans["retriever_payload"] = retrieval_spans[retriever_column].apply(parse_maybe_serialized_dict)
    retrieval_spans["chunk_ids"] = retrieval_spans["retriever_payload"].apply(
        lambda payload: parse_maybe_serialized_list(payload.get("result", {}).get("chunk_ids"))
    )
    retrieval_spans["retrieval_scores"] = retrieval_spans["retriever_payload"].apply(
        lambda payload: parse_maybe_serialized_list(payload.get("result", {}).get("scores"))
    )
    retrieval_spans = retrieval_spans[retrieval_spans["chunk_ids"].map(bool)].copy()
    retrieval_spans = retrieval_spans.rename(
        columns={
            trace_id_column: "trace_id",
            span_id_column: "span_id",
            input_column: "eval_input",
        }
    )

    eval_df = retrieval_spans[["trace_id", "span_id", "eval_input", "chunk_ids", "retrieval_scores"]].copy()
    return eval_df


def build_user_prompt(user_input: str, chunk_text: str) -> str:
    return f"""User question:
{user_input}

Retrieved chunk:
{chunk_text}
"""


def extract_text_response(response: Any) -> str:
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text.strip()

    choices = getattr(response, "choices", None)
    if choices:
        message = choices[0].message
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if hasattr(item, "text") and item.text:
                    text_parts.append(item.text)
                elif isinstance(item, dict) and item.get("text"):
                    text_parts.append(item["text"])
            return "\n".join(text_parts).strip()

    return ""


def parse_judge_response(raw_text: str) -> tuple[str, float | None, str, dict[str, Any]]:
    metadata: dict[str, Any] = {"raw_response": raw_text}
    explanation = raw_text.strip()

    try:
        parsed = json.loads(raw_text)
        label = str(parsed.get("label", "")).strip().lower()
        explanation = str(parsed.get("explanation", "")).strip() or explanation
        if label in LABEL_TO_SCORE:
            metadata["parse_mode"] = "json"
            return label, LABEL_TO_SCORE[label], explanation, metadata
    except json.JSONDecodeError:
        pass

    normalized = raw_text.strip().lower()
    for label, score in LABEL_TO_SCORE.items():
        if normalized == label or normalized.startswith(f"{label}\n") or normalized.startswith(f"{label} "):
            metadata["parse_mode"] = "text"
            return label, score, explanation, metadata

    metadata["parse_mode"] = "unparsed"
    metadata["parse_error"] = True
    return "unparsed", None, explanation, metadata


def judge_chunk(judge_client: OpenAI, user_input: str, chunk_text: str) -> tuple[str, float | None, str, dict[str, Any]]:
    response = judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(user_input, chunk_text)},
        ],
    )
    raw_text = extract_text_response(response)
    return parse_judge_response(raw_text)


def reciprocal_rank_weights(length: int) -> list[float]:
    return [1.0 / rank for rank in range(1, length + 1)]


def normalized_weighted_mean(scores: list[float], weights: list[float]) -> float | None:
    if not scores or not weights or len(scores) != len(weights):
        return None
    total_weight = sum(weights)
    if math.isclose(total_weight, 0.0):
        return None
    return sum(score * weight for score, weight in zip(scores, weights)) / total_weight


def build_annotation_rows(row: pd.Series, chunk_judgments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid_scores = [judgment["score"] for judgment in chunk_judgments if judgment["score"] is not None]
    mean_score = sum(valid_scores) / len(valid_scores) if valid_scores else None
    weights = reciprocal_rank_weights(len(valid_scores))
    weighted_score = normalized_weighted_mean(valid_scores, weights)

    metadata = {
        "top_k": len(chunk_judgments),
        "weighting": "reciprocal_rank",
        "chunk_judgments": chunk_judgments,
    }

    return [
        {
            "span_id": row["span_id"],
            "trace_id": row["trace_id"],
            "name": MEAN_ANNOTATION_NAME,
            "annotator_kind": "LLM",
            "label": "computed" if mean_score is not None else "unparsed",
            "score": mean_score,
            "explanation": "Mean chunk relevance over retrieved top-k.",
            "metadata": metadata,
        },
        {
            "span_id": row["span_id"],
            "trace_id": row["trace_id"],
            "name": WEIGHTED_ANNOTATION_NAME,
            "annotator_kind": "LLM",
            "label": "computed" if weighted_score is not None else "unparsed",
            "score": weighted_score,
            "explanation": "Reciprocal-rank-weighted chunk relevance over retrieved top-k.",
            "metadata": metadata,
        },
    ]


client = Client(base_url=PHOENIX_ENDPOINT)
judge_client = OpenAI(base_url=JUDGE_BASE_URL, api_key=JUDGE_API_KEY)
chunk_index = load_chunk_index(CHUNKS_PATH)

spans_df = client.spans.get_spans_dataframe(project_name=PHOENIX_PROJECT_NAME)
eval_df = build_eval_dataframe(spans_df)

print(f"Total spans in project: {len(spans_df)}")
print(f"Retrieval trace candidates found for evaluation: {len(eval_df)}")

if len(eval_df) == 0:
    print("No suitable retrieval spans were found.")
    print("The evaluation expects:")
    print("- retrieval.vector_search with attributes.retriever.result.chunk_ids")
    print("- retrieval.vector_search with attributes.input.value")
    raise SystemExit(1)

annotation_rows: list[dict[str, Any]] = []
trace_summaries: list[dict[str, Any]] = []

for index, row in enumerate(eval_df.itertuples(index=False), start=1):
    row_series = pd.Series(row._asdict())
    trace_id = row_series["trace_id"]
    chunk_ids = parse_maybe_serialized_list(row_series["chunk_ids"])
    retrieval_scores = parse_maybe_serialized_list(row_series.get("retrieval_scores"))
    print(
        f"Evaluating retrieval trace {index}/{len(eval_df)}: "
        f"trace_id={trace_id}, chunks={len(chunk_ids)}"
    )

    chunk_judgments: list[dict[str, Any]] = []
    for rank, chunk_id in enumerate(chunk_ids, start=1):
        print(f"    chunk {rank}/{len(chunk_ids)}: chunk_id={chunk_id}")
        chunk_record = chunk_index.get(chunk_id)
        retrieval_score = retrieval_scores[rank - 1] if rank - 1 < len(retrieval_scores) else None
        if not chunk_record:
            chunk_judgments.append(
                {
                    "rank": rank,
                    "chunk_id": chunk_id,
                    "label": "missing",
                    "score": None,
                    "retrieval_score": retrieval_score,
                    "error": "chunk_id not found in chunks.jsonl",
                }
            )
            continue

        try:
            label, score, explanation, parse_metadata = judge_chunk(
                judge_client,
                row_series["eval_input"],
                chunk_record["text"],
            )
            print(f"      -> label={label!r}, score={score}")
            judgment = {
                "rank": rank,
                "chunk_id": chunk_id,
                "label": label,
                "score": score,
                "retrieval_score": retrieval_score,
                "page_start": chunk_record.get("page_start"),
                "page_end": chunk_record.get("page_end"),
                "section_path": chunk_record.get("section_path"),
                "explanation": explanation,
                "parse_metadata": parse_metadata,
            }
        except Exception as error:
            print(f"      -> error={error}")
            judgment = {
                "rank": rank,
                "chunk_id": chunk_id,
                "label": "error",
                "score": None,
                "retrieval_score": retrieval_score,
                "page_start": chunk_record.get("page_start"),
                "page_end": chunk_record.get("page_end"),
                "section_path": chunk_record.get("section_path"),
                "error": str(error),
            }
        chunk_judgments.append(judgment)

    rows = build_annotation_rows(row_series, chunk_judgments)
    valid_scores = [judgment["score"] for judgment in chunk_judgments if judgment["score"] is not None]
    top2_scores = valid_scores[:2]
    top2_weights = reciprocal_rank_weights(len(top2_scores))
    top1_label = chunk_judgments[0]["label"] if chunk_judgments else None
    top2_labels = [judgment["label"] for judgment in chunk_judgments[:2]]
    tail_labels = [judgment["label"] for judgment in chunk_judgments[2:]]
    trace_summaries.append(
        {
            "trace_id": trace_id,
            "top1_label": top1_label,
            "top2_labels": top2_labels,
            "tail_labels": tail_labels,
            "relevant_count": sum(1 for judgment in chunk_judgments if judgment["label"] == "relevant"),
            "partial_count": sum(1 for judgment in chunk_judgments if judgment["label"] == "partial"),
            "irrelevant_count": sum(1 for judgment in chunk_judgments if judgment["label"] == "irrelevant"),
            "missing_or_error_count": sum(
                1 for judgment in chunk_judgments if judgment["score"] is None
            ),
            "projected_top2_mean": sum(top2_scores) / len(top2_scores) if top2_scores else None,
            "projected_top2_weighted": normalized_weighted_mean(top2_scores, top2_weights),
        }
    )
    for annotation in rows:
        print(
            "  -> "
            f"name={annotation['name']}, score={annotation['score']}, "
            f"target_span={annotation['span_id']}"
        )
    annotation_rows.extend(rows)

results_df = pd.DataFrame(annotation_rows)

print("Evaluation results:")
print(results_df[["trace_id", "span_id", "name", "score"]].head())

client.spans.log_span_annotations_dataframe(dataframe=results_df, sync=True)

trace_summary_df = pd.DataFrame(trace_summaries)
mean_scores = results_df[results_df["name"] == MEAN_ANNOTATION_NAME]["score"].dropna()
weighted_scores = results_df[results_df["name"] == WEIGHTED_ANNOTATION_NAME]["score"].dropna()
projected_top2_mean = trace_summary_df["projected_top2_mean"].dropna()
projected_top2_weighted = trace_summary_df["projected_top2_weighted"].dropna()

top1_relevant_rate = (
    (trace_summary_df["top1_label"] == "relevant").mean() if not trace_summary_df.empty else float("nan")
)
top2_any_useful_rate = (
    trace_summary_df["top2_labels"].apply(
        lambda labels: any(label in {"relevant", "partial"} for label in labels)
    ).mean()
    if not trace_summary_df.empty
    else float("nan")
)
tail_noise_rate = (
    trace_summary_df["tail_labels"].apply(
        lambda labels: any(label == "irrelevant" for label in labels)
    ).mean()
    if not trace_summary_df.empty
    else float("nan")
)

print("Research summary:")
print(f"- traces evaluated: {len(trace_summary_df)}")
print(f"- mean_topk mean: {mean_scores.mean():.3f}")
print(f"- mean_topk median: {mean_scores.median():.3f}")
print(f"- weighted_topk mean: {weighted_scores.mean():.3f}")
print(f"- weighted_topk median: {weighted_scores.median():.3f}")
print(f"- top1 relevant rate: {top1_relevant_rate:.1%}")
print(f"- top2 useful rate (relevant or partial): {top2_any_useful_rate:.1%}")
print(f"- tail noise rate (rank 3+ contains irrelevant): {tail_noise_rate:.1%}")
print(f"- avg relevant chunks per trace: {trace_summary_df['relevant_count'].mean():.2f}")
print(f"- avg partial chunks per trace: {trace_summary_df['partial_count'].mean():.2f}")
print(f"- avg irrelevant chunks per trace: {trace_summary_df['irrelevant_count'].mean():.2f}")
if not projected_top2_mean.empty:
    print(f"- projected top2 mean_topk: {projected_top2_mean.mean():.3f}")
if not projected_top2_weighted.empty:
    print(f"- projected top2 weighted_topk: {projected_top2_weighted.mean():.3f}")

print("Done: retrieval annotations were written back to Phoenix.")
