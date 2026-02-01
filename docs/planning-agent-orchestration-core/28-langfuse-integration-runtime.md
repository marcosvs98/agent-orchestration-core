## Planning (28b) — Langfuse Integration Runtime (Detalhado)

### Objetivo

Permitir rastreabilidade e observabilidade completas em runtime:

* Hierarquia de spans para **flows → nodes → LLM/tools → guardrails**
* Propagação de contexto (`trace_id`, `flow_run_id`, `node_id`, `tenant_id`, `user_id`)
* Registro de **input/output, token usage, prompt_version e frozen_hash**
* Suporte a todos os tipos de observação disponíveis na API oficial Langfuse
* Flush e shutdown confiáveis, sem perda de dados

---

### Tipos de observação e modos de uso

| Tipo             | Uso principal                                   | Hierarquia / Propagação                               | Detalhes adicionais                                                                 |
| ---------------- | ----------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `span`           | Flows, Nodes, Guardrails, Tools genéricos       | Cada `span` é filho do `flow_span` ou de outro `span` | Pode usar `propagate_attributes` para meta info (tenant, user, session)             |
| `generation`     | Chamadas LLM (P23)                              | Filho do node span correspondente                     | Registra input/output, tokens, custo, modelo, prompt_version, frozen_hash           |
| `tool`           | Execução de ferramentas externas                | Filho do node span ou flow span                       | Input/output da tool, tempo de execução, status                                     |
| `guardrail`      | Avaliação de limites (P25)                      | Filho do node span                                    | Tipo de guardrail (cost, rate, latency, semantic volume), decision, limite aplicado |
| `span + baggage` | Propagação entre requests HTTP ou microservices | Ativa contextos remotos mantendo trace_id             | Usa `as_baggage=True` para atributos que precisam atravessar serviços               |

**Princípios técnicos:**

* **Hierarquia determinística:** todo flow gera `flow_span`, cada node é filho do `flow_span`. Guardrails, tools e LLMs são filhos do node correspondente.
* **Propagação de contexto:** `propagate_attributes` garante que tenant_id, session_id e user_id estejam disponíveis em todos os spans filhos.
* **Observações manuais vs. ativas:** spans podem ser “manuais” (não alteram contexto ativo) ou “ativas” (substituem o contexto atual para operações subsequentes).

---

### Fluxo de uso recomendado

1. **Início do Flow**

```python
trace = tracer.start_flow_trace(
    flow_run_id=UUID(...),
    flow_id=UUID(...),
    tenant_id=UUID(...),
    session_id=UUID(...),
    user_id=UUID(...)
)
with tracer.start_flow_span(trace=trace):
    ...
```

2. **Node Execution**

```python
with tracer.start_node_span(node_id="IntentNode", node_type="IntentToolSelection", input=node_input):
    ...
```

3. **LLM Generation**

```python
with tracer.start_llm_generation(
    model_id="gpt-4o-mini",
    task_type="INTENT_SELECTION",
    input=node_input,
    prompt_version=1,
    prompt_frozen_hash="abc123",
    node_type="IntentToolSelection"
) as handle:
    handle.update_success(
        output=llm_output,
        token_usage={"input": 10, "output": 20, "total": 30},
        cost=0.002,
        latency_ms=45,
        model_version="1.0"
    )
```

4. **Tool Execution**

```python
with tracer.start_tool_span(tool_id="calculate-tax", input=tool_input):
    # tool logic
```

5. **Guardrail Decision**

```python
with tracer.start_guardrail_span(guardrail_type="COST", input={"estimated_cost": 0.05}):
    # guardrail evaluates -> ALLOW / BLOCK / DEGRADE
```

---

### Propagação avançada de atributos

* **Tenant / User / Session:** propagado via `propagate_attributes`, disponível em todos os spans filhos.
* **Trace / Parent Span:** cada span filho automaticamente herda `trace_id` e `parent_span_id`.
* **Metadata adicional:** experiment, version, prompt_frozen_hash, model_version, cost estimado.

Exemplo:

```python
with propagate_attributes(user_id="user_123", session_id="sess_abc", as_baggage=True):
    with tracer.start_node_span(node_id="Node1", node_type="ClarificationNode", input=input_data):
        ...
```

---

### Flush e Shutdown

* `flush()` envia todos os eventos pendentes para Langfuse. Deve ser chamado ao final de cada flow ou antes de shutdown.
* `shutdown()` encerra clientes SDK e garante que nenhum evento se perca.

---

### Estado esperado no Langfuse

Para cada flow executado:

* `flow_span` único → raiz da execução
* Nodes → filhos de `flow_span`
* LLM spans → filhos do node correspondente, contendo input/output, tokens, prompt metadata
* Tool spans → filhos do node ou flow, contendo execução detalhada da tool
* Guardrail spans → filhos do node, registrando decisão e limites aplicados

**Propagação determinística:** qualquer trace_id externo ou span pai garante consistência em ambientes distribuídos.

---

### Resultado esperado

* Observabilidade completa de flows, nodes, LLM, tools e guardrails
* Auditoria com input/output, token usage, custo, prompt_version e frozen_hash
* Propagação de contexto determinística e auditável entre todas as operações
* Preparação para P26 — Admin Control Plane e Prompt Management

---
# Extra content

