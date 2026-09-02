import pathlib
import re

OBSERVABILITY_PACKAGE = "adapters/observability/"
OTEL_IMPORT = re.compile(r"^\s*(?:import\s+opentelemetry|from\s+opentelemetry[.\s])", re.MULTILINE)
LANGFUSE_MENTION = re.compile(r"langfuse", re.IGNORECASE)

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"


def _source_files() -> list[pathlib.Path]:
    return sorted(_SRC.rglob("*.py"))


def test_opentelemetry_sdk_is_confined_to_the_observability_adapters() -> None:
    hits = [
        str(path.relative_to(_SRC))
        for path in _source_files()
        if OBSERVABILITY_PACKAGE not in str(path) and OTEL_IMPORT.search(path.read_text())
    ]

    assert not hits, f"opentelemetry imported outside the observability adapters: {hits}"


def test_domain_does_not_import_the_concrete_tracer_adapter() -> None:
    concrete = re.compile(r"otel_runtime_tracer|OtelRuntimeTracer")
    hits = [
        str(path.relative_to(_SRC))
        for path in _source_files()
        if str(path.relative_to(_SRC)).startswith("domain/") and concrete.search(path.read_text())
    ]

    assert not hits, f"domain code must depend on RuntimeTracerPort, not the adapter: {hits}"


def test_langfuse_is_fully_removed_from_the_source_tree() -> None:
    hits = [
        str(path.relative_to(_SRC))
        for path in _source_files()
        if LANGFUSE_MENTION.search(path.read_text())
    ]

    assert not hits, f"langfuse references remain in src: {hits}"
