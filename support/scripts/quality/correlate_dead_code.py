#!/usr/bin/env python3
"""Correlate Vulture findings with coverage hits and pyproject coverage omit patterns.

Outputs categories:
- ignore_omit: file matches [tool.coverage.run] omit (do not use global % alone to judge).
- strong_remove_candidate: measured line, Vulture finding, 0 coverage hits on that line.
- investigate: partial coverage, line missing from report, or executed line still flagged.
- no_coverage_data: file not present in coverage.xml (not measured in this run).
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

VULTURE_LINE = re.compile(
    r"^(?P<path>[^:]+):(?P<line>\d+):\s*(?P<msg>.*)$",
)


def load_omit_patterns(pyproject: Path) -> list[str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return list(data["tool"]["coverage"]["run"].get("omit", []))


def normalize_slashes(path: str) -> str:
    return path.replace("\\", "/")


def strip_src_prefix(path: str) -> str:
    p = normalize_slashes(path)
    if p.startswith("src/"):
        return p[len("src/") :]
    return p


def path_matches_omit(rel_path: str, patterns: list[str]) -> bool:
    """Match a project-relative path (with or without ``src/``) against coverage omit globs."""
    candidates = {normalize_slashes(rel_path), strip_src_prefix(rel_path)}
    for cand in candidates:
        for pat in patterns:
            if fnmatch.fnmatch(cand, pat):
                return True
    return False


def parse_coverage_xml(coverage_xml: Path) -> dict[str, dict[int, int]]:
    """Map filename (as in Cobertura, relative to ``src/``) -> line -> hit count."""
    tree = ET.parse(coverage_xml)
    root = tree.getroot()
    out: dict[str, dict[int, int]] = {}
    for cls in root.iter("class"):
        fname = cls.get("filename")
        if not fname:
            continue
        fname = normalize_slashes(fname)
        lines_el = cls.find("lines")
        if lines_el is None:
            continue
        file_map = out.setdefault(fname, {})
        for line in lines_el.findall("line"):
            num = int(line.get("number", 0))
            hits = int(line.get("hits", 0))
            file_map[num] = hits
    return out


def parse_vulture_report(path: Path) -> list[tuple[str, int, str]]:
    rows: list[tuple[str, int, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = VULTURE_LINE.match(line)
        if not m:
            continue
        rows.append(
            (
                m.group("path"),
                int(m.group("line")),
                m.group("msg").strip(),
            ),
        )
    return rows


def categorize(
    vulture_path: str,
    line_no: int,
    coverage: dict[str, dict[int, int]],
    omit_patterns: list[str],
) -> tuple[str, str]:
    """Return (category, detail_note)."""
    rel_for_omit = vulture_path
    rel_for_cov = strip_src_prefix(vulture_path)

    if path_matches_omit(rel_for_omit, omit_patterns):
        return "ignore_omit", "file matches [tool.coverage.run] omit"

    if rel_for_cov not in coverage:
        return "no_coverage_data", "file not in coverage.xml (unmeasured in this run)"

    line_hits = coverage[rel_for_cov].get(line_no)
    if line_hits is None:
        return (
            "investigate",
            "line not listed in coverage report (blank/non-executable?)",
        )
    if line_hits == 0:
        return "strong_remove_candidate", "coverage line hits=0 (measured surface)"
    return (
        "investigate",
        f"coverage line hits={line_hits} (still flagged by Vulture)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vulture-file",
        type=Path,
        default=Path("artifacts/vulture-latest.txt"),
        help="Vulture report (same format as ``uv run vulture`` stdout).",
    )
    parser.add_argument(
        "--coverage-xml",
        type=Path,
        default=Path("coverage.xml"),
        help="Cobertura XML from pytest-cov.",
    )
    parser.add_argument(
        "--pyproject",
        type=Path,
        default=Path("pyproject.toml"),
        help="Source of [tool.coverage.run] omit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/dead-code-correlation.txt"),
        help="Human-readable report path.",
    )
    args = parser.parse_args()

    if not args.vulture_file.is_file():
        print(f"Missing vulture file: {args.vulture_file}", file=sys.stderr)
        return 2
    if not args.pyproject.is_file():
        print(f"Missing pyproject: {args.pyproject}", file=sys.stderr)
        return 2

    omit_patterns = load_omit_patterns(args.pyproject)
    coverage: dict[str, dict[int, int]] = {}
    if args.coverage_xml.is_file():
        coverage = parse_coverage_xml(args.coverage_xml)
    else:
        print(
            f"Warning: no {args.coverage_xml}; categories needing coverage will be "
            "no_coverage_data or ignore_omit only.",
            file=sys.stderr,
        )

    findings = parse_vulture_report(args.vulture_file)
    lines_out: list[str] = [
        "Dead-code correlation (Vulture + coverage.xml + omit list)",
        f"Vulture: {args.vulture_file}",
        f"Coverage: {args.coverage_xml if args.coverage_xml.is_file() else '(missing)'}",
        f"Omit patterns: {len(omit_patterns)} from {args.pyproject}",
        "",
    ]

    buckets: dict[str, list[str]] = {
        "ignore_omit": [],
        "strong_remove_candidate": [],
        "investigate": [],
        "no_coverage_data": [],
    }

    for vpath, lineno, msg in findings:
        cat, note = categorize(vpath, lineno, coverage, omit_patterns)
        row = f"  {vpath}:{lineno}: {msg}  |  {note}"
        buckets[cat].append(row)

    for key in ("ignore_omit", "strong_remove_candidate", "investigate", "no_coverage_data"):
        lines_out.append(f"## {key}")
        if buckets[key]:
            lines_out.extend(buckets[key])
        else:
            lines_out.append("  (none)")
        lines_out.append("")

    text = "\n".join(lines_out).rstrip() + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
