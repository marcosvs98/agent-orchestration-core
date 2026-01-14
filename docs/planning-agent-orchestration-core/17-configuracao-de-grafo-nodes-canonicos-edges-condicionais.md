## Planning (17) — Configuração de Grafo, Nodes Canônicos e Edges Condicionais (Detalhado)

### Objetivo operacional

Transformar o runtime de fluxo em um **executor determinístico de grafos configuráveis**, onde:

• o grafo é dado de entrada
• nodes são unidades fechadas de decisão/ação
• edges apenas roteiam
• IA não vaza para a estrutura

Resultado: previsibilidade, testabilidade e custo controlado.

---

## Escopo EXATO deste planning

Este planning **NÃO** inclui:
• integração com OpenAI
• LangGraph
• UI de authoring
• otimização de prompt
• tuning de modelo

Este planning **INCLUI**:
• modelo de grafo
• contratos de node
• modelo de edge condicional
• validação estrutural
• seeds de desenvolvimento
• ajustes mínimos de banco e runtime

---

## 1. Modelo de Grafo (configuração)

### 1.1 Entidades de banco (mudanças necessárias)

#### NOVA tabela: `flow_graph`

Responsabilidade: representar **uma versão imutável** de um grafo.

Campos (alto nível):
• `flow_graph_id` (PK)
• `flow_version_id` (FK, published)
• `definition` (JSONB) ← **grafo inteiro**
• `created_at`
• `created_by`

Não normalizar nodes e edges agora.
O grafo é **um artefato fechado**.

Motivo: versionamento simples + replay determinístico.

---

### 1.2 Estrutura do JSON de grafo (contrato)

```json
{
  "start_node": "intent_select",
  "nodes": {
    "intent_select": {
      "type": "IntentToolSelectionNode",
      "config": {
        "confidence_threshold": 0.85
      }
    },
    "execute_tool": {
      "type": "ToolExecutionNode"
    },
    "clarify": {
      "type": "ClarificationNode"
    },
    "respond": {
      "type": "ResponseNode"
    },
    "fallback": {
      "type": "FallbackNode"
    }
  },
  "edges": [
    {
      "from": "intent_select",
      "to": "execute_tool",
      "condition": "validation_status == VALID && confidence >= 0.85"
    },
    {
      "from": "intent_select",
      "to": "clarify",
      "condition": "validation_status == MISSING_FIELDS"
    },
    {
      "from": "intent_select",
      "to": "fallback",
      "condition": "confidence < 0.85"
    },
    {
      "from": "execute_tool",
      "to": "respond",
      "condition": "execution_status == SUCCESS"
    },
    {
      "from": "execute_tool",
      "to": "fallback",
      "condition": "execution_status == ERROR"
    }
  ]
}
```

---

## 2. Contrato formal de Node

### 2.1 Interface base (runtime)

Todo node **DEVE** implementar:

```
execute(input: NodeInput, context: RuntimeContext) -> NodeOutput
```

Onde:

**NodeInput**
• payload do node anterior
• estado acumulado do FlowRun

**NodeOutput**
• objeto JSON plano
• sem texto livre fora de campos definidos
• serializável

---

### 2.2 Contrato fechado por tipo

#### IntentToolSelectionNode

Output obrigatório:
• `tool_id: string | null`
• `arguments: object | null`
• `confidence: number`
• `validation_status: VALID | MISSING_FIELDS | INVALID`

Não retorna texto para usuário.

---

#### ToolExecutionNode

Output obrigatório:
• `execution_status: SUCCESS | ERROR`
• `result: object | null`
• `error: { code, message } | null`

---

#### ClarificationNode

Output obrigatório:
• `missing_fields: string[]`
• `user_message: string`

---

#### ResponseNode

Output obrigatório:
• `message: string`
• `payload: object | null`

---

#### FallbackNode

Output obrigatório:
• `reason: string`
• `message: string`

---

## 3. Edges condicionais (engine)

### 3.1 Engine de condição (novo componente)

Criar componente:

**ConditionEvaluator**

Responsabilidades:
• avaliar expressões booleanas simples
• operar apenas sobre NodeOutput
• sem acesso a contexto global

Expressões permitidas:
• `==`, `!=`, `<`, `>`, `<=`, `>=`
• `&&`, `||`
• comparação com literals

Nada além disso.

---

### 3.2 Validação estática do grafo (obrigatória)

Na criação do FlowGraph:

• start_node existe
• todos os nodes referenciados existem
• todos os edges têm condition
• não há node inalcançável
• todo caminho termina em Response ou Fallback

Falhou → **não publica**.

---

## 4. Runtime (mudanças necessárias)

### 4.1 Alterações no executor de Flow

Hoje:
• executor avança baseado em código

Após P17:
• executor carrega `flow_graph.definition`
• executa node atual
• avalia edges em ordem
• escolhe o primeiro `true`
• avança

Nenhum if/else de negócio no código.

---

### 4.2 Estado do FlowRun

Não muda entidade, mas:

• estado passa a armazenar `current_node_id`
• histórico de node outputs já existe via ExecutionEvent

---

## 5. Seeds obrigatórios (ambiente dev)

### 5.1 Seed de Tool

• importar OpenAPI simples (ex: `GET /orders/{id}`)
• gerar tool + schema

---

### 5.2 Seed de FlowVersion

• flow publicado e ativado
• referencia FlowGraph seed

---

### 5.3 Seed de FlowGraph

• grafo canônico descrito acima
• confidence_threshold configurável

Esses seeds são **obrigatórios** para dev e testes.

---

## 6. Endpoints (mudanças)

### 6.1 NOVO endpoint (interno / admin)

```
POST /flows/{flow_version_id}/graph
```

• valida grafo
• persiste `flow_graph`
• só aceita flow_version PUBLISHED

---

### 6.2 Runtime

Nenhum endpoint público muda.

Execução continua via:

```
POST /sessions/{id}/events
```

---

## 7. O que NÃO muda neste planning

• modelo de billing
• observabilidade
• policies
• autenticação
• LangFuse
• OpenAI
• prompts

---

## Resultado concreto ao final do P17

Você deve conseguir:

• definir um flow **sem IA real**
• executar ponta-a-ponta com mock
• trocar grafo sem alterar código
• explicar o runtime para qualquer engenheiro em 5 minutos

Se isso não for possível, o planning falhou.

---

## Encadeamento correto depois

Somente após isso:

• **Planning (18)** — Executor LLM plugável (OpenAI / LangGraph)
• **Planning (19)** — Authoring (API / UI)
• **Planning (20)** — Testes determinísticos de grafos

---

Resumo final, sem romantismo:

> **P17 é onde o sistema vira produto.
> Antes disso, é só promessa arquitetural.**
