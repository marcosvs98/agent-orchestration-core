## Planning (27) — Dynamic Node Prompt Management

### Objetivo

Permitir que prompts usados nos nodes críticos do runtime (IntentToolSelection, ParamExtraction, Clarification e Response) sejam **definidos e atualizados dinamicamente via API**, mantendo:

* determinismo do fluxo
* governança de execução
* validação por schema
* controle de custo e tokens

---

### Tese central

Prompts são **configuração de execução**, não lógica de negócio.
O usuário/admin define ou atualiza o template, mas **o runtime decide como aplicar, validar e auditar**.

> “Prompt dinâmico não pode quebrar fluxo, alterar edges ou corromper o contexto do runtime.”

---

## Escopo

1. **Nodes suportados**:

   * IntentToolSelectionNode
   * ParamExtractionNode / Slot Filling
   * ClarificationNode
   * ResponseComposer

2. **Atualização via API**:

   * Endpoints administrativos seguros
   * Atualização em runtime sem restart
   * Fallback para último prompt válido

3. **Validação**:

   * Input/Output schema obrigatório
   * Limites de tokens
   * Guardrails (custo, rate, latência)

4. **Observabilidade**:

   * Eventos canônicos P22: `NodePromptUpdated`, `NodePromptExecuted`
   * Frozen hash de cada template para auditoria

---

## Componentes

### 1. Prompt Repository

* Persistência central de templates de prompt, versionados.

* Armazena:

  * node_type
  * template_text
  * input_schema_id / output_schema_id
  * metadata (autor, versão, descrição)
  * frozen_hash (P22)

* Localização: banco relacional (Postgres) + cache em memória para runtime.

---

### 2. Prompt API

**Endpoints administrativos**:

```
GET /nodes/{node_type}/prompt      # retorna prompt atual
POST /nodes/{node_type}/prompt     # cria/atualiza prompt
DELETE /nodes/{node_type}/prompt   # rollback / soft delete
```

**Payload exemplo:**

```json
{
  "template_text": "Analise a entrada do usuário e selecione a tool adequada...",
  "input_schema_id": "schema_v1",
  "output_schema_id": "schema_v1",
  "description": "Prompt atualizado para IntentToolSelectionNode"
}
```

* Retorna: versão, frozen_hash, timestamp
* Valida permissões do usuário (admin only)
* Garante observabilidade (`NodePromptUpdated`)

---

### 3. Prompt Service

* Encapsula lógica de leitura e cache de prompts.

* Funções:

  * `get_prompt(node_type)` → retorna prompt ativo (do cache, fallback para DB se necessário)
  * `validate_prompt(prompt)` → verifica schemas, tokens, limites
  * `update_prompt(prompt)` → persiste e dispara evento

* Integra com GuardrailEngine (P25) para aplicar limites antes de executar node.

---

### 4. Runtime Integration

Fluxo de execução:

1. Node inicia execução.
2. LLMExecutor solicita prompt ao PromptService.
3. PromptService retorna template atualizado + schema.
4. LLMExecutor aplica:

   * valida entrada
   * chama provider (P23)
   * valida saída contra schema
5. Observabilidade:

   * `NodePromptExecuted` → inclui node_type, prompt_version, frozen_hash, token_usage, latency, custo estimado.

---

### 5. Fallback e Segurança

* Se prompt inválido: Node entra em erro explícito (`NodeFailed`), segue edge de erro.
* Se schema mudou e invalida dados: Node bloqueia execução, alerta admin.
* Somente prompts validados entram no cache ativo.

---

### 6. Observabilidade / Auditoria (P22 + Langfuse)

* Cada execução de prompt gera **span e atributos enriquecidos**:

  * trace_id, node_run_id, tenant_id
  * frozen_hash do template
  * token_usage e custo estimado
  * versão do prompt

* Alterações de prompt disparam `NodePromptUpdated` com frozen hash, timestamp e autor.

* Compatível com LangfuseRuntimeTracer, propagando atributos de execução.

---

### 7. Resultado Esperado

Ao final do P27:

* O runtime consegue usar prompts dinâmicos sem perder determinismo.
* Administradores atualizam templates via API, auditáveis.
* Nodes sempre validam input/output contra schema.
* Guardrails P25 continuam ativos (custo, rate, latência, etc.).
* Observabilidade e auditoria de cada execução garantidas (P22).

---
Perfeito. Seguindo o padrão dos planos anteriores, aqui está o diagrama de fluxo para o **P27 — Dynamic Node Prompt Management**, usando **Mermaid** para visualização. Ele mostra como um node busca e executa prompts dinamicamente, com integração de cache, guardrails, LLMExecutor e observabilidade:

```mermaid
flowchart TD
    subgraph Admin
        A[Prompt API] -->|POST /nodes/{node_type}/prompt| B[Prompt Repository DB]
        A -->|GET /nodes/{node_type}/prompt| B
    end

    subgraph Runtime
        C[Node Execution] --> D[Prompt Service / Cache]
        D -->|get_prompt(node_type)| B
        D -->|validate_prompt()| E[Guardrail Engine]
        E -->|decision ALLOW| F[LLMExecutor]
        F -->|apply prompt + input schema| G[LLM / Provider Adapter]
        G -->|returns output| F
        F -->|validate output against schema| C
    end

    subgraph Observability
        F --> H[NodePromptExecuted Event]
        D --> H
        A --> I[NodePromptUpdated Event]
    end

    subgraph Langfuse
        H --> J[LangfuseRuntimeTracer]
        I --> J
    end

    style Admin fill:#f9f,stroke:#333,stroke-width:1px
    style Runtime fill:#bbf,stroke:#333,stroke-width:1px
    style Observability fill:#bfb,stroke:#333,stroke-width:1px
    style Langfuse fill:#ffb,stroke:#333,stroke-width:1px
```

### Explicação do fluxo

1. **Admin define/update prompt** via `Prompt API`.
2. **Prompt Repository** armazena template versionado e hash congelado.
3. **Node Execution** solicita prompt ao **Prompt Service**, que aplica cache.
4. **Prompt Service** valida prompt e envia para **Guardrail Engine** antes da execução.
5. **Guardrail Engine** decide: ALLOW, BLOCK ou DEGRADE (futuro).
6. **LLMExecutor** recebe o prompt validado e input schema, chama provider via **Adapter**, valida output contra schema.
7. Todos os eventos críticos disparam **NodePromptExecuted** e **NodePromptUpdated**, integrando **LangfuseRuntimeTracer** para auditoria, trace e observabilidade detalhada.

---
