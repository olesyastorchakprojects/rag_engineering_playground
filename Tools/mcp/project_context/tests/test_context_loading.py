from __future__ import annotations

from pathlib import Path

from validators import validate_context_file


def test_context_yaml_is_valid() -> None:
    path = Path(__file__).resolve().parents[1] / "context.yaml"
    validate_context_file(path)
