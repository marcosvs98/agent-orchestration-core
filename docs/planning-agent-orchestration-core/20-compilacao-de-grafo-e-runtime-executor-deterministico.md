## Planning (20) — Compilação de Grafo e Runtime Executor Determinístico

Objetivo: **transformar o grafo publicado e ativo em um plano de execução determinístico, previsível e reexecutável**, onde o runtime não interpreta intenção, não decide semântica e não contém lógica de negócio.

Se o runtime “pensa”, a arquitetura quebrou.

---

### Tese central

O runtime **executa instruções já decididas**.

Toda inteligência, heurística ou semântica:

* acontece **dentro do node**
* ou antes, no authoring

O runtime:

* resolve ordem
* avalia condições booleanas
* mantém estado
* emite eventos

Nada além disso.

---

## Escopo do P20

Este plano define:

* como um `flow_graph_snapshot` vira um artefato executável
* como o runtime percorre o grafo
* como estados, outputs e erros são tratados
* como garantir determinismo e replay

Não define:

* prompt engineering
* escolha de modelo
* UX de authoring
* otimizações de custo

---

## 1. Graph Compiler

### Responsabilidade

Converter um `flow_graph_snapshot` (estrutura declarativa) em um **ExecutionPlan imutável**.

O compiler é **puro**:

* input → output
* sem IO
* sem estado global

---

### Input do compiler

* `flow_graph_snapshot`

  * nodes (id, type, config)
  * edges (from, to, condition_expression)
* `policy_snapshot`

  * limites de execução
  * regras estruturais
* `schema_version`

---

### Output do compiler

`ExecutionPlan` (imutável):

* ordered_nodes (lista indexada)
* adjacency_map (node_id → [edges])
* start_node_id
* terminal_nodes (Response / Fallback)
* compiled_conditions (AST / bytecode)
* structural_hash (para cache)

Esse artefato:

* pode ser serializado
* pode ser cacheado em memória
* pode ser versionado

---

### Validações obrigatórias

Falha no compile **bloqueia execução**.

1. **Estrutura**

   * 1 e apenas 1 StartNode
   * ≥1 terminal node
   * todos os nodes alcançáveis

2. **Edges**

   * toda edge tem condição
   * condição é parseável pela DSL
   * nenhuma edge semântica (texto livre)

3. **Ambiguidade**

   * duas ou mais edges potencialmente verdadeiras
   * edge sem condição default explícita
   * ordem implícita não permitida

4. **Ciclos**

   * ciclos só se declarados
   * ciclos exigem limite de iteração

---

## 2. Runtime Executor

### Papel do runtime

Executar **um node por vez**, avaliando edges de forma determinística.

Runtime não:

* reordena nodes
* executa em paralelo
* tenta “escolher o melhor caminho”

---

### Estado mínimo do runtime

`ExecutionContext`:

* flow_run_id
* current_node_id
* node_output
* execution_state
* iteration_counters
* timestamps

Estado é:

* serializável
* persistido entre steps
* reexecutável

---

### Loop de execução

1. Carrega `ExecutionPlan`
2. Posiciona no StartNode
3. Executa NodeExecutor
4. Persiste output + evento
5. Avalia edges
6. Resolve próximo node
7. Repete até terminal

Sem exceções implícitas.

---

## 3. Node Executor Contract

Todo node implementa o mesmo contrato.

Input:

* execution_context
* node_config

Output:

* payload (estruturado)
* status (SUCCESS | FAILURE | WAITING)
* metadata

Node não decide próximo passo.

---

### Tipos de Node (referência P17)

* IntentToolSelectionNode
* ToolExecutionNode
* ClarificationNode
* ResponseNode
* FallbackNode

Runtime trata todos igualmente.

---

## 4. Avaliação de Edges

### Regra absoluta

Edge = expressão booleana pura.

* sem acesso a LLM
* sem acesso a texto livre
* sem efeitos colaterais

Avaliação:

* input: output do node anterior + context
* output: true | false

---

### Resolução

* 0 edges verdadeiras → erro estrutural
* 1 edge verdadeira → segue
* > 1 edge verdadeira → erro estrutural (P18)

Erro gera:

* FlowFailed
* estado terminal consistente

---

## 5. Determinismo

Garantias formais:

* mesmo snapshot + mesmo input → mesmo plano
* mesma sequência de eventos
* mesma ordem de nodes
* mesmo resultado (salvo side-effects externos)

Side-effects são:

* isolados
* auditáveis
* não influenciam routing

---

## 6. Replay e Reexecução

O runtime suporta:

* replay completo a partir de eventos
* reexecução de FlowRun falho
* simulação sem side-effects (dry-run)

Nada depende de estado implícito em memória.

---

## 7. Integração com LLMs

LLM **não é parte do runtime**.

* runtime chama NodeExecutor
* NodeExecutor chama Adapter (OpenAI, LangGraph, mock)
* Adapter é intercambiável

Trocar modelo não muda execução.

---

## 8. Eventos e Observabilidade

Eventos emitidos:

* FlowStarted
* NodeStarted
* NodeCompleted
* EdgeEvaluated
* FlowCompleted
* FlowFailed

Todos:

* correlacionados
* persistidos
* usados para auditoria e billing

---

## 9. Fail-Closed por design

Qualquer falha em:

* compile
* execução
* avaliação de edge
* timeout de node

Resulta em:

* FlowFailed
* estado final explícito
* nenhum caminho implícito

---

## 10. Mudanças necessárias no sistema

### Novos componentes

* GraphCompiler
* ExecutionPlan
* RuntimeExecutor
* NodeExecutor interface

---

### Persistência

* tabela/cache para `execution_plan` (opcional, derivável)
* nenhuma mutação em `flow_graph_snapshot`

---

### Endpoints (internos)

* compile_graph(snapshot_id)
* execute_flow(flow_run_id)

Não expostos ao cliente final.

---

## Resultado esperado do P20

Ao final deste plano:

* runtime é previsível
* execução é auditável
* integração com IA é plugável
* erro humano não vaza para produção
* o sistema suporta escala e replay

A partir daqui, qualquer engine de IA vira detalhe de implementação, não decisão arquitetural.

---
