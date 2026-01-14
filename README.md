# agent-orchestration-core

Este repositório implementa o *core* do **Agent Orchestration Core**.

Este README consolida o **primeiro backlog detalhado** derivado do planning canônico:
`/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/1-contexto-e-tese-do-servico.md` (linhas 1–111).

## O que este serviço é

Uma **plataforma de orquestração cognitiva multi-tenant**: interpreta entrada em linguagem natural, decide caminhos de execução e aciona integrações externas de forma controlada, auditável e previsível.

## O que este serviço não é

- Não é um chatbot
- Não é um assistente genérico
- Não é um wrapper de LLM

## Princípios não negociáveis

1. **Isolamento por tenant é estrutural**: todo dado, decisão e execução pertence a um tenant. Tenant vem do contexto de segurança.
2. **Definição é diferente de execução**: flows e agentes são definidos e versionados; execuções são rastreáveis e auditáveis e nunca alteram a definição.
3. **IA não executa efeitos colaterais**: IA apenas classifica/extrai/decide caminho/formata; side-effects são determinísticos fora da IA.
4. **Tudo é explícito e versionado**: fluxos, agentes, prompts, políticas, ferramentas e decisões têm versão.
5. **Canal é detalhe de entrada e saída**: o core é agnóstico ao meio de interação.

## Vocabulário canônico

Os termos abaixo têm significado preciso e não são intercambiáveis:

| Termo | Significado |
| --- | --- |
| Flow | definição lógica de um processo |
| FlowVersion | snapshot imutável de um flow |
| FlowRun | execução concreta de uma versão de flow |
| Node | unidade executável dentro de um flow |
| NodeRun | execução de um node |
| Agent | definição lógica de um agente cognitivo |
| AgentVersion | implementação imutável de um agente |
| AgentRun | execução efetiva de um agente |
| Tool | contrato abstrato de integração externa |
| ToolConfig | configuração concreta de uma tool para um tenant |
| Router | mecanismo declarativo de decisão de caminho |
| ConditionExpression | expressão reutilizável de decisão |
| Session / Interaction | contexto técnico e eventos de entrada/saída |
| GraphState | estado consolidado da execução de um flow |

## Backlog detalhado (primeiro recorte)

### Epic A — Tese, não-objetivos e vocabulário canônico (fundação)

- A1. Consolidar “o que é / o que não é” (sem ambiguidade).
- A2. Fixar não-objetivos e anti-usos (ex.: evitar “chatbot inteligente”).
- A3. Registrar invariantes e regras duras do sistema.

Critérios de aceite:
- Responde objetivamente “o que é / o que não é” sem interpretação criativa.
- Glossário é a referência única para specs e código.

### Epic C — Contratos mínimos de entrada e saída (agnóstico de canal)

- C1. Definir um envelope mínimo para entrada não-estruturada como evento (Interaction-like).
- C2. Definir output estruturado (o core entrega estrutura, adapters renderizam).

Critérios de aceite:
- Um canal novo pode ser adicionado sem mudar o core (apenas adapter).
- Entrada e saída são contratuais; não há “texto solto” como API principal.

### Epic D — IA sob contrato (limites desde o começo)

- D1. Definir claramente o que a IA pode fazer: classificar, extrair, decidir caminho sob regra, formatar.
- D2. Definir claramente o que a IA não pode fazer: executar integrações, persistir estado, carregar “memória mágica”.
- D3. Definir que toda saída de IA precisa ser validável por schema antes de avançar fluxo.

Critérios de aceite:
- Não existe cenário em que IA monta request final de Tool.
- “Saída inválida” não segue adiante; exige retry/fallback/erro controlado.

### Epic E — Versionamento como pilar do produto

- E1. Listar todos os artefatos relevantes que devem ser versionados (flows, agents, prompts, policies, tools, decisões).
- E2. Definir lifecycle mínimo de artefatos (editável vs imutável) e o que pode executar.

Critérios de aceite:
- Mudou algo relevante → nova versão (sem exceções).
- Execução sempre referencia versões explícitas (nunca “latest/current”).

### Epic F — Multi-tenant estrutural (com stub local)

