# Comunicação entre Serviços - agent-orchestration-core

## Visão Geral

O sistema utiliza padrões claros de comunicação entre componentes, separando **Control Plane** (authoring/config) e **Execution Plane** (runtime). Toda comunicação segue contratos explícitos, garantindo rastreabilidade, segurança e observabilidade.

### Princípios de Comunicação

1. **Contratos Explícitos**: Todas as interfaces são definidas via Ports (Protocol ou ABC)
2. **Separação de Responsabilidades**: Control Plane e Execution Plane são separados
3. **Idempotência**: Operações com efeito colateral exigem `Idempotency-Key`
4. **Observabilidade**: Toda comunicação relevante gera eventos auditáveis
5. **Segurança**: Autenticação e autorização em todas as fronteiras

### Control Plane vs Execution Plane

**Control Plane** (`/core/v1/*`):
- Authoring e configuração de artefatos
- Versionamento e governança
- Endpoints: Flows, Agents, Tools, AI Policy, RAG, Onboarding, Tenants

**Execution Plane** (`/core/v1/executions/*`):
- Runtime e execução de fluxos
- Observabilidade e inspeção
- Endpoints: FlowRuns, AgentRuns, ToolRuns, ExecutionEvents

**Nota**: Endpoints antigos de runtime em `/core/v1/*` permanecem apenas por compatibilidade e estão deprecated.

## APIs REST

### Estrutura de URLs

Padrão: `<protocolo>://<url>:<porta>/<versão>/<modulo>/<recurso>/`

Exemplo: `http://user.useyour_pypy.com.br:8000/core/v1/executions/flow-runs/`

### Versionamento de API

- Prefixo `/core/v1/` onde `v1` é a versão da API
- Nova versão para breaking changes (ex: `/core/v2/`)
- Versionamento sempre em números inteiros com prefixo "v"

### Autenticação e Autorização

#### JWT Bearer Token

Todas as requisições exigem autenticação via JWT Bearer Token:

```
Authorization: Bearer <jwt_token>
```

#### Claims Obrigatórios

O JWT deve conter os seguintes claims:

- `tenant_id` (UUID): Identificador do tenant (obrigatório)
- `principal_type` (string): Tipo de principal (`"human"` ou `"machine"`)
- `principal_id` (string): Identificador do principal (ou `sub`)
- `scopes` (array/string): Lista de scopes/permissões
- `iss` (string): Issuer do token (validado contra `JWT_ISSUER`)
- `aud` (string): Audience do token (validado contra `JWT_AUDIENCE`)
- `exp` (integer): Timestamp de expiração (validado com leeway)

#### Validação

O sistema valida:
- Assinatura do token
- Issuer e Audience
- Expiração (com leeway configurável)
- Presença e formato de todos os claims obrigatórios

**Arquivo**: `src/utils/auth.py` - `get_auth_context()`

#### Autorização por Scopes

Após autenticação, o sistema valida autorização via:

1. **AccessPolicyService**: Verifica se o principal tem permissão para a ação
2. **RateLimitService**: Aplica rate limiting por tenant/principal/action
3. **Scopes**: Validação de scopes específicos por endpoint

**Exemplo de Scope**: `execution:flow_run:create`, `flows:flow:list`, `agents:agent:create`

**Arquivo**: `src/domain/governance/schemas/scopes.py`

### Contratos de Erro Padronizados

Todos os erros seguem o formato `ErrorResponse`:

```json
{
  "code": "error_code",
  "message": "Human-readable message",
  "details": {},
  "correlation_id": "uuid",
  "request_id": "uuid"
}
```

**Códigos de Erro Comuns**:
- `missing_bearer_token`: Token de autenticação ausente
- `invalid_token`: Token inválido ou expirado
- `tenant_id_claim_required`: Claim tenant_id ausente
- `authorization_denied`: Principal não tem permissão
- `resource_not_found`: Recurso não encontrado
- `validation_failed`: Validação de entrada falhou
- `idempotency_key_conflict`: Chave de idempotência já usada

### Idempotência

POSTs com efeito colateral no Execution Plane exigem `Idempotency-Key`:

```
Idempotency-Key: <unique_key>
```

**Comportamento**:
- Primeira requisição: processa normalmente e armazena resultado
- Requisições subsequentes: retorna resultado armazenado (sem reprocessar)
- Chave deve ser única por tenant + endpoint + idempotency_key

**Implementação**: `IdempotencyService` usando Redis

**Arquivo**: `src/domain/execution/adapters/idempotency_service.py`

### Placeholders

Endpoints de roadmap retornam **405 Method Not Allowed** (placeholder explícito), nunca "endpoint mágico". Isso mantém o contrato da API explícito mesmo quando funcionalidades ainda não estão implementadas.

## Eventos Internos

### ExecutionEvent (Append-Only)

`ExecutionEvent` é o contrato histórico para observabilidade, auditoria e billing. Representa evidência técnica do que ocorreu no runtime.

#### Características

