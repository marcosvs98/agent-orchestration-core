## Planning (14) — Segurança, Limites e Hardening de Produção

Objetivo: **garantir que nenhum erro humano, input malicioso, prompt defeituoso ou comportamento probabilístico da IA resulte em vazamento de dados, violação de tenant, efeito colateral indevido ou custo não controlado**.

Segurança é **propriedade estrutural do sistema**, não feature opt-in.

---

## Tese central (formalizada)

Nenhuma camada confia na outra.
Nenhuma execução ocorre fora de policy.
Nenhuma ação sem identidade, escopo e limite.

Tudo opera com **menor privilégio possível**, sempre com **fail-closed**.

---

## Identidade — Fonte única de verdade

Dois e apenas dois tipos de principal:

• Usuário humano
• Cliente de API (machine / integration)

Características obrigatórias:

• OAuth2 como mecanismo de autenticação
• JWT assinado e verificável
• tenant_id obrigatório e imutável no token
• scopes explícitos e granulares
• exp, aud, iss validados sempre

Regras duras:

• Nenhum endpoint aceita identidade implícita
• Nenhum token “genérico” ou compartilhado
• Nenhuma execução sem principal resolvido

Identidade **não é inferida**, é exigida.

---

## Autorização — Policy-based, determinística

Autorização não é `if role == admin`.

Modelo:

Policy avalia, de forma explícita:

• principal
• tenant
• scope
• recurso
• ação

Exemplos claros:

• `flow:version:publish` → permitido
• `tool:invoke` → negado
• `agent:version:create` → permitido
• `agent:version:execute` → depende de policy

Regras:

• Fail-closed por padrão
• Negação gera evento auditável
• Nenhuma exceção silenciosa
• Policy versionada e rastreável

---

## Isolamento de tenant — Defesa em profundidade

Isolamento **obrigatório em três camadas independentes**:

### API

• tenant_id sempre derivado do token
• nunca do payload
• filtro implícito em todas as queries

### Banco

• FK explícita para tenant
• constraints estruturais
• impossibilidade física de cross-tenant

### Runtime

• GraphState isolado por FlowRun
• nenhum estado compartilhado
• nenhuma cache cross-tenant

Falha em uma camada **não vaza** a outra.

---

## Limites de execução — Guardrails não negociáveis

Limites são **dados**, não código.

Aplicados por policy:

• max nodes por FlowRun
• max NodeRuns por execução
• max AgentRuns por Interaction
• max ToolRuns por FlowRun
• max tokens por AgentRun
• max tempo total de execução

Objetivos:

• prevenir loops
• evitar DoS lógico
• controlar custo
• manter previsibilidade

Violação de limite:

• interrompe execução
• gera evento
• pode escalar

Nunca “continua porque parece ok”.

---

## IA sob contenção total

A IA opera em **sandbox lógico estrito**.

A IA **nunca recebe**:

• tokens reais
• secrets
• headers técnicos
• URLs internas
• respostas brutas sensíveis
• erros de infraestrutura

A IA:

• recebe input sanitizado
• produz output validado
• opera sob policy
• nunca executa efeito colateral

IA **opina**, não age.

---

## Validação de input e output — Zero tolerância

Tudo que cruza fronteira é validado por schema:

• Interaction (input externo)
• Output de Agent
• Resultado de Slot Filling
• Request de Tool
• Response normalizada de Tool

Se falhar:

• execução interrompida
• evento emitido
• estado consistente preservado

Nada segue em “best effort”.

---

## Secrets — Gestão profissional

Segredos:

• nunca no prompt
• nunca no banco
• nunca no código
• nunca no log

Modelo correto:

• Vault / Secret Manager
• resolução em runtime
• injeção mínima e pontual
• escopo restrito por ToolConfig

ToolConfig **referencia** segredo, não contém.

---

## Webhooks e canais — Superfície controlada

### Inbound

• validação de assinatura
• replay protection
• rate limit por origem
• idempotência por external_id

### Outbound

• timeout obrigatório
• retry com backoff
• circuit breaker
• isolamento por ToolConfig

Nenhuma chamada externa bloqueia o core.

---

## Rate limiting — Política, não infra

Rate limit aplicado por:

• tenant
• principal
• tipo de execução
• categoria de custo

Configurável por policy.
Auditável por evento.

---

## Falhas, escalonamento e encerramento

Erro não tratado **não existe**.

Toda falha:

• gera evento
• atualiza estado final
• respeita política
• pode escalar

Estados inconsistentes são proibidos.
Nada fica “pendurado”.

---

## Auditoria de segurança

Eventos mínimos de segurança:

• AuthFailed
• PolicyDenied
• LimitExceeded
• ValidationFailed
• SecretAccessed
• EscalationTriggered

Tudo correlacionado por FlowRun.
Tudo reproduzível.

---

## Anti-patterns proibidos (reforçados)

• lógica de segurança no adapter
• bypass de policy “temporário”
• secrets no prompt
• confiar na IA
• feature flag para desativar segurança
• exceção “só em produção”

Violou isso → incidente arquitetural.

---

## Fechamento executivo

Planning (14) define que:

• segurança não é opcional
• limite não é sugestão
• IA não é confiável
• tenant nunca vaza
• custo nunca explode por acidente
