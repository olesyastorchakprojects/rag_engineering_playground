#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Execution.parsing.common.book_metadata_validation import load_and_validate_book_content_metadata

SCHEMA_VERSION = 1
START_TS = datetime(2026, 2, 17, 9, 0, 0, tzinfo=timezone.utc)
PAGE_MARKER_RE = re.compile(r"<<<PAGE:(\d+)>>>")


@dataclass(frozen=True)
class PageRecord:
    page: int
    clean_text: str


@dataclass(frozen=True)
class SentenceUnit:
    sentence_text: str
    page_start: int
    page_end: int
    token_count: int


@dataclass(frozen=True)
class ChunkWindow:
    start_idx: int
    end_idx: int
    token_count: int


def fail(message: str) -> None:
    raise RuntimeError(message)


def norm_ws(text: str) -> str:
    text = (text or "").replace("\u00a0", " ")
    text = text.strip()
    return re.sub(r"\s+", " ", text)


def load_pages(path: Path) -> List[PageRecord]:
    if not path.exists():
        fail(f"Missing required pages file: {path}")
    rows: List[PageRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                fail(f"Invalid pages {path}: line {lineno} must be an object")
            page = payload.get("page")
            clean_text = payload.get("clean_text")
            if not isinstance(page, int):
                fail(f"Invalid pages {path}: line {lineno} field 'page' must be an int")
            if not isinstance(clean_text, str):
                fail(f"Invalid pages {path}: line {lineno} field 'clean_text' must be a string")
            rows.append(PageRecord(page=page, clean_text=clean_text))
    if not rows:
        fail(f"No pages loaded from {path}")
    return sorted(rows, key=lambda row: row.page)


def load_book_metadata(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"Missing required book metadata: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"Invalid book metadata {path}: root must be an object")
    for key in ("document_title", "source_pdf", "url", "book"):
        if key not in payload:
            fail(f"Invalid book metadata {path}: missing required field {key!r}")
    if not isinstance(payload.get("document_title"), str) or not payload["document_title"].strip():
        fail(f"Invalid book metadata {path}: document_title must be a non-empty string")
    if not isinstance(payload.get("source_pdf"), str) or not payload["source_pdf"].strip():
        fail(f"Invalid book metadata {path}: source_pdf must be a non-empty string")
    if not isinstance(payload.get("url"), str) or not payload["url"].strip():
        fail(f"Invalid book metadata {path}: url must be a non-empty string")
    tags = payload.get("tags")
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
        fail(f"Invalid book metadata {path}: tags must be an array of non-empty strings")
    book = payload.get("book")
    if not isinstance(book, dict):
        fail(f"Invalid book metadata {path}: book must be an object")
    for key in ("title", "edition", "version", "author", "date"):
        value = book.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(f"Invalid book metadata {path}: book.{key} must be a non-empty string")
    return payload


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        fail(f"Missing required config: {path}")
    with path.open("rb") as f:
        payload = tomllib.load(f)
    if not isinstance(payload, dict):
        fail(f"Invalid config {path}: root must be an object")

    chunking = payload.get("chunking")
    sent = payload.get("sentence_segmentation")
    tokenizer = payload.get("tokenizer")
    if not isinstance(chunking, dict):
        fail(f"Invalid config {path}: chunking must be an object")
    if not isinstance(sent, dict):
        fail(f"Invalid config {path}: sentence_segmentation must be an object")
    if not isinstance(tokenizer, dict):
        fail(f"Invalid config {path}: tokenizer must be an object")

    target_tokens = chunking.get("target_tokens")
    overlap_ratio = chunking.get("overlap_ratio")
    chunking_version = chunking.get("chunking_version")
    if not isinstance(target_tokens, int) or target_tokens < 1:
        fail(f"Invalid config {path}: chunking.target_tokens must be an int >= 1")
    if not isinstance(overlap_ratio, (int, float)) or not (0.0 <= float(overlap_ratio) < 1.0):
        fail(f"Invalid config {path}: chunking.overlap_ratio must be a number in [0.0, 1.0)")
    if not isinstance(chunking_version, str) or not chunking_version.strip():
        fail(f"Invalid config {path}: chunking.chunking_version must be a non-empty string")

    if sent.get("library") != "spacy":
        fail(f"Invalid config {path}: sentence_segmentation.library must be 'spacy'")
    if not isinstance(sent.get("library_version"), str) or not sent["library_version"].strip():
        fail(f"Invalid config {path}: sentence_segmentation.library_version must be a non-empty string")
    if sent.get("language") != "en":
        fail(f"Invalid config {path}: sentence_segmentation.language must be 'en'")

    if tokenizer.get("library") != "tokenizers":
        fail(f"Invalid config {path}: tokenizer.library must be 'tokenizers'")
    if not isinstance(tokenizer.get("source"), str) or not tokenizer["source"].strip():
        fail(f"Invalid config {path}: tokenizer.source must be a non-empty string")
    if "revision" in tokenizer and (
        not isinstance(tokenizer["revision"], str) or not tokenizer["revision"].strip()
    ):
        fail(f"Invalid config {path}: tokenizer.revision must be a non-empty string when present")

    return payload


def compute_content_start_page(content_metadata: Dict[str, Any]) -> int:
    starts: List[int] = []
    for key in ("parts", "chapters", "sections", "subsections"):
        for entry in content_metadata.get(key) or []:
            ranges = entry.get("ranges") if isinstance(entry, dict) else None
            pdf = ranges.get("pdf") if isinstance(ranges, dict) else None
            start = pdf.get("start") if isinstance(pdf, dict) else None
            if isinstance(start, int):
                starts.append(start)
    if not starts:
        fail("Unable to determine content_start_page from CONTENT_METADATA")
    return min(starts)


def build_document_stream(pages: Sequence[PageRecord], content_start_page: int) -> str:
    filtered = [row for row in pages if row.page >= content_start_page]
    if not filtered:
        fail("No pages remain after applying content_start_page")
    parts: List[str] = []
    for row in filtered:
        marker = f"<<<PAGE:{row.page}>>>"
        parts.append(f"{marker}\n{norm_ws(row.clean_text)}")
    return "\n\n".join(parts)


def init_spacy(language: str):
    try:
        import spacy
    except ModuleNotFoundError as e:
        fail(f"Missing required dependency 'spacy': {e}")
    nlp = spacy.blank(language)
    nlp.add_pipe("sentencizer")
    return nlp


def init_tokenizer(config: Dict[str, Any]):
    try:
        from tokenizers import Tokenizer
    except ModuleNotFoundError as e:
        fail(f"Missing required dependency 'tokenizers': {e}")

    source = config["tokenizer"]["source"]
    revision = config["tokenizer"].get("revision")

    source_path = Path(source)
    if source_path.exists():
        return Tokenizer.from_file(str(source_path))

    if revision:
        try:
            return Tokenizer.from_pretrained(source, revision=revision)
        except TypeError:
            # Older tokenizers releases may not accept revision.
            return Tokenizer.from_pretrained(source)
    return Tokenizer.from_pretrained(source)


def build_sentence_units(document_stream: str, nlp, tokenizer) -> List[SentenceUnit]:
    doc = nlp(document_stream)
    sentence_units: List[SentenceUnit] = []
    current_page: Optional[int] = None

    for sent in doc.sents:
        raw_span = sent.text
        page_cursor = current_page
        covered_pages: List[int] = []
        last_end = 0
        markers = list(PAGE_MARKER_RE.finditer(raw_span))
        for match in markers:
            text_before = norm_ws(raw_span[last_end:match.start()])
            if text_before:
                if page_cursor is None:
                    fail("Sentence segmentation produced text before any page marker")
                covered_pages.append(page_cursor)
            page_cursor = int(match.group(1))
            last_end = match.end()

        tail_text = norm_ws(raw_span[last_end:])
        if tail_text:
            if page_cursor is None:
                fail("Sentence segmentation produced text before any page marker")
            covered_pages.append(page_cursor)

        stripped = norm_ws(PAGE_MARKER_RE.sub(" ", raw_span))
        if markers:
            current_page = int(markers[-1].group(1))

        if not stripped:
            continue

        if not covered_pages:
            if current_page is None:
                fail("Sentence segmentation produced a span before any page marker")
            covered_pages = [current_page]

        page_start = covered_pages[0]
        page_end = covered_pages[-1]

        token_count = len(tokenizer.encode(stripped).ids)
        sentence_units.append(
            SentenceUnit(
                sentence_text=stripped,
                page_start=page_start,
                page_end=page_end,
                token_count=token_count,
            )
        )

    if not sentence_units:
        fail("Sentence segmentation produced no SentenceUnit")
    return sentence_units


def build_chunks(sentences: Sequence[SentenceUnit], target_tokens: int, overlap_ratio: float) -> List[ChunkWindow]:
    chunks: List[ChunkWindow] = []
    start = 0
    total_sentences = len(sentences)

    while start < total_sentences:
        end = start
        total_tokens = 0
        while end < total_sentences:
            total_tokens += sentences[end].token_count
            end += 1
            if total_tokens >= target_tokens:
                break

        chunk = ChunkWindow(start_idx=start, end_idx=end, token_count=total_tokens)
        chunks.append(chunk)
        if end >= total_sentences:
            break

        if overlap_ratio <= 0.0:
            start = end
            continue

        target_overlap_tokens = int(math.ceil(total_tokens * overlap_ratio))
        if target_overlap_tokens <= 0:
            start = end
            continue

        suffix_tokens = 0
        next_start = end
        for idx in range(end - 1, start - 1, -1):
            suffix_tokens += sentences[idx].token_count
            next_start = idx
            if suffix_tokens >= target_overlap_tokens:
                break

        if next_start <= start:
            if end - start <= 1:
                start = end
            else:
                start = start + 1
        else:
            start = next_start

    return chunks


def make_page_range(sentences: Sequence[SentenceUnit], chunk: ChunkWindow) -> tuple[int, int]:
    window = sentences[chunk.start_idx : chunk.end_idx]
    return (
        min(s.page_start for s in window),
        max(s.page_end for s in window),
    )


def _matching_entries(entries: Sequence[Dict[str, Any]], page: int) -> List[Dict[str, Any]]:
    matched: List[Dict[str, Any]] = []
    for entry in entries:
        ranges = entry.get("ranges") if isinstance(entry, dict) else None
        pdf = ranges.get("pdf") if isinstance(ranges, dict) else None
        start = pdf.get("start") if isinstance(pdf, dict) else None
        end = pdf.get("end") if isinstance(pdf, dict) else None
        if isinstance(start, int) and isinstance(end, int) and start <= page <= end:
            matched.append(entry)
    return matched


def annotate_section(page_start: int, content_metadata: Dict[str, Any]) -> tuple[Optional[str], List[str]]:
    parts = _matching_entries(content_metadata.get("parts") or [], page_start)
    chapters = _matching_entries(content_metadata.get("chapters") or [], page_start)
    sections = _matching_entries(content_metadata.get("sections") or [], page_start)
    subsections = _matching_entries(content_metadata.get("subsections") or [], page_start)
    front_matter = _matching_entries(content_metadata.get("front_matter") or [], page_start)

    selected_part = parts[0] if parts else None

    selected_chapter = None
    for chapter in chapters:
        chapter_part = chapter.get("part")
        if selected_part is None:
            if chapter_part is None:
                selected_chapter = chapter
                break
        elif chapter_part == selected_part.get("part"):
            selected_chapter = chapter
            break
    if selected_chapter is None and chapters and selected_part is None:
        selected_chapter = chapters[0]

    selected_section = None
    for section in sections:
        if selected_chapter is not None and section.get("chapter") == selected_chapter.get("chapter"):
            selected_section = section
            break

    selected_subsection = None
    for subsection in subsections:
        if selected_section is not None and subsection.get("section") == selected_section.get("section"):
            selected_subsection = subsection
            break

    if selected_subsection is not None:
        path: List[str] = []
        if selected_part is not None:
            path.append(str(selected_part["title"]))
        if selected_chapter is not None:
            path.append(str(selected_chapter["title"]))
        if selected_section is not None:
            path.append(str(selected_section["title"]))
        path.append(str(selected_subsection["title"]))
        return path[-1], path

    if selected_section is not None:
        path = []
        if selected_part is not None:
            path.append(str(selected_part["title"]))
        if selected_chapter is not None:
            path.append(str(selected_chapter["title"]))
        path.append(str(selected_section["title"]))
        return path[-1], path

    if selected_chapter is not None:
        path = []
        if selected_part is not None:
            path.append(str(selected_part["title"]))
        path.append(str(selected_chapter["title"]))
        return path[-1], path

    if selected_part is not None:
        path = [str(selected_part["title"])]
        return path[-1], path

    if front_matter:
        title = str(front_matter[0]["title"])
        return title, [title]

    fail(f"No CONTENT_METADATA match for page_start={page_start}")


def materialize_chunk_records(
    chunks: Sequence[ChunkWindow],
    sentences: Sequence[SentenceUnit],
    book_metadata: Dict[str, Any],
    content_metadata: Dict[str, Any],
    config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    doc_id = str(uuid.uuid4())
    out: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        window = sentences[chunk.start_idx : chunk.end_idx]
        text = " ".join(sentence.sentence_text for sentence in window)
        text = norm_ws(text)
        page_start, page_end = make_page_range(sentences, chunk)
        section_title, section_path = annotate_section(page_start, content_metadata)
        rec = {
            "schema_version": SCHEMA_VERSION,
            "doc_id": doc_id,
            "chunk_id": str(uuid.uuid4()),
            "url": book_metadata["url"],
            "document_title": book_metadata["document_title"],
            "section_title": section_title,
            "section_path": section_path,
            "chunk_index": idx,
            "page_start": page_start,
            "page_end": page_end,
            "tags": list(book_metadata["tags"]),
            "content_hash": f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
            "chunking_version": config["chunking"]["chunking_version"],
            "chunk_created_at": (START_TS + timedelta(minutes=idx)).isoformat().replace("+00:00", "Z"),
            "text": text,
        }
        out.append(rec)
    return out


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fixed-size sentence-preserving chunks from page JSONL")
    parser.add_argument("--pages", type=Path, required=True, help="Input page-level JSONL")
    parser.add_argument("--book-metadata", type=Path, required=True, help="Book-level metadata JSON")
    parser.add_argument("--content-metadata", type=Path, required=True, help="Content metadata JSON")
    parser.add_argument("--config", type=Path, required=True, help="Fixed chunker TOML config")
    parser.add_argument("--out", type=Path, required=True, help="Output chunks JSONL path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pages = load_pages(args.pages)
    book_metadata = load_book_metadata(args.book_metadata)
    content_metadata = load_and_validate_book_content_metadata(args.content_metadata)
    config = load_config(args.config)

    content_start_page = compute_content_start_page(content_metadata)
    document_stream = build_document_stream(pages, content_start_page)
    tokenizer = init_tokenizer(config)
    nlp = init_spacy(config["sentence_segmentation"]["language"])
    sentence_units = build_sentence_units(document_stream, nlp, tokenizer)
    chunks = build_chunks(
        sentence_units,
        target_tokens=int(config["chunking"]["target_tokens"]),
        overlap_ratio=float(config["chunking"]["overlap_ratio"]),
    )
    rows = materialize_chunk_records(chunks, sentence_units, book_metadata, content_metadata, config)
    write_jsonl(args.out, rows)
    print(f"Wrote {len(rows)} chunks to {args.out}")


if __name__ == "__main__":
    main()
