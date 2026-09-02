# Conversation — guide

The **conversation** bounded context exposes **streaming conversation turns** over **Server-Sent Events (SSE)** and **read APIs** for operators (interactions, sessions, end users). Runtime enforcement (rate limit + access policy) is applied in **`ConversationBoundary`** before `ConversationService`.

## Package map

| Area | Path |
|------|------|
| Streaming | `conversation_controller.py` → `ConversationBoundary` → `conversation_service.py` |
| Turn assembly | `conversation_turn_assembler.py`, `schemas/turn_spec.py` — typed prompt parts with trust levels |
| History bounding | `conversation_continuity_service.py` — provider-conversation rollover and carry-forward summary |
| MCP tools | `mcp_config_loader.py`, `conversation_mcp_tools.py` — the tenant's own MCP server as provider tools |
| Read API | `conversation_read_controller.py` → `conversation_read_service.py` |
| SSE helpers | `sse_writer.py`, `stream_bridge.py`, `conversation_turn_error_payload.py` |

## High-level runtime path

```mermaid
flowchart LR
  C[Client POST /conversations]
  B[ConversationBoundary]
  RL[RateLimitService]
  AP[AccessPolicyService]
  S[ConversationService]
  SSE[SSE stream]
  C --> B
  B --> RL
  B --> AP
  B --> S
  S --> SSE
```

## Reading order

1. [SSE and runtime](sse-and-runtime.md)
2. [Turn assembly](turn-assembly.md) (prompt parts, trust levels, history modes)
3. [User input and media](user-input-and-media.md) (optional `input_parts`, normalization to `user_input`)
4. [Read API](read-api.md)
5. [Governance — enforcement](../Governance/enforcement-and-limits.md)
6. [System events](../Develop/system-events-reference.md) for SSE event shapes
