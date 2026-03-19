# seed-example (seed-demo via API)

Exemplos de `Request Body` e `Response Body` para replicar a configuração do `seed-demo` via endpoints do serviço, usando o `http://localhost:8000/openapi.json` como fonte.

Observações importantes:
- Use os `id` retornados em chamadas anteriores (ex: `tenant_id`, `agent_id`, `flow_id`, `*_version_id`) como parâmetros nas próximas requisições.
- Para endpoints de `/admin/llm/*`, o OpenAPI indica que não há `requestBody` em JSON; os valores ficam em `query params` (veja abaixo).

---
1

POST - /core/v1/tenants

Request Body
```json
{"name":"string","external_id":"00000000-0000-0000-0000-000000000000","description":"string","timezone":"America/Sao_Paulo","is_active":true,"currency":"BRL","language":"pt_BR","contact_name":"string","contact_phone":"string","settings":{}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","external_id":"00000000-0000-0000-0000-000000000000","name":"string","description":"string","timezone":"string","is_active":true,"currency":"string","language":"string","contact_name":"string","contact_phone":"string","settings":{}}
```

Observação
Create the tenant used as tenant_id across the flow.
---
2

POST - /core/v1/ai-tasks

Request Body
```json
{"name":"string","allow_rag_tenant":false,"allow_user_memory":false,"allow_session_context":false,"allow_memory_write":false}
```

