## Planning (7) — Versionamento, Compatibilidade e Evolução Controlada

Objetivo: **permitir evolução contínua do sistema sem quebrar execuções passadas, contratos ou auditoria**. Aqui se evita o caos típico de “mudou o flow e tudo quebrou”.

---

### Tese central

Nada é mutável depois de publicado.
Tudo que executa **executa contra uma versão imutável**.

Versionamento não é detalhe técnico. É pilar do produto.

---

### O que é versionado (obrigatório)

• Flow
• Node
• Agent
• AIExecutionPolicy
• ToolConfig
• RagConfig

Se influencia execução → tem versão.

---

### Regra de ouro

**Execução sempre referencia versões explícitas.**

Nunca:
• “flow atual”
• “agent default”
• “latest”

Sempre:
• flow_version_id
• agent_version_id
• policy_version_id

---

### Modelo de versionamento

• Versões são **append-only**
• Não há update in-place
• Nova versão = novo registro

Estado antigo nunca é reescrito.

---

### Publicação

Estados canônicos de versão:

• DRAFT
• PUBLISHED
• DEPRECATED
• DISABLED

Regras:
• DRAFT não executa
• PUBLISHED executa
• DEPRECATED executa, mas não é default
• DISABLED nunca executa

---

### Compatibilidade

Compatibilidade é **declarada**, não inferida.

Exemplos:
• FlowVersion declara compatibilidade mínima de AgentVersion
• AgentVersion declara compatibilidade de ToolConfig
• ToolConfig declara schema_version suportado

Sem match → erro explícito, não fallback mágico.

---

### Breaking changes

Breaking change **sempre gera nova versão maior**.

Nunca:
• alterar schema de input/output de versão publicada
• alterar semântica de execução

Permitido:
• adicionar campos opcionais
• otimizações internas sem efeito externo

---

### Migração

Migração **não é automática em runtime**.

Modelos:
• Execuções antigas continuam com versões antigas
• Novas execuções usam versão nova
• Migração é decisão de negócio, não técnica

Ferramentas de migração existem, mas são explícitas.

---

### Rollback

Rollback = **selecionar versão anterior**, nunca desfazer código.

Pré-requisito:
• versões antigas sempre disponíveis
• artefatos nunca deletados

---

### Auditoria

Toda execução registra:
• versão exata de cada artefato
• hash de configuração relevante

Auditoria é reproduzível.

---

### Anti-patterns proibidos

• “editar versão publicada”
• “hotfix silencioso”
• “latest em produção”
• “migração automática implícita”

---