- F1. Garantir por contrato que tudo pertence a um tenant.
- F2. Definir fonte do tenant como “contexto de segurança”; localmente permitir stub para acelerar evolução.

Stub local (apenas desenvolvimento):
- Header sugerido: `X-Debug-Tenant-Id: <uuid-ou-slug>`

Critérios de aceite:
- Tenant não entra como parâmetro de domínio em URL/body/query.
- O stub é claramente “não-produção” e compatível com a migração para auth real.

### Epic G — Registro de riscos de degradação (evitar virar “chatbot”)

- G1. Risco: regra de negócio acoplada a prompt.
- G2. Risco: fluxo implícito sem auditoria/versionamento.
- G3. Risco: side-effect disparado diretamente por IA.
- G4. Risco: falta de reprodutibilidade/debug.

Critérios de aceite:
- Cada risco tem sinal de detecção e mitigação por design (não por disciplina manual).

## Próximo passo (fora deste backlog)

Transformar este backlog em specs alinhadas aos documentos 2–15 do planning canônico (modelo de dados, API, execução, observabilidade, segurança e governança de mudança).

## Spec — Planning (7) Versionamento, Compatibilidade e Evolução Controlada

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/7-especificacao-rest-e-contratos-de-api.md` (linhas 1–141).

### Estados de versão (dados, não enum mágico)
- `DRAFT`, `PUBLISHED`, `DEPRECATED`, `DISABLED`
- Execução **nunca** usa `DRAFT` ou `DISABLED`; `DEPRECATED` é permitido com sinalização/telemetria.

### Semver e imutabilidade (append-only)
- Campos em versões: `version_major`, `version_minor`, `version_patch`, `status`, `config_hash` (sha256).
- Unicidade por grupo + semver: flow_version, agent_version, ai_execution_policy_version, tool_config, rag_config.
- Mudou algo relevante → **nova linha** (nunca update in-place). Breaking change → `version_major`++.

### Compatibilidade declarada (sem fallback mágico)
- `flow_version` pode declarar mínimo de `agent_version` (min_agent_version_*).
- `agent_version` declara suporte de `tool_config` via `supported_tool_schema_version` e `supported_tool_config_hash_prefix`.
- `tool_config` declara `schema_version` e `config_hash`.
- Bindings/executions validam explicitamente; incompatibilidade gera erro, não fallback.

### Publicação (Authoring APIs)
- Endpoints para publicar/deprecar/desabilitar versões (flows, agents, ai policies, tool configs, rag configs).
- Criação de versão inicia em `DRAFT`; publicação é transição explícita.
- Listagens aceitam filtro por `status`.

### Guardrails de runtime
- `ExecutionService` bloqueia criação de runs quando a versão está `DRAFT` ou `DISABLED`.
- Validação de compatibilidade em `ToolRun`: schema_version/hash compatíveis com `agent_version` quando houver `agent_run_id`.

### Auditoria
- `config_hash` registra a configuração canonicalizada para reprodutibilidade.
- Execução sempre referencia IDs explícitos de versão (nunca “latest/current”).

## Spec — Planning (8) Modelo de API, Contratos e Superfície Pública

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/8-runtime-de-fluxo-e-mecanismo-de-execucao.md` (linhas 1–163).

### Separação de superfícies
- Control Plane: `/core/v1/*` (authoring/config).
- Execution Plane: `/core/v1/executions/*` (runtime). Endpoints antigos de runtime em `/core/v1/*` permanecem apenas por compatibilidade e estão deprecated.

### Placeholders
- Endpoints de roadmap retornam **405 Method Not Allowed** (placeholder explícito), nunca “endpoint mágico”.

### Contrato de erro
- Sempre retorna `code`, `message`, `correlation_id` (+ `details`).
- Tenants não aparecem em URL/body; vêm do contexto de autenticação.

### Idempotência
- POSTs com efeito colateral no Execution Plane exigem `Idempotency-Key`.

### Observabilidade via API
- Execução é assíncrona: criar FlowRun/ToolRun retorna imediato; inspeção via list/get/graph-state (ou eventos futuros).

### Segurança (escopo deste planning)
- Superfícies separadas (authoring vs runtime); rate limit e scopes devem ser aplicados no gateway.

