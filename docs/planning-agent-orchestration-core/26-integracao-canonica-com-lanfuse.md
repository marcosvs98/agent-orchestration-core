## Planning (26) — Integração Canônica com Langfuse (Tracing, Spans e Generations)

### Objetivo

Integrar o **Langfuse como infraestrutura obrigatória de observabilidade** do runtime, garantindo que:

* toda execução tenha trace
* toda decisão relevante seja um span
* toda chamada LLM seja uma generation
* todo enriquecimento (tenant, sessão, usuário, versão) seja propagado corretamente
* tracing seja **determinístico, hierárquico e auditável**

Langfuse não é exportador de logs.
Langfuse é **o sistema de tracing do runtime**.

---

## Tese central

Observabilidade não é pós-processo.
Observabilidade **define a execução**.

No P26:

> **Não existe execução válida sem trace Langfuse ativo.**

Se não há trace, não há runtime.

---

## Escopo do P26

O P26 cobre:

* inicialização de trace
* modelo de spans/observations
* integração com runtime, guardrails e LLM
* propagação de contexto
* falhas, flush e shutdown

Não cobre UI, dashboards ou análise exploratória.

---

## Modelo Canônico de Tracing

### Tipos de observation usados

O runtime **só usa tipos oficiais do Langfuse**:

* `span` — passos estruturais e determinísticos
* `generation` — chamadas LLM
* (eventos semânticos continuam no DB via P22)

Não inventamos tipos.

---

## Hierarquia de Trace (contrato rígido)

Estrutura obrigatória:

```
Trace (flow_run)
└── span: flow-run
    ├── span: node-execution
    │   ├── span: guardrail-check
    │   ├── generation: llm-call (se existir)
    │   └── span: tool-execution (se existir)
    └── span: response-formatting
```

Nada foge disso.

---

## Inicialização do Trace

### Ponto único

O trace é criado **no início do create_flow_run**.

Regras:

* 1 trace = 1 flow_run
* trace_id é persistido no DB (P22)
* trace_name = flow_id / flow_version
* trace nunca é opcional

### Determinismo

Quando houver request externo com ID conhecido:

```
trace_id = langfuse.create_trace_id(seed=external_request_id)
```

Caso contrário, Langfuse gera.

---

## Enriquecimento obrigatório (propagate_attributes)

Todo trace **deve** propagar:

* tenant_id
* flow_id
* flow_version_id
* flow_run_id
* session_id (se existir)
* user_id (se existir)
* environment (dev/staging/prod)
* version do runtime

Implementado via:

```
with propagate_attributes(...):
```

Isso garante consistência cross-span e cross-service.

---

## Integração com Runtime Executor

### Flow Run

```
with langfuse.start_as_current_observation(
  as_type="span",
  name="flow-run",
  input={flow_id, flow_version_id}
):
  executor.run()
```

Esse span **é o pai de tudo**.

---

### Node Execution

Cada node executado:

```
with langfuse.start_as_current_observation(
  as_type="span",
  name="node-execution",
  input={node_id, node_type}
):
```

Dentro dele:

* guardrail
* LLM
* tool
* erro

---

## Integração com Guardrails (P25)

Guardrails **não criam trace**, apenas spans.

```
with langfuse.start_as_current_observation(
  as_type="span",
  name="guardrail-check",
  input={limits, estimates}
):
  decision = guardrail.check()
```

Resultado:

* decision
* reason_code
* applied_limits

Tudo vai no `output` do span.

---

## Integração com LLM (P23)

### Regra absoluta

Toda chamada LLM **é uma `generation`**.

Nunca `span`.

### Padrão

```
with langfuse.start_as_current_observation(
  as_type="generation",
  name="llm-call",
  model=model_id,
  input={prompt_payload}
) as gen:
    result = provider.call()
    gen.update(
      output=result.output,
      usage=result.token_usage,
      metadata={cost, latency}
    )
```