Observation Types
Langfuse supports different observation types to provide more context to your spans and allow efficient filtering.
Available Types
 event is the basic building block. An event is used to track discrete events in a trace.
 span represents durations of units of work in a trace.
 generation logs generations of AI models incl. prompts, token usage and costs.
 agent decides on the application flow and can for example use tools with the guidance of a LLM.
 tool represents a tool call, for example to a weather API.
 chain is a link between different application steps, like passing context from a retriever to a LLM call.
 retriever represents data retrieval steps, such as a call to a vector store or a database.
 evaluator represents functions that assess relevance/correctness/helpfulness of a LLM’s outputs.
 embedding is a call to a LLM to generate embeddings and can include model, token usage and costs
 guardrail is a component that protects against malicious content or jailbreaks.

---

start_as_current_observation() is the primary way to create observations while ensuring the active OpenTelemetry context is updated. Any child observations created inside the with block inherit the parent automatically.
Observations can have different types by setting the as_type parameter.
from langfuse import get_client, propagate_attributes

langfuse = get_client()

with langfuse.start_as_current_observation(
    as_type="span",
    name="user-request-pipeline",
    input={"user_query": "Tell me a joke"},
) as root_span:
    with propagate_attributes(user_id="user_123", session_id="session_abc"):
        with langfuse.start_as_current_observation(
            as_type="generation",
            name="joke-generation",
            model="gpt-4o",
        ) as generation:
            generation.update(output="Why did the span cross the road?")

    root_span.update(output={"final_joke": "..."})

---
from langfuse import get_client

langfuse = get_client()

# This outer span establishes an active context.
with langfuse.start_as_current_observation(as_type="span", name="main-operation") as main_operation_span:
    # 'main_operation_span' is the current active context.

    # 1. Create a "manual" span using langfuse.start_observation().
    #    - It becomes a child of 'main_operation_span'.
    #    - Crucially, 'main_operation_span' REMAINS the active context.
    #    - 'manual_side_task' does NOT become the active context.
    manual_side_task = langfuse.start_observation(name="manual-side-task")
    manual_side_task.update(input="Data for side task")

    # 2. Start another operation that DOES become the active context.
    #    This will be a child of 'main_operation_span', NOT 'manual_side_task',
    #    because 'manual_side_task' did not alter the active context.
    with langfuse.start_as_current_observation(as_type="span", name="core-step-within-main") as core_step_span:
        # 'core_step_span' is now the active context.
        # 'manual_side_task' is still open but not active in the global context.
        core_step_span.update(input="Data for core step")
        # ... perform core step logic ...
        core_step_span.update(output="Core step finished")
    # 'core_step_span' ends. 'main_operation_span' is the active context again.

    # 3. Complete and end the manual side task.
    # This could happen at any point after its creation, even after 'core_step_span'.
    manual_side_task.update(output="Side task completed")
    manual_side_task.end() # Manual end is crucial for 'manual_side_task'

    main_operation_span.update(output="Main operation finished")
# 'main_operation_span' ends automatically here.

# Expected trace structure in Langfuse:
# - main-operation
#   |- manual-side-task
#   |- core-step-within-main
#     (Note: 'core-step-within-main' is a sibling to 'manual-side-task', both children of 'main-operation')
---


from langfuse import get_client, propagate_attributes

langfuse = get_client()

with langfuse.start_as_current_observation(as_type="span", name="user-workflow"):
    with propagate_attributes(
        user_id="user_123",
        session_id="session_abc",
        metadata={"experiment": "variant_a"},
        version="1.0",
        trace_name="user-workflow",
    ):
        with langfuse.start_as_current_observation(as_type="generation", name="llm-call"):
            pass

---

from langfuse import get_client, propagate_attributes
import requests

langfuse = get_client()

with langfuse.start_as_current_observation(as_type="span", name="api-request"):
    with propagate_attributes(
        user_id="user_123",
        session_id="session_abc",
        as_baggage=True,
    ):
        requests.get("https://service-b.example.com/api")

---

from langfuse import get_client

langfuse = get_client()

# Using the context manager
with langfuse.start_as_current_observation(
    as_type="span",
    name="user-request",
    input={"query": "What is the capital of France?"}  # This becomes the trace input
) as root_span:

    with langfuse.start_as_current_observation(
        as_type="generation",
        name="llm-call",
        model="gpt-4o",
        input={"messages": [{"role": "user", "content": "What is the capital of France?"}]}
    ) as gen:
        response = "Paris is the capital of France."
        gen.update(output=response)
        # LLM generation input/output are separate from trace input/output

    root_span.update(output={"answer": "Paris"})  # This becomes the trace output

---

from langfuse import get_client, Langfuse
langfuse = get_client()

external_request_id = "req_12345"
deterministic_trace_id = langfuse.create_trace_id(seed=external_request_id)

---
from langfuse import get_client, Langfuse
langfuse = get_client()

with langfuse.start_as_current_observation(as_type="span", name="my-op") as current_op:
    trace_id = langfuse.get_current_trace_id()
    observation_id = langfuse.get_current_observation_id()
    print(trace_id, observation_id)

---

from langfuse import get_client

langfuse = get_client()

existing_trace_id = "abcdef1234567890abcdef1234567890"
existing_parent_span_id = "fedcba0987654321"

with langfuse.start_as_current_observation(
    as_type="span",
    name="process-downstream-task",
    trace_context={
        "trace_id": existing_trace_id,
        "parent_span_id": existing_parent_span_id,
    },
):
    pass

---
from langfuse import get_client

langfuse = get_client()
# ... create traces and observations ...
langfuse.flush() # Ensures all pending data is sent

---

from langfuse import get_client

langfuse = get_client()
# ... application logic ...

# Before exiting:
langfuse.shutdown()

--

Depois de aprender, crie um plano para integração completo respeitando os types disponíveis e o enriquecimento propagado