## Spec — Planning (9) Modelo de Dados Canônico (authoring/runtime/observabilidade)

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/9-deteccao-de-intencao-e-slot-filling.md` (linhas 1–483).

### Principais regras estruturais
- Banco é backbone; tudo que afeta decisão/execução é persistido.
- Tenant é soberano; nada relevante existe fora de um tenant.
- Definition (authoring) é imutável; runtime não escreve em authoring.
- Sem “current_version”; execuções referenciam versões explícitas.

### Ajustes estruturais aplicados
- Router pertence a Node (não mais a FlowVersion).
- RoutingRule tem from_node_id e to_node_id explícitos.
- AgentVersion referencia AIExecutionPolicyVersion e RagConfig (quando aplicável).
- AgentRun referencia AIExecutionPolicyVersion.
- Novas entidades de observabilidade/auditoria: ExecutionEvent (append-only).
- EscalationPolicy referencia ConditionExpression; Escalation referencia FlowRun/Policy.

### Observabilidade/Auditoria
- ExecutionEvent para registrar decisões/erros/transições (append-only).
- GraphState permanece como materialização derivada do runtime.

### Migration
- Migration breaking (`20260112_04_backbone_v2_planning_9.py`) recria tabelas para aderência total ao contrato.

## Spec — Planning (10) Execução e Ciclo de Vida de um Run

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/10-orquestracao-de-tools-e-efeitos-colaterais.md` (linhas 1–223).

### Estados canônicos (camada dupla)
- FlowRun: CREATED, RUNNING, WAITING, COMPLETED, FAILED, ESCALATED
- NodeRun: PENDING, RUNNING, SKIPPED, COMPLETED, FAILED
- AgentRun: CREATED, RUNNING, COMPLETED, FAILED
- ToolRun: CREATED, EXECUTING, SUCCESS, ERROR, TIMEOUT
- `status` (P6) permanece para compat; `canonical_status` persiste Planning 10.

### Concorrência e lock
- Um FlowRun executa apenas um Node por vez.
- Lock local via tabela `flow_run_lock` (row lock + SELECT … FOR UPDATE).

### WAITING e Escalation
- WAITING exige reason, correlation_id, deadline.
- Escalated é estado terminal; sempre gera ExecutionEvent.

### Observabilidade e replay
- Toda transição gera ExecutionEvent (append-only).
- GraphState evolui incrementalmente; ToolRun nunca muta GraphState direto.

### Side-effects
- ToolRun é a unidade de efeito colateral; não altera GraphState diretamente.

### Migration
- `20260112_05_run_lifecycle_planning_10.py` adiciona canonical_status, waiting fields, flow_run_lock e índices de ExecutionEvent.

## Spec — Planning (11) IA: Prompts, Políticas, RAG e Responsabilidades

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/11-ia-prompts-politicas-e-rag.md` (linhas 1–270).

### Guardrails de atuação da IA
- IA não executa ações, não escolhe próximo node, não monta request final de ToolRun, não altera GraphState.
- IA só roda com AITask explícito (Node), AgentVersion publicada, AIExecutionPolicyVersion publicada e input resolvido.
- RAG é opcional e só permitido para AITasks compatíveis (IntentDetection, SlotFilling, ResponseFormatting); bloqueado para ContentModeration, FlowDecision, ExecutionControl.

### Contrato de output
- Toda saída de IA é validada contra schema estrito; falha gera erro controlado e evento `AI_VALIDATION_FAILED`.
- Saída normalizada é persistida e auditada; não há tolerância “best effort”.

### Auditoria e custos
- AgentRun registra modelo, tokens de entrada/saída e custo estimado.
- Execução referencia explicitamente AIExecutionPolicyVersion e AITask.
- Eventos de execução: `AI_STARTED`, `AI_COMPLETED`, `AI_VALIDATION_FAILED`, `AI_POLICY_BLOCKED`.

### Idempotência e observabilidade
- Criação de AgentRun segue idempotência; cada evento fica em ExecutionEvent (append-only).
- Tenants não transitam em payload; vêm do contexto de autenticação.

### Futuro próximo (prompts)
- Prompts serão persistidos como JSONB estruturado (system/task/constraints/context/output_format) com hash para versionamento; não implementado neste recorte.

## Spec — Planning (12) Canais, Eventos e Integração Externa (Ajustado)

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/12-canais-eventos-e-integracao-externa.md` (linhas 1–257).

