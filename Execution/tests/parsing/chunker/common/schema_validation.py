#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def check_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_instance(instance: Any, schema: Dict[str, Any], path: str, errors: List[Dict[str, str]]) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if not any(check_type(instance, item_type) for item_type in expected_type):
            errors.append(
                {
                    "kind": "type_error",
                    "path": path,
                    "reason": f"expected one of {expected_type!r}, got {type(instance).__name__}",
                }
            )
            return
    elif isinstance(expected_type, str):
        if not check_type(instance, expected_type):
            errors.append(
                {
                    "kind": "type_error",
                    "path": path,
                    "reason": f"expected {expected_type}, got {type(instance).__name__}",
                }
            )
            return

    if isinstance(instance, dict):
        required = schema.get("required") or []
        for field in required:
            if field not in instance:
                errors.append(
                    {
                        "kind": "missing_required",
                        "path": path,
                        "reason": f"missing required field {field!r}",
                    }
                )
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(
                        {
                            "kind": "additional_property",
                            "path": f"{path}.{key}",
                            "reason": "unexpected property",
                        }
                    )
        for key, subschema in properties.items():
            if key in instance:
                validate_instance(instance[key], subschema, f"{path}.{key}", errors)
        return

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(instance):
                validate_instance(item, item_schema, f"{path}[{idx}]", errors)
        return

    if isinstance(instance, str):
        min_length = schema.get("minLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(
                {
                    "kind": "value_error",
                    "path": path,
                    "reason": f"string shorter than minLength={min_length}",
                }
            )
        if schema.get("format") == "date-time" and not validate_datetime(instance):
            errors.append(
                {
                    "kind": "value_error",
                    "path": path,
                    "reason": "invalid date-time format",
                }
            )
        return

    if isinstance(instance, int) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and instance < minimum:
            errors.append(
                {
                    "kind": "value_error",
                    "path": path,
                    "reason": f"value {instance} < minimum {minimum}",
                }
            )


def validate_chunk(chunk: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    validate_instance(chunk, schema, "$", errors)
    page_start = chunk.get("page_start")
    page_end = chunk.get("page_end")
    if isinstance(page_start, int) and isinstance(page_end, int) and page_end < page_start:
        errors.append(
            {
                "kind": "value_error",
                "path": "$.page_end",
                "reason": f"page_end {page_end} < page_start {page_start}",
            }
        )
    return errors


def main() -> None:
    p = argparse.ArgumentParser(description="Validate chunks JSONL against chunk JSON Schema")
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--schema", type=Path, required=True)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--max-errors", type=int, default=10)
    args = p.parse_args()

    rows = load_jsonl(args.chunks)
    schema = load_json(args.schema)
    if not rows:
        print(f"FAIL: no chunks in {args.chunks}")
        sys.exit(1)

    invalid_rows = 0
    violation_counts: Counter[str] = Counter()
    examples: List[Dict[str, str]] = []
    for idx, row in enumerate(rows, start=1):
        errors = validate_chunk(row, schema)
        if not errors:
            continue
        invalid_rows += 1
        for error in errors:
            violation_counts[error["kind"]] += 1
            if len(examples) < args.max_errors:
                examples.append(
                    {
                        "row": str(idx),
                        "path": error["path"],
                        "reason": error["reason"],
                    }
                )

    print(f"chunks={len(rows)} invalid={invalid_rows}")
    print(f"violation_counts={dict(sorted(violation_counts.items()))}")
    if examples:
        print("Schema mismatch examples:")
        for example in examples:
            print(
                f"  row={example['row']} path={example['path']} reason={example['reason']}"
            )

    if invalid_rows:
        if args.report_only:
            print("WARN: chunk schema validation failed (report-only)")
            return
        print("FAIL: chunk schema validation failed")
        sys.exit(1)

    print("OK: all chunks satisfy the schema")


if __name__ == "__main__":
    main()