- **Append-Only**: Eventos nunca são alterados ou deletados
- **Denormalizado**: Carrega `tenant_id` e `session_id` para queries sem joins
- **Ordenação Causal**: `event_sequence` monotônico por `flow_run_id`
- **Rastreabilidade**: `correlation_id` (trace root) e `causation_id` (cadeia causal)

#### Campos Obrigatórios

- `execution_event_id`: UUID único do evento
- `tenant_id`: UUID do tenant (denormalizado)
- `session_id`: UUID da sessão (denormalizado)
- `flow_run_id`: UUID do flow run
- `correlation_id`: UUID raiz do trace
- `causation_id`: UUID do evento causador (quando aplicável)
- `event_type`: Tipo do evento (enum)
- `event_sequence`: Sequência monotônica por flow_run_id
- `occurred_at`: Timestamp do evento
- `payload`: JSONB com dados específicos do evento
- `schema_version`: Versão do schema do payload

#### Tipos de Eventos

**Flow Events**:
- `FlowStarted`: Flow iniciado
- `FlowRunning`: Flow em execução
- `FlowWaiting`: Flow aguardando (com reason)
- `FlowCompleted`: Flow completado com sucesso
- `FlowFailed`: Flow falhou
- `FlowEscalated`: Flow escalado

**Node Events**:
- `NodeEntered`: Node entrado
- `NodeStarted`: Node iniciado
- `NodeSkipped`: Node pulado
- `NodeCompleted`: Node completado
- `NodeFailed`: Node falhou
- `EdgeEvaluated`: Edge avaliado (decisão de caminho)

**Agent Events**:
- `AgentRunStarted`: Agent run iniciado
- `AgentRunCompleted`: Agent run completado
- `AgentRunFailed`: Agent run falhou
- `AgentRunRetried`: Agent run retentado
- `AgentRunAborted`: Agent run abortado

**Tool Events**:
- `ToolInvocationRequested`: Tool invocation solicitada
- `ToolInvocationSucceeded`: Tool invocation bem-sucedida
- `ToolInvocationFailed`: Tool invocation falhou
- `ToolInvocationTimedOut`: Tool invocation timeout
- `ToolInvocationRetried`: Tool invocation retentada

**LLM Events**:
- `LLMCallStarted`: Chamada LLM iniciada
- `LLMCallCompleted`: Chamada LLM completada
- `LLMCallFailed`: Chamada LLM falhou

**Guardrail Events**:
- `GuardrailChecked`: Guardrail verificado
- `GuardrailBlocked`: Guardrail bloqueou execução
- `GuardrailDegraded`: Guardrail degradou (aplicou overrides)

**Policy Events**:
- `PolicyEvaluated`: Política avaliada
- `PolicyDenied`: Política negou acesso
- `PolicyViolated`: Política violada

**Outros Events**:
- `LimitExceeded`: Limite excedido
- `ValidationFailed`: Validação falhou
- `SecretAccessed`: Secret acessado (auditoria)

**Arquivo**: `src/domain/execution/schemas/events.py`

#### Ordenação Causal

Eventos são ordenados por:
1. `flow_run_id`
2. `event_sequence` (monotônico, incrementado sequencialmente)

Isso garante ordem determinística para replay e auditoria.

**Correlation ID**: Identifica o trace root (correlaciona eventos relacionados)
**Causation ID**: Identifica o evento causador (encadeia causalidade)

### AuthoringEvent (Governança)

`AuthoringEvent` registra mudanças de governança em artefatos versionados:

- **Publish**: Publicação de versão
- **Activate**: Ativação de versão (ponteiro ativo)
- **Rollback**: Rollback para versão anterior
- **Deprecate**: Depreciação de versão
- **Disable**: Desabilitação de versão

#### Campos Obrigatórios

- `tenant_id`: UUID do tenant
- `principal_id`: UUID do principal que fez a mudança
- `change_type`: Tipo de mudança (publish, activate, rollback, etc.)
- `justification`: Justificativa obrigatória para a mudança
- `resource_type`: Tipo de recurso (flow, agent, tool_config, etc.)
- `resource_id`: ID do recurso
- `version_id`: ID da versão (quando aplicável)

**Arquivo**: `src/domain/governance/repositories/authoring_event_repository.py`

## Integração Externa

### ExecutionBoundary como Fronteira Única

`ExecutionBoundary` é a **única fronteira** entre o mundo externo e o core de execução. Nenhum canal fala com o core diretamente.

**Responsabilidades**:
- Aplicar rate limiting
- Aplicar autorização (AccessPolicyService)
- Validar tenant_id do AuthContext
- Delegar para ExecutionService

**Arquivo**: `src/services/execution_boundary.py`

```python
class ExecutionBoundary:
    async def ingest_interaction_and_create_flow_run(...):
        # 1. Rate limiting
        await self.rate_limit_service.enforce(...)
        # 2. Autorização
        await self.access_policy_service.authorize(...)
        # 3. Delegar para ExecutionService
        return await self.execution_service.create_flow_run(...)
```

### Interaction como Contrato de Entrada

`Interaction` é o **único input oficial** do core:

- **Imutável**: Uma vez criada, não pode ser alterada
- **Persistida**: Criada antes da execução
- **Metadata Técnica**: Channel, headers, trace, external IDs
- **Vínculo Explícito**: `FlowRun.interaction_id` torna explícito que a execução foi iniciada por um evento persistido