### Fronteira única: Execution Boundary
- Nenhum canal fala com o core diretamente.
- Adapters inbound (HTTP) apenas persistem `Interaction` e solicitam execução via `ExecutionBoundary` (`src/services/execution_boundary.py`).
- `FlowRun` só nasce dentro do core; canal não cria nem muta FlowRun.

### Interaction é contrato, não “pasta”
- `Interaction` é o único input oficial do core: imutável, persistida antes da execução, com metadata técnica (channel/headers/trace/external ids).
- A relação `FlowRun.interaction_id` torna explícito que a execução foi iniciada por um evento persistido.

### Eventos internos são fonte de verdade (append-only)
- `ExecutionEvent` é contrato histórico (observabilidade/auditoria/billing).
- Sem evento persistido, assume-se que não aconteceu.
- Eventos canônicos já emitidos: `FlowStarted`, `AgentRunStarted`, `AgentRunCompleted`, `AgentRunFailed`, `ToolInvocationRequested`, `ToolInvocationSucceeded`, `ToolInvocationFailed`.

## Spec — Planning (13) Observabilidade, Auditoria e Billing

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/13-observabilidade-auditoria-e-billing.md` (linhas 1–337).

### Evento é evidência (não log)
- `ExecutionEvent` é **append-only** e representa evidência técnica do que ocorreu no runtime.
- Eventos carregam contexto suficiente para auditoria e billing sem inferência externa.

### Campos obrigatórios e ordenação causal
- `ExecutionEvent` é denormalizado com `tenant_id` e `session_id` (audit/billing sem joins frágeis).
- Cada evento possui `occurred_at` e `event_sequence` monotônico por `flow_run_id` para ordenação determinística.
- `correlation_id` é o trace root; `causation_id` existe para encadear causalidade quando aplicável.

### Billing defensável por execução
- Custos de IA são registrados no `AgentRun` (tokens + custo estimado) e refletidos em eventos `AgentRunCompleted/Failed`.
- Custos/latências de ferramentas são registrados por evento (`ToolInvocationSucceeded/Failed`) com `latency_ms`, `request_size`, `response_size`, `retries`, `error_class` (quando falha).

### ResponseArtifact é a saída oficial do core
- O core não retorna string: persiste `ResponseArtifact` (estruturado, versionado e replayable) ligado a `Interaction` + `FlowRun`.

### Integração externa: ToolOrchestrator como firewall semântico
- Side-effects externos só ocorrem via `ToolOrchestrator` + executor HTTP mínimo (`httpx`).
- Orquestrador aplica timeout/retry e normaliza resposta/erro; falhas persistem em `RunFailure` (DLQ lógico).

## Spec — Planning (14) Segurança, Limites e Hardening

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/14-seguranca-limites-e-hardening.md` (linhas 1–282).

### Fail-closed por padrão
- Nenhuma execução ocorre sem identidade resolvida.
- Nenhuma ação ocorre sem autorização explícita.
- Ausência de policy versionada bloqueia (não existe fallback implícito).

### Identidade (JWT) endurecida
- Token exige `tenant_id`, `principal_type`, `principal_id` e `scopes`.
- Claims `iss`, `aud`, `exp` são validados sempre (sem “best effort”).

### Autorização versionada
- `AccessPolicy` + `AccessPolicyVersion` (status + semver) governam quais ações são permitidas.
- Enforcement ocorre no `ExecutionBoundary` (não nos adapters).

### Limites governáveis por policy
- `ExecutionLimitPolicyVersion` define limites (ex.: max AgentRuns/ToolRuns).
- Violação interrompe execução e gera evento `LimitExceeded`.

### Rate limit policy-driven
- `RateLimitPolicyVersion` aplica rate limit por tenant/principal/action (enforcement via Redis).

### Secrets profissionais (referência, não conteúdo)
- ToolConfig usa `secret_ref` (ex.: `env:MY_SECRET`) e resolve em runtime.
- Nunca persistimos/logamos valor de secret; apenas evidência de acesso via `SecretAccessed`.

