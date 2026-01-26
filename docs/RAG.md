# Sistema RAG - Retrieval-Augmented Generation

## Visão Geral do Sistema RAG

O sistema RAG (Retrieval-Augmented Generation) no **agent-orchestration-core** é uma **capability opcional** que enriquece a entrada para IA com contexto relevante recuperado de um vector store. RAG é usado para melhorar a qualidade das respostas de IA sem substituir a lógica de negócio ou estado do sistema.

### O que é RAG no Contexto do Sistema

RAG permite que agentes cognitivos acessem informações contextuais relevantes durante a execução de tarefas de IA. O sistema recupera documentos similares de um vector store e os inclui como contexto adicional no prompt enviado ao LLM.

**Características Principais**:
- **Opcional**: RAG só é usado quando explicitamente configurado
- **Contexto Auxiliar**: RAG fornece contexto, não é fonte de verdade
- **Versionado**: Configurações RAG são versionadas e imutáveis após publicação
- **Multi-Tenant**: Cada tenant pode ter suas próprias configurações RAG
- **Restrito por Task**: RAG só é permitido para AITasks compatíveis

### Quando RAG é Usado

RAG é usado quando:

1. **AgentVersion** tem `rag_config_id` associado
2. **AITask** é compatível com RAG (ver lista abaixo)
3. **RagConfig** está no status `PUBLISHED`
4. **VectorStore** referenciado existe e está acessível

**AITasks Compatíveis** (RAG permitido):
- `IntentDetection`: Detecção de intenção com exemplos históricos
- `SlotFilling`: Preenchimento de slots com catálogos e glossários
- `ResponseFormatting`: Formatação de resposta com documentação e FAQ

### Quando RAG é Bloqueado

RAG é **bloqueado** para os seguintes AITasks:

- `ContentModeration`: Moderação de conteúdo não deve usar contexto externo
- `FlowDecision`: Decisão de fluxo não deve depender de RAG
- `ExecutionControl`: Controle de execução não deve usar RAG

**Validação**: O sistema valida essas restrições em `ExecutionService.create_agent_run()` e lança `RagNotAllowedException` se RAG for usado com AITask incompatível.

**Arquivo**: `src/domain/execution/services/execution_service.py` (linhas 441-448)

### RAG não é Memória

**Regras Duras**:

- RAG **não substitui GraphState**: Estado de execução fica no banco relacional
- RAG **não carrega histórico de execução**: Não é usado para memória de conversação
- RAG **não contém decisão canônica**: Decisões ficam no banco, não em embeddings
- RAG **não é fonte de verdade**: Banco relacional é a fonte de verdade

Se algo muda o comportamento do fluxo, **tem que estar no banco relacional**.

**Embedding é contexto. Banco é verdade.**

## Componentes do Sistema RAG

### VectorStore

**Responsabilidade**: Armazenamento vetorial de documentos para busca semântica.

**Características**:
- Tabela global (sem `tenant_id`)
- Cada vector store tem um `name` opcional
- Vector stores são pré-configurados no sistema
- Listagem disponível via API

**Artefato**:
```python
class VectorStore(BaseModel):
    id: UUID
    name: str | None = None
```

**Arquivo**: `src/domain/rag/schemas/rag.py`

### RagConfig

**Responsabilidade**: Configuração RAG por tenant, versionada e imutável após publicação.

**Características**:
- **Multi-Tenant**: Cada tenant pode ter múltiplas configurações
- **Versionado**: Semantic versioning (major.minor.patch)
- **Imutável**: Versões publicadas não podem ser alteradas
- **Flexível**: Campo `options` (JSONB) para configurações específicas do vector store

**Campos**:
- `rag_config_id`: UUID único
- `tenant_id`: UUID do tenant (obrigatório)
- `vector_store_id`: UUID do vector store (obrigatório)
- `options`: JSONB com configurações específicas (ex: top_k, similarity_threshold)
- `status`: Estado da versão (`DRAFT`, `VALIDATED`, `PUBLISHED`, `DEPRECATED`, `DISABLED`)
- `version_major`, `version_minor`, `version_patch`: Versionamento semântico
- `config_hash`: Hash da configuração para reprodutibilidade
- `created_by`: ID do principal que criou

