## Planning (13) — Observabilidade, Auditoria e Billing

Objetivo: tornar o sistema **explicável, auditável e monetizável por construção**, não por batch posterior nem por inferência externa.

Se não é observável, **não é controlável**.
Se não é auditável, **não é confiável**.
Se não é mensurável, **não é cobravel**.

---

## Tese central (formalizada)

Tudo que:

* decide
* executa
* integra
* consome recurso

**gera evidência persistida**.

Evidência:

* não é log
* não é best-effort
* não é opcional

É **dado de primeira classe**, parte do domínio técnico.

---

## Unidade fundamental: Evento

Evento **não é log textual** e **não é métrica agregada**.

Evento é:

* estruturado
* versionado
* correlacionável
* append-only
* semanticamente explícito

Todo evento **obrigatoriamente** carrega:

* event_id
* event_type
* occurred_at (timestamp monotônico)
* tenant_id
* session_id (quando aplicável)
* flow_run_id
* correlation_id / causation_id
* payload tipado (schema versionado)

Sem isso, o evento é inválido.

---

## Tipos de eventos (taxonomia mínima)

### Execução de fluxo

* FlowStarted
* FlowRunning
* FlowWaiting
* FlowCompleted
* FlowFailed
* FlowEscalated

---

### Execução de nodes

* NodeEntered
* NodeSkipped
* NodeCompleted
* NodeFailed

---

### IA (AgentRun)

* AgentRunStarted
* AgentRunCompleted
* AgentRunFailed
* AgentRunRetried
* AgentRunAborted

Payload mínimo:

* agent_version_id
* ai_task
* model
* policy_version_id
* tokens_input
* tokens_output
* cost_estimated

---

### Ferramentas (ToolRun)

* ToolInvocationRequested
* ToolInvocationSucceeded
* ToolInvocationFailed
* ToolInvocationTimedOut
* ToolInvocationRetried

Payload mínimo:

* tool_config_version_id
* executor_type
* latency_ms
* request_size
* response_size
* error_class (quando falha)

---

### Governança e controle

* PolicyEvaluated
* PolicyDenied
* PolicyViolated
* EscalationTriggered
* ManualInterventionRequested

Governança **sempre gera evento**, inclusive quando bloqueia.

---

## Auditoria — Obrigação estrutural

Auditoria **não é relatório**.
Auditoria é **capacidade do sistema**.

Ela responde, sem interpretação humana:

* por que esta decisão ocorreu?
* qual regra/policy foi aplicada?
* qual versão exata do flow/agent/prompt/policy?
* qual input levou a este output?
* quem (tenant) foi impactado?

---

### Requisitos não negociáveis

* FlowVersion, AgentVersion, PolicyVersion são **imutáveis**
* Runs referenciam versões **por ID**, nunca por “latest”
* Prompts, policies e schemas são versionados
* Execuções são **replayáveis de forma controlada**

Sem isso, auditoria é ficção jurídica.

---

## Observabilidade operacional (runtime health)

Observabilidade **não depende de APM externo** para existir.
APM apenas consome o que o core produz.

---

### Métricas primárias deriváveis de eventos

* latência por FlowRun
* latência por NodeRun
* latência por AgentRun
* taxa de erro por Tool
* taxa de retry / fallback
* custo médio por execução
* custo por modelo
* custo por tenant

Agregáveis por:

* tenant
* flow
* agent
* versão
* modelo
* período

---

## Tracing determinístico

FlowRun é o **trace root**.

Hierarquia obrigatória:

FlowRun
→ NodeRun (span)
→ AgentRun (span)
→ ToolRun (span)

Benefícios:

* visão ponta-a-ponta real
* comparação entre versões
* debug causal, não narrativo

Se não há correlação, não há trace.

---

## Billing — Financeiramente correto por design

Billing **não é aproximação** nem “estimativa offline”.

Cada execução gera custo rastreável.

---

### Fontes de custo explícitas

IA:

* tokens de entrada
* tokens de saída
* modelo utilizado
* política aplicada

Ferramentas:

* número de chamadas
* latência
* payload size
* sucesso / falha

Infra:

* armazenamento (eventos, vetores)
* execuções de FlowRun

---

### Registro mínimo por execução

Cada AgentRun:

* model
* tokens_input
* tokens_output
* cost_estimated
* policy_version_id

Cada ToolRun:

* tool_config_version_id
* endpoint lógico
* latency
* sucesso / falha
* retries

Sem esses campos, cobrança não é defensável.

---

## Política de cobrança (governável)

Billing é **policy-driven**, nunca hard-coded.

Possibilidades:

* por execução
* por volume
* por custo real
* por SLA
* por pacote híbrido

Policy:

* versionada
* auditável
* aplicada no runtime
* registrada em evento

---

## Alertas — Reação, não polling

Alertas são **derivados de eventos**, não de cron.

Disparos típicos:

* custo acima do budget
* erro recorrente
* degradação de latência
* violações de policy
* comportamento anômalo por tenant

Sem evento, não há alerta.

---

## Retenção e compliance (implícito)

Eventos:

* append-only
* com política de retenção
* com trilha de exclusão lógica (LGPD-safe)

Auditoria exige:

* retenção mínima garantida
* versionamento preservado
* impossibilidade de mutação retroativa

---

## Anti-patterns proibidos (reforçados)

* log textual como fonte de verdade
* métricas sem correlação
* custo calculado fora do runtime
* “não sabemos por que aconteceu”
* billing baseado em média global
* versões implícitas

Quebrou isso → sistema não é auditável.

---

## Fechamento executivo

Planning (13) **não é sobre dashboards**.
É sobre **responsabilidade técnica e financeira**.

Se o sistema:

* decide
* executa
* cobra
