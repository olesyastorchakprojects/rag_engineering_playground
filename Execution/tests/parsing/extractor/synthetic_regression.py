#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from extract_pdf_pages_text import clean_page_text, load_json_file, normalize_line, validate_rules_metadata


DEFAULT_CASES = Path("data/synthetic/synthetic_cleanup_cases.json")
DEFAULT_CONTENT_METADATA = Path("data/content/book_content_metadata.json")
DEFAULT_RULES_METADATA = Path("data/rules/rules_metadata.json")
INLINE_FIG_REF_RE = re.compile(r"\b(?:Figure|Fig\.)\s+\d{1,2}\.\d{1,2}\b")
LARGE_GAP = 50.0


def normalize(text: str) -> str:
    return " ".join((text or "").split())


def fail(message: str) -> None:
    print(message)
    raise SystemExit(1)


def validate_words(words: Any, case_name: str) -> None:
    required_keys = {"text", "top", "x0", "size", "bottom"}
    if not isinstance(words, list) or not words:
        fail(f"FAIL: case {case_name} has invalid words")
    for index, item in enumerate(words):
        if not isinstance(item, dict):
            fail(f"FAIL: case {case_name} words[{index}] must be an object")
        if set(item.keys()) != required_keys:
            fail(f"FAIL: case {case_name} words[{index}] has invalid keys")
        if not isinstance(item["text"], str):
            fail(f"FAIL: case {case_name} words[{index}].text is invalid")
        for key in ("top", "x0", "size", "bottom"):
            if not isinstance(item[key], (int, float)):
                fail(f"FAIL: case {case_name} words[{index}].{key} is invalid")


def validate_page_lines(page_lines: Any, case_name: str) -> None:
    required_keys = {"top", "x0", "x1", "linewidth"}
    if not isinstance(page_lines, list):
        fail(f"FAIL: case {case_name} has invalid page_lines")
    for index, item in enumerate(page_lines):
        if not isinstance(item, dict):
            fail(f"FAIL: case {case_name} page_lines[{index}] must be an object")
        if set(item.keys()) != required_keys:
            fail(f"FAIL: case {case_name} page_lines[{index}] has invalid keys")
        for key in required_keys:
            if not isinstance(item[key], (int, float)):
                fail(f"FAIL: case {case_name} page_lines[{index}].{key} is invalid")