Response Body
```json
{"allow_rag_tenant":false,"allow_user_memory":false,"allow_session_context":false,"allow_memory_write":false,"id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create AI task used by nodes for execution.
---
3

POST - /core/v1/models

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create a model entry used by AI execution policies.
---
4

POST - /core/v1/ai-execution-policies

Request Body
```json
{"description":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","description":"string"}
```

Observação
Create AI execution policy container.
---
4

POST - /core/v1/ai-execution-policy-versions

Request Body
```json
{"ai_execution_policy_id":"00000000-0000-0000-0000-000000000000","model_id":"00000000-0000-0000-0000-000000000000","notes":"string","source_version_id":"00000000-0000-0000-0000-000000000000","version_major":1,"version_minor":1,"version_patch":1}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","ai_execution_policy_id":"00000000-0000-0000-0000-000000000000","model_id":"00000000-0000-0000-0000-000000000000","notes":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Create AI execution policy version for the model.
---
4

POST - /core/v1/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:validate

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","ai_execution_policy_id":"00000000-0000-0000-0000-000000000000","model_id":"00000000-0000-0000-0000-000000000000","notes":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Validate AI execution policy version (no request body).
---
4

POST - /core/v1/ai-execution-policies/{ai_execution_policy_id}/versions/{ai_execution_policy_version_id}:publish

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","ai_execution_policy_id":"00000000-0000-0000-0000-000000000000","model_id":"00000000-0000-0000-0000-000000000000","notes":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Publish AI execution policy version using ChangeRequest.
---
5

POST - /core/v1/tools/import-tools

Request Body
```json
{"openapi_url":"string","name":"string"}
```

Response Body
```json
{"imported_count":1,"tools":[{"id":"00000000-0000-0000-0000-000000000000","name":"string"}]}
```

Observação
Import tools from an OpenAPI spec (creates Tool + ToolConfig).
---
6

POST - /core/v1/vector-stores

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create vector store for RAG configuration.
---
6

POST - /core/v1/rag-configs

Request Body
```json
{"vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"source_version_id":"00000000-0000-0000-0000-000000000000","version_major":1,"version_minor":1,"version_patch":1}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Create RAG config pointing to the vector store.
---
6

POST - /core/v1/rag-configs/{rag_config_id}/documents:ingest

Request Body
```json
{"source":"string","doc_type":"string","content":"string","version":"string","metadata":{},"rag_config_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","source":"string","doc_type":"string","content_hash":"string","metadata":{},"embedding_status":"PENDING","rag_config_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Ingest one document (repeat for all documents/chunks).
---
6

POST - /core/v1/rag-configs/{rag_config_id}:publish

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Publish RAG config using ChangeRequest.
---
7

POST - /core/v1/vector-stores

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create vector store for the tool-catalog RAG.
---
7

POST - /core/v1/rag-configs

Request Body
```json
{"vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"source_version_id":"00000000-0000-0000-0000-000000000000","version_major":1,"version_minor":1,"version_patch":1}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Create tool-catalog RAG config.
---
7

POST - /core/v1/rag-configs/{rag_config_id}/documents:ingest

Request Body
```json
{"source":"string","doc_type":"string","content":"string","version":"string","metadata":{},"rag_config_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","source":"string","doc_type":"string","content_hash":"string","metadata":{},"embedding_status":"PENDING","rag_config_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Ingest one tool-catalog document (repeat).
---
7

POST - /core/v1/rag-configs/{rag_config_id}:publish

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","vector_store_id":"00000000-0000-0000-0000-000000000000","options":{},"status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string"}
```

Observação
Publish tool-catalog RAG config.
---
8

POST - /core/v1/agents

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create the agent container.
---
8

POST - /core/v1/agents/{agent_id}/versions

Request Body
```json
{"source_version_id":"00000000-0000-0000-0000-000000000000","description":"string","version_major":1,"version_minor":1,"version_patch":1,"supported_tool_schema_version":1,"supported_tool_config_hash_prefix":"string","persona_config":{"language":"pt_BR","tone":"professional","style":"concise","rules":["string"],"max_response_length":500},"system_prompt":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","agent_id":"00000000-0000-0000-0000-000000000000","description":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","supported_tool_schema_version":1,"supported_tool_config_hash_prefix":"string","persona_config":{"language":"pt_BR","tone":"professional","style":"concise","rules":["string"],"max_response_length":500},"system_prompt":"string"}
```

Observação
Create agent version (persona + prompts).
---
8

POST - /core/v1/agents/{agent_id}/versions/{agent_version_id}:validate

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","agent_id":"00000000-0000-0000-0000-000000000000","description":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","supported_tool_schema_version":1,"supported_tool_config_hash_prefix":"string","persona_config":{"language":"pt_BR","tone":"professional","style":"concise","rules":["string"],"max_response_length":500},"system_prompt":"string"}
```

Observação
Validate agent version (no request body).
---
8

POST - /core/v1/agents/{agent_id}/versions/{agent_version_id}:publish

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","agent_id":"00000000-0000-0000-0000-000000000000","description":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","supported_tool_schema_version":1,"supported_tool_config_hash_prefix":"string","persona_config":{"language":"pt_BR","tone":"professional","style":"concise","rules":["string"],"max_response_length":500},"system_prompt":"string"}
```

Observação
Publish agent version using ChangeRequest.
---
8

POST - /core/v1/agents/{agent_id}/versions/{agent_version_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","agent_id":"00000000-0000-0000-0000-000000000000","description":"string","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","supported_tool_schema_version":1,"supported_tool_config_hash_prefix":"string","persona_config":{"language":"pt_BR","tone":"professional","style":"concise","rules":["string"],"max_response_length":500},"system_prompt":"string"}
```

Observação
Activate agent version using ChangeRequest.
---
9

POST - /core/v1/flows

Request Body
```json
{"name":"string","description":"string","tags":["string"]}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","name":"string","description":"string","tags":["string"],"created_by":"string"}
```

Observação
Create the flow container.
---
9

POST - /core/v1/flows/{flow_id}/versions

Request Body
```json
{"source_version_id":"00000000-0000-0000-0000-000000000000","version_major":1,"version_minor":1,"version_patch":1,"min_agent_version_major":1,"min_agent_version_minor":1,"min_agent_version_patch":1}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","min_agent_version_major":1,"min_agent_version_minor":1,"min_agent_version_patch":1}
```

Observação
Create flow version (draft).
---
9

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}:validate

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","min_agent_version_major":1,"min_agent_version_minor":1,"min_agent_version_patch":1}
```

Observação
Validate flow version (no request body).
---
9

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}:publish

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","min_agent_version_major":1,"min_agent_version_minor":1,"min_agent_version_patch":1}
```

Observação
Publish flow version using ChangeRequest.
---
10

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:copy-from-template

Request Body
```json
{"flow_id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","node_template_id":"00000000-0000-0000-0000-000000000000","code":"string","overrides":{}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","ai_task_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Copy a system node template into this flow version (repeat per node).
---
10

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}/nodes:custom

Request Body
```json
{"flow_id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","node_type":"string","config":{}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","ai_task_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Create custom node with explicit config (repeat for special nodes).
---
11

POST - /core/v1/nodes/{node_type}/prompt

Request Body
```json
{"node_type":"string","template_text":"string","input_schema":{},"output_schema":{},"description":"string","created_by":"string"}
```

Response Body
```json
{"prompt_id":"00000000-0000-0000-0000-000000000000","node_type":"string","template_text":"string","input_schema":{},"output_schema":{},"version":1,"frozen_hash":"string","is_active":true,"description":"string","created_by":"string","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}
```

Observação
Create the node prompt for the given node_type (repeat per node_type).
---
12

POST - /core/v1/user-prompts

Request Body
```json
{"title":"string","content":"string","created_by":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","title":"string","content":"string","version":1,"is_active":true,"created_by":"string","created_at":"2026-01-01T00:00:00Z","updated_at":"2026-01-01T00:00:00Z"}
```

Observação
Create the user prompt (used by the runtime).
---
13

POST - /core/v1/node-agent-bindings

Request Body
```json
{"node_id":"00000000-0000-0000-0000-000000000000","agent_version_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","node_id":"00000000-0000-0000-0000-000000000000","agent_version_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Bind a node to an agent version (repeat per node).
---
13

POST - /core/v1/agent-version-tool-bindings

Request Body
```json
{"agent_version_id":"00000000-0000-0000-0000-000000000000","tool_config_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","agent_version_id":"00000000-0000-0000-0000-000000000000","tool_config_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Bind an agent version to a tool config (repeat if multiple tools).
---
14

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:draft

Request Body
```json
{"flow_id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","definition":{"start_node":"string","nodes":{"additional_prop":{"type":"string","config":{}}},"edges":[{"from_node":"string","to_node":"string","condition":"string","edge_kind":"NORMAL"}]},"principal_id":"string"}
```

Response Body
```json
{}
```

Observação
Create/overwrite the graph draft (provide nodes + edges).
---
14

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:validate

Request Body
```json
{"flow_id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","principal_id":"string"}
```

Response Body
```json
{}
```

Observação
Validate the graph draft against the contract.
---
14

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}/graph:compile

Request Body
```json
{"flow_id":"00000000-0000-0000-0000-000000000000","flow_version_id":"00000000-0000-0000-0000-000000000000","principal_id":"string"}
```

Response Body
```json
{}
```

Observação
Compile the graph into an executable snapshot.
---
14

POST - /core/v1/flows/{flow_id}/versions/{flow_version_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","flow_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"config_hash":"string","min_agent_version_major":1,"min_agent_version_minor":1,"min_agent_version_patch":1}
```

Observação
Activate the flow version using ChangeRequest.
---
15

POST - /core/v1/runtime-policies

Request Body
```json
{"scope":"string","flow_id":"00000000-0000-0000-0000-000000000000","version":"1","policy_definition":{"limits":{"max_nodes":1,"max_depth":1,"max_edges_per_node":1,"max_total_duration_ms":1,"max_node_duration_ms":1,"max_loop_iterations":1,"tool_fanout_max_concurrency":1},"execution":{"fail_on_multiple_true_edges":true,"fail_on_missing_graph":true,"allow_parallel_nodes":true,"strict_contract_mode":true},"tools":{"max_retries":1,"circuit_breaker":{"failure_threshold":null,"window_seconds":null}},"llm":{"max_retries":1,"timeout_ms":1,"stream_enabled":true,"stream_eligible_tasks":["string"],"history_enabled_tasks":["string"],"temperature":1.0,"max_tokens":1,"inference_layers":{"cache_enabled":null,"cache_similarity_threshold":null,"cache_ttl_seconds":null,"slm_enabled":null,"slm_eligible_tasks":null,"slm_provider":null,"slm_model_alias":null,"escalation_on_schema_mismatch":null}},"moderation":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"fallback_sla":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"memory_extraction":{"enabled":true,"rag_config_id":"string","preference_schema_id":"string","profile_schema_id":"string","llm":{"provider":null,"model_alias":null,"prompt":null,"task_type":null}},"memory_retrieval":{"temporal_scoring":{"enabled":null,"half_life_seconds":null,"timestamp_source":null,"candidate_multiplier":null}},"user_context_enrichment":{"enabled":true,"gating":true,"default_layers_when_published":{"allow_tenant_knowledge":null,"allow_user_memory_structured":null,"allow_user_memory_vector":null}}}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","scope":"string","flow_id":"00000000-0000-0000-0000-000000000000","version":"string","status":"string","policy_definition":{"limits":{"max_nodes":1,"max_depth":1,"max_edges_per_node":1,"max_total_duration_ms":1,"max_node_duration_ms":1,"max_loop_iterations":1,"tool_fanout_max_concurrency":1},"execution":{"fail_on_multiple_true_edges":true,"fail_on_missing_graph":true,"allow_parallel_nodes":true,"strict_contract_mode":true},"tools":{"max_retries":1,"circuit_breaker":{"failure_threshold":null,"window_seconds":null}},"llm":{"max_retries":1,"timeout_ms":1,"stream_enabled":true,"stream_eligible_tasks":["string"],"history_enabled_tasks":["string"],"temperature":1.0,"max_tokens":1,"inference_layers":{"cache_enabled":null,"cache_similarity_threshold":null,"cache_ttl_seconds":null,"slm_enabled":null,"slm_eligible_tasks":null,"slm_provider":null,"slm_model_alias":null,"escalation_on_schema_mismatch":null}},"moderation":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"fallback_sla":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"memory_extraction":{"enabled":true,"rag_config_id":"string","preference_schema_id":"string","profile_schema_id":"string","llm":{"provider":null,"model_alias":null,"prompt":null,"task_type":null}},"memory_retrieval":{"temporal_scoring":{"enabled":null,"half_life_seconds":null,"timestamp_source":null,"candidate_multiplier":null}},"user_context_enrichment":{"enabled":true,"gating":true,"default_layers_when_published":{"allow_tenant_knowledge":null,"allow_user_memory_structured":null,"allow_user_memory_vector":null}}}}
```

Observação
Create runtime policy (execution constraints).
---
15

POST - /core/v1/runtime-policies/{runtime_policy_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","scope":"string","flow_id":"00000000-0000-0000-0000-000000000000","version":"string","status":"string","policy_definition":{"limits":{"max_nodes":1,"max_depth":1,"max_edges_per_node":1,"max_total_duration_ms":1,"max_node_duration_ms":1,"max_loop_iterations":1,"tool_fanout_max_concurrency":1},"execution":{"fail_on_multiple_true_edges":true,"fail_on_missing_graph":true,"allow_parallel_nodes":true,"strict_contract_mode":true},"tools":{"max_retries":1,"circuit_breaker":{"failure_threshold":null,"window_seconds":null}},"llm":{"max_retries":1,"timeout_ms":1,"stream_enabled":true,"stream_eligible_tasks":["string"],"history_enabled_tasks":["string"],"temperature":1.0,"max_tokens":1,"inference_layers":{"cache_enabled":null,"cache_similarity_threshold":null,"cache_ttl_seconds":null,"slm_enabled":null,"slm_eligible_tasks":null,"slm_provider":null,"slm_model_alias":null,"escalation_on_schema_mismatch":null}},"moderation":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"fallback_sla":{"primary":{"provider":null,"model_alias":null,"timeout_ms":null},"fallback_enabled":true,"prompt_key":"string","temperature":1.0,"max_tokens":1},"memory_extraction":{"enabled":true,"rag_config_id":"string","preference_schema_id":"string","profile_schema_id":"string","llm":{"provider":null,"model_alias":null,"prompt":null,"task_type":null}},"memory_retrieval":{"temporal_scoring":{"enabled":null,"half_life_seconds":null,"timestamp_source":null,"candidate_multiplier":null}},"user_context_enrichment":{"enabled":true,"gating":true,"default_layers_when_published":{"allow_tenant_knowledge":null,"allow_user_memory_structured":null,"allow_user_memory_vector":null}}}}
```

Observação
Activate runtime policy using ChangeRequest.
---
16

POST - /admin/llm/provider

Request Body
```json
{}
```

Response Body
```json
{}
```

Observação
Create LLM provider config (query parameters; no JSON body).
Query params example:
- tenant_id=00000000-0000-0000-0000-000000000000
- provider=string
- status=string
- base_url=string
- credential_secret_ref=string
---
17

POST - /admin/llm/model-mapping

Request Body
```json
{}
```

Response Body
```json
{}
```

Observação
Create LLM provider model mapping (query parameters; no JSON body).
Query params example:
- tenant_id=00000000-0000-0000-0000-000000000000
- provider=string
- model_alias=string
- provider_model=string
- status=ACTIVE
---
18

POST - /core/v1/node-ai-execution-policy-bindings

Request Body
```json
{"node_id":"00000000-0000-0000-0000-000000000000","ai_execution_policy_version_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","node_id":"00000000-0000-0000-0000-000000000000","ai_execution_policy_version_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Bind a node to an AI execution policy version (repeat per node).
---
19

POST - /core/v1/routers

Request Body
```json
{"node_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","node_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Create a router for routing rules.
---
19

POST - /core/v1/routing-rules

Request Body
```json
{"router_id":"00000000-0000-0000-0000-000000000000","condition_expression_id":"00000000-0000-0000-0000-000000000000","from_node_id":"00000000-0000-0000-0000-000000000000","to_node_id":"00000000-0000-0000-0000-000000000000"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","router_id":"00000000-0000-0000-0000-000000000000","condition_expression_id":"00000000-0000-0000-0000-000000000000","from_node_id":"00000000-0000-0000-0000-000000000000","to_node_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Create a routing rule referencing a router + condition expression.
---
19

POST - /core/v1/condition-expressions

Request Body
```json
{"expression":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","expression":"string"}
```

Observação
Create a condition expression used by routing rules.
---
20

POST - /admin/llm/pricing

Request Body
```json
{}
```

Response Body
```json
{}
```

Observação
Create LLM pricing entry (query parameters; no JSON body).
Query params example:
- provider=string
- provider_model=string
- unit=string
- input_cost_per_1k=1.0
- output_cost_per_1k=1.0
- currency=USD
- status=ACTIVE
---
21

POST - /core/v1/access-policies

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create access policy container.
---
21

POST - /core/v1/access-policies/{access_policy_id}/versions

Request Body
```json
{"status":"DRAFT","version_major":1,"version_minor":0,"version_patch":0,"rules":{"allow":["string"],"deny":["string"]}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","access_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"rules":{"allow":["string"],"deny":["string"]}}
```

Observação
Create access policy version.
---
21

POST - /core/v1/access-policies/versions/{access_policy_version_id}:publish

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","access_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"rules":{"allow":["string"],"deny":["string"]}}
```

Observação
Publish access policy version using ChangeRequest.
---
22

POST - /core/v1/rate-limit-policies

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create rate-limit policy container.
---
22

POST - /core/v1/rate-limit-policies/{rate_limit_policy_id}/versions

Request Body
```json
{"status":"DRAFT","version_major":1,"version_minor":0,"version_patch":0,"action":"string","principal_type":"string","limit":1,"window_seconds":1}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","rate_limit_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"action":"string","principal_type":"string","limit":1,"window_seconds":1}
```

Observação
Create rate-limit policy version.
---
22

POST - /core/v1/rate-limit-policies/versions/{rate_limit_policy_version_id}:publish

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","rate_limit_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"action":"string","principal_type":"string","limit":1,"window_seconds":1}
```

Observação
Publish rate-limit policy version using ChangeRequest.
---
23

POST - /core/v1/billing-policies

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create billing policy container.
---
23

POST - /core/v1/billing-policies/{billing_policy_id}/versions

Request Body
```json
{"status":"DRAFT","version_major":1,"version_minor":0,"version_patch":0,"rules":{}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","billing_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"rules":{}}
```

Observação
Create billing policy version.
---
23

POST - /core/v1/billing-policies/versions/{billing_policy_version_id}:publish

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","billing_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"rules":{}}
```

Observação
Publish billing policy version using ChangeRequest.
---
23

POST - /core/v1/billing-policies/versions/{billing_policy_version_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","billing_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"rules":{}}
```

Observação
Activate billing policy version using ChangeRequest.
---
24

POST - /core/v1/memory-policies

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create memory policy container.
---
24

POST - /core/v1/memory-policies/{memory_policy_id}/versions

Request Body
```json
{"status":"DRAFT","version_major":1,"version_minor":0,"version_patch":0,"definition":{"retention_ttl_seconds":2592000,"consent":{"required":false,"preference_key":"memory.consent","required_for_sources":["explicit_user"]},"allowed_sources":["explicit_user"],"allowed_schemas":[{"schema_id":"string","max_item_bytes":1,"allow_fields":{},"write_targets":["USER_PREFERENCE"],"preference_update":{"fixed_key":null,"allowed_keys":[null],"ignore_if_unchanged":true,"overwrite_mode":null}}]}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","memory_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"retention_ttl_seconds":2592000,"consent":{"required":false,"preference_key":"memory.consent","required_for_sources":["explicit_user"]},"allowed_sources":["explicit_user"],"allowed_schemas":[{"schema_id":"string","max_item_bytes":1,"allow_fields":{},"write_targets":["USER_PREFERENCE"],"preference_update":{"fixed_key":null,"allowed_keys":[null],"ignore_if_unchanged":true,"overwrite_mode":null}}]}}
```

Observação
Create memory policy version.
---
24

POST - /core/v1/memory-policies/versions/{memory_policy_version_id}:publish

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","memory_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"retention_ttl_seconds":2592000,"consent":{"required":false,"preference_key":"memory.consent","required_for_sources":["explicit_user"]},"allowed_sources":["explicit_user"],"allowed_schemas":[{"schema_id":"string","max_item_bytes":1,"allow_fields":{},"write_targets":["USER_PREFERENCE"],"preference_update":{"fixed_key":null,"allowed_keys":[null],"ignore_if_unchanged":true,"overwrite_mode":null}}]}}
```

Observação
Publish memory policy version using ChangeRequest.
---
24

POST - /core/v1/memory-policies/versions/{memory_policy_version_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","memory_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"retention_ttl_seconds":2592000,"consent":{"required":false,"preference_key":"memory.consent","required_for_sources":["explicit_user"]},"allowed_sources":["explicit_user"],"allowed_schemas":[{"schema_id":"string","max_item_bytes":1,"allow_fields":{},"write_targets":["USER_PREFERENCE"],"preference_update":{"fixed_key":null,"allowed_keys":[null],"ignore_if_unchanged":true,"overwrite_mode":null}}]}}
```

Observação
Activate memory policy version using ChangeRequest.
---
25

POST - /core/v1/rag-policies

Request Body
```json
{"name":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","tenant_id":"00000000-0000-0000-0000-000000000000","name":"string"}
```

Observação
Create RAG policy container.
---
25

POST - /core/v1/rag-policies/{rag_policy_id}/versions

Request Body
```json
{"status":"DRAFT","version_major":1,"version_minor":0,"version_patch":0,"definition":{"defaults":{"additional_prop":{"tenant_knowledge":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]},"user_memory_vector":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]}}},"require_published_rag_config":true,"top_k_cap":1,"min_query_chars_by_scope":{"additional_prop":1},"allow_structured_input":false}}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","rag_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"defaults":{"additional_prop":{"tenant_knowledge":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]},"user_memory_vector":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]}}},"require_published_rag_config":true,"top_k_cap":1,"min_query_chars_by_scope":{"additional_prop":1},"allow_structured_input":false}}
```

Observação
Create RAG policy version.
---
25

POST - /core/v1/rag-policies/versions/{rag_policy_version_id}:publish

Request Body
```json
{}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","rag_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"defaults":{"additional_prop":{"tenant_knowledge":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]},"user_memory_vector":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]}}},"require_published_rag_config":true,"top_k_cap":1,"min_query_chars_by_scope":{"additional_prop":1},"allow_structured_input":false}}
```

Observação
Publish RAG policy version using ChangeRequest.
---
25

POST - /core/v1/rag-policies/versions/{rag_policy_version_id}:activate

Request Body
```json
{"change_type":"string","justification":"string"}
```

Response Body
```json
{"id":"00000000-0000-0000-0000-000000000000","rag_policy_id":"00000000-0000-0000-0000-000000000000","status":"string","version_major":1,"version_minor":1,"version_patch":1,"definition":{"defaults":{"additional_prop":{"tenant_knowledge":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]},"user_memory_vector":{"enabled":false,"allowed_tool_config_ids":["00000000-0000-0000-0000-000000000000"]}}},"require_published_rag_config":true,"top_k_cap":1,"min_query_chars_by_scope":{"additional_prop":1},"allow_structured_input":false}}
```

Observação
Activate RAG policy version using ChangeRequest.
---
26

POST - /core/v1/tenants/mcp-servers

Request Body
```json
{"tool_config_ids":["00000000-0000-0000-0000-000000000000"],"vector_store_ids":["00000000-0000-0000-0000-000000000000"],"user_prompt_ids":["00000000-0000-0000-0000-000000000000"],"name":"string"}
```

Response Body
```json
{"endpoint":"string","api_key":"string","mcp_server_id":"00000000-0000-0000-0000-000000000000"}
```

Observação
Create MCP server registry entry for the tenant.
---
