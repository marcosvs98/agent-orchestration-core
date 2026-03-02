"""Resolve SLM model path: env/relative path or discover under models/ (poc5-style)."""

from pathlib import Path

from exceptions.service_exceptions import DomainValidationException


def resolve_slm_model_path(path: str) -> str:
    """Return an absolute path to an existing GGUF file.

    Tries, in order: path as-is, cwd/path, project_root/path, then first
    *smollm2*.gguf under models/ (project root or cwd). Raises if none found.
    """
    if not path or not path.strip():
        raise DomainValidationException(
            "llm_provider_missing_model_path",
            errors=["SLM_MODEL_PATH is empty"],
        )
    path = path.strip()
    p = Path(path)
    if p.is_absolute() and p.is_file():
        return str(p)
    cwd = Path.cwd()
    if (cwd / path).is_file():
        return str((cwd / path).resolve())
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if (project_root / path).is_file():
        return str((project_root / path).resolve())
    for models_dir in (project_root / "models", cwd / "models"):
        if not models_dir.is_dir():
            continue
        for root, _dirs, files in models_dir.walk():
            if ".no_exist" in root.parts:
                continue
            for f in files:
                if f.endswith(".gguf") and "smollm2" in f.lower():
                    found = root / f
                    if found.is_file():
                        return str(found.resolve())
    raise DomainValidationException(
        "llm_provider_invalid_model_path",
        errors=[f"Model path does not exist: {path}"],
    )
