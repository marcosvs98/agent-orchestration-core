import pathlib


def test_no_direct_langfuse_import_outside_tracer() -> None:
    root = pathlib.Path(__file__).resolve().parents[3] / "src"
    hits = []
    for path in root.rglob("*.py"):
        text = path.read_text()
        if "langfuse" in text and "adapters/observability/langfuse_runtime_tracer.py" not in str(
            path
        ):
            hits.append(str(path))
    assert not hits, f"Direct langfuse import found outside tracer: {hits}"
