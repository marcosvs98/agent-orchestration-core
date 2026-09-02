from pathlib import Path

from exceptions.service_exceptions import DomainValidationException


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path(__file__).resolve().parents[4]


def find_slm_model_path(path: str) -> str | None:
    if not path or not path.strip():
        return None
    path = path.strip()
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_file():
        return str(candidate)
    cwd = Path.cwd()
    if (cwd / path).is_file():
        return str((cwd / path).resolve())
    project_root = _repository_root()
    if (project_root / path).is_file():
        return str((project_root / path).resolve())
    dir_candidate = project_root / path if (project_root / path).is_dir() else None
    if dir_candidate is None and (cwd / path).is_dir():
        dir_candidate = cwd / path
    if dir_candidate is not None:
        for gguf in dir_candidate.rglob("*.gguf"):
            if gguf.is_file():
                return str(gguf.resolve())
    for models_dir in (project_root / "models", cwd / "models"):
        if not models_dir.is_dir():
            continue
        for root, _dirs, files in models_dir.walk():
            if ".no_exist" in root.parts:
                continue
            for name in files:
                if not name.endswith(".gguf"):
                    continue
                if "smollm2" in name.lower() or any(
                    "schematron" in part.lower() for part in root.parts
                ):
                    found = root / name
                    if found.is_file():
                        return str(found.resolve())
    return None


def resolve_slm_model_path(path: str) -> str:
    if not path or not path.strip():
        raise DomainValidationException(
            "llm_provider_missing_model_path",
            errors=["SLM_MODEL_PATH is empty"],
        )
    found = find_slm_model_path(path)
    if found is None:
        raise DomainValidationException(
            "llm_provider_invalid_model_path",
            errors=[f"Model path does not exist: {path.strip()}"],
        )
    return found
