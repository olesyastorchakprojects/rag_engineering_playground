#!/usr/bin/env python3
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata

HEADING_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2})\s+(.+)$")


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_json(path: Path):
    return load_and_validate_book_content_metadata(path)


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def id_to_tuple(section_id: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in section_id.split("."))


def parse_chunk_heading(text: str) -> Optional[Tuple[str, str]]:
    t = normalize_text(text)
    m = HEADING_RE.match(t)
    if not m:
        return None
    section_id = m.group(1)
    title = normalize_text(m.group(2))
    return section_id, title


def title_tokens(s: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9']+", s.lower())


def canonical_path(path: object) -> Tuple[str, ...]:
    if isinstance(path, list):
        parts = path
    elif isinstance(path, str):
        parts = path.split("/")
    else:
        parts = []
    return tuple(normalize_text(str(part)).lower() for part in parts if normalize_text(str(part)))


def title_consistent(meta_title: str, chunk_head: str, prefix_window: int) -> bool:
    meta_toks = set(title_tokens(meta_title))
    head_toks = set(title_tokens(chunk_head[:prefix_window]))
    if not meta_toks:
        return True
    common = meta_toks & head_toks
    return len(common) >= min(2, len(meta_toks))


def format_samples(values: Sequence[Any], max_samples: int = 10) -> str:
    shown = ",".join(str(value) for value in values[:max_samples])
    suffix = ",..." if len(values) > max_samples else ""
    return f"samples=[{shown}{suffix}]"


def overlaps_pdf_range(
    start: object,
    end: object,
    chunk_start: int,
    chunk_end: int,
) -> bool:
    if not isinstance(start, int):
        return False
    end_norm = chunk_end if end == "end_of_book" else end
    if not isinstance(end_norm, int):
        return False
    return start <= chunk_end and chunk_start <= end_norm


def metadata_entries_in_scope(entries: List[dict], chunk_start: int, chunk_end: int) -> List[dict]:
    scoped = []
    for entry in entries:
        pdf_ranges = (entry.get("ranges") or {}).get("pdf") or {}
        start = pdf_ranges.get("start")
        end = pdf_ranges.get("end")
        if overlaps_pdf_range(start, end, chunk_start, chunk_end):
            scoped.append(entry)
    return scoped


def metadata_union_page_span(metadata: dict) -> Optional[Tuple[int, int]]:
    pages: List[int] = []
    for key in ("parts", "chapters", "sections", "subsections"):
        for entry in metadata.get(key) or []:
            pdf_ranges = (entry.get("ranges") or {}).get("pdf") or {}
            start = pdf_ranges.get("start")
            end = pdf_ranges.get("end")
            if isinstance(start, int) and isinstance(end, int):
                pages.extend((start, end))
    if not pages:
        return None
    return min(pages), max(pages)


def main() -> None:
    p = argparse.ArgumentParser(description="Structure checks for chunker output")
    p.add_argument("--chunks", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--prefix-window", type=int, default=220)
    p.add_argument("--allow-title-mismatch-ratio", type=float, default=0.20)
    p.add_argument("--report-only", action="store_true")
    p.add_argument("--max-errors", type=int, default=30)
    args = p.parse_args()

    chunks = load_jsonl(args.chunks)
    metadata = load_json(args.metadata)
    if not chunks:
        print(f"FAIL: no chunks in {args.chunks}")
        sys.exit(1)

    chunks = sorted(chunks, key=lambda r: int(r.get("chunk_index", 0)))
    idxs = [int(r.get("chunk_index", -1)) for r in chunks]
    if idxs != list(range(len(chunks))):
        print("FAIL: chunk_index is not strictly increasing 0..N-1")
        sys.exit(1)

    min_chunk_page = min(int(r.get("page_start", 0)) for r in chunks)
    max_chunk_page = max(int(r.get("page_end", 0)) for r in chunks)
    metadata_page_span = metadata_union_page_span(metadata)

    chapters = metadata.get("chapters") or []
    sections = metadata.get("sections") or []
    subsections = metadata.get("subsections") or []
    parts = metadata.get("parts") or []
    chapter_titles: Dict[int, str] = {
        int(entry["chapter"]): normalize_text(entry.get("title", ""))
        for entry in chapters
        if isinstance(entry.get("chapter"), int)
    }
    part_titles: Dict[str, str] = {
        str(entry["part"]): normalize_text(entry.get("title", ""))
        for entry in parts
        if entry.get("part") is not None
    }

    metadata_chapters = metadata_entries_in_scope(chapters, min_chunk_page, max_chunk_page)
    metadata_sections = metadata_entries_in_scope(sections, min_chunk_page, max_chunk_page)
    metadata_subsections = metadata_entries_in_scope(subsections, min_chunk_page, max_chunk_page)
    part_ids_in_scope = {
        str(entry.get("part"))
        for entry in metadata_chapters
        if entry.get("part") is not None
    }

    expected_headings: List[Tuple[str, str, str, str]] = []
    expected_by_id: Dict[str, Tuple[str, str, str, str]] = {}
    for entry in metadata_sections:
        section_id = str(entry.get("section", "")).strip()
        if not section_id:
            continue
        title = normalize_text(entry.get("title", ""))
        chapter_no = entry.get("chapter")
        chapter_title = chapter_titles.get(int(chapter_no), "") if isinstance(chapter_no, int) else ""
        part_id = entry.get("part")
        part_title = part_titles.get(str(part_id), "") if part_id is not None else ""
        expected = (section_id, title, chapter_title, part_title)
        expected_headings.append(expected)
        expected_by_id[section_id] = expected
    for entry in metadata_subsections:
        subsection_id = str(entry.get("subsection", "")).strip()
        if not subsection_id:
            continue
        title = normalize_text(entry.get("title", ""))
        chapter_no = entry.get("chapter")
        chapter_title = chapter_titles.get(int(chapter_no), "") if isinstance(chapter_no, int) else ""
        part_id = entry.get("part")
        part_title = part_titles.get(str(part_id), "") if part_id is not None else ""
        expected = (subsection_id, title, chapter_title, part_title)
        expected_headings.append(expected)
        expected_by_id[subsection_id] = expected
    expected_headings.sort(key=lambda item: id_to_tuple(item[0]))

    metadata_path_set = set()
    metadata_parent_paths = set()
    for part_id in part_ids_in_scope:
        part_title = part_titles.get(part_id, "")
        if part_title:
            metadata_path_set.add(canonical_path(part_title))
    if any(entry.get("part") is None for entry in metadata_chapters):
        metadata_path_set.add(canonical_path("Introduction"))
    for entry in metadata_chapters:
        part_id = entry.get("part")
        chapter_no = entry.get("chapter")
        if not isinstance(chapter_no, int):
            continue
        chapter_title = chapter_titles.get(chapter_no, "")
        part_title = part_titles.get(str(part_id), "") if part_id is not None else "Introduction"
        if part_title and chapter_title:
            path = canonical_path(f"{part_title}/{chapter_title}")
            metadata_path_set.add(path)
            metadata_parent_paths.add(path)
    for entry in metadata_sections:
        section_id = str(entry.get("section", "")).strip()
        if not section_id:
            continue
        if any(str(sub.get("section", "")).strip() == section_id for sub in metadata_subsections):
            chapter_no = entry.get("chapter")
            chapter_title = chapter_titles.get(int(chapter_no), "") if isinstance(chapter_no, int) else ""
            part_id = entry.get("part")
            part_title = part_titles.get(str(part_id), "") if part_id is not None else "Introduction"
            section_title = normalize_text(entry.get("title", ""))
            if part_title and chapter_title and section_title:
                path = canonical_path(f"{part_title}/{chapter_title}/{section_title}")
                metadata_path_set.add(path)
                metadata_parent_paths.add(path)
        else:
            chapter_no = entry.get("chapter")
            chapter_title = chapter_titles.get(int(chapter_no), "") if isinstance(chapter_no, int) else ""
            part_id = entry.get("part")
            part_title = part_titles.get(str(part_id), "") if part_id is not None else "Introduction"
            section_title = normalize_text(entry.get("title", ""))
            if part_title and chapter_title and section_title:
                metadata_path_set.add(canonical_path(f"{part_title}/{chapter_title}/{section_title}"))
    for entry in metadata_subsections:
        subsection_id = str(entry.get("subsection", "")).strip()
        if not subsection_id:
            continue
        chapter_no = entry.get("chapter")
        chapter_title = chapter_titles.get(int(chapter_no), "") if isinstance(chapter_no, int) else ""
        part_id = entry.get("part")
        part_title = part_titles.get(str(part_id), "") if part_id is not None else "Introduction"
        section_title = normalize_text(next(
            (sec.get("title", "") for sec in metadata_sections if str(sec.get("section", "")).strip() == str(entry.get("section", "")).strip()),
            "",
        ))
        subsection_title = normalize_text(entry.get("title", ""))
        if part_title and chapter_title and section_title and subsection_title:
            metadata_path_set.add(canonical_path(f"{part_title}/{chapter_title}/{section_title}/{subsection_title}"))

    chunk_headings: List[Tuple[int, str, str, str]] = []
    for r in chunks:
        parsed = parse_chunk_heading(r.get("text", ""))
        if not parsed:
            continue
        sid, title = parsed
        chunk_headings.append((int(r["chunk_index"]), sid, title, r.get("section_path", "")))

    expected_ids = [sid for sid, _, _, _ in expected_headings]
    chunk_ids = [sid for _, sid, _, _ in chunk_headings]
    expected_id_set = set(expected_ids)
    chunk_id_set = set(chunk_ids)

    order_viol = []
    jump_viol = []
    for i in range(1, len(chunk_headings)):
        _, prev_sid, _, _ = chunk_headings[i - 1]
        cur_idx, cur_sid, _, _ = chunk_headings[i]
        a = id_to_tuple(prev_sid)
        b = id_to_tuple(cur_sid)
        if b <= a:
            order_viol.append((cur_idx, prev_sid, cur_sid))
            continue
        if len(a) == len(b) and a[:-1] == b[:-1] and b[-1] > a[-1] + 1:
            jump_viol.append((cur_idx, prev_sid, cur_sid))

    dup_ids = [sid for sid, c in Counter(chunk_ids).items() if c > 1]
    missing_ids = sorted(expected_id_set - chunk_id_set, key=id_to_tuple)
    unexpected_ids = sorted(chunk_id_set - expected_id_set, key=id_to_tuple)

    path_hierarchy_viol = []
    chunk_paths = [
        (int(r["chunk_index"]), r.get("section_path", []), canonical_path(r.get("section_path", [])))
        for r in chunks
    ]
    for idx, path, canon in chunk_paths:
        if canon and canon not in metadata_path_set:
            path_hierarchy_viol.append(("unknown_path", idx, path))
    for parent_path in sorted(metadata_parent_paths):
        descendant_positions = [
            idx for idx, _path, canon in chunk_paths
            if len(canon) > len(parent_path) and canon[:len(parent_path)] == parent_path
        ]
        if not descendant_positions:
            continue
        lo = min(descendant_positions)
        hi = max(descendant_positions)
        for idx, path, canon in chunk_paths:
            if canon == parent_path and lo < idx < hi:
                path_hierarchy_viol.append(("midstream_parent", idx, path))

    title_mismatch = []
    checked = 0
    for idx, sid, head_title, _ in chunk_headings:
        expected = expected_by_id.get(sid)
        if expected is None:
            continue
        checked += 1
        expected_title = expected[1]
        if not title_consistent(expected_title, head_title, args.prefix_window):
            title_mismatch.append((idx, sid, expected_title, head_title[:120]))

    mismatch_ratio = (len(title_mismatch) / checked) if checked else 0.0
    metadata_counts = {
        "metadata_parts": len(part_ids_in_scope),
        "metadata_chapters": len(metadata_chapters),
        "metadata_sections": len(metadata_sections),
        "metadata_subsections": len(metadata_subsections),
    }
    violation_counts = {
        "order_violations": len(order_viol),
        "jump_violations": len(jump_viol),
        "path_hierarchy_violations": len(path_hierarchy_viol),
        "duplicate_heading_ids": len(dup_ids),
        "missing_heading_ids": len(missing_ids),
        "unexpected_heading_ids": len(unexpected_ids),
    }
    violation_samples = {
        "order_violations": [cur_sid for _, _, cur_sid in order_viol],
        "jump_violations": [cur_sid for _, _, cur_sid in jump_viol],
        "path_hierarchy_violations": [f"{kind}:{path}@{idx}" for kind, idx, path in path_hierarchy_viol],
        "duplicate_heading_ids": dup_ids,
        "missing_heading_ids": missing_ids,
        "unexpected_heading_ids": unexpected_ids,
    }
    counts_width = max(
        max(len(name) for name in metadata_counts),
        max(len(name) for name in violation_counts),
    )

    scope_page_span = (
        f"{metadata_page_span[0]}..{metadata_page_span[1]}"
        if metadata_page_span
        else f"{min_chunk_page}..{max_chunk_page}"
    )
    print(
        f"chunks={len(chunks)} scope_page_span={scope_page_span} "
        f"expected_headings={len(expected_headings)} chunk_headings={len(chunk_headings)}"
    )
    print("metadata:")
    for name, value in metadata_counts.items():
        print(f"  {name:<{counts_width}} = {value}")
    print("violations:")
    for name, value in violation_counts.items():
        print(
            f"  {name:<{counts_width}} = {value} "
            f"{format_samples(violation_samples[name])}"
        )
    print(
        f"title_consistency_checked={checked} title_mismatch={len(title_mismatch)} "
        f"mismatch_ratio={mismatch_ratio:.3f} "
        f"allow_title_mismatch_ratio={args.allow_title_mismatch_ratio:.3f}"
    )

    fail = False
    if order_viol:
        fail = True
    if jump_viol:
        fail = True
    if dup_ids:
        fail = True
    if path_hierarchy_viol:
        fail = True
    if missing_ids:
        fail = True
    if unexpected_ids:
        fail = True
    if mismatch_ratio > args.allow_title_mismatch_ratio:
        print(
            f"VIOLATION: title mismatch ratio {mismatch_ratio:.3f} > "
            f"allow_title_mismatch_ratio {args.allow_title_mismatch_ratio:.3f}"
        )
        fail = True

    if fail:
        if args.report_only:
            print("WARN: structure checks failed (report-only)")
            return
        print("FAIL: structure checks failed")
        sys.exit(1)

    print("OK: structure checks passed")


if __name__ == "__main__":
    main()
