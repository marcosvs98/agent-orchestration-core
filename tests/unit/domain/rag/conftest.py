from __future__ import annotations

import pytest

from domain.rag.repositories.rag_repository import RagRepository

from tests.unit.domain.rag.rag_repository_doubles import make_rag_repository


@pytest.fixture
def rag_repo() -> RagRepository:
    return make_rag_repository(with_tracer=True)


@pytest.fixture
def rag_repo_no_tracer() -> RagRepository:
    return make_rag_repository(with_tracer=False)
