# Demo Seeds to Postman Request Body Mapping

This document maps each demo seed script to the corresponding Postman request(s) in **demo > financial-assistance** and provides the **exact request body JSON** (raw) that reproduces the same logical data as the seed when sent to the API.

**Note:** Create endpoints generally do not accept resource `id` in the body; the server generates IDs. The payloads below use the same **content** (names, descriptions, options) as the seeds. Where the API accepts IDs (e.g. `flow_version_id`, `node_id`, `vector_store_id`), UUIDs from `resources/scripts/seeds/demo/ids.py` are used. After running these requests, created resource IDs will be returned in the response; use those for subsequent requests that reference them (e.g. vector_store_id for RAG Config), unless you run seeds first to get fixed demo UUIDs.

**Missing in Postman:** There is no **"3 - Create Model"** request in the demo section. Seed `seed_03_model.py` creates model catalog entries; the collection has **"3.1 - Create Ai Execution Policy"** instead. Model catalog may be created via a different endpoint or admin flow.

---

## Seed → Postman mapping


| Seed file                                   | Postman request(s)                                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| seed_01_tenant.py                           | 1 - Create Tenant                                                                           |
| seed_02_ai_tasks.py                         | No-op (AI Task removido do fluxo)                                                           |
| seed_03_model.py                            | *(No direct request; 3.1 is AI Execution Policy)*                                           |
| seed_04_policy.py                           | 3.1 - Create Ai Execution Policy (+ policy version via separate endpoint)                   |
| seed_05_tool.py                             | 4 - Import Tools (tool + config; import uses OpenAPI URL)                                   |
| seed_06_agent.py                            | 9 - Create Agent (+ agent version)                                                          |
| seed_07_flow.py                             | 10 - Create Flow (+ flow version)                                                           |
| seed_08_nodes.py                            | 11 - Copy Node From Template (per node)                                                     |
| seed_09_prompts.py                          | 12 - Create Or Update Prompt (per prompt)                                                   |
| seed_10_bindings.py                         | 14 - Create Node Agent Binding, 15 - Create Agent Version Tool Binding                      |
| seed_11_graph.py                            | 16 - Upsert Flow Graph Draft                                                                |
| seed_12_runtime_policy.py                   | 17 - Create Runtime Policy                                                                  |
| seed_15_node_ai_execution_policy_binding.py | 18 - Create Node Ai Execution Policy Binding                                                |
| seed_16_router.py                           | 19 - Create Router, 20 - Create Condition Expression (+ routing rule)                       |
| seed_18_access_policy.py                    | 21 - Create Access Policy (+ version)                                                       |
| seed_19_rate_limit_policy.py                | 22 - Create Rate Limit Policy (+ version)                                                   |
| seed_20_billing_policy.py                   | 23 - Create Billing Policy (+ version)                                                      |
| seed_21_rag.py                              | 5 - Create Vector Store, 6 - Create Rag Config, 7 - Ingest Document, 8 - Publish Rag Config |
| seed_22_memory_policy.py                    | 24 - Create Memory Policy (+ version)                                                       |
| seed_22_tool_catalog_rag.py                 | 7 - Ingest Document (additional documents)                                                  |
| seed_23_rag_policy.py                       | 25 - Create Rag Policy (+ version)                                                          |
| seed_24_user_prompt.py                      | 13 - Create User Prompt                                                                     |
| seed_25_mcp_server.py                       | 26 - Create Mcp Server                                                                      |


Seeds **seed_13_llm_provider_config**, **seed_14_llm_model_mapping**, **seed_17_llm_pricing** have no direct demo Postman request names listed; they configure LLM provider/model/pricing.

---

## Tenant ponta a ponta (fluxo atual do seed)

Ordem executada em `resources/scripts/seeds/demo/run.py` para provisionar o tenant completo:

