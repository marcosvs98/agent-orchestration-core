from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import utils.query_compiler as qc


def test_compile_query_when_tracing_off_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qc, "TRACING_ENABLED", False)
    stmt = MagicMock()
    assert qc.compile_query(stmt) is None


def test_compile_query_string_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qc, "TRACING_ENABLED", True)
    assert qc.compile_query("SELECT 1") == "SELECT 1"


def test_compile_query_compile_exception_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(qc, "TRACING_ENABLED", True)
    bad = MagicMock()
    bad.compile.side_effect = RuntimeError("boom")
    assert qc.compile_query(bad) is None


def test_compile_query_fallback_str_when_no_compile_attr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(qc, "TRACING_ENABLED", True)
    assert qc.compile_query(42) == "42"
