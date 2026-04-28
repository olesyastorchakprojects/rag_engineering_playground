You are writing one Python script: `chanker.py`.
This is a CLI chunker for a book. It must build chunks using only page `clean_text` and `book_content_metadata.json`.

The script must:
- use only the standard library;
- be metadata-driven;
- not fix or clean text;
- not build book structure heuristically from scratch;
- operate only as a CLI;
- write one JSONL output file.

## 1. Purpose
The chunker must:
- read already prepared page-level `clean_text`;
- read valid content metadata;
- build the metadata tree `part -> chapter -> section -> subsection`;
- turn this tree structure into a sequence of chunks;
- preserve text segments in their original form, with only soft whitespace normalization.

The chunker must not:
- clean extraction artifacts;
- join split words;
- remove captions;
- fix OCR;
- reconstruct structure without metadata;
- write auxiliary `.txt` files.

## 2. CLI
Required arguments:
- `--pages` (`Path`)
- `--metadata` (`Path`)
- `--book-metadata` (`Path`)
- `--out` (`Path`)

There must be no default paths.

Argument descriptions:
- `--pages`: input page-level JSONL
- `--metadata`: validated content metadata JSON
- `--book-metadata`: document-level metadata JSON (document_title, url, tags)
- `--out`: output chunks JSONL

## 3. Inputs
The `--pages` file:
- JSONL;
- each non-empty line is a JSON object;
- the following fields are used:
  - `page`
  - `clean_text`

`page` must be interpreted as `int`.
`clean_text` must be interpreted as `str`, default `""`.

The `--metadata` file:
- a JSON object;
- must be loaded only through the shared validator:
  - `Execution/parsing/common/book_metadata_validation.py`
  - function: `load_and_validate_book_content_metadata(path)`

If metadata is missing or does not pass validation:
- the chunker must fail;
- metadata is required; there must be no alternative structure source.

## 4. Output Constants
The following values must be loaded from `--book-metadata` JSON at startup:
- `TITLE` — from field `document_title` (`str`, required)
- `URL` — from field `url` (`str`, required)
- `TAGS` — from field `tags` (`list[str]`, required)

If any of these fields is missing or has the wrong type, the chunker must fail with a clear error message.

The following remain as fixed constants:
- `CHUNKING_VERSION = "v1"`

The following must be created once per run:
- `DOC_ID = str(uuid.uuid4())`
- `START_TS = datetime.now(timezone.utc)` — captured once at startup; used as base for `chunk_created_at`

## 5. Normalization
The following helper functions are required:

`normalize_line(s: str) -> str`
- returns `re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ").strip())`

`clean_title(s: str) -> str`
- returns `normalize_line(s).strip(" .:-")`

`title_case(s: str) -> str`
- returns `clean_title(s).title()`

Important:
- no other text cleanup is allowed;
- chunk text must not be changed semantically.

## 6. Page Loading
The following function is required:
`load_clean_pages(path: Path) -> List[Dict]`

Logic:
- read JSONL;
- for each line, build an object:
  - `page = int(rec.get("page", idx))`
  - `clean_text = normalize_line(rec.get("clean_text", "") or "")`
- sort rows by `page`
- return the list of rows

If `pages` is empty after loading:
- `build_structured_chunks()` must raise `RuntimeError(f"No pages loaded from {pages_path}")`

## 7. Metadata Tree
The following function is required:
`build_tree(metadata: Dict) -> List[Dict]`

It must build tree nodes at four levels:
- `part`
- `chapter`
- `section`
- `subsection`

Each node must contain:
- `level`
- `title`
- `part_title`
- `chapter_title`
- `section_title`
- `subsection_title`
- `start_page`
- `end_page`
- `children`
- `anchor_patterns`

Additional id fields by level:
- `part`: `part_id`
- `chapter`: `chapter_num`
- `section`: `section_id`
- `subsection`: `subsection_id`

Rules:
- `parts` are taken from metadata as-is;
- chapters with `part is None` must be grouped under a virtual part:
  - `part_id = "0"`
  - `title = "Introduction"`
  - `virtual = True`
- `part_title/chapter_title/section_title/subsection_title` must form the future path;
- default tail values until a deeper level appears:
  - `chapter_title = "Overview"`
  - `section_title = "Overview"`
  - `subsection_title = "Overview"`

## 8. Page Source
The following function is required:
`build_page_source(pages) -> Tuple[str, Dict[int, str], Dict[int, Tuple[int, int]]]`

Logic:
- `source` must be built only from non-empty `clean_text`;
- exactly one space must be inserted between pages;
- return:
  - the full `source`
  - `page_text[page] = text`
  - `page_offsets[page] = (start, end)`

The following helper functions are required:
- `first_offset_in_range(start_page, end_page, page_offsets)`
- `last_offset_in_range(start_page, end_page, page_offsets)`

They must search for the first / last non-empty page in the range.

## 9. Anchor Patterns
The following function is required:
`anchor_patterns(node) -> List[re.Pattern]`

Patterns by level:

`part`:
- strong: `r"\bPart\s+{part_id}(?:\s+{title})?\b"`
- weak: `r"\b{title}\b"`

`chapter`:
- strong: `r"\bChapter\s+{chapter_num}(?:\.)?\s+{title}\b"`
- weak: `r"\b{title}\b"`

`section`:
- strong: `r"\b{section_id_pattern}\s+{title}\b"`
- weak: `r"\b{title}\b"`

`subsection`:
- strong: `r"\b{subsection_id_pattern}\s+{title}\b"`
- weak: `r"\b{title}\b"`

`section_id_pattern(section_id)`:
- must allow spaces around dots:
  - `"7.3.1"` -> regex with `\s*\.\s*`