1. Tenant
2. Model
3. AI Execution Policy
4. Tool
5. RAG
6. Tool Catalog RAG
7. Agent
8. Flow
9. Prompts
10. Nodes
11. User prompt
12. Bindings
13. Graph
14. Runtime Policy
15. LLM Provider Config
16. LLM Model Mapping
17. Node AI Execution Policy Binding
18. Router
19. LLM Pricing
20. Access Policy
21. Rate Limit Policy
22. Billing Policy
23. Memory Policy
24. RAG Policy
25. MCP Server

---

## Mudanças de endpoint/schema após remoção de AI Task

- `POST /core/v1/ai-tasks` não faz mais parte do fluxo de criação.
- A criação de `Node` concentra o comportamento que antes estava em `ai_task`.
- Em `Node`, use os campos:
  - `node_prompt_id`
  - `allow_rag_tenant`
  - `allow_user_memory`
  - `allow_session_context`
  - `allow_memory_write`

---

## Exact request body JSON (raw) by Postman request

Use each block below as the **Body > raw** (application/json) for the corresponding request. Replace `{{tenantId}}`, `{{flowVersionId}}`, etc. with values from previous responses if not using seed IDs.

---

### 1 - Create Tenant

```json
{
  "name": "Assistente de Bolso",
  "external_id": null,
  "description": "Agente financeiro conversacional via WhatsApp: controle financeiro pessoal com integração bancária (Open Finance), categorização de gastos, relatórios, metas financeiras e compromissos.",
  "timezone": "America/Sao_Paulo",
  "is_active": true,
  "currency": "BRL",
  "language": "pt-BR",
  "contact_name": null,
  "contact_phone": null,
  "settings": null
}
```

---

### 2 - AI Task

Não aplicável no fluxo atual. `ai_task` não é mais criado via endpoint e `seed_02_ai_tasks.py` é no-op.

---

### 3.1 - Create Ai Execution Policy

Policy only (no version). Seed also creates a policy version with model_id and status PUBLISHED; that is typically a separate “Create AI Execution Policy Version” endpoint.

```json
{
  "description": "AI Execution Policy para tenant demo"
}
```

---

### 4 - Import Tools

Seed creates a tool from `resources/scripts/seeds/demo/openapi/demo_api.json`. Use a URL that serves that OpenAPI spec (e.g. hosted or local server).

```json
{
  "openapi_url": "http://localhost:3001/openapi.json",
  "name": "createExpense"
}
```

---

### 5 - Create Vector Store

```json
{
  "name": "Assistente de Bolso - Conhecimento"
}
```

---

### 6 - Create Rag Config

Use the `vector_store_id` from the Create Vector Store response (or `00000000-0000-0000-0000-000000001400` if seed was run). Options match `RagConfigOptions()` defaults.

```json
{
  "vector_store_id": "00000000-0000-0000-0000-000000001400",
  "options": {
    "embedding": {
      "provider": "OPENAI",
      "model_alias": "text-embedding-3-small",
      "dimension": 1536
    },
    "chunking": {
      "target_tokens": 500,
      "overlap_tokens": 50,
      "max_chunks_per_document": 100,
      "max_document_chars": 100000
    },
    "retrieval": {
      "top_k": 5,
      "similarity_threshold": 0.5,
      "filters": null
    },
    "generation_contract": {
      "allow_extrapolation": false,
      "no_context_behavior": "FALLBACK_MESSAGE"
    }
  }
}
```

---

### 7 - Ingest Document

Batch ingest of all documents from seed_21_rag. Use `rag_config_id` from Create Rag Config response (or `00000000-0000-0000-0000-000000001401`).

