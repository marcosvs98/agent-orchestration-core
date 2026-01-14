Perfeito. O problema não é o **conteúdo** do P23 — é a **mistura de responsabilidades** entre:

* *plataforma de IA genérica*
* *executor controlado dentro de um runtime determinístico*

Vou ajustar **sem mudar sua tese**. Vou **cortar o que não pertence ao P23** e **reposicionar o restante**.

---

## Diagnóstico direto (sem rodeio)

Hoje o texto mistura **dois planos diferentes**:

1. **P23 correto (o que você quer agora)**
   → LLM como *executor encapsulado dentro do grafo*

2. **Um “Pxx futuro”**
   → Plataforma de capacidades de IA genérica (orquestrador, capabilities, etc.)

Isso gera ruído porque:

* fala em *AI Platform*, *capabilities*, *orchestrator*
* quando seu runtime **já é o orquestrador**

👉 **Correção:**
No P23 **não existe “orquestração de IA”**.
Existe **execução controlada de LLM como um node especial**.

---

## Versão AJUSTADA do P23 (clean, sem mistura)

### Planning (23) — LLM como Executor Determinístico de Node

### Objetivo real do P23

Introduzir LLMs no runtime **sem alterar**:

* determinismo do grafo
* avaliação de edges
* controle de execução
* modelo mental do sistema

P23 não cria uma plataforma de IA.**
Ele cria **um executor de LLM compatível com o runtime existente**.

---

## Tese central (mantida, agora mais rígida)

* O **grafo orquestra**
* As **políticas governam**
* A **LLM apenas executa**

A LLM é tratada como:

> “Uma função probabilística, cara e lenta, chamada sob contrato rígido.”

---

## Escopo correto do P23

### O que o P23 FAZ

* Define **como** um node pode chamar uma LLM
* Impõe **contrato de entrada e saída**
* Centraliza **custo, timeout e rastreabilidade**
* Garante **substituição de provider sem impacto no grafo**

### O que o P23 NÃO FAZ

* Não cria capabilities genéricas
* Não orquestra chamadas
* Não decide fluxo
* Não abstrai o runtime
* Não vira “AI Platform”

Tudo isso **fica fora**.

---

## Novo componente (único): `LLMExecutor`

Não existe:

* AI Orchestrator
* Capability Registry
* AI Core

Existe apenas **um executor especializado**, equivalente a um `ToolExecutor`, porém probabilístico.

---

## Papel do LLMExecutor

Responsabilidade única:

> Executar uma chamada LLM **como parte de um Node**, sob contrato e política.

Ele **não conhece**:

* edges
* estados globais
* grafo
* intenção de negócio

---

## Interface canônica (ajustada)

```python
execute_llm(
  task_type: LLMTaskType,
  input_payload: dict,
  input_schema: JSONSchema,
  output_schema: JSONSchema,
  policy: LLMPolicy,
  trace_context: TraceContext
) -> LLMResult
```

⚠️ **Modelo não vem direto**
O modelo é resolvido **pela policy**, não pelo node.

---

## Task Types (escopo fechado)

```text
INTENT_SELECTION
PARAM_EXTRACTION
CLARIFICATION
RESPONSE_RENDER
```

Se alguém quiser outro tipo → **novo plano**, não P23.

---

## Política (integração direta com P21)

`LLMPolicy` é resolvida pelo runtime, não pelo node.

Campos mínimos:

* model_alias
* max_tokens
* max_latency_ms
* max_cost_usd
* retry_limit
* fallback_model_alias

Se violar → **NodeFailed**, edge explícito.

Sem exceção.

---

## Contrato de schema (ponto inegociável)

Regra absoluta do P23:

> **LLM nunca retorna texto livre para o runtime.**

Sempre:

* JSON
* Validado
* Tipado

Se falhar:

* não “interpreta”
* não “tenta consertar”
* não “ajusta prompt”

Falha → erro de node.

---

## Exemplo correto — IntentToolSelectionNode

### Input enviado ao executor

```json
{
  "user_input": "Quero parcelar o IPVA",
  "available_tools": [
    {
      "tool_id": "parcelar_ipva",
      "schema": { "...": "..." }
    }
  ]
}
```

### Output esperado (schema validado)

```json
{
  "tool_id": "parcelar_ipva",
  "arguments": {
    "vehicle_plate": "ABC1234"
  },
  "confidence": 0.91
}
```

Nada além disso entra no runtime.

---

## Integração com OpenAPI (mantida, agora bem posicionada)

* OpenAPI **define tools**
* LLM **só faz slot filling**
* Executor **não executa tools**

Pipeline:

```
OpenAPI → Tool Schema
User Input → LLMExecutor
LLM Output → ToolExecutor
```

Separação limpa.

---

## Observabilidade (100% alinhado ao P22)

Cada chamada gera eventos **do runtime**, não “eventos de IA”.

Eventos canônicos:

* ExecutionEvent(type=LLM_CALL_STARTED)
* ExecutionEvent(type=LLM_CALL_COMPLETED)
* ExecutionEvent(type=LLM_CALL_FAILED)

Sempre com:

* trace_id
* flow_run_id
* node_id
* model_alias
* token_usage
* cost
* latency

---

## Erros e previsibilidade

Toda falha da LLM resulta em:

* NodeFailed
* edge explícito de erro
* execução previsível

Nunca:

* retry invisível
* fallback silencioso
* mudança de comportamento

---

## O que FOI REMOVIDO do P23 (correção importante)

Esses itens **não pertencem ao P23**:

* “Plataforma de IA”
* “Capabilities genéricas”
* “AI Orchestrator”
* “Conversation abstractions”
* “Memory / RAG”
* “Prompt engineering avançado”

Isso vira **P24+**, se fizer sentido.

---

## Resultado final do P23 (ajustado)

Ao final do P23:

* LLM é **apenas mais um executor**
* Grafo continua soberano
* Políticas continuam mandando
* OpenAI/LangGraph são detalhe
* Nenhum vazamento semântico para o runtime

---

## Frase final (agora correta)

> **P23 não integra IA ao sistema.
> Ele impede que a IA quebre o sistema.**

Se quiser, próximo passo natural é:

* desenhar o **LLMExecutor como Node interno**
* ou refatorar **um node real** usando esse contrato
* ou escrever o **JSON Schema padrão** por task_type