**Artefato**:
```python
class RagConfig(BaseModel):
    id: UUID
    vector_store_id: UUID
    options: dict[str, object] | None = None
    status: str
    version_major: int
    version_minor: int
    version_patch: int
    config_hash: str | None = None
```

**Arquivo**: `src/domain/rag/schemas/rag.py`

### Versionamento Semântico

RagConfig segue **semantic versioning** com lógica híbrida:

- **Com `source_version_id`**: Deriva versão da versão fonte (incrementa patch)
- **Sem `source_version_id`**: Auto-incrementa patch da última versão do tenant
- **Unicidade**: Constraint `uq_rag_config_semver` garante unicidade por tenant + semver

**Estados de Versão**:
- `DRAFT`: Rascunho, pode ser editado
- `VALIDATED`: Validado, pronto para publicação
- `PUBLISHED`: Publicado, imutável, pode ser usado em execuções
- `DEPRECATED`: Depreciado, ainda pode ser usado mas com sinalização
- `DISABLED`: Desabilitado, não pode ser usado em execuções

**Arquivo**: `src/domain/rag/repositories/rag_repository.py`

## APIs e Endpoints

### Listar Configurações RAG

**Endpoint**: `GET /core/v1/rag-configs`

**Query Parameters**:
- `status_filter` (opcional): Lista de status para filtrar (ex: `["PUBLISHED"]`)
- `limit` (opcional): Limite de resultados (padrão: 200, máximo: 1000)

**Resposta**: Lista de `RagConfig`

**Autenticação**: Requer JWT Bearer Token com scope apropriado

**Exemplo**:
```bash
curl -X GET "https://api.example.com/core/v1/rag-configs?status_filter=PUBLISHED&limit=50" \
  -H "Authorization: Bearer <token>"
```

### Criar Configuração RAG

**Endpoint**: `POST /core/v1/rag-configs`

**Body**:
```json
{
  "vector_store_id": "uuid",
  "options": {
    "top_k": 5,
    "similarity_threshold": 0.7
  },
  "source_version_id": "uuid (opcional)",
  "version_major": 1,
  "version_minor": 0,
  "version_patch": 0
}
```

**Resposta**: `RagConfig` criado (status `DRAFT`)

**Autenticação**: Requer JWT Bearer Token com scope `rag:rag_config:create`

**Nota**: Criação gera evento de authoring `RAG_CONFIG_CREATED`

### Publicar Configuração RAG

**Endpoint**: `POST /core/v1/rag-configs/{rag_config_id}:publish`

**Body**:
```json
{
  "change_type": "PUBLISH",
  "justification": "Ready for production use"
}
```

**Resposta**: `RagConfig` atualizado (status `PUBLISHED`)

**Pré-requisitos**:
- Configuração deve estar em status `VALIDATED`
- Justification é obrigatória

**Autenticação**: Requer JWT Bearer Token com scope apropriado

**Nota**: Publicação gera evento de authoring `RAG_CONFIG_PUBLISHED`

### Depreciar Configuração RAG

**Endpoint**: `POST /core/v1/rag-configs/{rag_config_id}:deprecate`

**Body**:
```json
{
  "change_type": "DEPRECATE",
  "justification": "Replaced by new version"
}
```

**Resposta**: `RagConfig` atualizado (status `DEPRECATED`)

**Pré-requisitos**:
- Configuração deve estar em status `PUBLISHED`
- Justification é obrigatória

**Autenticação**: Requer JWT Bearer Token com scope apropriado

**Nota**: Depreciação gera evento de authoring `RAG_CONFIG_DEPRECATED`

### Desabilitar Configuração RAG

**Endpoint**: `POST /core/v1/rag-configs/{rag_config_id}:disable`

**Body**:
```json
{
  "change_type": "DISABLE",
  "justification": "Security issue found"
}
```

**Resposta**: `RagConfig` atualizado (status `DISABLED`)

**Pré-requisitos**:
- Configuração deve estar em status `PUBLISHED` ou `DEPRECATED`
- Justification é obrigatória

**Autenticação**: Requer JWT Bearer Token com scope apropriado

**Nota**: Desabilitação gera evento de authoring `RAG_CONFIG_DISABLED`

### Listar Vector Stores