```json
[
  {
    "source": "assistente-bolso",
    "doc_type": "identity_proposito",
    "content": "Identidade: O Assistente de Bolso é uma IA de controle financeiro pessoal operada via WhatsApp. Atua como interface conversacional para organização de receitas, despesas, saldos, metas financeiras e compromissos. É um operador financeiro conversacional. Não substitui contador, assessor de investimentos ou consultor jurídico/tributário. Seu papel é fornecer organização, visibilidade e apoio operacional. Proposta de valor: Conecta automaticamente às contas bancárias via Open Finance; categoriza ganhos e gastos; permite consultas financeiras por mensagem; gera relatórios e resumos periódicos; gerencia compromissos e lembretes; pode integrar com Google Agenda; opera de forma simples, direto no WhatsApp. A experiência deve ser conversacional, prática e sem fricção. Propósito: Organizar a vida financeira do usuário; reduzir fricção no registro de movimentações; fornecer clareza sobre para onde o dinheiro está indo; apoiar criação e acompanhamento de metas financeiras; centralizar finanças e compromissos em uma única conversa. Tom de voz: profissional, claro, direto, objetivo, didático quando necessário, respeitoso. Small talk é permitido, mas deve ser breve e reconduzido para utilidade prática.",
    "version": "1",
    "metadata": {
      "topic": "identity_proposito"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "escopo",
    "content": "Escopo funcional – Inclui: Registro manual de despesas e receitas via linguagem natural; registro automático via conexão bancária; consulta de saldo; consulta de gastos por categoria; consulta de economia acumulada; relatórios mensais e resumos periódicos; criação de metas financeiras; cálculo simples de quanto precisa economizar para atingir uma meta; criação e consulta de compromissos; criação de lembretes; integração com Google Agenda. Não inclui: Aconselhamento de investimentos avançado; planejamento tributário; decisões financeiras autônomas; simulação de operações financeiras inexistentes.",
    "version": "1",
    "metadata": {
      "topic": "scope"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_conexao_bancaria",
    "content": "FAQ – Conexão Bancária. Pergunta: Como conecto minha conta bancária? Resposta: Você pode conectar sua conta por meio do fluxo de Open Finance. Após autorização, suas movimentações passam a ser sincronizadas automaticamente. Pergunta: Preciso atualizar manualmente as transações? Resposta: Não. Após a conexão, as movimentações são sincronizadas automaticamente. Pergunta: Minhas transações são registradas automaticamente? Resposta: Sim, quando a conta está conectada, receitas e despesas são importadas e categorizadas automaticamente.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "conexao_bancaria"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_registro_despesas_receitas",
    "content": "FAQ – Registro de Despesas e Receitas. Pergunta: Como registro uma despesa? Resposta: Basta informar o valor e a descrição, por exemplo: “Gastei 120 reais no mercado”. Se houver integração ativa, o sistema pode já ter registrado automaticamente. Pergunta: Como registro uma receita? Resposta: Informe o valor e a origem, por exemplo: “Recebi 2.000 reais de salário”. Pergunta: Preciso informar a data? Resposta: Se não informar, será considerada a data atual.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "registro"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_consultas_financeiras",
    "content": "FAQ – Consultas Financeiras. Pergunta: Quanto eu economizei este mês? Resposta: O assistente calcula com base nas receitas e despesas registradas no período. Pergunta: Quais são meus maiores gastos? Resposta: O assistente pode informar os principais gastos por categoria no período solicitado. Pergunta: Qual meu saldo atual? Resposta: O saldo é calculado com base nas contas conectadas e movimentações registradas.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "consultas"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_relatorios",
    "content": "FAQ – Relatórios e Resumos. Pergunta: Recebo relatório mensal? Resposta: Sim, o assistente pode fornecer resumos mensais com visão consolidada de receitas, despesas e economia. Pergunta: Posso ver meus gastos por categoria? Resposta: Sim, é possível consultar gastos segmentados por categoria.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "relatorios"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_metas_financeiras",
    "content": "FAQ – Metas Financeiras. Pergunta: Posso criar uma meta financeira? Resposta: Sim. Você pode definir um objetivo, como “Quero economizar 5.000 reais”. O assistente ajuda a calcular quanto precisa poupar por período. Pergunta: Como sei quanto posso gastar por dia para atingir minha meta? Resposta: O assistente pode calcular um limite médio de gasto com base no prazo e no valor da meta.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "metas"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "faq_uso_geral",
    "content": "FAQ – Uso Geral. Pergunta: Como começo a usar? Resposta: Inicie a conversa com uma saudação e siga o fluxo de configuração, incluindo conexão bancária se desejar sincronização automática. Pergunta: Posso usar apenas por mensagem? Resposta: Sim. Toda interação ocorre via WhatsApp. Pergunta: O assistente entende áudio ou imagem? Resposta: Conforme escopo do agente, o assistente pode interpretar áudios e imagens enviadas, tratando-as como entradas da conversa.",
    "version": "1",
    "metadata": {
      "topic": "faq",
      "section": "uso_geral"
    }
  },
  {
    "source": "assistente-bolso",
    "doc_type": "comportamento_limites",
    "content": "Princípios de comportamento: O assistente deve nunca inventar dados financeiros; trabalhar exclusivamente com dados disponíveis no sistema; informar explicitamente quando não houver informação; confirmar dados em caso de ambiguidade relevante; não assumir contexto financeiro não informado; não prometer funcionalidades inexistentes. Se houver limitação técnica, deve informar claramente. Tratamento de dados: Utiliza integração bancária via Open Finance para sincronizar movimentações; evita duplicidade quando integração estiver ativa; pode integrar com Google Agenda para compromissos. Segurança: Comunicação via WhatsApp; dados financeiros tratados com segurança; nunca expor dados sensíveis além do necessário. Small talk – Cumprimento: responder de forma cordial e oferecer ajuda objetiva (ex: “Olá. Como posso ajudar com sua organização financeira hoje?”). Usuário frustrado: reconhecer a situação e oferecer solução prática. Pedido genérico: converter para ação concreta (ex: “Você quer registrar uma despesa, consultar seu saldo ou criar uma meta?”). Limitações estratégicas: Não realiza aconselhamento financeiro profundo; não toma decisões pelo usuário; não executa operações bancárias; não simula funcionalidades inexistentes. Diretriz final: O Assistente de Bolso deve operar como um copiloto financeiro pessoal: organizado, confiável, orientado a execução e focado em clareza financeira.",
    "version": "1",
    "metadata": {
      "topic": "policy"
    }
  }
]
```

