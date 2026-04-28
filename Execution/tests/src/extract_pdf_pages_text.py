"""Re-export shim so tests can import from extract_pdf_pages_text."""
import sys
from pathlib import Path

_EXTRACTOR_DIR = Path(__file__).resolve().parents[2] / "parsing" / "extractor"
if str(_EXTRACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(_EXTRACTOR_DIR))

from extractor import (  # noqa: F401
    clean_page_text,
    load_json_file,
    normalize_line,
    validate_rules_metadata,
    validate_terms_metadata,
    load_clean_text_overrides,
)
