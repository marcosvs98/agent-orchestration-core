from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Final

STATE_DIR: Final[Path] = Path(__file__).resolve().parents[1] / ".state"
DEFAULT_STATE_FILE: Final[Path] = STATE_DIR / "full_tenant_setup.json"


class DemoState:
    def __init__(self, path: Path = DEFAULT_STATE_FILE) -> None:
        self.path = path
        self.values: Dict[str, Any] = {}

    def load(self) -> "DemoState":
        if not self.path.exists():
            raise SystemExit(
                f"no provisioning state at {self.path}\n"
                "run it first: PYTHONPATH=src uv run python -m examples.full_tenant_setup"
            )
        self.values = json.loads(self.path.read_text(encoding="utf-8"))
        return self

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.values, indent=2, sort_keys=True), encoding="utf-8")

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def get(self, key: str) -> Any:
        if key not in self.values:
            raise SystemExit(f"provisioning state is missing '{key}'; re-run full_tenant_setup")
        return self.values[key]

    def optional(self, key: str) -> Any:
        return self.values.get(key)