---

### 8 - Publish Rag Config

Typically a PUT/PATCH to the RAG config resource to set status to PUBLISHED, or a dedicated “Publish” endpoint. If the request body is empty or a small payload, use the response from 6 - Create Rag Config to get `rag_config_id` and call the publish endpoint for that id.

```json
{}
```

*(Adjust to actual API: may be a query/path-only request or a body with `status: "PUBLISHED"`.)*

---

### 9 - Create Agent

```json
{
  "name": "Assistente de Bolso"
}
```

---

### 10 - Create Flow

```json
{
  "name": "fluxo-assistente-bolso",
  "description": "Fluxo conversacional do Assistente de Bolso: intent, extração de parâmetros, execução de ferramentas (registro de despesas/receitas, consultas, metas, lembretes) e resposta ao usuário.",
  "tags": null
}
```

---

### 11 - Copy Node From Template

Varies by node. Example for one node: copy from template and optionally override config. Use `flow_version_id` from Create Flow version (e.g. `00000000-0000-0000-0000-000000000701`). Request schema depends on endpoint (e.g. template_code + flow_version_id).

No fluxo atual, o `Node` precisa refletir os campos de governança no próprio schema (`node_prompt_id` + flags `allow_*`), sem `ai_task_id`.

```json
{
  "template_code": "catalog.intent_detection.v1",
  "flow_version_id": "00000000-0000-0000-0000-000000000701"
}
```

*(Repeat for other template codes used in seed_08; exact field names may differ per API.)*

---

### 12 - Create Or Update Prompt

One of the node prompts (e.g. IntentDetectionNode). Use same `node_type`, `template_text`, `output_schema` as in seed_09_prompts.

