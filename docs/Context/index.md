# Context — guide

The **context** bounded context has **no public REST controller** in `src/domain/context/`. It provides **services and protocols** used during execution and LLM inference to combine **tenant knowledge (RAG)**, **user memory**, **session snapshots**, **memory extraction**, and **RAG activation** decisions.

Think of it as the **runtime context layer** sitting between [Execution](../Execution/index.md), [RAG](../RAG/index.md), [LLM](../LLM/index.md), and [AI policy](../AI-Policy/index.md).

## Package map (selected)

| Module | Role |
|--------|------|
| `memory_retrieval.py` | `MemoryRetrievalService` — layered retrieval |
| `memory_writer.py` | Writes structured/vector memory items |
| `memory_extraction_processor.py` | Extraction pipeline hooks |
| `rag_activation_service.py` | When to retrieve tenant knowledge |
| `session_context.py` | Session snapshot load/persist |
| `scope_resolver.py` | Scope resolution helpers |
| `runtime_policy.py` | Context-side runtime policy helpers |
| `retrievers.py` | Retriever implementations |

Ports: `src/domain/context/ports/service.py` (`TenantKnowledgeRetrieverPort`, `UserMemoryReaderPort`, `SessionContextPort`, `MemoryRetrievalServicePort`, …).

## Reading order

1. [Persistence and data](persistence-and-data.md)
2. [Integration and runtime](integration-and-runtime.md)
3. [Services and ports](services-and-ports.md)

## Related

- [Governance — runtime resolution](../Governance/runtime-resolution.md)
- [RAG runtime and integration](../RAG/runtime-and-integration.md)
