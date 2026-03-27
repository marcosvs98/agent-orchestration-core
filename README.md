# agent-orchestration-core

Plataforma de orquestração cognitiva multi-tenant . Interpreta entrada em linguagem natural, decide caminhos de execução e aciona integrações externas de forma controlada, auditável e previsível.

---

## 1. Contexto da Aplicação

### Objetivo do Sistema

O **agent-orchestration-core** é uma plataforma que orquestra agentes cognitivos e fluxos de execução de forma determinística e auditável. O sistema permite:

- **Definição e versionamento** de fluxos, agentes, tools e políticas de IA
- **Execução determinística** de fluxos com rastreamento completo de estado
- **Integração controlada** com sistemas externos via tools
- **Governança multi-tenant** com isolamento estrutural por tenant
- **Observabilidade completa** via eventos de execução e tracing distribuído

### Problemas que Aborda

- **Orquestração de IA controlada**: IA não executa efeitos colaterais; apenas classifica, extrai, decide caminho e formata
- **Versionamento explícito**: Tudo é versionado e imutável após publicação; execuções sempre referenciam versões explícitas
- **Isolamento multi-tenant**: Isolamento estrutural por tenant desde a fundação
- **Reprodutibilidade**: Execuções são determinísticas e auditáveis; estado completo é rastreável
- **Separação authoring/runtime**: Definições são imutáveis; execução nunca altera definições

### Bounded Contexts / Subdomínios

| Subdomínio      | Função                                           | Tecnologias / Padrões                    |
| --------------- | ------------------------------------------------ | ---------------------------------------- |
| Execution       | Execução real de fluxos, rastreamento de estado | Python, FastAPI, Runtime Executor, DDD   |
| Flows           | Definição lógica de processos e versionamento    | Python, Graph Compiler, Semantic Version |
| Agents          | Definição de agentes cognitivos                 | Python, Versionamento, DDD               |
| Tools           | Contratos de integração externa                 | Python, OpenAPI Parser, HTTP Executor   |
| AI Policy       | Controle de execução de IA, modelos, limites    | Python, Versionamento, DDD               |
| RAG             | Recuperação de contexto para IA                 | Python, Vector Stores, Versionamento     |
| Onboarding      | Coleta estruturada de informações               | Python, Step Management, DDD             |
| Tenants         | Gerenciamento de tenants e configurações        | Python, JSONB Settings                   |
| Governance      | Autorização, limites, rate limiting             | Python, Policy Engine, Redis             |
| Prompts         | Gerenciamento de prompts dinâmicos              | Python, Versionamento                    |

### Modelo de Domínio

O sistema segue **Domain-Driven Design (DDD)** com separação clara entre **authoring** (design-time) e **runtime** (execution-time):

**Authoring (Design-Time)**:
- Definição e versionamento de artefatos (Flows, Agents, Tools, Policies, RAG Configs)
- Estados: `DRAFT`, `VALIDATED`, `PUBLISHED`, `DEPRECATED`, `DISABLED`
- Imutabilidade: versões publicadas não podem ser alteradas
- Governança: eventos de authoring para auditoria

**Runtime (Execution-Time)**:
- Execução de artefatos versionados (FlowRun, AgentRun, ToolRun)
- Estados de execução (CREATED, RUNNING, COMPLETED, FAILED)
- Append-only: execução nunca altera definições
- Rastreabilidade: eventos de execução para observabilidade
- **Runtime node types**: Execução usa tipos de node do `FlowGraphSnapshot` (ex: `IntentToolResolver`, `ResponseBuilder`, `QueryClarifier`, `HumanFallback`); não depende de registros `Node` ou `AITask` da tabela de authoring
- **Node/AITask opcionais**: Na fase atual, `Node` e `AITask` são opcionais para o ciclo de vida de `FlowVersion` (validate/publish/activate); validação baseia-se em `FlowGraphDraft` validado, não em registros `Node`

**Diretórios Principais**:
- `src/domain/<context>/` - Domínios organizados por contexto
- `src/adapters/` - Entradas e saídas do sistema
- `src/infra/` - Implementações técnicas substituíveis