```json
{
  "node_type": "IntentDetectionNode",
  "template_text": "# Task\nClassify all user intents types and confidence.",
  "output_schema": {
    "type": "object",
    "additionalProperties": false,
    "properties": {
      "result": {
        "type": "array",
        "items": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "intent_type": { "type": "string", "enum": ["query", "command", "conversation"] },
            "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
            "priority": { "type": "integer", "minimum": 1 }
          },
          "required": ["intent_type", "confidence", "priority"]
        }
      },
      "overall_confidence": { "type": "number", "minimum": 0, "maximum": 1 }
    },
    "required": ["result", "overall_confidence"]
  },
  "description": "Prompt for IntentDetectionNode",
  "created_by": "system"
}
```

---

### 13 - Create User Prompt

```json
{
  "title": "financial_context_default",
  "content": "Prioritize objective financial guidance. If user intent is ambiguous, ask one direct clarification question. When possible, present concise recommendations with clear next action.",
  "created_by": "system"
}
```

---

### 14 - Create Node Agent Binding

Use `node_id` and `agent_version_id` from previous responses (or seed IDs).

```json
{
  "node_id": "00000000-0000-0000-0000-000000000800",
  "agent_version_id": "00000000-0000-0000-0000-000000000601"
}
```

---

### 15 - Create Agent Version Tool Binding

```json
{
  "agent_version_id": "00000000-0000-0000-0000-000000000601",
  "tool_config_id": "00000000-0000-0000-0000-000000000501"
}
```

---

### 16 - Upsert Flow Graph Draft

Full graph definition from seed_11. Use `flow_id` and `flow_version_id` in path/body; `principal_id` from auth or `"system"`. Below: `definition` only (start_node, nodes, edges). If the API expects `FlowGraphDraftCreate`, add `flow_id`, `flow_version_id`, `principal_id` at top level.

