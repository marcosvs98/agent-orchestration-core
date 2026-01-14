## Planning (11) — IA: Prompts, Políticas, RAG e Responsabilidades

Objetivo: **delimitar rigorosamente o papel da IA no sistema**, garantindo previsibilidade, auditabilidade e governança.
Aqui se evita o erro clássico de tratar IA como “motor de decisão implícito”.

IA é **capability controlada**, nunca autoridade.

---

### Tese central (não negociável)

IA:

* **não executa ações**
* **não altera estado diretamente**
* **não escolhe caminho de fluxo**
* **não invoca tools**

IA apenas **produz artefatos cognitivos**, que o runtime interpreta sob regras explícitas.

O runtime manda.
O grafo manda.
A IA só responde perguntas bem definidas.

---

### Contrato de atuação da IA

IA **só pode rodar** quando:

* associada a um **AITask explícito**
* invocada por um **Node declarativo**
* sob uma **AIExecutionPolicy versionada**
* com **input totalmente resolvido**

Qualquer execução fora disso é bug arquitetural.

---

### AITask — unidade mínima cognitiva

AITask define **o que a IA faz**, nunca *como* o sistema se comporta.

Exemplos canônicos:

* ContentModeration
* IntentDetection
* SlotFilling
* ResponseFormatting
* Summarization
* Classification
* Validation

Cada AITask define contrato fechado:

* input schema (estrito)
* output schema (estrito)
* semântica clara (o que significa “success”)

AITask:

* não conhece Flow
* não conhece Node
* não conhece Tool
* não conhece Tenant

Ela é reutilizável e neutra.

---

### Prompts — artefatos versionados de produto

Prompt **não é detalhe de implementação**.
Prompt é **parte do contrato cognitivo**.

Estrutura mínima obrigatória:

* **system**: papel fixo e invariável
* **task**: objetivo explícito
* **constraints**: regras duras (o que não fazer)
* **context**: dados resolvidos pelo runtime
* **output_format**: schema obrigatório

Regras:

* Prompt pertence a um **AgentVersion**
* Prompt pode variar por **AITask**
* Mudou prompt → nova versão
* Prompt nunca é montado “no meio” do código

---

### AgentVersion — encapsulamento cognitivo

AgentVersion é o **contêiner de cognição**.

Ele agrega:

* prompts
* AITasks suportadas
* policies permitidas
* bindings de tools (indiretos)

AgentVersion:

* não executa fluxo
* não escolhe Node
* não chama Tool

Ele apenas responde quando invocado.

---

### AIExecutionPolicy — governança de execução

Policy define **como** a IA é executada, não *quando*.

Controla:

* modelo (ex: GPT-4.1, Claude 3)
* parâmetros (temperature, max_tokens)
* retries
* timeout
* custo máximo
* limites por tenant / flow / agent

Policy é:

* versionada
* imutável após publish
* aplicada explicitamente por Node ou AgentVersion

Nunca:

* policy hard-coded
* policy implícita por ambiente

---

### RAG — contexto auxiliar, nunca verdade

RAG é **capability opcional**, não estado.

Roda apenas quando:

* explicitamente configurado
* associado a um AITask compatível

Casos comuns:

* IntentDetection (exemplos históricos)
* SlotFilling (catálogos, glossários)
* ResponseFormatting (documentação, FAQ)

Casos proibidos:

* moderação
* decisão de fluxo
* controle de execução

---

### RAG não é memória

Regras duras:

* RAG **não substitui GraphState**
* RAG **não carrega histórico de execução**
* RAG **não contém decisão canônica**
* RAG **não é fonte de verdade**

Se algo muda o comportamento do fluxo, **tem que estar no banco relacional**.

Embedding é contexto.
Banco é verdade.

---

### Exemplos e few-shot

Exemplos:

* são dados de produto
* versionados
* isolados por tenant
* associados a AITask / AgentVersion

Usos:

* few-shot
* grounding semântico
* redução de ambiguidade

Nunca:

* exemplos hard-coded
* exemplos implícitos por prompt genérico

---

### Output da IA — sempre validado

Toda resposta da IA:

* é validada contra schema
* é normalizada antes de uso
* é registrada para auditoria

Falha de validação:

* retry conforme policy
* fallback explícito
* erro controlado

Nunca:

* “best effort”
* parsing heurístico
* tolerância silenciosa

---

### Custos, métricas e limites

Cada AgentRun registra:

* modelo
* tokens de entrada
* tokens de saída
* custo estimado
* policy aplicada

Policy pode:

* bloquear execução
* forçar downgrade de modelo
* disparar escalation
* encerrar FlowRun

Custo é **dado de negócio**, não métrica técnica opcional.

---

### Segurança e isolamento

IA **nunca recebe**:

* secrets
* tokens reais
* credenciais
* endpoints internos

IA produz texto/estrutura.
ToolRun executa ação.

Separação absoluta.

---

### Anti-patterns proibidos (reforçado)

* prompt genérico (“faça o que achar melhor”)
* IA escolhendo tool ou endpoint
* IA decidindo próximo node
* contexto implícito fora do GraphState
* “memória infinita” de chat
* lógica de controle embutida em prompt

---
