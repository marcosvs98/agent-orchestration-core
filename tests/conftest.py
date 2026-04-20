"""Pytest bootstrapping: keep application packages importable before test package paths.

Test modules live under ``tests/unit/pkg/domain/...`` to mirror ``src/domain/...``. Pytest
adds parent directories (e.g. ``tests/unit/pkg``) to ``sys.path`` so that layout is
importable as ``tests.unit.pkg.domain...``. That also makes a *top-level* ``domain``
package resolve to ``tests/unit/pkg/domain``, which shadows ``src/domain`` and breaks
``from domain....`` imports. Prepend ``src`` so the application package wins.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = str(_ROOT / "src")
if _SRC in sys.path:
    sys.path.remove(_SRC)
sys.path.insert(0, _SRC)
