from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


EVIDENCE_ROOT = Path(__file__).resolve().parents[3] / "docs" / "validation"


def write_markdown(filename: str, sections: Iterable[str]) -> None:
    """Write concatenated markdown sections to the validation evidence directory."""
    content = "\n\n".join(sections)
    path = EVIDENCE_ROOT / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def json_block(title: str, payload: Any) -> str:
    """Format a title and JSON payload as a markdown block."""
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    return f"### {title}\n\n```json\n{rendered}\n```"


def text_block(title: str, body: str) -> str:
    """Format a simple text section."""
    return f"### {title}\n\n{body}"
