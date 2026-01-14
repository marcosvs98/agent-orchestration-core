## Planning (25) — Runtime Guardrails, Quotas e Enforcement Determinístico

### Objetivo

Introduzir **enforcement real de limites operacionais** no runtime, garantindo que:

* custo
* uso
* frequência
* latência
* volume semântico

sejam **controlados de forma determinística**, antes, durante e após a execução.

Sem P25, políticas existem, observabilidade existe, LLM existe —
mas **nada impede o sistema de se autodestruir sob carga ou abuso**.

---

### Tese central

Política que só observa **não é política**.
Política que só alerta **chega tarde**.

No P25:

> **Toda execução é permitida, degradada ou bloqueada explicitamente.**

Nada passa “porque sim”.

---

## Escopo do P25

O P25 cobre **enforcement**, não definição de política (P21) nem execução de LLM (P23).

Ele atua como **última linha de defesa síncrona** do runtime.

---

## Novos Conceitos Introduzidos

### 1. Runtime Guardrail Engine

Componente responsável por **avaliar e aplicar limites** em tempo real.

Ele atua em três momentos:

1. **Pre-execution** (fail-fast)
2. **Mid-execution** (short-circuit / degrade)
3. **Post-execution** (accounting + lock)

Nenhum node, tool ou LLM ignora esse engine.

---

### 2. Tipos de Guardrail

#### 2.1 Cost Guardrail

Limita custo monetário acumulado.

Exemplos:

* custo máximo por flow_run
* custo máximo por tenant / janela
* custo máximo por capability (LLM, embedding, tool)

Ação possível:

* BLOCK
* DEGRADE (trocar modelo)
* ALLOW

---

#### 2.2 Rate / Frequency Guardrail

Limita chamadas por tempo.

Exemplos:

* X execuções por minuto por tenant
* Y chamadas LLM por sessão
* Z tool executions por flow_run

Implementação:

* chave composta (tenant_id, capability, window)
* contadores atômicos (Redis)

---

#### 2.3 Latency Guardrail

Controla execução lenta.

Exemplos:

* LLM > 4s → abort
* tool > timeout → circuit break

Ação:

* abortar node
* seguir edge de erro
* registrar evento canônico

---

#### 2.4 Semantic Volume Guardrail

Controla **tamanho semântico**, não só tokens.

Exemplos:

* input muito longo
* número excessivo de tools candidatas
* schemas grandes demais

Isso protege prompt explosion e custo indireto.

---

## Integração com o Runtime

### Ponto de Hook (obrigatório)

Todo executor chama:

```
guardrail.check_and_reserve(context) -> GuardrailDecision
```

Antes de executar qualquer coisa externa.

---

### Estrutura da decisão

```
GuardrailDecision {
  decision: ALLOW | DEGRADE | BLOCK
  reason_code
  applied_limits
  overrides (ex: model downgrade)
}
```

Nenhuma decisão implícita.

---

## Integração com P23 (LLM)

Exemplo de fluxo:

1. Node solicita LLMExecutor
2. Guardrail avalia:

   * custo estimado
   * tokens esperados
   * rate
3. Se:

   * ALLOW → segue
   * DEGRADE → troca model_id lógico
   * BLOCK → NodeFailed + edge explícito

LLM nunca decide nada aqui.

---

## Integração com P22 (Observabilidade)

Toda decisão gera evento:

* GuardrailChecked
* GuardrailBlocked
* GuardrailDegraded

Payload mínimo:

* trace_id
* flow_run_id
* node_id
* guardrail_type
* limit
* current_value
* decision

Auditoria e troubleshooting ficam triviais.

---

## Persistência e Estado

### Onde vive o estado

* **Redis**: contadores, janelas, locks (tempo real)
* **Postgres**: eventos, histórico, auditoria

Nada crítico vive só em memória.

---

## O que muda no código

### Novos componentes

* GuardrailEngine
* CostEstimator (plugável)
* RateLimiterAdapter
* GuardrailPolicyResolver (usa P21)

---

### Alterações em componentes existentes

* Runtime Executor:

  * passa por guardrail antes de executar node
* LLMExecutor:

  * não chama provider sem decisão explícita
* ToolExecutionNode:

  * respeita circuit breaker + guardrail

---

## O que NÃO entra no P25

* UI de gestão de quotas
* auto-scaling inteligente
* billing externo
* predição de custo por ML

Isso vem depois.

---

## Exemplo Concreto

Cenário:

* tenant A
* limite diário: USD 5.00
* flow_run já gastou USD 4.92
* próxima chamada LLM estimada: USD 0.15

Resultado:

```
decision = BLOCK
reason = COST_LIMIT_EXCEEDED
```

Runtime:

* NodeFailed
* Edge de erro seguido
* Nenhuma chamada externa feita
* Evento auditável registrado

Zero surpresa.

---

## Resultado Esperado do P25

Ao final do P25, o sistema terá:

* Enforcement real de políticas
* Controle de custo previsível
* Proteção contra abuso e runaway
* Degradação controlada
* Runtime seguro para escalar

---

## Por que o P25 é o próximo passo lógico

Você já tem:

* Grafo determinístico (P17–P19)
* Execução observável (P20–P22)
* IA controlada (P23)
* Modelos e custo governados (P24)

Sem P25, tudo isso é **frágil em produção**.

Com P25:

> **O runtime deixa de ser apenas correto
> e passa a ser seguro.**