def load_cases(path: Path) -> List[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        fail(f"FAIL: cases not found: {path}")
    except json.JSONDecodeError as exc:
        fail(f"FAIL: invalid cases JSON: {exc}")
    if not isinstance(payload, list):
        fail("FAIL: cases root must be a JSON array")

    allowed_keys = {"name", "expected_clean_text", "raw_text", "words", "page_num", "page_height", "page_lines"}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            fail(f"FAIL: case {index} must be an object")
        if not set(item.keys()) <= allowed_keys:
            fail(f"FAIL: case {index} has invalid keys")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            fail(f"FAIL: case {index} has invalid name")
        if not isinstance(item.get("expected_clean_text"), str):
            fail(f"FAIL: case {item.get('name', index)} has invalid expected_clean_text")

        has_raw_text = "raw_text" in item
        has_words = "words" in item
        if not has_raw_text and not has_words:
            fail(f"FAIL: case {item['name']} must define raw_text or words")
        if has_raw_text and has_words:
            fail(f"FAIL: case {item['name']} must not define both raw_text and words")
        if has_raw_text and not isinstance(item["raw_text"], str):
            fail(f"FAIL: case {item['name']} has invalid raw_text")
        if not has_words and any(key in item for key in ("page_num", "page_height", "page_lines")):
            fail(f"FAIL: case {item['name']} has geometry-only fields without words")
        if "page_num" in item and not isinstance(item["page_num"], int):
            fail(f"FAIL: case {item['name']} has invalid page_num")
        if "page_height" in item and not isinstance(item["page_height"], (int, float)):
            fail(f"FAIL: case {item['name']} has invalid page_height")
        if has_words:
            validate_words(item["words"], item["name"])
        if "page_lines" in item:
            validate_page_lines(item["page_lines"], item["name"])
    return payload


class SyntheticPage:
    def __init__(self, case: Mapping[str, Any]) -> None:
        if "words" in case:
            self.raw_text = ""
            self.height = float(case.get("page_height", 1000.0))
            self.lines: List[Dict[str, Any]] = list(case.get("page_lines", []))
            self.explicit_words: Optional[List[Dict[str, Any]]] = list(case["words"])
        else:
            self.raw_text = case["raw_text"]
            self.height = 1000.0
            self.lines = []
            self.explicit_words = None

    def extract_words(self, **kwargs: Any) -> List[Dict[str, Any]]:
        if self.explicit_words is not None:
            return list(self.explicit_words)
        words: List[Dict[str, Any]] = []
        normalized_lines = [normalize_line(raw_line) for raw_line in self.raw_text.split("\n")]
        top = 0.0
        for index, line in enumerate(normalized_lines):
            if not line:
                top += 18.0
                continue
            x0 = 0.0
            for token in line.split():
                words.append({"text": token, "top": top, "x0": x0, "size": 10.0, "bottom": top + 10.0})
                x0 += max(8.0, float(len(token) * 6.0))
            top += synthetic_gap(normalized_lines, index)
        return words


def synthetic_gap(lines: List[str], index: int) -> float:
    current_line = lines[index]
    next_line = lines[index + 1] if index + 1 < len(lines) else ""
    prev_line = lines[index - 1] if index > 0 else ""
    next_next_line = lines[index + 2] if index + 2 < len(lines) else ""
    if not next_line:
        return 14.0
    if current_line.startswith("Figure ") and len(current_line) < 40:
        return LARGE_GAP
    if current_line.startswith("Figure "):
        return 14.0
    if prev_line.startswith("Figure ") and current_line[:1].islower():
        if INLINE_FIG_REF_RE.search(next_line) and not next_line.startswith("Figure "):
            return LARGE_GAP
        if next_line[:1].isupper():
            if next_next_line and not normalize(next_line).endswith((".", "?", "!")):
                return 14.0
            return LARGE_GAP
    return 14.0


def infer_page_num(raw_text: str, content_metadata: Dict[str, Any]) -> int:
    match = re.search(r"^Figure\s+(\d{1,2})\.\d{1,2}\s*:", raw_text, flags=re.I | re.M)
    if match is None:
        return 1
    chapter = int(match.group(1))
    chapters = content_metadata.get("chapters")
    if not isinstance(chapters, list):
        return 1
    for item in chapters:
        if not isinstance(item, dict):
            continue
        if item.get("chapter") != chapter:
            continue
        ranges = item.get("ranges")
        if not isinstance(ranges, dict):
            continue
        pdf_ranges = ranges.get("pdf")
        if not isinstance(pdf_ranges, dict):
            continue
        start = pdf_ranges.get("start")
        if isinstance(start, int):
            return start
    return 1


def print_diff(expected: str, actual: str, max_diff_tokens: int) -> None:
    expected_norm = normalize(expected)
    actual_norm = normalize(actual)
    print(f"  expected_norm: {expected_norm!r}")
    print(f"  actual_norm  : {actual_norm!r}")
    expected_tokens = expected_norm.split(" ") if expected_norm else []
    actual_tokens = actual_norm.split(" ") if actual_norm else []
    limit = min(max(len(expected_tokens), len(actual_tokens)), max_diff_tokens)
    for index in range(limit):
        exp = expected_tokens[index] if index < len(expected_tokens) else "<EOF>"
        act = actual_tokens[index] if index < len(actual_tokens) else "<EOF>"
        if exp != act:
            print(f"  diff[{index}]: expected={exp!r} actual={act!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--content-metadata", type=Path, default=DEFAULT_CONTENT_METADATA)
    parser.add_argument("--rules-metadata", type=Path, default=DEFAULT_RULES_METADATA)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--show-diff", action="store_true")
    parser.add_argument("--max-diff-tokens", type=int, default=30)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    content_metadata = load_json_file(args.content_metadata, "content-metadata")
    rules_metadata = validate_rules_metadata(load_json_file(args.rules_metadata, "rules-metadata"))
    content_dict = content_metadata if isinstance(content_metadata, dict) else {}

    failed = 0
    passed = 0
    for case in cases:
        page = SyntheticPage(case)
        if "page_num" in case:
            page_num = int(case["page_num"])
        elif "words" in case:
            page_num = 1
        else:
            page_num = infer_page_num(page.raw_text, content_dict)
        actual = clean_page_text(page.extract_words(), page.height, page_num, rules_metadata, page.lines)
        expected = case["expected_clean_text"]
        if normalize(actual) == normalize(expected):
            passed += 1
            if args.verbose:
                print(f"OK   [{case['name']}]")
            continue
        failed += 1
        print(f"FAIL [{case['name']}]")
        print(f"  expected: {expected!r}")
        print(f"  actual  : {actual!r}")
        if args.show_diff:
            print_diff(expected, actual, args.max_diff_tokens)

    print(f"summary: total={len(cases)} failed={failed} passed={passed}")
    raise SystemExit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
