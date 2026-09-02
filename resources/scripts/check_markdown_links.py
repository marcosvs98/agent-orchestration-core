from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
MKDOCS_CONFIG = REPO_ROOT / "mkdocs.yml"

SKIPPED_DIRECTORIES = frozenset(
    {
        "__pycache__",
        "site",
        "htmlcov",
        "docker-volumes",
        "node_modules",
    }
)
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "tel:", "ftp:", "//")
UNRESOLVABLE_URL_MARKERS = ("github.com/OWNER/",)

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE_PATTERN = re.compile(r"^\s*(```|~~~)")


def markdown_files() -> list[Path]:
    found: list[Path] = []
    for path in REPO_ROOT.rglob("*.md"):
        parts = path.relative_to(REPO_ROOT).parts
        if any(part in SKIPPED_DIRECTORIES or part.startswith(".") for part in parts):
            continue
        found.append(path)
    return sorted(found)


def excluded_doc_patterns() -> list[str]:
    if not MKDOCS_CONFIG.is_file():
        return []
    lines = MKDOCS_CONFIG.read_text(encoding="utf-8").splitlines()
    patterns: list[str] = []
    collecting = False
    for line in lines:
        if line.startswith("exclude_docs:"):
            collecting = True
            continue
        if collecting:
            if line.startswith(" ") and line.strip():
                patterns.append(line.strip())
            elif line.strip():
                break
    return patterns


def is_excluded_from_site(relative_to_docs: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        cleaned = pattern.lstrip("/")
        if cleaned.endswith("/"):
            if relative_to_docs.startswith(cleaned):
                return True
        elif relative_to_docs == cleaned:
            return True
    return False


def links_in(path: Path) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_PATTERN.finditer(line):
            found.append((number, match.group(1)))
    return found


def main() -> int:
    patterns = excluded_doc_patterns()
    dead: list[str] = []
    unresolvable: list[str] = []
    into_excluded: list[str] = []

    for path in markdown_files():
        display = path.relative_to(REPO_ROOT)
        source_is_published_doc = DOCS_DIR in path.parents and not is_excluded_from_site(
            str(path.relative_to(DOCS_DIR)), patterns
        )

        for number, raw_target in links_in(path):
            if any(marker in raw_target for marker in UNRESOLVABLE_URL_MARKERS):
                unresolvable.append(f"{display}:{number} -> {raw_target}")
                continue
            if raw_target.startswith(EXTERNAL_SCHEMES) or raw_target.startswith("#"):
                continue

            target = unquote(raw_target.split("#", 1)[0].split("?", 1)[0])
            if not target:
                continue

            base = REPO_ROOT if target.startswith("/") else path.parent
            resolved = (base / target.lstrip("/")).resolve()

            if not resolved.exists():
                dead.append(f"{display}:{number} -> {raw_target}")
                continue

            if source_is_published_doc and DOCS_DIR in resolved.parents:
                if is_excluded_from_site(str(resolved.relative_to(DOCS_DIR)), patterns):
                    into_excluded.append(f"{display}:{number} -> {raw_target}")

    for title, entries in (
        ("Dead links (target does not exist)", dead),
        ("Unresolvable repository URLs", unresolvable),
        ("Published pages linking into the excluded set", into_excluded),
    ):
        if entries:
            print(f"\n{title}: {len(entries)}")
            for entry in entries:
                print(f"  {entry}")

    total = len(dead) + len(unresolvable) + len(into_excluded)
    if total:
        print(f"\nFAIL: {total} broken markdown link(s).")
        return 1
    print(f"OK: checked {len(markdown_files())} markdown files, no broken links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