**Campos**:
- `interaction_id`: UUID único
- `session_id`: UUID da sessão
- `channel`: Canal de entrada (http, whatsapp, etc.)
- `headers`: Headers HTTP (quando aplicável)
- `external_message_id`: ID externo (quando aplicável)
- `request_id`: ID da requisição
- `trace_id`: ID do trace distribuído

### ToolOrchestrator para Side-Effects

Side-effects externos só ocorrem via `ToolOrchestrator`:

**Responsabilidades**:
- Aplicar timeout configurável
- Aplicar retry com backoff exponencial
- Normalizar resposta/erro
- Persistir falhas em `RunFailure` (DLQ lógico)
- Resolver secrets via `SecretResolverPort`

**Arquivo**: `src/domain/tools/services/tool_orchestrator.py`

**Executor HTTP**: `src/infra/http_tool_executor.py` (usa `httpx`)

### Webhooks e Callbacks

Atualmente, o sistema não implementa webhooks ou callbacks externos. Toda comunicação é síncrona via APIs REST ou assíncrona via eventos internos (ExecutionEvent).

## Observabilidade

### Logging Estruturado

O sistema usa logging estruturado via `adapters.observability.logging.get_logger()`:

**Características**:
- Contexto estruturado: `request_id`, `tenant_id`, `flow_run_id`, etc.
- Níveis apropriados: DEBUG, INFO, WARNING, ERROR
- Sem dados sensíveis: CPF, CNPJ, senhas, tokens completos nunca são logados

**Exemplo**:
```python
logger.info(
    "Flow run created",
    extra={
        "request_id": request_id,
        "tenant_id": str(tenant_id),
        "flow_run_id": str(flow_run_id),
        "correlation_id": str(correlation_id),
    }
)
```

### Tracing Distribuído

O sistema suporta tracing distribuído via `RuntimeTracerPort`:

**Implementação**: `LangfuseRuntimeTracer` (integração com Langfuse)

**Funcionalidades**:
- `start_flow_trace()`: Inicia trace de flow
- `start_node_span()`: Inicia span de node
- `start_llm_generation()`: Inicia geração LLM com métricas
- `start_guardrail_span()`: Inicia span de guardrail
- `flush()`: Flush de eventos pendentes
- `shutdown()`: Shutdown graceful

**Arquivo**: `src/domain/execution/ports/runtime_tracer.py`

### ExecutionEventHook para Eventos de Execução

Sistema de hooks para eventos de execução:

**Interface**: `ExecutionEventHook` (ABC)

**Implementação**: `DbExecutionEventHook` (persiste eventos no banco)

**Métodos**:
- `on_flow_start()`: Flow iniciado
- `on_node_start()`: Node iniciado
- `on_node_complete()`: Node completado
- `on_edge_evaluated()`: Edge avaliado
- `on_flow_complete()`: Flow completado
- `on_flow_failed()`: Flow falhou

**Integração**: Hooks são injetados no `RuntimeExecutor` e `ExecutionService`

**Arquivo**: `src/domain/execution/services/observability/hooks.py`

### Integração com Langfuse

O sistema integra com Langfuse para observabilidade de LLM:

- **Traces**: Rastreamento de execuções de flow
- **Spans**: Rastreamento de nodes e operações
- **Generations**: Rastreamento de chamadas LLM com métricas (tokens, custo, latência)
- **Observations**: Atualizações incrementais de observações

**Configuração**: Via variáveis de ambiente (Langfuse API key, host, etc.)

**Arquivo**: `src/adapters/observability/langfuse_runtime_tracer.py`

## Padrões de Comunicação

### Síncrono vs Assíncrono

**Síncrono**:
- APIs REST: Request/Response imediato
- Criação de FlowRun: Retorna imediatamente após criação (execução continua em background)
- Consultas: GET endpoints retornam dados imediatamente

**Assíncrono**:
- Execução de FlowRun: Executa em background após criação
- Eventos: ExecutionEvent são emitidos assincronamente
- Polling: Cliente pode fazer polling de status via `GET /flow-runs/{id}`

### Polling vs Streaming

**Polling**:
- Cliente faz requisições periódicas para verificar status
- Exemplo: `GET /flow-runs/{id}` para verificar status de execução
- Exemplo: `GET /execution-events?flow_run_id={id}` para listar eventos

**Streaming**:
- Atualmente não implementado
- Futuro: Server-Sent Events (SSE) para eventos em tempo real

### Retry e Circuit Breakers

**Retry**:
- ToolOrchestrator aplica retry com backoff exponencial
- Configurável por tool config
- Máximo de tentativas configurável

**Circuit Breakers**:
- `CircuitBreaker` para chamadas LLM
- Escopo: `{provider}:{tenant_id}`
- Previne sobrecarga quando provider está instável

**Arquivo**: `src/domain/llm/services/circuit_breaker.py`

## Referências

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Arquitetura do sistema
- [README.md](../README.md) - Visão geral e specs
- [RAG.md](./RAG.md) - Sistema RAG
