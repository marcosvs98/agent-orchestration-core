import asyncio
import sys
from pathlib import Path


def _repo_root() -> Path:
    for anc in Path(__file__).resolve().parents:
        if (anc / "pyproject.toml").exists():
            return anc
    raise SystemExit("repository root not found")


root = _repo_root()
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root / "resources" / "scripts"))
sys.path.insert(0, str(root))

from seeds.demo.run import main

if __name__ == "__main__":
    asyncio.run(main())