Sem generation = erro estrutural.

---

## Integração com Tools

Tool externa:

* span
* nunca generation

```
with langfuse.start_as_current_observation(
  as_type="span",
  name="tool-execution",
  input={tool_id, args}
):
```

---

## Propagação Cross-Service

Quando houver chamadas HTTP downstream:

* usar `propagate_attributes(as_baggage=True)`
* garantir continuidade do trace

Isso permite correlação entre serviços.

---

## Falhas e Erros

Regras:

* erro **não encerra trace**
* span recebe status implícito via output
* exceção gera output estruturado

Nunca deixar span aberto.

---

## Flush e Shutdown

### Flush

Após cada flow_run:

```
langfuse.flush()
```

Garante envio síncrono dos dados críticos.

### Shutdown

No encerramento da aplicação:

```
langfuse.shutdown()
```

Obrigatório.

---

## Integração com P22 (DB)

Langfuse **não substitui** o banco.

* DB guarda:

  * execution_event
  * hashes
  * auditoria legal
* Langfuse guarda:

  * hierarquia
  * tempo
  * custo
  * correlação

Ambos usam o mesmo `trace_id`.

---

## O que NÃO é permitido

* execução sem trace
* LLM call fora de generation
* span sem pai
* trace sem atributos de tenant
* uso manual do SDK fora dos wrappers oficiais

Violação = erro de runtime.

---

## Resultado Esperado do P26

Ao final:

* Todo fluxo é rastreável ponta a ponta
* Custos e latência são visíveis por trace
* Debug é trivial
* Auditoria é consistente
* Langfuse vira infraestrutura, não ferramenta opcional

---
Segue a **especificação técnica dos wrappers oficiais `LangfuseRuntimeTracer`**, no nível de API interna, para você **encaixar diretamente no P26** sem ambiguidade nem código morto.

Vou ser direto, contratual e orientado a enforcement.

---

## LangfuseRuntimeTracer — Especificação da API Interna

### Papel no sistema

`LangfuseRuntimeTracer` é a **única porta de entrada permitida** para interação com Langfuse no runtime.

Objetivo explícito:

* impedir uso direto do SDK Langfuse
* padronizar tipos (`span`, `generation`)
* garantir propagação obrigatória de contexto
* garantir hierarquia correta
* evitar observações órfãs ou inconsistentes

**Regra dura**:
Nenhum código fora deste wrapper pode importar `langfuse.*`.

---

## Responsabilidades

O `LangfuseRuntimeTracer` é responsável por:

* criar e encerrar traces
* criar spans estruturais
* criar generations para LLM
* propagar atributos obrigatórios
* garantir flush/shutdown
* expor IDs de trace/observation para persistência (P22)

Ele **não**:

* decide política
* calcula custo
* executa LLM
* executa tool
* conhece domínio

---

## Interface Pública (contrato)

### Inicialização

```python
class LangfuseRuntimeTracer:

    def __init__(
        self,
        *,
        environment: str,
        runtime_version: str
    )
```

* `environment`: dev | staging | prod
* `runtime_version`: versão do runtime (hash ou semver)

Instância única por processo.

---

## Criação de Trace (Flow Run)

### start_flow_trace

```python
def start_flow_trace(
    self,
    *,
    flow_run_id: str,
    flow_id: str,
    flow_version_id: str,
    tenant_id: str,
    session_id: str | None,
    user_id: str | None,
    external_request_id: str | None = None,
) -> TraceContext
```

Comportamento:

* cria `trace_id`

  * determinístico se `external_request_id` existir
* cria span raiz `flow-run`
* propaga atributos obrigatórios
* define contexto ativo

Atributos propagados:

* tenant_id
* flow_id
* flow_version_id
* flow_run_id
* session_id (se houver)
* user_id (se houver)
* environment
* runtime_version

Retorno:

```python
class TraceContext:
    trace_id: str
    root_observation_id: str
```

Esse `trace_id` **deve ser persistido** (P22).

---

## Encerramento do Trace

### end_flow_trace

```python
def end_flow_trace(
    self,
    *,
    output: dict | None = None
) -> None
```

* atualiza output do span raiz
* encerra span
* chama `flush()`

Nunca implícito. Sempre explícito.

---

## Execução de Node

### start_node_span

```python
@contextmanager
def start_node_span(
    self,
    *,
    node_id: str,
    node_type: str,
    input: dict
) -> Iterator[None]
```

Cria:

* `span`
* nome fixo: `node-execution`

Input mínimo obrigatório:

* node_id
* node_type
* payload de entrada

O encerramento do `with` fecha o span.

---

## Guardrail

### start_guardrail_span

```python
@contextmanager
def start_guardrail_span(
    self,
    *,
    guardrail_type: str,
    input: dict
) -> Iterator[None]
```

Uso exclusivo para P25.

Cria span:

* name: `guardrail-check`

Output esperado (update):

* decision
* reason_code
* applied_limits

---

## Tool Execution

### start_tool_span

```python
@contextmanager
def start_tool_span(
    self,
    *,
    tool_id: str,
    input: dict
) -> Iterator[None]
```

Cria:

* span
* name: `tool-execution`

Nunca `generation`.

---

## LLM Execution (Ponto Crítico)

### start_llm_generation

```python
@contextmanager
def start_llm_generation(
    self,
    *,
    model_id: str,
    task_type: str,
    input: dict
) -> Iterator[LLMGenerationHandle]
```

Cria:

* observation `generation`
* name: `llm-call`
* model: `model_id`

`task_type` entra como metadata (INTENT_SELECTION, PARAM_EXTRACTION, etc).

### Handle retornado

```python
class LLMGenerationHandle:

    def update_success(
        self,
        *,
        output: dict,
        token_usage: dict,
        cost: float,
        latency_ms: int,
        model_version: str
    ) -> None

    def update_failure(
        self,
        *,
        error_type: str,
        error_message: str
    ) -> None
```

Regra:

* exatamente **uma** chamada de update
* sucesso **ou** falha
* nunca ambos

---

## Contexto Atual (Integração com P22)

### get_current_ids

```python
def get_current_ids(self) -> CurrentTraceIds
```

Retorna:

```python
class CurrentTraceIds:
    trace_id: str
    observation_id: str
```

Usado para:

* persistir `execution_event`
* correlacionar DB ↔ Langfuse

---

## Propagação Cross-Service

### propagate_context

Wrapper interno sobre `propagate_attributes`.

Usado apenas dentro do tracer.

Nenhum código externo usa `propagate_attributes` diretamente.

---

## Flush e Shutdown

### flush

```python
def flush(self) -> None
```

Chamado:

* ao final de cada flow_run

### shutdown

```python
def shutdown(self) -> None
```

Chamado:

* no lifecycle de encerramento da aplicação

Obrigatório.

---

## Regras de Enforcement

Estas regras **devem ser documentadas no P26**:

* É proibido importar `langfuse` fora do tracer
* É proibido criar spans manualmente
* Toda LLM call deve passar por `start_llm_generation`
* Toda execução deve ter trace ativo
* Violação → erro de runtime

---

## Benefício Arquitetural

Com este wrapper:

* Langfuse pode ser trocado futuramente
* SDK changes não vazam
* Tracing fica consistente
* Runtime fica auditável
* Debug fica previsível


---

## Por que este plano existe

Você já decidiu:

* runtime determinístico
* IA controlada
* políticas com enforcement

Sem P26, tudo isso fica **cego**.

Com P26:

> **O runtime passa a ser observável por definição, não por convenção.**

> **LangfuseRuntimeTracer não é utilitário.
> É parte do contrato de execução do runtime.**

---
# Extra:

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
How