## 10. Anchor Offset Search
The following function is required:
`find_anchor_offset(node, page_text, page_offsets) -> int`

Logic:
- if the node is `virtual`, return `first_offset_in_range(...)`
- strong pattern = the first pattern
- weak patterns = the remaining patterns

Search order:
1. if `prev_page = start_page - 1` exists and is present in `page_offsets`:
   - search the strong pattern on the previous page
   - if found, return the absolute offset
2. search strong patterns on pages in the range
3. search weak patterns on pages in the range
4. fallback:
   - `first_offset_in_range(start_page, end_page, page_offsets)`

This is required so that a heading placed on the previous page can become the node anchor.

## 11. Tree Sorting
The following are required:
- `dotted_id_key(value)`
- `ROMAN_PART_ORDER`
- `node_sort_key(node)`
- `sort_tree(nodes)`

Ordering:
- `part` by roman order `0, I, II, III, IV, V`
- `chapter` by `chapter_num`
- `section` by numeric dotted id
- `subsection` by numeric dotted id

This is required so that same-page siblings are not reordered by title.

## 12. Segmentation
The following helper functions are required:
- `interval_text(source, interval)`
- `offset_to_page(offset, page_offsets)`
- `make_chunk(node, interval, source, page_offsets)`

`make_chunk(...)` must return a dict with:
- `page_start`
- `page_end`
- `part`
- `chapter`
- `section`
- `subsection`
- `text`

If the text is empty after `interval_text`, return `None`.

Main function:
`emit_node(node, source, page_text, page_offsets, next_sibling_start=None, upper_bound=None)`

Logic:
1. `start_offset = find_anchor_offset(node, ...)`
2. `end_offset = last_offset_in_range(node["start_page"], node["end_page"], page_offsets)`
3. if `next_sibling_start` exists, cap `end_offset = min(end_offset, next_sibling_start)`
4. if `upper_bound` exists, cap `end_offset = min(end_offset, upper_bound)`
5. `node_interval = (start_offset, end_offset)`

If the node has no children:
- return one chunk for `node_interval`

If the node has children:
- recursively call `emit_node(...)` for each child
- `next_child_start` must be computed through `find_anchor_offset(next_child, ...)`
- the child's `upper_bound` must be `node_interval[1]`

Residual logic:
- leading residual before the first child -> separate parent chunk
- middle residual between child intervals:
  - must not become a separate parent chunk
  - must be attached to the last chunk of the previous child
- trailing residual after the last child -> separate parent chunk

This is a mandatory contract:
- parent chunks are allowed as intro / trailing residuals;
- there must be no midstream parent chunk between children.

## 13. Root Assembly
The following function is required:
`build_structured_chunks(pages_path, metadata_path) -> List[Dict]`

Logic:
- load pages
- load metadata through the validator
- build `source`, `page_text`, `page_offsets`
- build roots through `build_tree(metadata)`
- for each root:
  - compute `next_root_start`
  - call `emit_node(...)`
- collect all `(offset, chunk)` pairs
- sort them by offset
- return only the list of chunk dicts

Front matter and back matter must not be chunked unless they are described in content metadata.

## 14. Section Path
The following function is required:
`build_section_path(chunk: Dict) -> str`

Logic:
- take:
  - `part`
  - `chapter`
  - `section`
  - `subsection`
- while the list length is > 1 and the last element == `"Overview"`, remove the tail
- return the list of path segments

Consequence:
- part-only chunk -> `PartTitle`
- chapter intro chunk -> `PartTitle/ChapterTitle`
- section intro chunk -> `PartTitle/ChapterTitle/SectionTitle`
- leaf subsection -> full path down to the subsection

## 15. JSONL Output
The following function is required:
`materialize_jsonl(chunks, out_path)`

For each chunk, in `enumerate(chunks)` order, write a record with:
- `doc_id = DOC_ID`
- `chunk_id = str(uuid.uuid4())`
- `url = URL`
- `document_title = TITLE`
- `section_title = section_path[-1] if section_path else None`
- `section_path = build_section_path(chunk)`
- `chunk_index = idx`
- `page_start = chunk["page_start"]`
- `page_end = chunk["page_end"]`
- `tags = TAGS`
- `content_hash = "sha256:" + sha256(text.encode("utf-8")).hexdigest()`
- `chunking_version = CHUNKING_VERSION`
- `chunk_created_at = (START_TS + timedelta(minutes=idx)).isoformat().replace("+00:00", "Z")`
- `text = chunk["text"]`

Do not write the `ingest` field before the ingest stage.

Write only to `--out`.
There must be no additional output directories.

## 16. CLI and Print Output
The following function is required:
`parse_args()`

Description:
- `"Build metadata-driven chunks from page JSONL"`

After `materialize_jsonl(...)`, `main()` must print:
- `Wrote <len(chunks)> chunks to <out>`

If chunks are not empty:
- `Sample chunk path: <part> > <chapter> > <section> > <subsection>`
- `Sample chunk text: <first 500 chars>`

## 17. Contract Restrictions
The following are not allowed:
- hardcoded chapter maps;
- text cleanup heuristics;
- synthetic "fixes" for specific PDF artifacts;
- output text-file materialization;
- hidden rules that are not present in metadata and in this prompt.

If an observed scenario cannot be expressed by the current metadata schema and the current segmenter logic:
- do not add a new heuristic;
- a metadata schema update or prompt update is required.

## 18. Implementation Requirements
- Standard library only.
- Use `argparse`, `json`, `re`, `sys`, `uuid`, `datetime`, `Path`.
- Importing the shared metadata validator is allowed.
- The code must stay metadata-first and straightforward.
- At the end, the file must contain:
  - `if __name__ == "__main__":`
  - `    main()`
