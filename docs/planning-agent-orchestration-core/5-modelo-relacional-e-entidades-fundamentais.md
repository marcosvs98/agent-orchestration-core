## Planning (5) — Superfície de API e Contratos REST (Design-first, execução depois)

Objetivo: **expor tudo que existe no banco de forma explícita, versionada e governável**, permitindo que um MCP Host entenda o sistema apenas lendo contratos.

Aqui não se “desenha endpoint depois”.
O contrato **define o sistema**. Implementação é detalhe.

---

### Princípios de API

• REST estrito
• Versionamento explícito
• Recursos > ações
• Nenhuma decisão escondida em controller
• Endpoint pode existir sem implementação (405/501 é aceitável)

Base obrigatória:
`/core/v1/`

---

### Isolamento de Tenant

Tenant **não vai em path**. Vai em **contexto de segurança**.

Modelo recomendado:
• `Authorization: Bearer <token>`
• Token carrega `tenant_id`
• Headers opcionais apenas para tracing

Nunca:
• `/tenant/{id}/...`
• query param para tenant

Separação é **infra + auth**, não URL.

---

### Blocos de API (por domínio)

#### 1. Tenant & Governança

• GET /tenants/current
• GET /tenants/current/settings

Somente leitura em runtime.

---

#### 2. Flows (design-time)

• GET /flows
• POST /flows
• GET /flows/{id}
• GET /flows/{id}/versions
• POST /flows/{id}/versions

Flow nunca é alterado. Só versionado.

---

#### 3. Nodes & Routing

• GET /flows/{id}/versions/{vid}/nodes
• POST /nodes
• GET /routers
• POST /routers
• POST /routing-rules

Router e regra são dados, não código.

---

#### 4. Agents

• GET /agents
• POST /agents
• GET /agents/{id}/versions
• POST /agents/{id}/versions
• POST /node-agent-bindings

Sem binding implícito.

---

#### 5. Tools

• POST /tools/import-tools
• GET /tools
• POST /tool-configs
• POST /agent-version-tool-bindings

Importação cria tools **desabilitadas por default**.

---

#### 6. AI / Policies

• GET /ai-tasks
• POST /ai-execution-policies
• POST /ai-execution-policy-versions
• GET /models

Modelo nunca é inferido.

---

#### 7. RAG

• GET /rag-configs
• POST /rag-configs
• GET /vector-stores

RAG é capability declarada.

---

#### 8. Execução

• POST /flow-runs
• GET /flow-runs/{id}
• GET /flow-runs/{id}/graph-state
• GET /node-runs
• GET /agent-runs

Execução é auditável, nunca mutável.

---

#### 9. Onboarding

• GET /onboardings
• POST /onboardings
• POST /onboarding-runs
• GET /onboarding-runs/{id}

Onboarding segue o mesmo modelo de flow.

---

### Contratos antes da implementação

Para o MCP Host:

• Todo endpoint existe no OpenAPI
• Mesmo que retorne 405
• Schema de request/response já definido
• Erros padronizados

Isso permite:
• geração de tools
• simulação de chamadas
• reasoning estrutural

---

### Anti-patterns explicitamente proibidos

• Endpoint “faça_algo”
• Side-effect sem entidade
• Lógica de decisão em controller
• Estado transitório fora do banco