**Endpoint**: `GET /core/v1/vector-stores`

**Resposta**: Lista de `VectorStore`

**Autenticação**: Requer JWT Bearer Token

**Nota**: Vector stores são globais (não filtrados por tenant)

**Arquivo**: `src/domain/rag/controllers/rag_controller.py`

## Fluxo de Uso

### 1. Criar RagConfig

```python
# 1. Criar configuração RAG
rag_config = await rag_service.create_rag_config(
    tenant_id=tenant_id,
    rag_config_create=RagConfigCreate(
        vector_store_id=vector_store_id,
        options={"top_k": 5, "similarity_threshold": 0.7},
        version_major=1,
        version_minor=0,
        version_patch=0,
    ),
    principal_id=principal_id,
)
# Status: DRAFT
```

### 2. Validar RagConfig

```python
# 2. Validar configuração (mudança de status para VALIDATED)
# Implementação futura: validação de configuração
```

### 3. Publicar RagConfig

```python
# 3. Publicar configuração
published_config = await rag_service.publish_rag_config(
    tenant_id=tenant_id,
    rag_config_id=str(rag_config.id),
    principal_id=principal_id,
    change_request=ChangeRequest(
        change_type="PUBLISH",
        justification="Ready for production",
    ),
)
# Status: PUBLISHED
```

### 4. Associar RagConfig a AgentVersion

```python
# 4. Associar RagConfig a AgentVersion (via AgentVersion.rag_config_id)
# Isso é feito durante criação/atualização de AgentVersion
agent_version = await agents_service.create_agent_version(
    agent_id=agent_id,
    agent_version_create=AgentVersionCreate(
        # ... outros campos
        rag_config_id=published_config.id,  # Associação
    ),
    principal_id=principal_id,
)
```

### 5. Usar RAG Durante Execução

Durante a execução de um `AgentRun`:

1. Sistema verifica se `AgentVersion.rag_config_id` está presente
2. Sistema valida que `AITask` é compatível com RAG
3. Sistema recupera `RagConfig` (deve estar `PUBLISHED`)
4. Sistema usa `RagConfig` para enriquecer contexto do LLM
5. Sistema executa LLM com contexto enriquecido

**Validações Durante Execução**:
- `RagConfig` deve existir
- `RagConfig` deve estar em status `PUBLISHED`
- `AITask` deve ser compatível (não bloqueado)
- `VectorStore` deve estar acessível

**Arquivo**: `src/domain/execution/services/execution_service.py` (método `create_agent_run`)

## Versionamento e Governança

### Lógica Híbrida de Versionamento

RagConfig suporta dois modos de versionamento:

**Modo 1: Derivação de Versão Existente**
```python
RagConfigCreate(
    source_version_id=existing_rag_config_id,  # Deriva desta versão
    # version_major, version_minor, version_patch são opcionais
    # Sistema incrementa patch automaticamente
)
```

**Modo 2: Nova Versão Independente**
```python
RagConfigCreate(
    # source_version_id não fornecido
    version_major=1,
    version_minor=0,
    version_patch=0,  # Sistema auto-incrementa se já existir 1.0.0
)
```

**Implementação**: `RagRepository.create_rag_config()` aplica lógica híbrida similar a Flows/Agents.

**Arquivo**: `src/domain/rag/repositories/rag_repository.py`

### Estados de Versão

**Transições Válidas**:
- `DRAFT` → `VALIDATED` → `PUBLISHED`
- `PUBLISHED` → `DEPRECATED`
- `PUBLISHED` → `DISABLED`
- `DEPRECATED` → `DISABLED`

**Regras**:
- Apenas versões `PUBLISHED` podem ser usadas em execuções
- Versões `DEPRECATED` ainda podem ser usadas (com sinalização)
- Versões `DISABLED` bloqueiam uso em execuções
- Versões publicadas são imutáveis

### Authoring Events

Todas as mudanças de governança geram eventos de authoring:

**Tipos de Eventos**:
- `RAG_CONFIG_CREATED`: Configuração criada
- `RAG_CONFIG_PUBLISHED`: Configuração publicada
- `RAG_CONFIG_DEPRECATED`: Configuração depreciada
- `RAG_CONFIG_DISABLED`: Configuração desabilitada

