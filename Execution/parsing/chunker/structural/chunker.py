#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata

DOC_ID = str(uuid.uuid4())
TITLE = "Understanding Distributed Systems (2nd Edition)"
URL = "local://Understanding-Distributed-Systems-2nd-Edition.pdf"
TAGS = ["distributed-systems", "book", "architecture", "qdrant-learning"]
START_TS = datetime(2026, 2, 17, 9, 0, 0, tzinfo=timezone.utc)
CHUNKING_VERSION = "v1"
SCHEMA_VERSION = 1


def normalize_line(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ").strip())


def clean_title(s: str) -> str:
    return normalize_line(s).strip(" .:-")


def title_case(s: str) -> str:
    return clean_title(s).title()


def load_clean_pages(path: Path) -> List[Dict]:
    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            rec = json.loads(line)
            rows.append(
                {
                    "page": int(rec.get("page", idx)),
                    "clean_text": normalize_line(rec.get("clean_text", "") or ""),
                }
            )
    rows.sort(key=lambda r: r["page"])
    return rows


def load_metadata(path: Path) -> Dict:
    return load_and_validate_book_content_metadata(path)


def range_from_entry(entry: Dict) -> Tuple[Optional[int], Optional[int]]:
    ranges = entry.get("ranges") or {}
    pdf = ranges.get("pdf") if isinstance(ranges, dict) else None
    if not isinstance(pdf, dict):
        return None, None
    start = pdf.get("start")
    end = pdf.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return None, None
    return start, end


def section_id_pattern(section_id: str) -> str:
    return r"\s*\.\s*".join(re.escape(part) for part in section_id.split(".") if part)


def anchor_patterns(node: Dict) -> List[re.Pattern]:
    title = clean_title(node["title"])
    title_pat = re.escape(title).replace(r"\ ", r"\s+")
    patterns: List[str] = []
    if node["level"] == "part":
        part_id = re.escape(str(node["part_id"]))
        patterns.append(rf"\bPart\s+{part_id}(?:\s+{title_pat})?\b")
        patterns.append(rf"\b{title_pat}\b")
    elif node["level"] == "chapter":
        patterns.append(rf"\bChapter\s+{node['chapter_num']}(?:\.)?\s+{title_pat}\b")
        patterns.append(rf"\b{title_pat}\b")
    elif node["level"] == "section":
        sid = section_id_pattern(node["section_id"])
        patterns.append(rf"\b{sid}\s+{title_pat}\b")
        patterns.append(rf"\b{title_pat}\b")
    elif node["level"] == "subsection":
        sid = section_id_pattern(node["subsection_id"])
        patterns.append(rf"\b{sid}\s+{title_pat}\b")
        patterns.append(rf"\b{title_pat}\b")
    return [re.compile(pattern, flags=re.I) for pattern in patterns]


def build_page_source(pages: List[Dict]) -> Tuple[str, Dict[int, str], Dict[int, Tuple[int, int]]]:
    source_parts: List[str] = []
    page_text: Dict[int, str] = {}
    page_offsets: Dict[int, Tuple[int, int]] = {}
    cursor = 0
    for row in pages:
        text = row["clean_text"]
        if not text:
            continue
        page = row["page"]
        if source_parts:
            cursor += 1
        start = cursor
        source_parts.append(text)
        cursor += len(text)
        end = cursor
        page_text[page] = text
        page_offsets[page] = (start, end)
    return " ".join(source_parts), page_text, page_offsets


def first_offset_in_range(start_page: int, end_page: int, page_offsets: Dict[int, Tuple[int, int]]) -> int:
    for page in range(start_page, end_page + 1):
        if page in page_offsets:
            return page_offsets[page][0]
    return 0


def last_offset_in_range(start_page: int, end_page: int, page_offsets: Dict[int, Tuple[int, int]]) -> int:
    for page in range(end_page, start_page - 1, -1):
        if page in page_offsets:
            return page_offsets[page][1]
    return 0


def build_tree(metadata: Dict) -> List[Dict]:
    parts_by_key: Dict[Optional[str], Dict] = {}

    for entry in metadata.get("parts") or []:
        if not isinstance(entry, dict):
            continue
        part_id = entry.get("part")
        start, end = range_from_entry(entry)
        if part_id is None or start is None or end is None:
            continue
        node = {
            "level": "part",
            "part_id": str(part_id),
            "title": title_case(entry.get("title", "")),
            "part_title": title_case(entry.get("title", "")),
            "chapter_title": "Overview",
            "section_title": "Overview",
            "subsection_title": "Overview",
            "start_page": start,
            "end_page": end,
            "children": [],
        }
        node["anchor_patterns"] = anchor_patterns(node)
        parts_by_key[str(part_id)] = node

    intro_chapters = [c for c in metadata.get("chapters") or [] if isinstance(c, dict) and c.get("part") is None]
    if intro_chapters:
        starts = [range_from_entry(c)[0] for c in intro_chapters if range_from_entry(c)[0] is not None]
        ends = [range_from_entry(c)[1] for c in intro_chapters if range_from_entry(c)[1] is not None]
        if starts and ends:
            intro_node = {
                "level": "part",
                "part_id": "0",
                "title": "Introduction",
                "virtual": True,
                "part_title": "Introduction",
                "chapter_title": "Overview",
                "section_title": "Overview",
                "subsection_title": "Overview",
                "start_page": min(starts),
                "end_page": max(ends),
                "children": [],
            }
            intro_node["anchor_patterns"] = anchor_patterns(intro_node)
            parts_by_key[None] = intro_node

    chapters_by_num: Dict[int, Dict] = {}
    for entry in metadata.get("chapters") or []:
        if not isinstance(entry, dict):
            continue
        chapter_num = entry.get("chapter")
        start, end = range_from_entry(entry)
        if not isinstance(chapter_num, int) or start is None or end is None:
            continue
        part_key = entry.get("part")
        parent = parts_by_key.get(str(part_key)) if part_key is not None else parts_by_key.get(None)
        part_title = parent["part_title"] if parent is not None else "Book"
        title = title_case(entry.get("title", ""))
        node = {
            "level": "chapter",
            "chapter_num": chapter_num,
            "title": title,
            "part_title": part_title,
            "chapter_title": title,
            "section_title": "Overview",
            "subsection_title": "Overview",
            "start_page": start,
            "end_page": end,
            "children": [],
        }
        node["anchor_patterns"] = anchor_patterns(node)
        chapters_by_num[chapter_num] = node
        if parent is not None:
            parent["children"].append(node)

    sections_by_id: Dict[str, Dict] = {}
    for entry in metadata.get("sections") or []:
        if not isinstance(entry, dict):
            continue
        section_id = entry.get("section")
        chapter_num = entry.get("chapter")
        start, end = range_from_entry(entry)
        if not isinstance(section_id, str) or not isinstance(chapter_num, int) or start is None or end is None:
            continue
        chapter = chapters_by_num.get(chapter_num)
        if chapter is None:
            continue
        title = title_case(entry.get("title", ""))
        node = {
            "level": "section",
            "section_id": section_id,
            "title": title,
            "part_title": chapter["part_title"],
            "chapter_title": chapter["chapter_title"],
            "section_title": title,
            "subsection_title": "Overview",
            "start_page": start,
            "end_page": end,
            "children": [],
        }
        node["anchor_patterns"] = anchor_patterns(node)
        sections_by_id[section_id] = node
        chapter["children"].append(node)

    for entry in metadata.get("subsections") or []:
        if not isinstance(entry, dict):
            continue
        subsection_id = entry.get("subsection")
        section_id = entry.get("section")
        start, end = range_from_entry(entry)
        if not isinstance(subsection_id, str) or not isinstance(section_id, str) or start is None or end is None:
            continue
        section = sections_by_id.get(section_id)
        if section is None:
            continue
        title = title_case(entry.get("title", ""))
        node = {
            "level": "subsection",
            "subsection_id": subsection_id,
            "title": title,
            "part_title": section["part_title"],
            "chapter_title": section["chapter_title"],
            "section_title": section["section_title"],
            "subsection_title": title,
            "start_page": start,
            "end_page": end,
            "children": [],
        }
        node["anchor_patterns"] = anchor_patterns(node)
        section["children"].append(node)

    roots = list(parts_by_key.values())
    roots.sort(key=node_sort_key)
    sort_tree(roots)
    return roots


def dotted_id_key(value: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in value.split(".") if part)


ROMAN_PART_ORDER = {
    "0": 0,
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4,
    "V": 5,
}


def node_sort_key(node: Dict) -> Tuple:
    level = node["level"]
    if level == "part":
        return (0, ROMAN_PART_ORDER.get(str(node.get("part_id")), 999), node["start_page"], node["end_page"], node["title"])
    if level == "chapter":
        return (1, int(node["chapter_num"]), node["start_page"], node["end_page"], node["title"])
    if level == "section":
        return (2, dotted_id_key(node["section_id"]), node["start_page"], node["end_page"], node["title"])
    if level == "subsection":
        return (3, dotted_id_key(node["subsection_id"]), node["start_page"], node["end_page"], node["title"])
    return (9, node["start_page"], node["end_page"], node["title"])


def sort_tree(nodes: List[Dict]) -> None:
    for node in nodes:
        node["children"].sort(key=node_sort_key)
        sort_tree(node["children"])


def find_anchor_offset(node: Dict, page_text: Dict[int, str], page_offsets: Dict[int, Tuple[int, int]]) -> int:
    start_page = node["start_page"]
    end_page = node["end_page"]
    if node.get("virtual"):
        return first_offset_in_range(start_page, end_page, page_offsets)
    strong_patterns = node["anchor_patterns"][:1]
    weak_patterns = node["anchor_patterns"][1:]

    search_pages_in_range = [page for page in range(start_page, end_page + 1) if page in page_offsets]
    prev_page = start_page - 1 if (start_page - 1) in page_offsets else None

    if prev_page is not None:
        prev_text = page_text.get(prev_page, "")
        prev_start, _ = page_offsets[prev_page]
        for pattern in strong_patterns:
            match = pattern.search(prev_text)
            if match:
                return prev_start + match.start()

    for page in search_pages_in_range:
        page_value = page_text.get(page, "")
        page_start, _ = page_offsets[page]
        for pattern in strong_patterns:
            match = pattern.search(page_value)
            if match:
                return page_start + match.start()

    for page in search_pages_in_range:
        page_value = page_text.get(page, "")
        page_start, _ = page_offsets[page]
        for pattern in weak_patterns:
            match = pattern.search(page_value)
            if match:
                return page_start + match.start()

    return first_offset_in_range(start_page, end_page, page_offsets)


def offset_to_page(offset: int, page_offsets: Dict[int, Tuple[int, int]]) -> int:
    page_no = 0
    for page, (start, end) in sorted(page_offsets.items()):
        if start <= offset < end:
            return page
        if offset < start:
            return page
        page_no = page
    return page_no


def subtract_intervals(parent: Tuple[int, int], children: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    start, end = parent
    if start >= end:
        return []
    merged: List[Tuple[int, int]] = []
    for child_start, child_end in sorted(children):
        child_start = max(start, child_start)
        child_end = min(end, child_end)
        if child_start >= child_end:
            continue
        if not merged or child_start > merged[-1][1]:
            merged.append((child_start, child_end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], child_end))
    residuals: List[Tuple[int, int]] = []
    cursor = start
    for child_start, child_end in merged:
        if cursor < child_start:
            residuals.append((cursor, child_start))
        cursor = max(cursor, child_end)
    if cursor < end:
        residuals.append((cursor, end))
    return residuals


def interval_text(source: str, interval: Tuple[int, int]) -> str:
    start, end = interval
    return normalize_line(source[start:end])


def make_chunk(node: Dict, interval: Tuple[int, int], source: str, page_offsets: Dict[int, Tuple[int, int]]) -> Optional[Dict]:
    text = interval_text(source, interval)
    if not text:
        return None
    page_start, page_end = interval_page_span(interval, page_offsets)
    return {
        "page_start": page_start,
        "page_end": page_end,
        "part": node["part_title"],
        "chapter": node["chapter_title"],
        "section": node["section_title"],
        "subsection": node["subsection_title"],
        "text": text,
    }


def interval_page_span(interval: Tuple[int, int], page_offsets: Dict[int, Tuple[int, int]]) -> Tuple[int, int]:
    covered_pages = [
        page
        for page, (start, end) in sorted(page_offsets.items())
        if start < interval[1] and interval[0] < end
    ]
    if covered_pages:
        page_start = covered_pages[0]
        page_end = covered_pages[-1]
    else:
        page_start = offset_to_page(interval[0], page_offsets)
        page_end = offset_to_page(max(interval[0], interval[1] - 1), page_offsets)
    return page_start, page_end


def emit_node(
    node: Dict,
    source: str,
    page_text: Dict[int, str],
    page_offsets: Dict[int, Tuple[int, int]],
    next_sibling_start: Optional[int] = None,
    upper_bound: Optional[int] = None,
) -> Tuple[Tuple[int, int], List[Tuple[int, Dict]]]:
    start_offset = find_anchor_offset(node, page_text, page_offsets)
    end_offset = last_offset_in_range(node["start_page"], node["end_page"], page_offsets)
    if next_sibling_start is not None:
        end_offset = min(end_offset, next_sibling_start)
    if upper_bound is not None:
        end_offset = min(end_offset, upper_bound)
    node_interval = (start_offset, end_offset)

    children = node["children"]
    if not children:
        chunk = make_chunk(node, node_interval, source, page_offsets)
        return node_interval, ([(node_interval[0], chunk)] if chunk else [])

    child_results: List[Tuple[Tuple[int, int], List[Tuple[int, Dict]]]] = []
    child_intervals: List[Tuple[int, int]] = []
    for idx, child in enumerate(children):
        next_child = children[idx + 1] if idx + 1 < len(children) else None
        next_child_start = find_anchor_offset(next_child, page_text, page_offsets) if next_child is not None else None
        child_interval, child_chunks = emit_node(
            child,
            source,
            page_text,
            page_offsets,
            next_child_start,
            node_interval[1],
        )
        child_intervals.append(child_interval)
        child_results.append((child_interval, child_chunks))

    chunks: List[Tuple[int, Dict]] = []

    if child_intervals:
        first_child_start = child_intervals[0][0]
        if node_interval[0] < first_child_start:
            leading = (node_interval[0], first_child_start)
            chunk = make_chunk(node, leading, source, page_offsets)
            if chunk:
                chunks.append((leading[0], chunk))

        for idx in range(len(child_intervals) - 1):
            gap = (child_intervals[idx][1], child_intervals[idx + 1][0])
            if gap[0] >= gap[1]:
                continue
            gap_text = interval_text(source, gap)
            if not gap_text:
                continue
            prev_chunks = child_results[idx][1]
            if prev_chunks:
                prev_pos, prev_chunk = prev_chunks[-1]
                prev_chunk["text"] = normalize_line(f"{prev_chunk['text']} {gap_text}")
                _gap_start, gap_end = interval_page_span(gap, page_offsets)
                prev_chunk["page_end"] = max(int(prev_chunk["page_end"]), gap_end)
            else:
                chunk = make_chunk(node, gap, source, page_offsets)
                if chunk:
                    chunks.append((gap[0], chunk))

        last_child_end = child_intervals[-1][1]
        if last_child_end < node_interval[1]:
            trailing = (last_child_end, node_interval[1])
            chunk = make_chunk(node, trailing, source, page_offsets)
            if chunk:
                chunks.append((trailing[0], chunk))

    for _interval, child_chunks in child_results:
        chunks.extend(child_chunks)

    chunks.sort(key=lambda item: item[0])
    return node_interval, chunks


def build_structured_chunks(pages_path: Path, metadata_path: Path) -> List[Dict]:
    pages = load_clean_pages(pages_path)
    if not pages:
        raise RuntimeError(f"No pages loaded from {pages_path}")
    metadata = load_metadata(metadata_path)
    source, page_text, page_offsets = build_page_source(pages)
    roots = build_tree(metadata)

    chunks_with_pos: List[Tuple[int, Dict]] = []
    for idx, node in enumerate(roots):
        next_root = roots[idx + 1] if idx + 1 < len(roots) else None
        next_root_start = find_anchor_offset(next_root, page_text, page_offsets) if next_root is not None else None
        _interval, root_chunks = emit_node(node, source, page_text, page_offsets, next_root_start)
        chunks_with_pos.extend(root_chunks)

    chunks_with_pos.sort(key=lambda item: item[0])
    return [chunk for _pos, chunk in chunks_with_pos]


def build_section_path(chunk: Dict) -> List[str]:
    parts = [chunk["part"], chunk["chapter"], chunk["section"], chunk["subsection"]]
    while len(parts) > 1 and parts[-1] == "Overview":
        parts.pop()
    return parts


def materialize_jsonl(chunks: List[Dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for idx, chunk in enumerate(chunks):
            text = chunk["text"]
            section_path = build_section_path(chunk)
            rec = {
                "schema_version": SCHEMA_VERSION,
                "doc_id": DOC_ID,
                "chunk_id": str(uuid.uuid4()),
                "url": URL,
                "document_title": TITLE,
                "section_title": section_path[-1] if section_path else None,
                "section_path": section_path,
                "chunk_index": idx,
                "page_start": chunk["page_start"],
                "page_end": chunk["page_end"],
                "tags": TAGS,
                "content_hash": f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
                "chunking_version": CHUNKING_VERSION,
                "chunk_created_at": (START_TS + timedelta(minutes=idx)).isoformat().replace("+00:00", "Z"),
                "text": text,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build metadata-driven chunks from page JSONL")
    parser.add_argument("--pages", type=Path, required=True, help="Input page-level JSONL")
    parser.add_argument("--metadata", type=Path, required=True, help="Book content metadata JSON")
    parser.add_argument("--out", type=Path, required=True, help="Output chunks JSONL path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = build_structured_chunks(args.pages, args.metadata)
    materialize_jsonl(chunks, args.out)
    print(f"Wrote {len(chunks)} chunks to {args.out}")
    if chunks:
        sample = chunks[0]
        print("Sample chunk path:", " > ".join([sample["part"], sample["chapter"], sample["section"], sample["subsection"]]))
        print("Sample chunk text:", sample["text"][:500])


if __name__ == "__main__":
    main()
