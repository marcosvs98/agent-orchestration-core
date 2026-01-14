## Planning (9) — Modelo de Dados Canônico (Entidades, Responsabilidades e Relações)

**Objetivo**
Fixar o **contrato estrutural definitivo** do sistema.
Depois disso, ninguém “interpreta” o domínio — apenas implementa.

Banco de dados = **backbone do produto**.
Quem não respeita isso, quebra governança, auditoria e evolução.

---

## Tese central

1. Toda entidade relevante:

   * tem **identidade própria (PK)**
   * tem **dono explícito (Tenant direto ou indireto)**
   * tem **ciclo de vida definido**

2. Tudo que:

   * influencia decisão
   * altera execução
   * muda comportamento

**precisa existir como dado persistido.**

Prompt não é fonte de verdade.
Memória não é fonte de verdade.
Código não é fonte de verdade.

---

## Camadas conceituais (não misturar)

1. **Governança / Identidade**
2. **Authoring (design-time, imutável)**
3. **Execução (runtime, histórico)**
4. **Observabilidade / Auditoria**

Runtime **nunca** escreve em Authoring.
Authoring **nunca** depende de Runtime.

---

# 1. Governança e Identidade

### Tenant

**Raiz soberana do sistema.**

* PK: `tenant_id`
* Responsável por isolamento, billing, governança

Relações:

* Tenant 1–N User
* Tenant 1–N APIClient
* Tenant 1–N Flow
* Tenant 1–N Agent
* Tenant 1–N ToolConfig
* Tenant 1–N RagConfig
* Tenant 1–N AIExecutionPolicy

**Nada relevante existe fora de um Tenant.**

---

# 2. Authoring — Definição Imutável

## Flow

Identidade lógica de um processo.

* PK: `flow_id`
* FK: `tenant_id`

Relações:

* Flow 1–N FlowVersion

---

## FlowVersion

Snapshot imutável do fluxo.

* PK: `flow_version_id`
* FK: `flow_id`

Relações:

* FlowVersion 1–N Node
* FlowVersion 1–N RoutingRule

**Executa apenas via versão.**

---

## Node

Unidade declarativa de execução.

* PK: `node_id`
* FK: `flow_version_id`

Semântica:

* Representa **o que acontece**, não como
* Tipo é dado (ex: IntentDetection, SlotFilling)

Relações:

* Node N–1 FlowVersion
* Node 1–N NodeAgentBinding
* Node 0–1 Router

---

## Router

Estratégia de decisão declarativa.

* PK: `router_id`
* FK: `node_id`

Relações:

* Router 1–N RoutingRule

Router **pertence a um Node**, não ao Flow inteiro.

---

## RoutingRule

Transição condicional explícita.

* PK: `routing_rule_id`
* FK: `router_id`
* FK: `condition_expression_id`
* FK: `from_node_id`
* FK: `to_node_id`

Decisão = **dado versionado**, nunca `if` em código.

---

## ConditionExpression

Expressão declarativa reutilizável.

* PK: `condition_expression_id`

Relações:

* ConditionExpression 1–N RoutingRule
* ConditionExpression 1–N EscalationPolicy
* ConditionExpression 1–N OnboardingTransitionRule

---

# 3. Agentes e IA

## Agent

Conceito lógico do agente.

* PK: `agent_id`
* FK: `tenant_id`

Relações:

* Agent 1–N AgentVersion

---

## AgentVersion

Implementação executável imutável.

* PK: `agent_version_id`
* FK: `agent_id`
* FK: `ai_execution_policy_version_id`

Contém:

* prompts
* bindings
* políticas

Relações:

* AgentVersion 1–N NodeAgentBinding
* AgentVersion 1–N AgentVersionToolBinding
* AgentVersion 1–N AgentRun

---

## NodeAgentBinding

Associação explícita Node ↔ AgentVersion.

* PK: `node_agent_binding_id`
* FK: `node_id`
* FK: `agent_version_id`

**Agente nunca é implícito.**

---

## AITask

Tipo de responsabilidade cognitiva.

