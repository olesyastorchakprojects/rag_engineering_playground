from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


def _fail(path: Path, message: str) -> None:
    raise RuntimeError(f"Invalid metadata {path}: {message}")


def _require_dict(value: Any, path: Path, label: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, f"{label} must be an object")
    return value


def _require_list(value: Any, path: Path, label: str) -> list:
    if not isinstance(value, list):
        _fail(path, f"{label} must be an array")
    return value


def _require_int(value: Any, path: Path, label: str) -> int:
    if not isinstance(value, int):
        _fail(path, f"{label} must be an int")
    return value


def _require_str(value: Any, path: Path, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(path, f"{label} must be a non-empty string")
    return value


def _validate_pdf_ranges(entry: Dict[str, Any], path: Path, label: str) -> None:
    ranges = _require_dict(entry.get("ranges"), path, f"{label}.ranges")
    pdf = _require_dict(ranges.get("pdf"), path, f"{label}.ranges.pdf")
    start = _require_int(pdf.get("start"), path, f"{label}.ranges.pdf.start")
    end = _require_int(pdf.get("end"), path, f"{label}.ranges.pdf.end")
    if start > end:
        _fail(path, f"{label}.ranges.pdf.start must be <= end")


def _check_duplicates(values: Iterable[str], path: Path, label: str) -> None:
    seen = set()
    for value in values:
        if value in seen:
            _fail(path, f"duplicate {label}: {value}")
        seen.add(value)


def validate_book_content_metadata(payload: Any, path: Path) -> Dict[str, Any]:
    root = _require_dict(payload, path, "root")

    parts = _require_list(root.get("parts", []), path, "parts")
    chapters = _require_list(root.get("chapters", []), path, "chapters")
    sections = _require_list(root.get("sections", []), path, "sections")
    subsections = _require_list(root.get("subsections", []), path, "subsections")

    part_ids = set()
    for i, entry in enumerate(parts):
        label = f"parts[{i}]"
        entry = _require_dict(entry, path, label)
        part_id = _require_str(entry.get("part"), path, f"{label}.part")
        _require_str(entry.get("title"), path, f"{label}.title")
        _validate_pdf_ranges(entry, path, label)
        part_ids.add(part_id)
    _check_duplicates(part_ids, path, "part id")

    chapter_nums = []
    for i, entry in enumerate(chapters):
        label = f"chapters[{i}]"
        entry = _require_dict(entry, path, label)
        chapter_num = _require_int(entry.get("chapter"), path, f"{label}.chapter")
        _require_str(entry.get("title"), path, f"{label}.title")
        _validate_pdf_ranges(entry, path, label)
        part = entry.get("part")
        if part is not None and str(part) not in part_ids:
            _fail(path, f"{label}.part references unknown part: {part}")
        chapter_nums.append(str(chapter_num))
    _check_duplicates(chapter_nums, path, "chapter")

    section_ids = []
    for i, entry in enumerate(sections):
        label = f"sections[{i}]"
        entry = _require_dict(entry, path, label)
        section_id = _require_str(entry.get("section"), path, f"{label}.section")
        chapter_num = _require_int(entry.get("chapter"), path, f"{label}.chapter")
        _require_str(entry.get("title"), path, f"{label}.title")
        _validate_pdf_ranges(entry, path, label)
        if str(chapter_num) not in chapter_nums:
            _fail(path, f"{label}.chapter references unknown chapter: {chapter_num}")
        part = entry.get("part")
        if part is not None and str(part) not in part_ids:
            _fail(path, f"{label}.part references unknown part: {part}")
        section_ids.append(section_id)
    _check_duplicates(section_ids, path, "section")

    subsection_ids = []
    for i, entry in enumerate(subsections):
        label = f"subsections[{i}]"
        entry = _require_dict(entry, path, label)
        subsection_id = _require_str(entry.get("subsection"), path, f"{label}.subsection")
        section_id = _require_str(entry.get("section"), path, f"{label}.section")
        chapter_num = _require_int(entry.get("chapter"), path, f"{label}.chapter")
        _require_str(entry.get("title"), path, f"{label}.title")
        _validate_pdf_ranges(entry, path, label)
        if section_id not in section_ids:
            _fail(path, f"{label}.section references unknown section: {section_id}")
        if str(chapter_num) not in chapter_nums:
            _fail(path, f"{label}.chapter references unknown chapter: {chapter_num}")
        part = entry.get("part")
        if part is not None and str(part) not in part_ids:
            _fail(path, f"{label}.part references unknown part: {part}")
        subsection_ids.append(subsection_id)
    _check_duplicates(subsection_ids, path, "subsection")

    return root


def load_and_validate_book_content_metadata(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing required metadata: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return validate_book_content_metadata(payload, path)