## Spec — Planning (15) Evolução, Versionamento e Governança de Mudança

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/15-evolucao-versionamento-e-governanca-de-mudanca.md` (linhas 1–215).

### Princípio de ouro
- Runtime não referencia “latest/current”.
- Runtime executa apenas contra **snapshot fechado** e **explicitamente ativado**.

### Lifecycle de versão (authoring)
- `DRAFT` -> `VALIDATED` -> `PUBLISHED` (imutável)
- Publicar congela; não expõe para execução automaticamente.

### Publish != Activate (ponteiro ativo, global-only por recurso)
- Ativação é um ponteiro persistido, separado do status da versão:
  - `active_flow_version` (`flow_id` -> `flow_version_id`)
  - `active_agent_version` (`agent_id` -> `agent_version_id`)
- Rollback é apenas atualizar o ponteiro para outra versão publicada.

### Runtime resolve versão por ponteiro (fail-closed)
- `POST /flow-runs` aceita `flow_id` **ou** `flow_version_id` (compat).
- Se receber `flow_id`, resolve `flow_version_id` via ponteiro ativo.
- Se receber `flow_version_id`, exige que ele seja o ponteiro ativo daquele `flow_id`.
- Ausência de ponteiro ativo bloqueia execução.

### Auditoria de mudança (authoring)
- Eventos de governança são persistidos em `authoring_event` (publish/activate/rollback), com `tenant_id`, `principal_id`, `change_type` e `justification` obrigatória.

## Spec — Planning (2) Fronteiras de domínio e não-objetivos

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/2-fronteiras-de-responsabilidade-e-nao-objetivos.md` (linhas 1–269).

### Princípio central

Cada domínio existe para resolver um único tipo de problema. Domínios não se misturam, não se substituem e não “se ajudam” informalmente.

### Regra de ouro transversal

Se um domínio:
- conhece detalhes internos de outro
- executa responsabilidades alheias
- tenta “resolver rápido” algo fora do seu escopo

ele está errado.

### Matriz de domínios (responsabilidade, inclui, exclui)

#### 1) Governance

- Responsabilidade: isolamento e governança multi-tenant; resolução de identidade; escopo e permissões.
- Inclui: tenant corrente; tipo de principal (humano vs máquina); scopes/policies de acesso.
- Exclui: regras de negócio; flows; execução; IA.
- Artefatos esperados (conceituais): TenantContext, Principal, Scopes, AccessPolicy.

#### 2) Conversation

- Responsabilidade: contexto técnico de interação; persistência de entradas/saídas; vínculo com execução quando aplicável.
- Inclui: Session; Interaction; payload bruto de entrada/saída.
- Exclui: decisão de fluxo; intenção; IA; estado de negócio.
- Artefatos esperados (conceituais): Session, Interaction, ChannelMetadata.

#### 3) Flow (Authoring)

- Responsabilidade: definição lógica de processos; versionamento; composição de nodes.
- Inclui: Flow; FlowVersion; Node.
- Exclui: execução; estado; persistência de resultados; integração externa.
- Artefatos esperados (conceituais): Flow, FlowVersion, Node.

#### 4) Routing

- Responsabilidade: decisão declarativa de caminho; avaliação de condições; controle de bifurcação.
- Inclui: Router; RoutingRule; ConditionExpression.
- Exclui: IA; execução; efeito colateral; persistência de estado.
- Artefatos esperados (conceituais): Router, RoutingRule, ConditionExpression.

#### 5) Agent

- Responsabilidade: definição de agentes cognitivos; especialização por tarefa; associação com nodes.
- Inclui: Agent; AgentVersion; NodeAgentBinding.
- Exclui: escolha de modelo; custo; limite; RAG; execução de tools.
- Artefatos esperados (conceituais): Agent, AgentVersion, NodeAgentBinding.

#### 6) AI Policy

- Responsabilidade: controle de execução de IA; escolha de modelo; parâmetros, limites e custo.
- Inclui: Model; AITask; AIExecutionPolicy (+Version).
- Exclui: fluxo; prompt de negócio; integração externa.
- Artefatos esperados (conceituais): Model, AITask, AIExecutionPolicy, PolicyVersion.