Para detalhes completos, consulte [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 2. Arquitetura e Padrões

### Estilo Arquitetural

**Arquitetura Hexagonal (Ports & Adapters)** com **Domain-Driven Design (DDD)**:

- **Ports**: Interfaces que definem contratos (Protocol ou ABC)
- **Adapters**: Implementações concretas que conectam domínio ao mundo externo
- **Domain**: Lógica de negócio isolada, independente de frameworks

### Padrões Aplicados

- **Hexagonal Architecture**: Separação clara entre domínio e infraestrutura
- **Domain-Driven Design**: Organização por domínios de negócio, não por camadas técnicas
- **Repository Pattern**: Abstrações para persistência
- **Service Layer**: Lógica de negócio em services, não em controllers
- **Dependency Injection**: Gerenciamento de dependências via `dependency-injector`
- **Semantic Versioning**: Versionamento semântico híbrido para artefatos
- **Event Sourcing (parcial)**: ExecutionEvent e AuthoringEvent para auditoria
- **CQRS (parcial)**: Separação entre authoring (write) e consultas (read)

### Diagrama de Alto Nível

```mermaid
flowchart TB
    subgraph External["Mundo Externo"]
        HTTP[HTTP Clients]
        Webhooks[Webhooks]
    end

    subgraph Adapters["Adaptadores"]
        HTTPAdapter[HTTP Adapters]
    end

    subgraph Domain["Domínio"]
        Controllers[Controllers]
        Services[Services]
        Repositories[Repositories]
    end

    subgraph Infra["Infraestrutura"]
        Database[(PostgreSQL)]
        Redis[(Redis)]
        LLMProviders[LLM Providers]
    end

    External --> Adapters
    Adapters --> Controllers
    Controllers --> Services
    Services --> Repositories
    Services --> Ports[Ports/Interfaces]
    Repositories --> Database
    Ports --> Infra
    Infra --> Database
    Infra --> Redis
    Infra --> LLMProviders
```

Para diagramas detalhados, consulte [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## 3. Tecnologias Utilizadas

- **Python 3.12+**: Runtime moderno com type hints
- **FastAPI**: Framework REST API assíncrono
- **Pydantic v2**: Validação e serialização de dados
- **SQLAlchemy 2.0**: ORM para PostgreSQL
- **Alembic**: Migrações de banco de dados
- **PostgreSQL + PGVector**: Banco de dados relacional com suporte a vetores
- **Redis**: Cache, idempotência e rate limiting
- **Langfuse**: Observabilidade e tracing de LLM
- **httpx**: Cliente HTTP assíncrono para integrações
- **dependency-injector**: Gerenciamento de dependências
- **UV**: Gerenciador de dependências Python (substitui uv)
- **Docker / Docker Compose**: Containerização e orquestração
- **Makefile**: Automação de tarefas de desenvolvimento

---

## 4. Setup e Execução

### 4.1 Via Docker Compose

```bash
# Iniciar serviços (PostgreSQL, Redis, App)
docker compose up -d

# Ver logs da aplicação
docker compose logs -f app

# Parar serviços
docker compose down
```

### 4.2 Via Makefile

```bash
# Configurar pre-commit hooks
make pc-config

# Executar pre-commit hooks
make pc-run

# Executar pre-commit hooks em todos os arquivos
make pc-run-all

# Executar testes de validação (requer docker compose)
make validate-test
```

### 4.3 Configuração de Ambiente

Copiar arquivo de exemplo `.env` e ajustar variáveis conforme necessidade:

**Principais variáveis**:

- `DATABASE_URL` — conexão com PostgreSQL (ex: `postgresql+asyncpg://user:pass@host:5432/dbname`)
- `REDIS_URL` — conexão com Redis (ex: `redis://localhost:6379/3`). Scripts de demo (ex: `resources/scripts/examples/execute_flow_demo_direct.py`) beneficiam de Redis ativo para cache do repositório de execução; sem Redis, o cache falha em silêncio quando `CACHE_SILENT_MODE=true` (default).
- `JWT_SECRET` — chave secreta para validação de JWT
- `JWT_ISSUER` — issuer esperado nos tokens JWT
- `JWT_AUDIENCE` — audience esperado nos tokens JWT
- `LANGFUSE_PUBLIC_KEY` — chave pública do Langfuse (opcional)
- `LANGFUSE_SECRET_KEY` — chave secreta do Langfuse (opcional)
- `LANGFUSE_HOST` — host do Langfuse (opcional)

**Profile do demo**: Para comparar impacto de cache no demo (`resources/scripts/examples/execute_flow_demo_direct.py`), rode uma vez sem Redis (ou com cache desabilitado) e salve o profile (ex: `execute_flow_demo_direct_no_redis.prof`), depois com Redis ativo e salve (ex: `execute_flow_demo_direct_with_redis.prof`). Compare tempo em `session.execute`/`commit` e em métodos do repositório; com cache ativo espera-se redução de I/O e de chamadas ao repositório.

**Custo create_flow_run/executor**: O caminho create_flow_run carrega flow, flow_version e graph_snapshot uma vez por run e reutiliza o plano compilado (com cache por graph_hash). Os eventos de execução são persistidos em batch (buffer por flow_run_id, flush por tamanho ou ao fim do run), reduzindo transações. Para auditar chamadas por run, use o profile do demo (pstats) e inspecione contagens de `get_flow`, `get_flow_version`, `append_execution_event`/`flush_execution_events`.

**Nota**: O sistema usa **UV** para gerenciamento de dependências. Instale UV e execute:

```bash
# Instalar dependências
uv sync

# Ativar ambiente virtual
source .venv/bin/activate  # ou uv shell
```

---

## 5. Endpoints e Uso

### Control Plane (`/core/v1/*`)

**Authoring e Configuração**:

- **Tenants**: `GET /core/v1/tenants/current`, `GET /core/v1/tenants/current/settings`
- **Flows**: `GET /core/v1/flows`, `POST /core/v1/flows`, `GET /core/v1/flows/{id}`, `GET /core/v1/flows/{id}/versions`, `POST /core/v1/flows/{id}/versions`
- **Nodes & Routing**: `GET /core/v1/flows/{id}/versions/{vid}/nodes`, `POST /core/v1/nodes`, `GET /core/v1/routers`, `POST /core/v1/routers`, `POST /core/v1/routing-rules`, `POST /core/v1/condition-expressions`
- **Agents**: `GET /core/v1/agents`, `POST /core/v1/agents`, `GET /core/v1/agents/{id}/versions`, `POST /core/v1/agents/{id}/versions`, `POST /core/v1/node-agent-bindings`
- **Tools**: `POST /core/v1/tools/import-tools`, `GET /core/v1/tools`, `POST /core/v1/tool-configs`, `POST /core/v1/agent-version-tool-bindings`
- **AI Policy**: `GET /core/v1/ai-tasks`, `POST /core/v1/ai-execution-policies`, `POST /core/v1/ai-execution-policy-versions`, `GET /core/v1/models`
- **RAG**: `GET /core/v1/rag-configs`, `POST /core/v1/rag-configs`, `GET /core/v1/vector-stores`
- **Onboarding**: `GET /core/v1/onboardings`, `POST /core/v1/onboardings`, `POST /core/v1/onboarding-runs`, `GET /core/v1/onboarding-runs/{id}`, `GET /core/v1/onboardings/{id}/versions`

**Governança**:
- `POST /core/v1/{resource}/{id}:publish` — Publicar versão
- `POST /core/v1/{resource}/{id}:deprecate` — Depreciar versão
- `POST /core/v1/{resource}/{id}:disable` — Desabilitar versão
- `POST /core/v1/{resource}/{id}:activate` — Ativar versão (quando aplicável)
- `POST /core/v1/{resource}/{id}:rollback` — Rollback para versão anterior (quando aplicável)

### Execution Plane (`/core/v1/executions/*`)

**Runtime e Execução**:

- `POST /core/v1/executions/flow-runs` — Criar e executar FlowRun
- `GET /core/v1/executions/flow-runs/{id}` — Obter FlowRun
- `GET /core/v1/executions/flow-runs/{id}/graph-state` — Obter estado do grafo
- `POST /core/v1/executions/tool-runs` — Criar ToolRun
- `POST /core/v1/executions/tool-runs/{id}:execute` — Executar ToolRun
- `GET /core/v1/executions/execution-events` — Listar eventos de execução
- `GET /core/v1/executions/node-runs` — Listar NodeRuns
- `GET /core/v1/executions/agent-runs` — Listar AgentRuns

**Autenticação**: Todos os endpoints exigem JWT Bearer Token com claims obrigatórios (`tenant_id`, `principal_type`, `principal_id`, `scopes`).

**Idempotência**: POSTs no Execution Plane exigem header `Idempotency-Key`.

Para detalhes completos sobre APIs, consulte [COMMUNICATION.md](docs/COMMUNICATION.md).

### Observabilidade

- `/health` — Health check da aplicação
- `/openapi.json` — Especificação OpenAPI 3.0

---

## 6. Testes

### Instalação de Dependências de Desenvolvimento

```bash
# Usando UV
uv sync --dev

# Ativar ambiente virtual
source .venv/bin/activate
```

### Executar Testes

```bash
# Todos os testes
pytest

# Com cobertura
pytest --cov=src --cov-report=html

# Teste específico
pytest src/tests/domain/execution/test_execution_service.py

# Verbose
pytest -vv

# Com prints
pytest -s
```

### Cobertura de Testes

- **Cobertura mínima**: 80% para código crítico
- **Padrão AAA**: Arrange, Act, Assert (comentários opcionais quando código é autoexplicativo)
- **Testes isolados**: Cada teste é independente
- **Fixtures**: Setup comum em `conftest.py`

### Observações

- Fixtures e mocks devem ser usados para dependências externas
- Testes devem cobrir: validação de tenant, versionamento, fluxos de governança
- Infra deve ser mockada via ports
- Adapters devem ser testados por contrato

---

## 7. Versionamento e Governança

### Versionamento Semântico

Todos os artefatos versionados seguem **semantic versioning** (major.minor.patch) com **lógica híbrida**:

- **Com `source_version_id`**: Deriva versão da versão fonte (incrementa patch)
- **Sem `source_version_id`**: Auto-incrementa patch da última versão do escopo

**Artefatos Versionados**:
- `FlowVersion`, `AgentVersion`, `OnboardingVersion`
- `AIExecutionPolicyVersion`, `RagConfig`
- `ToolConfig` (com `schema_version` e `config_hash`)

### Controle de Mudanças

**Estados de Versão**:
- `DRAFT` → `VALIDATED` → `PUBLISHED` (imutável)
- `PUBLISHED` → `DEPRECATED` → `DISABLED`

**Eventos de Authoring**:
- `CREATE`: Criação de versão
- `PUBLISH`: Publicação de versão
- `ACTIVATE`: Ativação de versão (ponteiro ativo)
- `ROLLBACK`: Rollback para versão anterior
- `DEPRECATE`: Depreciação de versão
- `DISABLE`: Desabilitação de versão

Todos os eventos exigem `justification` obrigatória e são persistidos em `authoring_event` para auditoria.

### Políticas de Acesso

**Scope-based Authorization**:
- Scopes definidos em `src/domain/governance/schemas/scopes.py`
- Enforcement via `AccessPolicyService` no `ExecutionBoundary`
- Rate limiting via `RateLimitService` (Redis)
- Limites de execução via `ExecutionLimitService`

**Exemplos de Scopes**:
- `execution:flow_run:create`
- `flows:flow:list`, `flows:flow:create`
- `agents:agent:create`, `agents:agent_version:publish`
- `rag:rag_config:create`, `rag:rag_config:publish`

---

## 8. Dicionário de Dados / Glossário

| Entidade              | Descrição                                          | Relacionamento                                    |
| --------------------- | -------------------------------------------------- | ------------------------------------------------- |
| **Tenant**            | Isolamento estrutural por organização/cliente      | Raiz de isolamento; FK de Flow, Agent, ToolConfig |
| **Flow**              | Definição lógica de processo                       | Tenant 1:N Flows                                  |
| **FlowVersion**       | Versão imutável de um flow                         | Flow 1:N FlowVersions                             |
| **FlowRun**           | Execução concreta de uma versão de flow            | FlowVersion 1:N FlowRuns                          |
| **Node**              | Unidade executável dentro de um flow (opcional na fase atual) | FlowVersion 1:N Nodes (opcional para FlowRun)     |
| **AITask**            | Catálogo global de capacidades cognitivas (authoring) | Raiz (global); não usado diretamente pelo runtime  |
| **NodeRun**           | Execução de um node                                | FlowRun 1:N NodeRuns, Node 1:N NodeRuns           |
| **Agent**             | Definição lógica de agente cognitivo               | Tenant 1:N Agents                                 |
| **AgentVersion**      | Versão imutável de um agent                        | Agent 1:N AgentVersions                           |
| **AgentRun**          | Execução efetiva de um agent                       | AgentVersion 1:N AgentRuns, NodeRun 1:1 AgentRun  |
| **Tool**              | Contrato abstrato de integração externa            | Raiz (global)                                     |
| **ToolConfig**        | Configuração concreta de uma tool para um tenant   | Tool 1:N ToolConfigs, Tenant 1:N ToolConfigs      |
| **ToolRun**           | Execução de uma tool                               | ToolConfig 1:N ToolRuns                           |
| **AIExecutionPolicy** | Política de execução de IA                         | Raiz (global)                                     |
| **AIExecutionPolicyVersion** | Versão imutável de política de IA          | AIExecutionPolicy 1:N Versions                    |
| **RagConfig**         | Configuração RAG por tenant                         | Tenant 1:N RagConfigs, VectorStore 1:N RagConfigs |
| **Onboarding**       | Definição de processo de onboarding                | Tenant 1:N Onboardings                            |
| **OnboardingVersion** | Versão imutável de onboarding                  | Onboarding 1:N OnboardingVersions                |
| **OnboardingRun**    | Execução de um onboarding                          | OnboardingVersion 1:N OnboardingRuns             |
| **StepRun**          | Execução de um step dentro de onboarding run       | OnboardingRun 1:N StepRuns                       |
| **ExecutionEvent**    | Evento de execução (append-only)                   | FlowRun 1:N ExecutionEvents                       |
| **AuthoringEvent**    | Evento de governança (mudanças de versão)          | Recurso 1:N AuthoringEvents                        |
| **GraphState**       | Estado consolidado da execução de um flow          | FlowRun 1:1 GraphState                            |
| **Session**          | Contexto técnico de interação                      | Tenant 1:N Sessions                               |
| **Interaction**     | Evento de entrada persistido                       | Session 1:N Interactions, FlowRun 0:1 Interaction |

**Diretórios de Código**:
- Modelos ORM: `src/infra/database/models/`
- Schemas Pydantic: `src/domain/<context>/schemas/`
- Repositories: `src/domain/<context>/repositories/`

---

## 9. Referências

### Documentação Interna

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arquitetura detalhada do sistema
- [COMMUNICATION.md](docs/COMMUNICATION.md) - Padrões de comunicação entre serviços
- [RAG.md](docs/RAG.md) - Sistema RAG (Retrieval-Augmented Generation)
- [UNIMPLEMENTED_COMPONENTS.md](UNIMPLEMENTED_COMPONENTS.md) - Componentes pendentes de implementação

### Arquitetura e Padrões

- [Hexagonal Architecture](https://herbertograca.com/2017/11/16/explicit-architecture-01-ddd-hexagonal-onion-clean-cqrs-how-i-put-it-all-together/)
- [Domain Driven Design - Blue Book](https://lyz-code.github.io/blue-book/architecture/domain_driven_design/)
- [Repository Pattern](https://lyz-code.github.io/blue-book/architecture/repository_pattern/)
- [Service Layer Pattern](https://www.cosmicpython.com/book/chapter_04_service_layer.html)

### Tecnologias

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic v2](https://docs.pydantic.dev/)
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/)
- [Alembic](https://alembic.sqlalchemy.org/)
- [UV Package Manager](https://github.com/astral-sh/uv)

---

## Princípios Não Negociáveis

1. **Isolamento por tenant é estrutural**: Todo dado, decisão e execução pertence a um tenant. Tenant vem do contexto de segurança.
2. **Definição é diferente de execução**: Flows e agentes são definidos e versionados; execuções são rastreáveis e auditáveis e nunca alteram a definição.
3. **IA não executa efeitos colaterais**: IA apenas classifica/extrai/decide caminho/formata; side-effects são determinísticos fora da IA.
4. **Tudo é explícito e versionado**: Fluxos, agentes, prompts, políticas, ferramentas e decisões têm versão.
5. **Canal é detalhe de entrada e saída**: O core é agnóstico ao meio de interação.

---

## O que este Serviço Não É

- Não é um chatbot
- Não é um assistente genérico
- Não é um wrapper de LLM