```json
{
  "flow_id": "00000000-0000-0000-0000-000000000700",
  "flow_version_id": "00000000-0000-0000-0000-000000000701",
  "principal_id": "system",
  "definition": {
    "start_node": "00000000-0000-0000-0000-00000000080d",
    "nodes": {
      "00000000-0000-0000-0000-00000000080d": {
        "type": "InputModerationNode",
        "config": {
          "primary": { "provider": "SLM_LOCAL", "model_alias": "slm-local-moderation", "timeout_ms": 300 },
          "fallback": { "provider": "OPENAI", "model_alias": "omni-moderation-latest", "timeout_ms": 1000 },
          "fallback_enabled": true,
          "prompt_key": "InputModerationNode",
          "temperature": 0.0,
          "max_tokens": 18
        }
      },
      "00000000-0000-0000-0000-000000000805": {
        "type": "UserContextEnrichmentNode",
        "config": {
          "publish": true,
          "layers": {
            "allow_tenant_knowledge": true,
            "allow_user_memory_structured": true,
            "allow_user_memory_vector": true
          }
        }
      },
      "00000000-0000-0000-0000-000000000800": {
        "type": "IntentDetectionNode",
        "config": {
          "llm": {
            "task_type": "INTENT_SELECTION",
            "provider": "OPENAI",
            "model_alias": "gpt-4.1-mini",
            "temperature": 0,
            "top_p": 0.05,
            "use_system_prompt": false,
            "use_system_context": true,
            "use_conversation_history": false,
            "completion_budget": { "schema_factor": 1.2, "safety_margin": 16, "floor": 32 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000807": {
        "type": "ToolSelectionNode",
        "config": {
          "llm": {
            "task_type": "TOOL_SELECTION",
            "provider": "OPENAI",
            "model_alias": "gpt-4.1-mini",
            "temperature": 0,
            "top_p": 0.1,
            "use_system_prompt": false,
            "use_system_context": true,
            "use_conversation_history": false,
            "completion_budget": { "schema_factor": 1.2, "safety_margin": 16, "floor": 48 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000801": {
        "type": "ParamExtractionNode",
        "config": {
          "llm": {
            "task_type": "SLOT_FILLING",
            "provider": "OPENAI",
            "model_alias": "gpt-4.1-mini",
            "temperature": 0.2,
            "top_p": 0.2,
            "use_system_prompt": false,
            "use_system_context": true,
            "use_conversation_history": true,
            "completion_budget": { "schema_factor": 1.5, "safety_margin": 24, "floor": 64 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000806": {
        "type": "ClarificationNode",
        "config": {
          "resume_to_node_id": "00000000-0000-0000-0000-000000000800",
          "llm": {
            "task_type": "CLARIFICATION",
            "provider": "OPENAI",
            "model_alias": "gpt-4o",
            "temperature": 0.3,
            "top_p": 0.4,
            "use_system_prompt": true,
            "use_system_context": true,
            "use_conversation_history": true,
            "completion_budget": { "schema_factor": 1.7, "safety_margin": 24, "floor": 80 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000804": {
        "type": "ClarificationNode",
        "config": {
          "resume_to_node_id": "00000000-0000-0000-0000-000000000801",
          "llm": {
            "task_type": "CLARIFICATION",
            "provider": "OPENAI",
            "model_alias": "gpt-4o",
            "temperature": 0.3,
            "top_p": 0.4,
            "use_system_prompt": true,
            "use_system_context": true,
            "use_conversation_history": true,
            "completion_budget": { "schema_factor": 1.7, "safety_margin": 24, "floor": 80 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000803": { "type": "ToolExecutionNode", "config": {} },
      "00000000-0000-0000-0000-00000000080a": { "type": "ToolErrorHandlerNode", "config": { "max_retries": 1 } },
      "00000000-0000-0000-0000-00000000080c": {
        "type": "FallbackNodeSLA",
        "config": {
          "llm": {
            "task_type": "FALLBACK_SLA",
            "provider": "OPENAI",
            "model_alias": "gpt-4.1-mini",
            "temperature": 0.0,
            "top_p": 0.0,
            "use_system_prompt": false,
            "use_system_context": false,
            "use_conversation_history": false,
            "completion_budget": { "schema_factor": 1.2, "safety_margin": 16, "floor": 32 }
          }
        }
      },
      "00000000-0000-0000-0000-000000000802": {
        "type": "ResponseComposer",
        "config": {
          "llm": {
            "task_type": "RESPONSE_RENDER",
            "provider": "OPENAI",
            "model_alias": "gpt-4o",
            "temperature": 0.3,
            "top_p": 0.4,
            "use_system_prompt": true,
            "use_system_context": true,
            "use_conversation_history": true,
            "completion_budget": { "schema_factor": 1.7, "safety_margin": 24, "floor": 80 }
          }
        }
      }
    },
    "edges": [
      { "from_node": "00000000-0000-0000-0000-00000000080d", "to_node": "00000000-0000-0000-0000-000000000805", "condition": "flagged == false", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-00000000080d", "to_node": "00000000-0000-0000-0000-00000000080c", "condition": "flagged == true", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000805", "to_node": "00000000-0000-0000-0000-000000000800", "condition": "1==1", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000800", "to_node": "00000000-0000-0000-0000-000000000806", "condition": "overall_confidence < 0.6", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000800", "to_node": "00000000-0000-0000-0000-000000000807", "condition": "HasAny(result.intent_type, ['command']) and overall_confidence >= 0.8", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000800", "to_node": "00000000-0000-0000-0000-000000000802", "condition": "overall_confidence >= 0.6 and (HasAny(result.intent_type, ['conversation']) or not HasAny(result.intent_type, ['command']))", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000806", "to_node": "00000000-0000-0000-0000-000000000802", "condition": "1==1", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000807", "to_node": "00000000-0000-0000-0000-000000000801", "condition": "len(result) >= 1", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000801", "to_node": "00000000-0000-0000-0000-000000000804", "condition": "HasAny(result.status, ['incomplete'])", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000804", "to_node": "00000000-0000-0000-0000-000000000801", "condition": "1==1", "edge_kind": "LOOP" },
      { "from_node": "00000000-0000-0000-0000-000000000801", "to_node": "00000000-0000-0000-0000-000000000803", "condition": "HasAll(result.status, ['ready'])", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000803", "to_node": "00000000-0000-0000-0000-000000000802", "condition": "HasAll(result.status, ['success', 'scheduled'])", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-000000000803", "to_node": "00000000-0000-0000-0000-00000000080a", "condition": "HasAny(result.status, ['incomplete', 'error', 'cancelled'])", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-00000000080a", "to_node": "00000000-0000-0000-0000-000000000803", "condition": "retry_operation_ids_count > 0", "edge_kind": "LOOP" },
      { "from_node": "00000000-0000-0000-0000-00000000080a", "to_node": "00000000-0000-0000-0000-00000000080c", "condition": "fallback_required == true", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-00000000080a", "to_node": "00000000-0000-0000-0000-000000000802", "condition": "retry_operation_ids_count == 0 and fallback_required == false", "edge_kind": "NORMAL" },
      { "from_node": "00000000-0000-0000-0000-00000000080c", "to_node": "00000000-0000-0000-0000-000000000802", "condition": "1==1", "edge_kind": "NORMAL" }
    ]
  }
}
```

