from __future__ import annotations

from typing import Any, Dict, Final, List, Tuple

import tiktoken

from domain.rag.schemas.rag import RagChunkingStrategy, parse_rag_chunking_rule_params
from domain.rag.services.rag_runtime_service import RagRuntimeService
from examples.rag._corpus import HANDBOOK, PAGES, token_estimate
from examples.support import expect, field, heading
from exceptions.service_exceptions import DomainValidationException

ENCODER: Final[tiktoken.Encoding] = tiktoken.get_encoding("cl100k_base")


def chunker() -> RagRuntimeService:
    return RagRuntimeService(
        repository=None,
        tracer=None,
        rag_policy_service=None,
        ai_repository=None,
        embedding_executor=None,
    )


def run(
    params: Dict[str, Any],
    *,
    content: str = HANDBOOK,
    pages: List[str] | None = None,
) -> Tuple[List[str], bool]:
    return chunker()._chunks_for_ingest(
        content=content,
        rule_params=parse_rag_chunking_rule_params(params),
        ingest_pages=pages,
    )


def describe(label: str, chunks: List[str], truncated: bool) -> None:
    sizes = [token_estimate(chunk) for chunk in chunks]
    largest = max(sizes) if sizes else 0
    smallest = min(sizes) if sizes else 0
    print(
        f"  {label:<26} chunks={len(chunks):<4} distinct={len(set(chunks)):<4} "
        f"tokens[min={smallest} max={largest}] truncated={truncated}"
    )


