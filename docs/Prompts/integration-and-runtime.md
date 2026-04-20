# Prompts — integration and runtime

**Node prompts** are resolved when graph nodes need default template text for a **`node_type`**, complementary to inline prompts stored on nodes in **Flows**.

## Placement

```mermaid
flowchart LR
  subgraph pr["domain/prompts"]
    PS[PromptService]
    PC[PromptController]
  end
  subgraph exec["Execution / LLM nodes"]
    LLM[LLM-backed nodes]
  end
  PC --> PS
  PS -.->|"template lookup"| LLM
```

## Related

- [LLM-backed nodes](../Execution/graph-runtime/nodes/llm-nodes.md)
- [User prompts](../User-Prompts/index.md)
