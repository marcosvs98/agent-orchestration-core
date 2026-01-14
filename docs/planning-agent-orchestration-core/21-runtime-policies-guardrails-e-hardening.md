## Planning (21) — Runtime Policies, Guardrails e Hardening

### Objetivo

Garantir que **todo FlowRun execute dentro de limites explícitos, determinísticos e auditáveis**, definidos por tenant e flow.
O runtime deixa de ser “best effort” e passa a ser **fail-closed por política**.

IA executa. **Política governa.**

---

## Tese central

O runtime **nunca decide se pode rodar**.
Ele apenas **verifica políticas**, e:

* executa se **permitido**
* aborta com motivo tipado se **violado**

Sem exceções implícitas.
Sem “deixa passar”.

---

## Escopo do P21

Este plano **não altera semântica do grafo**.
Ele **envolve o runtime** com limites, contratos e interrupções previsíveis.

---

## 1. Modelo de Políticas de Execução

### 1.1 Nova entidade: `runtime_policy`

**Tabela nova** (obrigatória).

Campos mínimos:

* `runtime_policy_id` (PK)
* `tenant_id` (FK)
* `scope` (ENUM: TENANT | FLOW)
* `flow_id` (nullable, FK)
* `version` (int)
* `status` (DRAFT | ACTIVE)
* `policy_definition` (JSONB)
* `created_at`

### 1.2 Estrutura do `policy_definition`

```json
{
  "limits": {
    "max_nodes": 50,
    "max_depth": 20,
    "max_edges_per_node": 3,
    "max_total_duration_ms": 60000,
    "max_node_duration_ms": 15000
  },
  "execution": {
    "fail_on_multiple_true_edges": true,
    "fail_on_missing_graph": true,
    "allow_parallel_nodes": false
  },
  "tools": {
    "max_retries": 2,
    "circuit_breaker": {
      "failure_threshold": 5,
      "window_seconds": 60
    }
  }
}
```

Nada disso é hard-coded.

---

## 2. Resolução de Política (Policy Resolution)

### Ordem de precedência (obrigatória):

1. Policy **FLOW + ACTIVE**
2. Policy **TENANT + ACTIVE**
3. **DEFAULT SYSTEM POLICY** (imutável)

Se nenhuma policy ativa existir → **fail-closed**.

### Nova abstração:

`ResolvedRuntimePolicy`

Gerada **antes de qualquer execução**.

---

## 3. Pre-Flight Validation (antes do primeiro node)

### 3.1 Novo componente: `RuntimePolicyValidator`

Executado em `create_flow_run`.

Valida:

* FlowVersion está published + active
* Existe `flow_graph_snapshot`
* Grafo respeita:

  * max_nodes
  * max_depth
  * fan-out por node
* ExecutionPlan respeita policy
* Policy permite execução

Falha aqui:

* **NÃO inicia runtime**
* Cria FlowRun com status `FAILED`
* Emite evento `FlowFailed`

---

## 4. Enforcement durante execução

### 4.1 Enforcement por Node

Antes de executar um node:

* checar timeout restante do flow
* checar timeout do node
* checar max_steps

Se violar:

* interrompe execução
* marca FlowRun como FAILED
* motivo tipado

### 4.2 Enforcement de Edges

Durante avaliação de edges:

* se `fail_on_multiple_true_edges == true`
* e >1 edge retorna true
  → erro estrutural, aborta

### 4.3 Enforcement de Tool Execution

* aplica retry conforme policy
* aplica circuit breaker por `tool_id`
* circuit breaker é **stateful** (cache/redis ou db leve)

---

## 5. Motivos de Falha Tipados (obrigatório)

### Novo ENUM: `FlowFailureReason`

Valores iniciais:

* `POLICY_VIOLATION`
* `TIMEOUT`
* `STRUCTURAL_ERROR`
* `CIRCUIT_BREAKER_OPEN`
* `MISSING_GRAPH`
* `MAX_STEPS_EXCEEDED`

Nenhuma mensagem livre substitui isso.

---

## 6. Eventos de Observabilidade

Estender ExecutionEventType (sem quebrar compatibilidade):

Novos eventos:

* `PolicyResolved`
* `PolicyViolation`
* `FlowAbortedByPolicy`

Payload sempre inclui:

* `policy_version`
* `rule`
* `limit`
* `actual_value`

---

## 7. API / Admin

### 7.1 Endpoints novos

* `POST /runtime/policies`
* `POST /runtime/policies/{id}/activate`
* `GET /runtime/policies/resolve?tenant_id=&flow_id=`

### 7.2 Seeds de desenvolvimento

Criar:

* 1 policy default system (hardcoded + seed)
* 1 policy tenant dev permissiva
* 1 policy tenant restritiva (teste)

---

## 8. Refactors explícitos

### Adicionar

* `RuntimePolicyResolver`
* `RuntimePolicyValidator`
* `PolicyEnforcer`

### Refatorar

* `create_flow_run` → chamar resolver + validator
* Runtime loop → chamar enforcer a cada step

### Remover

* Qualquer if/else implícito de segurança no runtime
* Qualquer fallback silencioso

---

## 9. Critérios de aceite (Definition of Done)

* Nenhum flow executa sem policy resolvida
* Toda falha tem reason tipado
* Policy é auditável por versão
* Runtime previsível sob erro
* Nenhuma integração externa pode bypassar policy

---

## Resultado final do P21

O sistema passa a ter:

* **Governança real**
* **Fail-closed por contrato**
* **Execução previsível**
* **Base segura para OpenAI / LangGraph**

Depois do P21, integração externa é risco controlado — não aposta.
