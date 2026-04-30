#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.schema_validation import load_json, validate_chunk
from Execution.parsing.chunker.fixed.chunker import (
    SCHEMA_VERSION,
    START_TS,
    SentenceUnit,
    build_chunks,
    init_spacy,
    init_tokenizer,
    load_config,
    norm_ws,
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def _format_validation_errors(errors: Sequence[Dict[str, str]]) -> str:
    return "; ".join(f"{err['path']}: {err['reason']}" for err in errors[:5])


def load_structural_chunks(path: Path, schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not path.exists():
        fail(f"Missing required chunks file: {path}")
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                fail(f"Invalid chunks {path}: line {lineno} must be an object")
            errors = validate_chunk(payload, schema)
            if errors:
                fail(
                    f"Invalid chunks {path}: line {lineno} failed schema validation: "
                    f"{_format_validation_errors(errors)}"
                )
            rows.append(payload)
    return rows


def build_sentence_units_from_parent(parent: Dict[str, Any], nlp, tokenizer) -> List[SentenceUnit]:
    text = norm_ws(str(parent.get("text", "") or ""))
    if not text:
        return []

    page_start = parent.get("page_start")
    page_end = parent.get("page_end")
    if not isinstance(page_start, int) or not isinstance(page_end, int):
        fail("Validated parent chunk is missing integer page_start/page_end")

    doc = nlp(text)
    sentence_units: List[SentenceUnit] = []
    for sent in doc.sents:
        sentence_text = norm_ws(sent.text)
        if not sentence_text:
            continue
        token_count = len(tokenizer.encode(sentence_text).ids)
        sentence_units.append(
            SentenceUnit(
                sentence_text=sentence_text,
                page_start=page_start,
                page_end=page_end,
                token_count=token_count,
            )
        )
    return sentence_units


def materialize_child_records(
    parents: Sequence[Dict[str, Any]],
    schema: Dict[str, Any],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    tokenizer = init_tokenizer(config)
    nlp = init_spacy(config["sentence_segmentation"]["language"])
    rows: List[Dict[str, Any]] = []

    for parent in parents:
        sentence_units = build_sentence_units_from_parent(parent, nlp, tokenizer)
        if not sentence_units:
            continue
        windows = build_chunks(
            sentence_units,
            target_tokens=int(config["chunking"]["target_tokens"]),
            overlap_ratio=float(config["chunking"]["overlap_ratio"]),
        )
        for window in windows:
            output_index = len(rows)
            window_sentences = sentence_units[window.start_idx : window.end_idx]
            text = norm_ws(" ".join(sentence.sentence_text for sentence in window_sentences))
            row = {
                "schema_version": SCHEMA_VERSION,
                "doc_id": parent["doc_id"],
                "chunk_id": str(uuid.uuid4()),
                "url": parent["url"],
                "document_title": parent["document_title"],
                "section_title": parent.get("section_title"),
                "section_path": list(parent.get("section_path", []) or []),
                "chunk_index": output_index,
                "page_start": parent["page_start"],
                "page_end": parent["page_end"],
                "tags": list(parent.get("tags", []) or []),
                "content_hash": f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
                "chunking_version": config["chunking"]["chunking_version"],
                "chunk_created_at": (START_TS + timedelta(minutes=output_index)).isoformat().replace("+00:00", "Z"),
                "text": text,
            }
            errors = validate_chunk(row, schema)
            if errors:
                fail(f"Output chunk at chunk_index={output_index} failed schema validation: {_format_validation_errors(errors)}")
            rows.append(row)

    return rows


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build fixed-size sentence-preserving chunks from structural chunk JSONL"
    )
    parser.add_argument("--chunks", type=Path, required=True, help="Input structural chunks JSONL")
    parser.add_argument("--config", type=Path, required=True, help="Fixed-in-structural chunker TOML config")
    parser.add_argument("--chunk-schema", type=Path, required=True, help="Chunk JSON Schema path")
    parser.add_argument("--out", type=Path, required=True, help="Output chunks JSONL path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    schema = load_json(args.chunk_schema)
    config = load_config(args.config)
    parents = load_structural_chunks(args.chunks, schema)
    rows = materialize_child_records(parents, schema, config)
    write_jsonl(args.out, rows)
    print(f"Wrote {len(rows)} chunks to {args.out}")


if __name__ == "__main__":
    main()