* PK: `ai_task_id`

Exemplos:

* moderation
* intent_detection
* slot_filling
* response_formatting

Relações:

* AITask 1–N AgentVersion

---

## AIExecutionPolicy

Definição lógica da política.

* PK: `ai_execution_policy_id`
* FK: `tenant_id`

Relações:

* AIExecutionPolicy 1–N AIExecutionPolicyVersion

---

## AIExecutionPolicyVersion

Snapshot imutável da política.

* PK: `ai_execution_policy_version_id`
* FK: `ai_execution_policy_id`
* FK: `model_id`

Relações:

* AIExecutionPolicyVersion 1–N AgentVersion

---

## Model

Abstração de modelo de IA.

* PK: `model_id`

Relações:

* Model 1–N AIExecutionPolicyVersion

---

# 4. Ferramentas / Integrações

## Tool

Contrato abstrato (ex: OpenAPI).

* PK: `tool_id`

Relações:

* Tool 1–N ToolConfig

---

## ToolConfig

Configuração concreta por tenant.

* PK: `tool_config_id`
* FK: `tool_id`
* FK: `tenant_id`

Relações:

* ToolConfig 1–N AgentVersionToolBinding
* ToolConfig 1–N ToolRun

---

## AgentVersionToolBinding

Autorização explícita de uso.

* PK: `agent_version_tool_binding_id`
* FK: `agent_version_id`
* FK: `tool_config_id`

Sem binding = **uso proibido**.

---

# 5. RAG

## RagConfig

Configuração de recuperação.

* PK: `rag_config_id`
* FK: `tenant_id`
* FK: `vector_store_id`

Relações:

* RagConfig 1–N AgentVersion

---

## VectorStore

Backend vetorial concreto.

* PK: `vector_store_id`

Relações:

* VectorStore 1–N RagConfig

---

# 6. Execução — Runtime

## Session

Contexto técnico da interação.

* PK: `session_id`
* FK: `tenant_id`

Relações:

* Session 1–N Interaction
* Session 1–N FlowRun

---

## Interaction

Evento imutável de entrada/saída.

* PK: `interaction_id`
* FK: `session_id`
* FK opcional: `flow_run_id`

Não interpreta significado. Apenas registra.

---

## FlowRun

Execução concreta de um FlowVersion.

* PK: `flow_run_id`
* FK: `flow_version_id`
* FK: `session_id`

Relações:

* FlowRun 1–N NodeRun
* FlowRun 1–1 GraphState
* FlowRun 1–N Escalation

---

## NodeRun

Execução de um Node.

* PK: `node_run_id`
* FK: `flow_run_id`
* FK: `node_id`

Relações:

* NodeRun 0–1 AgentRun

---

## AgentRun

Execução efetiva do agente.

* PK: `agent_run_id`
* FK: `node_run_id`
* FK: `agent_version_id`
* FK: `ai_execution_policy_version_id`

---

## ToolRun

Chamada efetiva de ferramenta.

* PK: `tool_run_id`
* FK: `agent_run_id`
* FK: `tool_config_id`

---

# 7. Observabilidade e Auditoria

## ExecutionEvent

Evento append-only.

* PK: `execution_event_id`
* FK: `flow_run_id`

Registra:

* decisão
* erro
* transição
* política aplicada

---

## GraphState

Estado lógico consolidado.

* PK: `graph_state_id`
* FK: `flow_run_id`

---

## EscalationPolicy

Regra de exceção.

* PK: `escalation_policy_id`
* FK: `condition_expression_id`

---

## Escalation

Evento de escalada.

* PK: `escalation_id`
* FK: `flow_run_id`
* FK: `escalation_policy_id`

---

# Regras estruturais inegociáveis

* Definition é **imutável**
* Execução referencia **versões exatas**
* Tenant nunca é opcional
* Compatibilidade é **dado**
* Observabilidade é **append-only**

---

## Anti-patterns proibidos

* `current_version`
* FK nullable para Tenant
* Decisão em código
* Prompt como fonte de verdade
* Runtime alterando authoring

---
