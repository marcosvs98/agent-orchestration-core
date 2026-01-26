## Planning (8) — Modelo de API, Contratos e Superfície Pública

Objetivo: **definir a superfície pública do serviço de forma explícita, previsível e segura**, permitindo integração por MCP Hosts e clientes externos sem ambiguidade. Aqui se evita acoplamento acidental e “API que vira domínio”.

---

### Tese central

A API **não é a aplicação**.
A API é um **contrato estável** sobre um core versionado.

Tudo que é exposto:
• é intencional
• é versionado
• pode ser auditado

---

### Princípios de API

• REST pragmático (sem purismo acadêmico)
• Versionamento por path (`/core/v1`)
• Tenant implícito via contexto de autenticação
• Idempotência explícita onde há efeito colateral
• APIs administrativas ≠ APIs de execução

---

### Separação de superfícies

**1. Control Plane (authoring / configuração)**
Usado por:
• painéis
• MCP Hosts
• automações de setup

Características:
• baixo volume
• altamente validado
• write-heavy

**2. Execution Plane (runtime)**
Usado por:
• canais
• webhooks
• workers

Características:
• alto volume
• baixa latência
• append-only

Misturar os dois é erro estrutural.

---

### Identidade e Tenant

Tenant **não vem no body nem na URL**.

Fonte única:
• token (JWT / API Key)
• contexto resolvido no gateway

Header:
• Authorization

Resultado:
• isolamento garantido
• zero risco de cross-tenant por bug de payload

---

### Convenção de recursos (exemplos)

Control Plane:
• `/flows`
• `/flows/{id}/versions`
• `/agents`
• `/tools`
• `/ai-policies`
• `/rag-configs`

Execution Plane:
• `/executions/flow-runs`
• `/executions/agent-runs`
• `/executions/events`

---

### Endpoints “placeholder”

Endpoints não implementados **existem e retornam 405**.

Motivo:
• guiar MCP Host
• documentar roadmap
• evitar interpretação criativa do modelo

OpenAPI é **fonte de verdade**, não código.

---

### Contratos de request/response

Regras:

• Schemas explícitos
• Nenhum campo implícito
• Enums fechados
• Erros padronizados

Erro sempre retorna:
• code
• message
• correlation_id

---

### Execução assíncrona

Execução nunca bloqueia canal.

Modelo:
• request cria `FlowRun`
• retorno imediato com `run_id`
• eventos posteriores via polling ou webhook

WhatsApp, HTTP, app → todos iguais.

---

### Observabilidade via API

Endpoints obrigatórios:
• listar runs
• buscar run por id
• eventos de execução
• estado atual do grafo

Nada de log scraping.

---

### Segurança

• Rate limit por tenant
• Scopes por tipo de operação
• APIs de execução separadas das de authoring
• Tool nunca acessa token do tenant diretamente

---

### Anti-patterns proibidos

• API “helper” sem contrato
• Endpoint que executa e configura ao mesmo tempo
• TenantId em query/body
• “endpoint mágico” que faz tudo

---
