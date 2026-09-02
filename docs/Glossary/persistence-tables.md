# Persistence tables (SQL index)

**Source of truth:** Alembic migrations under `src/infra/database/migrations/versions/` (initial schema revision `861cb744f4f0` plus follow-ups such as `c8f1a2b3d4e5` for `tenant_inbound_service_key`). ORM models live under `src/infra/database/models/` when present in the checkout.

Use this index to map **SQL table** → **domain area** → **typical `src/domain` owner**. New `op.create_table` additions should update this document in the same change.

## Core / tenant

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `tenant` | Tenants | `domain/tenants/` |
| `tenant_inbound_service_key` | Auth / inbound API keys | `domain/auth/` |

## Users / session

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `end_user` | Identity / end users | `domain/conversation/` / context |
| `session` | Conversation session | `domain/conversation/` |
| `conversation_summary` | Durable carry-forward summary for provider-conversation rollover | `domain/conversation/` |
| `user_memory_profile` | Memory | `domain/context/` |
| `user_prompt` | User prompts | `domain/user_prompts/` |

## Flows (authoring)

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `flow` | Flows | `domain/flows/` |
| `flow_version` | Flows | `domain/flows/` |
| `flow_graph` | Graph structure | `domain/flows/` |
| `flow_graph_draft` | Draft editing | `domain/flows/` |
| `flow_graph_snapshot` | Compiled snapshot | `domain/flows/` |
| `node` | Authoring node | `domain/flows/` |
| `node_template` | Templates | `domain/flows/` |
| `condition_expression` | Edge conditions | `domain/flows/` |
| `interaction` | Interaction records | `domain/conversation/` |

## Deployments / materialization

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `flow_snapshot` | Deployment bundle | `domain/flows/` |
| `snapshot_effective_policy` | Policy resolution | `domain/governance/` |
| `snapshot_binding` | Bindings | `domain/flows/` / governance |
| `flow_deployment` | Environment slot | `domain/flows/` |

## Runtime execution

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `flow_run` | Execution | `domain/execution/` |
| `flow_run_lock` | Concurrency | `domain/execution/` |
| `graph_state` | Graph runtime state | `domain/execution/` |
| `node_run` | Node execution | `domain/execution/` |
| `agent_run` | Agent invocation | `domain/execution/` |
| `agent_run_message` | Append-only agent transcript (`role`, `source`, `trust_level`) | `domain/execution/` |
| `agent_run_event` | Append-only agent-run events (reuses `ExecutionEventType`) | `domain/execution/` |
| `agent_run_artifact` | Agent-run output artifacts (A2A `Part` list + payload) | `domain/execution/` |
| `agent_delegation` | One row per delegated A2A task | `domain/execution/` |
| `tool_run` | Tool invocation | `domain/execution/` |
| `step_run` | Onboarding steps | `domain/onboarding/` |
| `execution_event` | Runtime events | `domain/execution/` |
| `response_artifact` | Outputs | `domain/execution/` |
| `run_failure` | Failures | `domain/execution/` |
| `router` | Routing | `domain/execution/` |
| `routing_rule` | Routing rules | `domain/execution/` |

## Agents / tools

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `agent` | Agents | `domain/agents/` |
| `agent_version` | Versioned agent | `domain/agents/` |
| `tool` | Tool registry | `domain/tools/` |
| `tool_config` | Tool definitions | `domain/tools/` |
| `agent_version_tool_binding` | Bindings | `domain/agents/` |
| `node_agent_binding` | Node bindings | `domain/agents/` / flows |

## Onboarding

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `onboarding` | Onboarding defs | `domain/onboarding/` |
| `onboarding_version` | Versions | `domain/onboarding/` |
| `onboarding_run` | Runs | `domain/onboarding/` |
| `onboarding_step` | Steps | `domain/onboarding/` |

## Governance / policies

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `access_policy` | Access | `domain/governance/` |
| `access_policy_version` | Version | `domain/governance/` |
| `ai_execution_policy` | AI execution | `domain/governance/` / `domain/ai_policy/` |
| `ai_execution_policy_version` | Version | `domain/governance/` |
| `billing_policy` | Billing | `domain/governance/` |
| `billing_policy_version` | Version | `domain/governance/` |
| `memory_policy` | Memory | `domain/governance/` |
| `memory_policy_version` | Version | `domain/governance/` |
| `rag_policy` | RAG | `domain/governance/` |
| `rag_policy_version` | Version | `domain/governance/` |
| `execution_limit_policy` | Limits | `domain/governance/` |
| `execution_limit_policy_version` | Version | `domain/governance/` |
| `rate_limit_policy` | Rate limits | `domain/governance/` |
| `rate_limit_policy_version` | Version | `domain/governance/` |
| `runtime_policy` | Runtime policy bundle | `domain/governance/` |
| `node_ai_execution_policy_binding` | Node policy binding | `domain/governance/` |

## LLM / pricing

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `model` | Model registry | `domain/llm/` |
| `llm_pricing` | Pricing | `domain/governance/` / LLM |
| `llm_model_mapping` | Aliases | `domain/llm/` |
| `llm_provider_config` | Provider config | `domain/llm/` |
| `llm_usage_ledger` | Append-only spend ledger (tokens, `cost_usd`, `inference_layer`) | `domain/llm/` / execution |

## Prompts

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `node_prompt` | Node prompts | `domain/prompts/` / application |

## RAG

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `rag_config` | RAG configuration | `domain/rag/` |
| `vector_store` | Index metadata | `domain/rag/` |
| `rag_chunking_rule` | Chunking | `domain/rag/` |
| `rag_document` | Documents | `domain/rag/` |
| `rag_chunk` | Chunks | `domain/rag/` |
| `rag_usage_counter` | Usage | `domain/rag/` |
| `rag_query_cache` | Cache | `domain/rag/` |
| `semantic_answer_cache` | Cache | `domain/rag/` |

## Human SLA

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `human_sla_policy` | SLA policy | `domain/human_sla/` |
| `human_sla_escalation_rule` | Escalation | `domain/human_sla/` |
| `sla_case` | Cases | `domain/human_sla/` |

## MCP

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `mcp_server` | MCP registry | `domain/mcp_registry/` |
| `mcp_server_tool` | Tools | `domain/mcp_registry/` |
| `mcp_server_vector_store` | RAG link | `domain/mcp_registry/` |
| `mcp_server_user_prompt` | Prompts | `domain/mcp_registry/` |
| `mcp_server_credential` | Credentials | `domain/mcp_registry/` |
| `tenant_mcp_credential` | The tenant's own MCP server + keys, attached to conversation turns as provider tools (`McpConfigLoader`). ORM lives under `models/governance/`. | `domain/conversation/` |

## Auditing (authoring)

| Table | Domain area | Typical code |
|-------|-------------|--------------|
| `authoring_event` | Audit | cross-cutting / governance |

## Related

- [Glossary index](index.md)
- [Domain model overview](../Models/domain-overview.md)