#### 7) Tool

- Responsabilidade: contratos de integração externa; configuração por tenant; autorização de uso.
- Inclui: Tool; ToolConfig; AgentVersionToolBinding.
- Exclui: lógica de negócio; decisão de quando chamar; IA.
- Artefatos esperados (conceituais): Tool, ToolConfig, AgentVersionToolBinding.

#### 8) RAG

- Responsabilidade: recuperação de contexto relevante; enriquecimento de entrada para IA.
- Inclui: RagConfig; VectorStore.
- Exclui: decisão; execução; persistência de estado.
- Artefatos esperados (conceituais): RagConfig, VectorStore.

#### 9) Execution (Runtime)

- Responsabilidade: execução real dos fluxos; rastreamento de estado; observabilidade.
- Inclui: FlowRun; NodeRun; AgentRun; GraphState.
- Exclui: definição de fluxo; mutação de configuração; IA livre.
- Artefatos esperados (conceituais): FlowRun, NodeRun, AgentRun, GraphState.

#### 10) Escalation

- Responsabilidade: tratamento de exceções de negócio; escalada controlada de fluxos.
- Inclui: EscalationPolicy; Escalation.
- Exclui: fluxo principal; IA; tool.
- Artefatos esperados (conceituais): EscalationPolicy, Escalation.

#### 11) Onboarding

- Responsabilidade: coleta estruturada de informações; validação progressiva de dados.
- Inclui: Onboarding; OnboardingVersion; OnboardingRun.
- Exclui: detecção de intenção; execução de tools; decisão de fluxo global.
- Artefatos esperados (conceituais): Onboarding, OnboardingVersion, OnboardingRun.

### Checklist bloqueante (acoplamento ilegal)

Um PR viola a arquitetura se qualquer item abaixo ocorrer:

- Governance contém regra de negócio, fluxo, execução ou IA.
- Conversation interpreta significado (intenção, decisão de fluxo, estado de negócio).
- Flow/Authoring executa ações ou persiste resultados de runtime.
- Routing usa IA ou dispara side-effects.
- Agent escolhe modelo/custo/limites, executa tools, ou acopla RAG/execução diretamente.
- AI Policy contém prompts de negócio ou lógica de integração externa.
- Tool decide quando chamar, contém regra de negócio, ou depende de IA.
- RAG comanda execução ou vira fonte de verdade de estado.
- Execution muta definição/configuração ou roda “IA livre” sem contrato.
- Escalation vira caminho feliz.
- Onboarding vira fluxo universal ou decide intenção global.

### Anti-patterns proibidos (para code review)

- “Atalho” cross-domain para acelerar implementação.
- Lógica de decisão de fluxo escondida em Conversation ou Tool.
- Side-effects disparados sem passar por Execution/Runtime.
- RAG usado como memória/estado do sistema.

### Critérios de aceite desta Spec

- Toda feature nova pode ser atribuída a exatamente um domínio (ou explicitamente rejeitada).
- Para qualquer ação do sistema, é possível apontar o domínio dono e o domínio proibido.
- Não existe dependência implícita entre domínios fora de contratos.

