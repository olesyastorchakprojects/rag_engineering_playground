import json
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
ANNOTATION_NAME = "answer_completeness"

LABEL_TO_SCORE = {
    "complete": 1.0,
    "partial": 0.5,
    "incomplete": 0.0,
}

SYSTEM_PROMPT = """You are evaluating a RAG system answer.

Your task is to classify the answer as complete, partial, or incomplete.
You must be conservative and consistent.

Label definitions:
- complete:
  The answer directly addresses the user question, is relevant, factually usable, and covers the main requested information with no important omissions.
- partial:
  The answer is relevant and somewhat useful, but it is missing important details, is too vague, only answers part of the question, or gives a weak summary instead of a solid answer.
- incomplete:
  The answer fails to address the question, is mostly irrelevant, is too shallow to be useful, or does not provide a meaningful answer.

Decision rules:
- Prefer complete only when the answer is clearly sufficient on its own.
- Use partial when the answer is directionally correct but noticeably incomplete.
- Use incomplete when the user would still not have a usable answer after reading it.
- If you are uncertain between complete and partial, choose partial.
- If you are uncertain between partial and incomplete, choose incomplete.
- Do not reward fluency alone. A smooth but vague answer is partial or incomplete.
- Do not infer missing details that are not present in the answer.
- Judge only the answer that is written, not what the model may have intended.

Consistency checklist:
1. Does the answer directly address the user's question?
2. Does it contain the main requested information?
3. Would a reasonable reader consider it sufficient without needing major follow-up?

Scoring policy:
- complete only if the answer is yes on all three checklist items.
- partial if the answer is yes on item 1 but no on item 2 or 3.
- incomplete if the answer fails item 1, or is too weak to be useful.

Return valid JSON with exactly these keys:
{"label": "complete|partial|incomplete", "explanation": "short explanation"}
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


def build_eval_dataframe(spans_df: pd.DataFrame) -> pd.DataFrame:
    trace_id_column = "context.trace_id"
    span_id_column = "context.span_id"
    span_name_column = "name"
    input_column = "attributes.input.value"
    output_column = "attributes.output.value"

    require_columns(
        spans_df,
        [trace_id_column, span_id_column, span_name_column],
    )

    input_spans = spans_df[
        (spans_df[span_name_column] == "retrieval.embedding")
        & spans_df.get(input_column, pd.Series(dtype="object")).notna()
    ][[trace_id_column, input_column]].copy()
    input_spans = input_spans.drop_duplicates(subset=[trace_id_column], keep="first")
    input_spans = input_spans.rename(columns={input_column: "eval_input"})

    output_spans = spans_df[
        (spans_df[span_name_column] == "generation.chat")
        & spans_df.get(output_column, pd.Series(dtype="object")).notna()
    ][[trace_id_column, span_id_column, output_column]].copy()
    output_spans = output_spans.drop_duplicates(subset=[trace_id_column], keep="last")
    output_spans = output_spans.rename(
        columns={
            span_id_column: "generation_span_id",
            output_column: "eval_output",
        }
    )

    root_spans = spans_df[
        spans_df[span_name_column] == "rag.request"
    ][[trace_id_column, span_id_column]].copy()
    root_spans = root_spans.drop_duplicates(subset=[trace_id_column], keep="first")
    root_spans = root_spans.rename(columns={span_id_column: "span_id"})

    eval_df = output_spans.merge(input_spans, on=trace_id_column, how="inner")
    eval_df = eval_df.merge(root_spans, on=trace_id_column, how="inner")
    eval_df = eval_df.rename(columns={trace_id_column: "trace_id"})
    return eval_df


def build_user_prompt(user_input: str, system_output: str) -> str:
    return f"""User question:
{user_input}

System answer:
{system_output}
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


def judge_row(judge_client: OpenAI, row: pd.Series) -> dict[str, Any]:
    response = judge_client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(row["eval_input"], row["eval_output"])},
        ],
    )
    raw_text = extract_text_response(response)
    label, score, explanation, metadata = parse_judge_response(raw_text)
    return {
        "span_id": row["span_id"],
        "trace_id": row["trace_id"],
        "generation_span_id": row["generation_span_id"],
        "name": ANNOTATION_NAME,
        "annotator_kind": "LLM",
        "label": label,
        "score": score,
        "explanation": explanation,
        "metadata": metadata,
    }


client = Client(base_url=PHOENIX_ENDPOINT)
judge_client = OpenAI(base_url=JUDGE_BASE_URL, api_key=JUDGE_API_KEY)

spans_df = client.spans.get_spans_dataframe(project_name=PHOENIX_PROJECT_NAME)
eval_df = build_eval_dataframe(spans_df)

print(f"Total spans in project: {len(spans_df)}")
print(f"Trace candidates found for evaluation: {len(eval_df)}")

if len(eval_df) == 0:
    print("No suitable trace/span pairs were found.")
    print("The evaluation expects:")
    print("- retrieval.embedding with attributes.input.value")
    print("- generation.chat with attributes.output.value")
    print("- rag.request as the target span for annotations")
    print("Dataframe columns:")
    print(list(spans_df.columns))
    raise SystemExit(1)

annotation_rows: list[dict[str, Any]] = []

for index, row in enumerate(eval_df.itertuples(index=False), start=1):
    row_series = pd.Series(row._asdict())
    trace_id = row_series["trace_id"]
    print(f"Evaluating trace {index}/{len(eval_df)}: trace_id={trace_id}")
    try:
        annotation = judge_row(judge_client, row_series)
        print(
            "  -> "
            f"label={annotation['label']!r}, score={annotation['score']}, "
            f"target_span={annotation['span_id']}"
        )
    except Exception as error:
        annotation = {
            "span_id": row_series["span_id"],
            "trace_id": row_series["trace_id"],
            "generation_span_id": row_series["generation_span_id"],
            "name": ANNOTATION_NAME,
            "annotator_kind": "LLM",
            "label": "error",
            "score": None,
            "explanation": str(error),
            "metadata": {"error": True},
        }
        print(f"  -> error={error}")
    annotation_rows.append(annotation)

results_df = pd.DataFrame(annotation_rows)

print("Evaluation results:")
print(results_df[["trace_id", "generation_span_id", "span_id", "label", "score"]].head())

client.spans.log_span_annotations_dataframe(dataframe=results_df, sync=True)

print("Summary by label:")
print(results_df["label"].value_counts(dropna=False).to_string())

print("Summary by score:")
print(results_df["score"].value_counts(dropna=False).sort_index().to_string())

print("Done: annotations were written back to Phoenix.")
