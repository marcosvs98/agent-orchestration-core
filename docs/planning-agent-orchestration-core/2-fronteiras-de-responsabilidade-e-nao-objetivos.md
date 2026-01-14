## Planning (2) — Fronteiras de Domínio e Responsabilidades

Objetivo deste planning: **impedir acoplamento indevido** e **fixar responsabilidades claras** para que qualquer agente (humano ou MCP Host) saiba **onde cada decisão pertence** e, principalmente, **onde ela não pertence**.

Aqui não há implementação, apenas contratos conceituais.

---

### Princípio central

Cada domínio existe para **resolver um único tipo de problema**.
Domínios **não se misturam**, **não se substituem** e **não “se ajudam” informalmente**.

Quando um domínio começa a “facilitar” a vida de outro, o sistema degrada.

---

### 1. Governance

**Responsabilidade**
– Isolamento e governança multi-tenant
– Resolução de identidade (quem é o caller)
– Escopo e permissões

**O que pertence aqui**
– Tenant corrente
– Tipo de principal (humano vs máquina)
– Scopes e políticas de acesso

**O que não pertence aqui**
– Regras de negócio
– Fluxos
– Execução
– IA

Governance é infraestrutura lógica, não domínio funcional.

---

### 2. Conversation

**Responsabilidade**
– Contexto técnico de interação
– Persistência de entradas e saídas
– Vinculação com execução quando aplicável

**O que pertence aqui**
– Session
– Interaction
– Payload bruto de entrada/saída

**O que não pertence aqui**
– Decisão de fluxo
– Intenção
– IA
– Estado de negócio

Conversation **não entende significado**, apenas registra eventos.

---

### 3. Flow (Authoring)

**Responsabilidade**
– Definição lógica de processos
– Versionamento de fluxos
– Composição de nodes

**O que pertence aqui**
– Flow
– FlowVersion
– Node

**O que não pertence aqui**
– Execução
– Estado
– Persistência de resultados
– Integração externa

Flow é **design-time**, nunca runtime.

---

### 4. Routing

**Responsabilidade**
– Decisão declarativa de caminho
– Avaliação de condições
– Controle de bifurcação

**O que pertence aqui**
– Router
– RoutingRule
– ConditionExpression

**O que não pertence aqui**
– IA
– Execução
– Efeito colateral
– Persistência de estado

Routing decide **para onde ir**, não **o que fazer**.

---

### 5. Agent

**Responsabilidade**
– Definição de agentes cognitivos
– Especialização por tarefa
– Associação com nodes

**O que pertence aqui**
– Agent
– AgentVersion
– NodeAgentBinding

**O que não pertence aqui**
– Escolha de modelo
– Custo
– Limite
– RAG
– Tool execution

Agent define **o que o agente faz conceitualmente**, não como ele executa.

---

### 6. AI Policy

**Responsabilidade**
– Controle de execução de IA
– Escolha de modelo
– Parâmetros, limites e custo

**O que pertence aqui**
– Model
– AITask
– AIExecutionPolicy (+Version)

**O que não pertence aqui**
– Fluxo
– Prompt de negócio
– Integração externa

AI Policy responde: **como a IA roda**, não **por que**.

---

### 7. Tool

**Responsabilidade**
– Contratos de integração externa
– Configuração por tenant
– Autorização de uso

**O que pertence aqui**
– Tool
– ToolConfig
– AgentVersionToolBinding

**O que não pertence aqui**
– Lógica de negócio
– Decisão de quando chamar
– IA

Tool **nunca decide**, apenas executa quando chamada.

---

### 8. RAG

**Responsabilidade**
– Recuperação de contexto relevante
– Enriquecimento de entrada para IA

**O que pertence aqui**
– RagConfig
– VectorStore

**O que não pertence aqui**
– Decisão
– Execução
– Persistência de estado

RAG **informa**, não comanda.

---

### 9. Execution (Runtime)

**Responsabilidade**
– Execução real dos fluxos
– Rastreamento de estado
– Observabilidade

**O que pertence aqui**
– FlowRun
– NodeRun
– AgentRun
– GraphState

**O que não pertence aqui**
– Definição de fluxo
– Mutação de configuração
– IA livre

Execution é **o que aconteceu**, não **o que deveria acontecer**.

---

### 10. Escalation

**Responsabilidade**
– Tratamento de exceções de negócio
– Escalada controlada de fluxos

**O que pertence aqui**
– EscalationPolicy
– Escalation

**O que não pertence aqui**
– Fluxo principal
– IA
– Tool

Escalation é exceção, nunca caminho feliz.

---

### 11. Onboarding

**Responsabilidade**
– Coleta estruturada de informações
– Validação progressiva de dados

**O que pertence aqui**
– Onboarding
– OnboardingVersion
– OnboardingRun

**O que não pertence aqui**
– Detecção de intenção
– Execução de tools
– Decisão de fluxo global

Onboarding é um **subprocesso**, não um fluxo universal.

---

### Regra de ouro transversal

Se um domínio:
– conhece detalhes internos de outro
– executa responsabilidades alheias
– tenta “resolver rápido” algo fora de seu escopo

ele está errado.

---

### Resultado esperado deste planning

Após este documento, qualquer agente deve ser capaz de:

– Saber onde criar algo novo
– Saber onde **não** criar
– Evitar acoplamentos ilegais
– Manter o core coerente ao longo do tempo