"""
Ground truth management for validation.

Ground truth in this context means: periods or commits where a developer
has publicly declared using AI assistance.  Without such declarations,
no label can be assigned.

Limitations:
  - Extremely sparse: few developers publicly declare AI usage per-commit.
  - Selection bias: developers who declare AI usage may have different profiles
    than those who use AI without declaring.
  - Temporal noise: declarations after the fact may not be precise about scope.

Usage:
  Register declarations in data/ground_truth/declared.yaml.
  Load with load_declared().

YAML format:
  declarations:
    - developer: torvalds
      type: "none_declared"          # "ai_assisted", "no_ai", "none_declared"
      period_start: "2022-01-01"
      period_end: "2024-12-31"
      source: "https://..."
      notes: "..."
    - developer: dhh
      type: "ai_assisted"
      period_start: "2023-06-01"
      period_end: null               # ongoing
      source: "https://twitter.com/dhh/..."
      notes: "DHH publicly stated he uses GitHub Copilot since mid-2023"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

_DEFAULT_YAML = (
    Path(__file__).parent.parent.parent.parent / "data" / "ground_truth" / "declared.yaml"
)


@dataclass
class Declaration:
    developer: str
    type: str              # "ai_assisted", "no_ai", "none_declared"
    period_start: datetime
    period_end: Optional[datetime]
    source: str
    notes: str = ""


def load_declared(path: Path = _DEFAULT_YAML) -> list[Declaration]:
    """
    Load developer AI-usage declarations from a YAML file.

    Returns an empty list if the file does not exist — do not raise,
    as running without ground truth is the normal case.
    """
    if not path.exists():
        return []

    with path.open() as f:
        data = yaml.safe_load(f) or {}

    result: list[Declaration] = []
    for raw in data.get("declarations", []):
        end = raw.get("period_end")
        result.append(Declaration(
            developer=raw["developer"],
            type=raw["type"],
            period_start=datetime.fromisoformat(raw["period_start"]),
            period_end=datetime.fromisoformat(end) if end else None,
            source=raw.get("source", ""),
            notes=raw.get("notes", ""),
        ))
    return result


def get_label(
    developer: str,
    date: datetime,
    declarations: list[Declaration],
) -> Optional[str]:
    """
    Return the ground-truth label for a developer at a given date.

    Returns None when no declaration covers this period (most common case).
    Returns "ai_assisted", "no_ai", or "none_declared" otherwise.
    """
    for decl in declarations:
        if decl.developer != developer:
            continue
        if date < decl.period_start:
            continue
        if decl.period_end is not None and date > decl.period_end:
            continue
        return decl.type
    return None


def write_template(output_path: Path) -> None:
    """Write an empty ground truth YAML template."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "declarations": [
            {
                "developer": "example_dev",
                "type": "ai_assisted",
                "period_start": "2023-06-01",
                "period_end": None,
                "source": "https://twitter.com/example_dev/...",
                "notes": "Publicly stated Copilot usage",
            }
        ]
    }
    with output_path.open("w") as f:
        yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