def main() -> None:
    print("RAG chunking strategies: the catalog, applied to one document")
    field("document tokens", token_estimate(HANDBOOK))
    field("document chars", len(HANDBOOK))
    print()
    print("  Strategies come from RagChunkingStrategy and each has its own params model")
    print("  (discriminated on `strategy`). The rule is stored once and referenced by")
    print("  every rag_config that uses it.")
    field("available", ", ".join(s.value for s in RagChunkingStrategy))

    heading("1. TOKEN_WINDOW - fixed token windows with overlap")
    print("  The workhorse. Cuts on tiktoken cl100k_base boundaries, so chunk size is")
    print("  predictable in the unit the embedding model actually bills.")
    for target, overlap in ((120, 20), (240, 40), (240, 0)):
        chunks, truncated = run(
            {
                "strategy": "TOKEN_WINDOW",
                "target_tokens": target,
                "overlap_tokens": overlap,
            }
        )
        describe(f"target={target} overlap={overlap}", chunks, truncated)

    window, _ = run({"strategy": "TOKEN_WINDOW", "target_tokens": 120, "overlap_tokens": 20})
    first = ENCODER.encode(window[0])
    second = ENCODER.encode(window[1])
    expect(first[-20:] == second[:20], "consecutive windows share exactly overlap_tokens tokens")
    expect(len(window) == len(set(window)), "no window is emitted twice")

    heading("2. SEMANTIC - declared, but not yet distinct")
    semantic, _ = run({"strategy": "SEMANTIC", "target_tokens": 120, "overlap_tokens": 20})
    describe("target=120 overlap=20", semantic, False)
    expect(
        semantic == window,
        "SEMANTIC produces byte-identical chunks to TOKEN_WINDOW with the same params",
    )
    print()
    print("  _chunks_for_ingest dispatches SEMANTIC to the same _chunk_text call as")
    print("  TOKEN_WINDOW. There is no embedding-similarity boundary detection today, so")
    print("  choosing SEMANTIC buys nothing but a different label in the rule row.")

    heading("3. RECURSIVE_CHARACTER - respects separators")
    print("  Cuts on the first separator found in the second half of the window, so it")
    print("  keeps paragraphs and sentences intact. Sizes are in CHARACTERS, not tokens,")
    print("  so chunk token counts vary with the language and alphabet.")
    for size, overlap in ((600, 80), (1200, 150)):
        chunks, truncated = run(
            {
                "strategy": "RECURSIVE_CHARACTER",
                "chunk_size": size,
                "chunk_overlap": overlap,
            }
        )
        describe(f"chunk_size={size} overlap={overlap}", chunks, truncated)

    paragraph_aware, _ = run(
        {
            "strategy": "RECURSIVE_CHARACTER",
            "chunk_size": 600,
            "chunk_overlap": 80,
            "separators": ["\n\n", "\n", " ", ""],
        }
    )
    no_separators, _ = run(
        {
            "strategy": "RECURSIVE_CHARACTER",
            "chunk_size": 600,
            "chunk_overlap": 80,
            "separators": [""],
        }
    )
    field("with separators, chunk 0 ends", repr(paragraph_aware[0][-34:]))
    field("separators=[''], chunk 0 ends", repr(no_separators[0][-34:]))
    expect(
        paragraph_aware != no_separators,
        "the separator list changes where the cuts land",
    )

    heading("4. PER_PAGE - one chunk per supplied page")
    print("  Does not split text at all: it trusts the caller's page boundaries. Meant for")
    print("  documents that arrive already paginated, e.g. OCR output via ingestFromMedia.")
    chunks, truncated = run(
        {"strategy": "PER_PAGE", "max_chunks_per_document": 500},
        content="\n".join(PAGES),
        pages=PAGES,
    )
    describe(f"{len(PAGES)} pages in", chunks, truncated)
    expect(chunks == PAGES, "each page became exactly one chunk, unmodified")

    try:
        run({"strategy": "PER_PAGE"}, content=HANDBOOK, pages=None)
        raise SystemExit("FAILED: PER_PAGE without pages should have been rejected")
    except DomainValidationException as exc:
        field("without pages", f"{exc.message} (HTTP 422)")
    print("  PER_PAGE is the one strategy that can reject an otherwise valid document:")
    print("  ingest must carry a non-empty `pages` array.")

    heading("5. Bounds: max_chunks_per_document and max_document_chars")
    chunks, truncated = run(
        {
            "strategy": "TOKEN_WINDOW",
            "target_tokens": 60,
            "overlap_tokens": 10,
            "max_chunks_per_document": 4,
        }
    )
    describe("max_chunks_per_document=4", chunks, truncated)
    expect(truncated is True, "hitting the cap reports truncated=True")
    expect(len(chunks) == 4, "and stops at exactly the cap")

    complete, complete_truncated = run(
        {"strategy": "TOKEN_WINDOW", "target_tokens": 60, "overlap_tokens": 10}
    )
    describe("default cap (100)", complete, complete_truncated)
    expect(
        complete_truncated is False,
        "a document that fits under the cap is not reported as truncated",
    )
    print()
    print("  truncated=True means chunks were DROPPED - the tail of the document was")
    print("  never embedded and can never be retrieved. Treat it as a data-loss signal,")
    print("  not a warning.")

    heading("6. Degenerate overlap")
    print("  overlap_tokens is not validated against target_tokens. When overlap >= target")
    print("  the window cannot advance by a full step, so the chunker falls back to a")
    print("  one-token step and burns straight through max_chunks_per_document.")
    for target, overlap in ((120, 20), (120, 120), (120, 200)):
        chunks, truncated = run(
            {
                "strategy": "TOKEN_WINDOW",
                "target_tokens": target,
                "overlap_tokens": overlap,
            }
        )
        describe(f"target={target} overlap={overlap}", chunks, truncated)
    print()
    print("  Keep overlap_tokens well below target_tokens - 10 to 20 percent is typical.")

    heading("Choosing a strategy")
    print("  TOKEN_WINDOW         default; predictable embedding cost per chunk")
    print("  RECURSIVE_CHARACTER  prose with meaningful paragraph structure")
    print("  SEMANTIC             currently an alias for TOKEN_WINDOW")
    print("  PER_PAGE             pre-paginated sources; requires `pages` on ingest")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
