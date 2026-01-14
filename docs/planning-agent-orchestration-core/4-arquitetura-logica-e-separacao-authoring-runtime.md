## Planning (4) — Modelo Relacional como Backbone do Sistema

### Tese central

O banco de dados é o **contrato estrutural do sistema**.

Ele define:

* o que pode existir,
* o que pode ser executado,
* o que pode decidir,
* o que pode ser auditado.

Runtime **não cria comportamento**.
IA **não decide arquitetura**.
Código **não substitui dados**.

Se algo:

* influencia decisão,
* altera execução,
* muda resposta,
* gera custo,
* precisa ser auditado,

então **existe como entidade persistida**.

Se não está no banco, **não existe**.

---

## Raiz de Governança

### Tenant

**PK**

* tenant_id

**Contexto**
Fronteira soberana de isolamento, política e escopo.

**Relações**

* Tenant 1:N Session (Session.tenant_id)
* Tenant 1:N Flow (Flow.tenant_id)
* Tenant 1:N Agent (Agent.tenant_id)
* Tenant 1:N ToolConfig (ToolConfig.tenant_id)
* Tenant 1:N RagConfig (RagConfig.tenant_id)

Nenhuma entidade relevante existe fora de um tenant.

---

## Interação / Registro de Eventos

### Session

**PK**

* session_id

**FK**

* tenant_id → Tenant.tenant_id

**Contexto**
Contexto técnico da interação. Não interpreta significado.

---

### Interaction

**PK**

* interaction_id

**FK**

* session_id → Session.session_id
* flow_run_id → FlowRun.flow_run_id (opcional)

**Contexto**
Evento imutável de entrada ou saída.

---

## Definição de Fluxo (Design-time)

### Flow

**PK**

* flow_id

**FK**

* tenant_id → Tenant.tenant_id

**Contexto**
Identidade lógica de um processo.

---

### FlowVersion

**PK**

* flow_version_id

**FK**

* flow_id → Flow.flow_id

**Contexto**
Snapshot imutável do fluxo.

---

### Node

**PK**

* node_id

**FK**

* flow_version_id → FlowVersion.flow_version_id

**Contexto**
Unidade executável pertencente a uma versão específica.

---

## Decisão de Caminho

### Router

**PK**

* router_id

**FK**

* flow_version_id → FlowVersion.flow_version_id

**Contexto**
Estratégia declarativa de decisão.

---

### RoutingRule

**PK**

* routing_rule_id

**FK**

* router_id → Router.router_id
* condition_expression_id → ConditionExpression.condition_expression_id

**Contexto**
Regra individual de roteamento.

---

### ConditionExpression

**PK**

* condition_expression_id

**Contexto**
Expressão reutilizável e versionável de condição.

---

## Agentes (Cognição Controlada)

### Agent

**PK**

* agent_id

**FK**

* tenant_id → Tenant.tenant_id

**Contexto**
Conceito lógico de agente.

---

### AgentVersion

**PK**

* agent_version_id

**FK**

* agent_id → Agent.agent_id

**Contexto**
Implementação imutável do agente.

---

### NodeAgentBinding

**PK**

* node_agent_binding_id

**FK**

* node_id → Node.node_id
* agent_version_id → AgentVersion.agent_version_id

**Contexto**
Associação explícita entre node e agente.

---

## IA / Execução / Políticas

### AITask

**PK**

* ai_task_id

**Contexto**
Tipo de tarefa cognitiva (classificação, geração, extração etc).

---

### AIExecutionPolicy

**PK**

* ai_execution_policy_id

**Contexto**
Definição lógica de política de execução.

---

### AIExecutionPolicyVersion

**PK**

* ai_execution_policy_version_id

**FK**

* ai_execution_policy_id → AIExecutionPolicy.ai_execution_policy_id
* model_id → Model.model_id

**Contexto**
Snapshot imutável da política associada a um modelo.

---

### Model

**PK**

* model_id

**Contexto**
Abstração de modelo de IA.

---

## Ferramentas / Integrações

### Tool

**PK**

* tool_id

**Contexto**
Contrato abstrato de integração (ex: OpenAPI).

---

### ToolConfig

**PK**

* tool_config_id

**FK**

* tool_id → Tool.tool_id
* tenant_id → Tenant.tenant_id

**Contexto**
Configuração concreta da tool por tenant.

---

### AgentVersionToolBinding

**PK**

* agent_version_tool_binding_id

**FK**

* agent_version_id → AgentVersion.agent_version_id
* tool_config_id → ToolConfig.tool_config_id

**Contexto**
Autorização explícita de uso de tool.

---

## RAG

### RagConfig

**PK**

* rag_config_id

**FK**

* tenant_id → Tenant.tenant_id
* vector_store_id → VectorStore.vector_store_id

**Contexto**
Configuração declarativa de recuperação.

---

### VectorStore

**PK**

* vector_store_id

**Contexto**
Backend vetorial.

---

## Execução (Runtime)

### FlowRun

**PK**

* flow_run_id

**FK**

* flow_version_id → FlowVersion.flow_version_id
* session_id → Session.session_id

**Contexto**
Execução concreta de um fluxo versionado.

---

### NodeRun

**PK**

* node_run_id

**FK**

* flow_run_id → FlowRun.flow_run_id
* node_id → Node.node_id

**Contexto**
Execução de um node específico.

---

### AgentRun

**PK**

* agent_run_id

**FK**

* node_run_id → NodeRun.node_run_id
* agent_version_id → AgentVersion.agent_version_id

**Contexto**
Execução concreta de um agente.

---

### GraphState

**PK**

* graph_state_id

**FK**

* flow_run_id → FlowRun.flow_run_id

**Contexto**
Estado consolidado e persistido da execução.

---

## Escalonamento

### EscalationPolicy

**PK**

* escalation_policy_id

**Contexto**
Regra declarativa de exceção.

---

### Escalation

**PK**

* escalation_id

**FK**

* flow_run_id → FlowRun.flow_run_id
* escalation_policy_id → EscalationPolicy.escalation_policy_id

**Contexto**
Evento de desvio controlado.

---

## Onboarding

### Onboarding

**PK**

* onboarding_id

**FK**

* tenant_id → Tenant.tenant_id

---

### OnboardingVersion

**PK**

* onboarding_version_id

**FK**

* onboarding_id → Onboarding.onboarding_id

---

### OnboardingRun

**PK**

* onboarding_run_id

**FK**

* onboarding_version_id → OnboardingVersion.onboarding_version_id

---

### OnboardingStep

**PK**

* onboarding_step_id

**FK**

* onboarding_version_id → OnboardingVersion.onboarding_version_id

---

### StepRun

**PK**

* step_run_id

**FK**

* onboarding_step_id → OnboardingStep.onboarding_step_id
* onboarding_run_id → OnboardingRun.onboarding_run_id

---

## Regra de Integridade Fundamental

Qualquer decisão que:

* afete execução,
* altere caminho,
* modifique resposta,

**precisa ter uma representação persistida e versionada**.

Sem isso, o sistema vira:

* imprevisível,
* impossível de auditar,
* impossível de escalar.

Esse modelo deixa claro:
**arquitetura aqui não está no código — está no banco.**
