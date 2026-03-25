## Demo seed graph: conditional edges (`seed_11_graph.py`)

The demo flow graph is defined in `resources/scripts/seeds/demo/seed_11_graph.py`. Below, **node labels** use short IDs (UUID suffix) for traceability; **edge labels** summarize conditions (full strings are in the seed). There is **no** `UserContextEnrichmentNode`; read gating for USER_MEMORY layers is applied from **runtime policy** in the executor.

**Entry path:** after `ContentModeration`, the graph runs **`ToolResolver` first** (semantic catalog retrieval + optional LLM fallback). If at least one tool is selected (`len(result) >= 1`), execution continues to **`ToolInputFiller`**. If none (`len(result) < 1`), execution goes to **`MemoryCommitNode`** and then **`ResponseBuilder`** (no `IntentClassifier` in this graph for now).

The demo **`ToolResolver`** node sets **`confidence_threshold`** `0.78` (below the runtime default `0.9`) and **`top_k`** `10` to favor recall; tune per tenant.

```mermaid
flowchart TD
    MOD["ContentModeration\n…80d"]
    TOOLSEL["ToolResolver\n…807"]
    SLOT["ToolInputFiller\n…801"]
    CLAR_S["QueryClarifier\n(slot resume → 801)\n…804"]
    TOOLEX["ToolExecutor\n…803"]
    SUM["ContextSummarizer\n…805"]
    ERR["ToolErrorHandlerNode\n…80a"]
    FB["HumanFallback\n…80c"]
    MEM["MemoryCommitNode\n…80f"]
    RESP["ResponseBuilder\n…802"]

    MOD -->|"flagged == false"| TOOLSEL
    MOD -->|"flagged == true"| FB

    TOOLSEL -->|"len(result) >= 1"| SLOT
    TOOLSEL -->|"len(result) < 1"| MEM

    SLOT -->|"HasAny(status incomplete)"| CLAR_S
    CLAR_S -.->|"LOOP 1==1"| SLOT
    SLOT -->|"HasAll(status ready)"| TOOLEX

    TOOLEX -->|"HasAll(success, scheduled)"| SUM
    TOOLEX -->|"HasAny(incomplete, error, cancelled)"| ERR

    SUM -->|"1==1"| MEM

    ERR -.->|"LOOP retry_operation_ids_count > 0"| TOOLEX
    ERR -->|"fallback_required == true"| FB
    ERR -->|"retry == 0 and\nfallback_required == false"| MEM

    FB -->|"1==1"| MEM
    MEM -->|"1==1"| RESP
```

**Notes**

- **Moderation → ToolResolver:** first pass runs without prior intent from this graph; `ToolResolver` uses the full tool catalog when no `IntentClassifier` output is present in state (`_resolve_detected_intent`).
- **ToolResolver → MemoryCommit:** when no tool is selected, the run still completes via commit + response (conversational or ambiguous input).
- **Tool success path:** `ToolExecutor` → optional **`ContextSummarizer`** (runs only when staged payload exceeds `min_payload_bytes_to_run`) → **`MemoryCommitNode`**. The summarize step **does not** persist; only `MemoryCommitNode` updates session memory via `NodeResult.memory` for USER_MEMORY on this graph.
- **`data_merge` on `MemoryCommitNode`:** merges slot `nickname` / `financial_goal` and optional `prepared_memory_data` from the summarize node into the commit payload (paths validated in `FlowGraphValidator`).
- **Terminal completion** for post-flow extraction is **`ResponseBuilder` / `HumanFallback`** types; `QueryClarifier` pauses do not invoke `on_flow_complete` extraction.
