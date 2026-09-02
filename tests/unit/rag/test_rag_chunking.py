import tiktoken

from domain.rag.schemas.rag import parse_rag_chunking_rule_params
from domain.rag.services.rag_runtime_service import RagRuntimeService

ENCODER = tiktoken.get_encoding("cl100k_base")


def _service() -> RagRuntimeService:
    return RagRuntimeService(
        repository=None,
        tracer=None,
        rag_policy_service=None,
        ai_repository=None,
        embedding_executor=None,
    )


def _varied_text(words: int) -> str:
    return " ".join(f"palavra{index}" for index in range(words))


def test_short_document_is_a_single_chunk():
    chunks, truncated = _service()._chunk_text("texto curto", 500, 50, 100)

    assert chunks == ["texto curto"]
    assert truncated is False


def test_sliding_window_advances_and_does_not_repeat_the_tail():
    text = _varied_text(400)
    total = len(ENCODER.encode(text))

    chunks, truncated = _service()._chunk_text(text, 60, 10, 100)

    assert truncated is False
    assert len(chunks) == len(set(chunks))
    assert len(chunks) < total


def test_chunk_count_matches_the_sliding_window_arithmetic():
    text = _varied_text(400)
    total = len(ENCODER.encode(text))
    target, overlap = 60, 10
    step = target - overlap
    expected = 1 + -(-(total - target) // step)

    chunks, _ = _service()._chunk_text(text, target, overlap, 1000)

    assert len(chunks) == expected


def test_consecutive_chunks_overlap_by_exactly_the_configured_tokens():
    text = _varied_text(300)
    target, overlap = 50, 10

    chunks, _ = _service()._chunk_text(text, target, overlap, 1000)

    first = ENCODER.encode(chunks[0])
    second = ENCODER.encode(chunks[1])
    assert first[-overlap:] == second[:overlap]


def test_chunks_cover_the_whole_document_from_first_token_to_last():
    text = _varied_text(300)

    chunks, _ = _service()._chunk_text(text, 50, 10, 1000)

    assert chunks[0].startswith("palavra0 ")
    assert chunks[-1].endswith("palavra299")


def test_truncation_is_reported_only_when_chunks_are_actually_dropped():
    text = _varied_text(400)

    complete, complete_truncated = _service()._chunk_text(text, 60, 10, 1000)
    capped, capped_truncated = _service()._chunk_text(text, 60, 10, 3)

    assert complete_truncated is False
    assert capped_truncated is True
    assert len(capped) == 3
    assert len(complete) > 3


def test_overlap_equal_to_target_terminates_instead_of_looping():
    text = _varied_text(300)

    chunks, truncated = _service()._chunk_text(text, 50, 50, 100)

    assert len(chunks) <= 100
    assert truncated is True


def test_overlap_greater_than_target_terminates_instead_of_looping():
    text = _varied_text(300)

    chunks, truncated = _service()._chunk_text(text, 50, 80, 100)

    assert len(chunks) <= 100
    assert truncated is True


def test_semantic_strategy_is_identical_to_token_window_today():
    service = _service()
    text = _varied_text(400)
    token_window = parse_rag_chunking_rule_params(
        {"strategy": "TOKEN_WINDOW", "target_tokens": 60, "overlap_tokens": 10}
    )
    semantic = parse_rag_chunking_rule_params(
        {"strategy": "SEMANTIC", "target_tokens": 60, "overlap_tokens": 10}
    )

    window_chunks, _ = service._chunks_for_ingest(
        content=text, rule_params=token_window, ingest_pages=None
    )
    semantic_chunks, _ = service._chunks_for_ingest(
        content=text, rule_params=semantic, ingest_pages=None
    )

    assert window_chunks == semantic_chunks