---

### 17 - Create Runtime Policy

```json
{
    "scope": "TENANT",
    "flow_id": null,
    "version": "1",
    "policy_definition": {
        "limits": {
            "max_nodes": 50,
            "max_depth": 20,
            "max_edges_per_node": 3,
            "max_total_duration_ms": 60000,
            "max_node_duration_ms": 15000,
            "max_loop_iterations": 10,
            "tool_fanout_max_concurrency": 4
        },
        "execution": {
            "fail_on_multiple_true_edges": true,
            "fail_on_missing_graph": true,
            "allow_parallel_nodes": false,
            "strict_contract_mode": true
        },
        "tools": {
            "max_retries": 2,
            "circuit_breaker": {
                "failure_threshold": 5,
                "window_seconds": 60
            }
        },
        "llm": {
            "max_retries": 3,
            "timeout_ms": 30000,
            "stream_enabled": true,
            "stream_eligible_tasks": [
                "response_render",
                "clarification"
            ],
            "history_enabled_tasks": [
                "intent_selection",
                "tool_selection",
                "slot_filling",
                "clarification",
                "response_render"
            ],
            "temperature": 0,
            "max_tokens": 1024,
            "inference_layers": {
                "cache_enabled": true,
                "cache_similarity_threshold": 0.95,
                "cache_ttl_seconds": 3600,
                "slm_enabled": true,
                "slm_eligible_tasks": [
                    "intent_selection",
                    "tool_selection",
                    "fallback_response"
                ],
                "slm_provider": "SLM_LOCAL",
                "slm_model_alias": "qwen2.5-1.5b-instruct",
                "escalation_on_schema_mismatch": true
            }
        },
        "moderation": {
            "primary": {
                "provider": "SLM_LOCAL",
                "model_alias": "slm-local-moderation",
                "timeout_ms": 300
            },
            "fallback": {
                "provider": "OPENAI",
                "model_alias": "omni-moderation-latest",
                "timeout_ms": 1000
            },
            "fallback_enabled": true,
            "prompt_key": "InputModerationNode",
            "temperature": 0.0,
            "max_tokens": 18
        },
        "fallback_sla": {
            "primary": {
                "provider": "SLM_LOCAL",
                "model_alias": "slm-local-moderation",
                "timeout_ms": 300
            },
            "fallback_enabled": false,
            "prompt_key": "FallbackNode",
            "temperature": 0.0,
            "max_tokens": 100
        },
        "user_context_enrichment": {
            "enabled": false,
            "gating": false,
            "default_layers_when_published": {
                "allow_tenant_knowledge": true,
                "allow_user_memory_structured": true,
                "allow_user_memory_vector": true
            }
        },
        "memory_extraction": {
            "enabled": true,
            "rag_config_id": "00000000-0000-0000-0000-000000001401",
            "preference_schema_id": "user.preference.v1",
            "profile_schema_id": "user.profile_signal.v1",
            "llm": {
                "provider": "OPENAI",
                "model_alias": "gpt-4o-mini",
                "prompt": "Extract user preferences from flow output.",
                "task_type": "MEMORY_EXTRACTION"
            }
        },
        "memory_retrieval": {
            "temporal_scoring": {
                "enabled": false,
                "half_life_seconds": 604800,
                "timestamp_source": "OBSERVED_AT",
                "candidate_multiplier": 3
            }
        }
    }
}
```