**Campos do Evento**:
- `tenant_id`: UUID do tenant
- `principal_id`: ID do principal que fez a mudança
- `change_type`: Tipo de mudança (CREATE, PUBLISH, DEPRECATE, DISABLE)
- `justification`: Justificativa obrigatória
- `resource_type`: "rag_config"
- `resource_id`: UUID da configuração

**Arquivo**: `src/domain/governance/repositories/authoring_event_repository.py`

## Exemplos de Uso

### Exemplo 1: Criar e Publicar RagConfig

```python
from domain.rag.schemas.rag import RagConfigCreate
from domain.common.schemas.change import ChangeRequest

# 1. Listar vector stores disponíveis
vector_stores = await rag_service.list_vector_stores()
vector_store_id = vector_stores[0].id

# 2. Criar configuração RAG
rag_config = await rag_service.create_rag_config(
    tenant_id=tenant_id,
    rag_config_create=RagConfigCreate(
        vector_store_id=vector_store_id,
        options={
            "top_k": 5,
            "similarity_threshold": 0.7,
            "max_tokens": 1000,
        },
        version_major=1,
        version_minor=0,
        version_patch=0,
    ),
    principal_id=principal_id,
)
print(f"Created RagConfig: {rag_config.id} (status: {rag_config.status})")

# 3. Publicar configuração
published_config = await rag_service.publish_rag_config(
    tenant_id=tenant_id,
    rag_config_id=str(rag_config.id),
    principal_id=principal_id,
    change_request=ChangeRequest(
        change_type="PUBLISH",
        justification="Ready for production use with IntentDetection tasks",
    ),
)
print(f"Published RagConfig: {published_config.id} (status: {published_config.status})")
```

### Exemplo 2: Associar RagConfig a AgentVersion

```python
from domain.agents.schemas.agents import AgentVersionCreate

# Criar AgentVersion com RagConfig associado
agent_version = await agents_service.create_agent_version(
    agent_id=agent_id,
    agent_version_create=AgentVersionCreate(
        ai_execution_policy_version_id=policy_version_id,
        rag_config_id=published_config.id,  # Associação RAG
        # ... outros campos
    ),
    principal_id=principal_id,
)
print(f"AgentVersion {agent_version.id} associated with RagConfig {published_config.id}")
```

### Exemplo 3: Usar RAG Durante Execução

```python
# Durante criação de AgentRun, o sistema automaticamente:
# 1. Valida que AgentVersion.rag_config_id existe
# 2. Valida que AITask é compatível (IntentDetection, SlotFilling, ResponseFormatting)
# 3. Recupera RagConfig (deve estar PUBLISHED)
# 4. Usa RagConfig para enriquecer contexto do LLM
# 5. Executa LLM com contexto enriquecido

agent_run = await execution_service.create_agent_run(
    tenant_id=tenant_id,
    endpoint="/core/v1/executions/agent-runs",
    idempotency_key="agent-run-123",
    payload=AgentRunCreate(
        agent_version_id=agent_version.id,
        ai_execution_policy_version_id=policy_version_id,
        # ... outros campos
    ),
)
# RAG é usado automaticamente se AgentVersion.rag_config_id estiver configurado
```

### Exemplo 4: Criar Nova Versão Derivada

```python
# Criar nova versão derivada de versão existente
new_config = await rag_service.create_rag_config(
    tenant_id=tenant_id,
    rag_config_create=RagConfigCreate(
        vector_store_id=vector_store_id,
        source_version_id=published_config.id,  # Deriva desta versão
        options={
            "top_k": 10,  # Mudança: aumentou top_k
            "similarity_threshold": 0.7,
        },
        # version_major, version_minor, version_patch são opcionais
        # Sistema incrementa patch automaticamente (1.0.0 -> 1.0.1)
    ),
    principal_id=principal_id,
)
print(f"Created derived RagConfig: {new_config.id} (version: {new_config.version_major}.{new_config.version_minor}.{new_config.version_patch})")
```

## Referências

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Arquitetura do sistema
- [COMMUNICATION.md](./COMMUNICATION.md) - Padrões de comunicação
- [README.md](../README.md) - Visão geral e specs
- Planning (11) - IA: Prompts, Políticas, RAG e Responsabilidades