## Spec — Planning (3) Estrutura do projeto e regras de organização de código

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/3-modelo-mental-e-vocabulario-canonico.md` (linhas 1–188).

### Princípio estrutural

A estrutura do projeto reflete o domínio (responsabilidade), não o framework, não o runtime e não o canal.

### Camadas globais (fora do domínio)

#### `src/adapters/`

- Responsabilidade: entradas e saídas do sistema (HTTP, webhooks, workers, schedulers, consumers).
- Regras:
  - adapta payload para o core
  - não contém lógica de negócio
  - não acessa diretamente outros adapters
  - adapters chamam controllers, nunca services diretamente

#### `src/infra/`

- Responsabilidade: implementações técnicas substituíveis (database, llm providers, vector_store backends, cache).
- Regras:
  - não importa código de domínio
  - implementa apenas interfaces definidas em `ports/`
  - pode ser trocado sem afetar domínio

#### `src/ports/` (global)

- Responsabilidade: contratos técnicos transversais (AuthContext, Clock, Logger, TransactionManager).
- Regras:
  - só interfaces
  - sem dependência de infra
  - usado por múltiplos domínios

### Estrutura interna de cada domínio (`src/packages/*`)

Todo domínio segue o mesmo padrão:

- `controllers/`: orquestra request, valida input, chama services; sem regra de negócio; sem infra direto.
- `services/`: regras de negócio e invariantes; sem HTTP/fila/canal; sem ORM; fala com infra via ports.
- `schemas/`: DTOs e validação estrutural; sem lógica; não chama services.
- `ports/` (por domínio): contratos de dependências externas; implementados em `infra/`; injetados nos services.
- `exceptions/`: erros semânticos do domínio (não técnicos).

### Regras invioláveis de dependência (bloqueantes)

- Domínio nunca depende de infra.
- Infra nunca depende de domínio.
- Adapters não conversam entre si.
- Services não conhecem controllers.
- Controllers não contêm regra de negócio.

Violou isso, violou a arquitetura.

### Organização de testes

- Cada domínio testa a si mesmo.
- Prioridade para testes de service.
- Infra deve ser mockada via ports.
- Adapters devem ser testados por contrato.

### Proibidos (anti-padrões estruturais)

- Lógica de negócio em controller.
- Prompt hardcoded em adapter.
- ORM dentro de service.
- Chamada de tool dentro de agent.
- IA decidindo efeito colateral.

### Estado atual do repositório vs modelo do Planning (3)

Estrutura atual em `src/` (resumo):
- existe: `adapters/`, `infra/`, `controllers/`, `services/`, `schemas/`
- falta: `ports/` (global) e `packages/*` (domínios explícitos)

Implicação:
- hoje `controllers/`, `services/`, `schemas/` estão globais e ainda não estão organizados por domínio em `packages/*`.
- antes de uma migração estrutural maior, novas features devem evitar aumentar o acoplamento nesses diretórios globais.
- observação: hoje há uso de `adapters.observability` dentro de `src/infra/` para logging/ambiente; isso deve ser tratado como exceção explícita de cross-cutting (fora disso, `infra/` não deve depender de camadas acima).

## Spec — Planning (4) Database as Backbone e separação authoring/runtime

Fonte: `/Users/marcossilveira/repositories/marcos/planning-agent-orchestration-core/4-arquitetura-logica-e-separacao-authoring-runtime.md` (linhas 1–527).

### Tese central

O banco de dados é o contrato estrutural do sistema. Se algo influencia decisão, execução, resposta, custo ou auditoria, então existe como entidade persistida. Se não está no banco, não existe.

### Separação authoring vs runtime

- Authoring (design-time): definem e versionam artefatos (Flow, FlowVersion, Node, Router, RoutingRule, ConditionExpression, Agent, AgentVersion, AIExecutionPolicy, AIExecutionPolicyVersion, Tool, ToolConfig, RagConfig, etc.).
- Runtime (execution-time): instâncias imutáveis que referenciam versões (FlowRun, NodeRun, AgentRun, GraphState, Interaction vinculada a FlowRun, Escalation, OnboardingRun).
- Execução nunca muta definição. Rollback/compatibilidade são feitos por seleção de versão, nunca por edição in-place.

### Entidades canônicas e relações (PK/FK essenciais)

- Tenant: raiz de isolamento; FK de Flow, Agent, ToolConfig, RagConfig, Onboarding.
- Session: FK tenant; Interaction: FK session, FK opcional flow_run.
- Flow: FK tenant; FlowVersion: FK flow; Node: FK flow_version.
- Router: FK flow_version; RoutingRule: FK router, FK condition_expression; ConditionExpression: raiz.
- Agent: FK tenant; AgentVersion: FK agent; NodeAgentBinding: FK node, FK agent_version.
- AITask: raiz; AIExecutionPolicy: raiz; AIExecutionPolicyVersion: FK policy, FK model; Model: raiz.
- Tool: raiz; ToolConfig: FK tool, FK tenant; AgentVersionToolBinding: FK agent_version, FK tool_config.
- RagConfig: FK tenant, FK vector_store; VectorStore: raiz.
- FlowRun: FK flow_version, FK session.
- NodeRun: FK flow_run, FK node.
- AgentRun: FK node_run, FK agent_version.
- GraphState: FK flow_run.
- EscalationPolicy: raiz; Escalation: FK flow_run, FK escalation_policy.
- Onboarding: FK tenant; OnboardingVersion: FK onboarding; OnboardingRun: FK onboarding_version; OnboardingStep: FK onboarding_version; StepRun: FK onboarding_step, FK onboarding_run.

### Regras estruturais

- Toda execução referencia versões explícitas (nunca “current”).
- Entidades de execução são append-only; finalização não edita definição.
- Tenant é obrigatório onde o planning define fronteira soberana.

### Checklist de conformidade (authoring/runtime)

- Alguma execução usa artefato sem versionamento? Bloqueia.
- Existe entidade relevante sem `tenant_id` quando exigido? Bloqueia.
- Existe runtime escrevendo/alterando definição? Bloqueia.
- FlowRun/NodeRun/AgentRun não referenciam versões? Bloqueia.

### Proibidos

- Comportamento implícito apenas em memória ou em prompt.
- Execução que altera definição publicada.
- Artefatos “latest” sem ID de versão explícito em runtime.

## Spec — Planning (5) Superfície REST design-first

Base: `/core/v1/`. REST estrito e versionado; recursos > ações; tenant nunca no path (derivado de JWT claim `tenant_id`).

### Princípios

- Endpoints existem mesmo sem implementação; 501 é aceitável para sinalizar contrato.
- Segurança: `Authorization: Bearer <jwt>` obrigatório, claim `tenant_id` UUID; sem claim → 403.
- Erros padronizados (`ErrorResponse`): code, message, details?, request_id?.

### Blocos de API

- Tenants: `GET /tenants/current`, `GET /tenants/current/settings`.
- Flows: `GET/POST /flows`, `GET /flows/{id}`, `GET/POST /flows/{id}/versions`.
- Nodes & Routing: `GET /flows/{id}/versions/{vid}/nodes`, `POST /nodes`, `GET/POST /routers`, `POST /routing-rules`, `POST /condition-expressions`.
- Agents: `GET/POST /agents`, `GET/POST /agents/{id}/versions`, `POST /node-agent-bindings`.
- Tools: `POST /tools/import-openapi`, `GET /tools`, `POST /tool-configs`, `POST /agent-version-tool-bindings`.
- AI: `GET /ai-tasks`, `POST /ai-execution-policies`, `POST /ai-execution-policy-versions`, `GET /models`.
- RAG: `GET /rag-configs`, `POST /rag-configs`, `GET /vector-stores`.
- Execução: `POST /flow-runs`, `GET /flow-runs/{id}`, `GET /flow-runs/{id}/graph-state`, `GET /node-runs`, `GET /agent-runs`.
- Onboarding: `GET/POST /onboardings`, `POST /onboarding-runs`, `GET /onboarding-runs/{id}`, `GET /onboardings/{id}/versions`.

### Implementação (estado atual)

- Routers FastAPI criados por domínio em `src/controllers/core_v1/*`, com prefix `/core/v1` e auth via JWT.
- Schemas Pydantic em `src/schemas/core_v1/*` (recursos + erro).
- Endpoints ainda retornam 501 para manter contrato explícito.
- OpenAPI é exposto pelo FastAPI (ex.: `/openapi.json`); pode ser exportado para tools MCP.

## Estrutura de domínios (hexagonal) para API `/core/v1`

- Organização por contexto em `src/domain/<context>/` com subpastas: adapters/, controllers/, ports/, repositories/, services/, schemas/, exceptions/.
- Controllers são classes que encapsulam `APIRouter` (OO), sem routers soltos.
- DI e bootstrap em `src/containers.py` (ApplicationContainer retorna routers para o `rest.py`/`app.py`).
- Erros padronizados em `service_exceptions.py` (inclui `NotImplementedServiceException` para contratos 501).
- Auth compartilhado em `utils/auth.py` (JWT Bearer com claim `tenant_id`).

### Contextos mapeados

- tenants, flows (nodes/routing), agents, tools, ai_policy, rag, execution, onboarding.
- Schemas por contexto em `src/domain/<context>/schemas`.
- Controllers por contexto em `src/domain/<context>/controllers` (prefix `/core/v1`).