---

### 18 - Create Node Ai Execution Policy Binding

```json
{
    "node_id": "00000000-0000-0000-0000-000000000800",
    "ai_execution_policy_version_id": "00000000-0000-0000-0000-000000000401"
}
```

*(Repeat for other node/policy-version pairs: slot, response, clarification, clarification_intent.)*

---

### 19 - Create Router

```json
{
  "node_id": "00000000-0000-0000-0000-000000000800"
}
```

---

### 20 - Create Condition Expression

```json
{
  "expression": "ctx.get(\"primary_intent_type\") == \"command\""
}
```

---

### 21 - Create Access Policy

```json
{
  "name": "Assistente de Bolso - Access Policy"
}
```

*(Create version separately with rules.allow containing scope values, e.g. `["execution:flow_run:create"]`.)*

---

### 22 - Create Rate Limit Policy

```json
{
  "name": "Assistente de Bolso - Rate Limit Policy"
}
```

*(Create version with action, principal_type, limit, window_seconds per seed_19.)*

---

### 23 - Create Billing Policy

```json
{
    "name": "Assistente de Bolso - Billing Policy"
}
```

---

### 24 - Create Memory Policy

```json
{
  "name": "Assistente de Bolso - Memory Policy"
}
```

*(Create version with definition containing retention_ttl_seconds, consent, allowed_sources, allowed_schemas per seed_22_memory_policy.)*

---

### 25 - Create Rag Policy

```json
{
  "name": "Assistente de Bolso - RAG Activation Policy"
}
```

*(Create version with definition containing defaults (intent_selection, slot_filling, response_render, clarification), require_published_rag_config, top_k_cap, min_query_chars_by_scope, allow_structured_input per seed_23.)*

---

### 26 - Create Mcp Server

MCP server create returns an endpoint and API key; the seed uses a fixed demo key. Request body only needs name and optional bindings; server generates id and key.

```json
{
  "name": "demo-mcp-server",
  "tool_config_ids": ["00000000-0000-0000-0000-000000000501"],
  "vector_store_ids": ["00000000-0000-0000-0000-000000001400"],
  "user_prompt_ids": ["00000000-0000-0000-0000-000000000907"]
}
```

---

## Policy version and publish steps

For **Access**, **Rate Limit**, **Billing**, **Memory**, and **RAG** policies, the demo seeds also create a **version** (with rules or definition) and may publish/activate. Those are separate API calls after creating the policy, for example:

- **Access Policy Version**: `rules: { "allow": ["execution:flow_run:create"] }`, then publish.
- **Rate Limit Policy Version**: `action: "execution:flow_run:create"`, `principal_type: "human"`, `limit: 100`, `window_seconds: 60`, then publish.
- **Billing Policy Version**: default empty rules, then publish.
- **Memory Policy Version**: `definition` with retention_ttl_seconds, consent, allowed_sources, allowed_schemas (see seed_22_memory_policy), then publish.
- **RAG Policy Version**: `definition` with defaults for intent_selection, slot_filling, response_render, clarification (see seed_23_rag_policy), then publish/activate.

Use the policy IDs returned from the “Create X Policy” requests when calling the corresponding “Create X Policy Version” and “Publish” endpoints.