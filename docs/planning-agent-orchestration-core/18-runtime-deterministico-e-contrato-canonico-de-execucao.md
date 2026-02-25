## Planning (18) — Runtime Determinístico e Contrato Canônico de Execução

### Objetivo

Definir **como o grafo é executado**, de forma:

* determinística
* previsível
* auditável
* desacoplada de vendor (OpenAI, LangGraph, etc.)

Após o P18, o runtime deixa de ser implícito e passa a ser **um produto com contrato**.

---

### Tese central

O runtime **não pensa**.
O runtime **não decide semântica**.
O runtime **apenas executa contratos**.

Toda inteligência está **dentro do node**.
Toda decisão estrutural está **no grafo**.

---

## 1. Fonte de verdade do runtime

* `flow_graph` é a **única fonte de verdade**
* routing legado é ignorado pelo runtime
* se não há grafo, o fluxo **não executa**

Regra simples:

> Sem grafo válido, não há execução.

---

## 2. Modelo mental do runtime

O runtime é uma **máquina de estados linear**, step-based:

1. Recebe um `ExecutionContext`
2. Executa exatamente **um node**
3. Avalia edges condicionais
4. Avança para o próximo node
5. Repete até `ResponseComposer` ou `FallbackNode`

Não existe paralelismo implícito.
Não existe branching concorrente.
Não existe execução fora do grafo.

---

## 3. ExecutionContext (contrato obrigatório)

Estrutura mínima:

* `tenant_id`
* `flow_id`
* `flow_version_id`
* `run_id`
* `current_node_id`
* `state` (imutável por step)
* `memory` (acumulativa)
* `metadata` (trace_id, timestamps, policies)

### Regras

* `state` nunca é mutado in-place
* cada node gera um **novo state**
* `memory` é append-only
* nenhum node acessa banco diretamente

---

## 4. Contrato canônico de Node

Todo node implementa obrigatoriamente:

* `node_type`
* `input_schema`
* `output_schema`
* `side_effect: bool`
* `deterministic: bool`

### Execução

Input do node:

* `state`
* `metadata`
* `policy`

Output do node (sempre estruturado):

* `status` (SUCCESS | ERROR | NEEDS_INPUT)
* `payload`
* `error` (se houver)
* `metrics` (latência, custo estimado)

Nunca retorna texto solto.
Nunca lança exceção não tratada.

Erro é dado, não fluxo de controle.

---

## 5. Tipos de execução

### Deterministic Node

* mesmo input → mesmo output
* ex: validação, roteamento, parsing

### Non-deterministic Node

* depende de LLM ou integração externa
* ex: IntentToolSelectionNode, ToolExecutionNode

O runtime **não diferencia comportamento**.
A diferença existe apenas para auditoria e replay.

---

## 6. Loop de execução (canônico)

Pseudofluxo lógico:

1. Resolver `current_node`
2. Validar input contra `input_schema`
3. Executar node
4. Persistir output + métricas
5. Avaliar edges do node
6. Selecionar **exatamente um** edge
7. Atualizar `current_node`
8. Repetir

Se:

* zero edges válidos → erro estrutural
* mais de um edge válido → erro estrutural

---

## 7. Avaliação de edges

Edges são avaliados **exclusivamente** com:

* output do node anterior
* expressões determinísticas
* DSL validada estaticamente

Edges:

* não acessam LLM
* não acessam contexto externo
* não executam código

Erro de avaliação encerra o fluxo.

---

## 8. Side-effects e isolamento

Regra de ouro:

> Apenas ToolExecutionNode pode gerar side-effect externo.

Runtime garante:

* timeout
* retry policy
* circuit breaker
* idempotência (quando aplicável)

Nodes sem side-effect:

* não fazem I/O
* não chamam APIs
* não persistem estado externo

---

## 9. Persistência e observabilidade

Para cada step:

* salvar input do node
* salvar output do node
* salvar edge escolhida
* salvar métricas

Isso habilita:

* replay
* auditoria
* billing
* debugging determinístico

---

## 10. Integração futura (explicitamente fora do escopo)

O runtime define **ports**, não implementações:

* LLMExecutorPort
* ToolExecutorPort
* GraphExecutorAdapter (LangGraph opcional)

LangGraph:

* pode executar o grafo
* não define o grafo
* não define contratos
* não decide fluxo

Se LangGraph sair, nada quebra.

---

## 11. O que o P18 exige mudar

### Código

* criar `RuntimeExecutor`
* criar `NodeExecutor`
* criar `EdgeEvaluator`
* remover lógica de fluxo espalhada

### Banco

* nenhuma mudança estrutural
* apenas uso consistente de `flow_graph`

### API

* nenhuma nova rota
* runtime consome graph já anexado

---

## 12. Resultado esperado

Ao final do P18:

* runtime previsível
* execução step-by-step auditável
* edges confiáveis
* nodes intercambiáveis
* base sólida para OpenAI, LangGraph, qualquer vendor

---

### Encerramento

O P17 define **o que é executado**.
O P18 define **como isso executa**.

Sem o 18, você tem configuração bonita e runtime frágil.
Com o 18, você tem uma plataforma.
