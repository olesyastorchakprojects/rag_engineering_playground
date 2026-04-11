from __future__ import annotations

from pathlib import Path

import yaml


def validate_context_file(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    required_top_level = [
        "project",
        "operational_defaults",
        "system_roles",
        "data_flow",
        "debugging_defaults",
        "language_boundaries",
        "decision_rules",
    ]

    for key in required_top_level:
        if key not in data:
            raise ValueError(f"Missing required top-level key: {key}")
