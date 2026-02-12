# Glossario 

### Tenant Knowledge (memória organizacional)

**Características:**
Persistente.
Versionada (via RagConfig + RagPolicy).
Escopada por `tenant_id`.
Não depende de `user_id`.
Recuperada via RAG.
Usada quando `allow_rag_tenant_knowledge = true`.

**Conteúdo típico:**
Regras do plano financeiro.
Categorias padrão.
Políticas contábeis.
Limites por tipo de conta.
Convenções internas.
Documentação institucional.
FAQs do produto.

---

### User Preference (configuração explícita do usuário)

**Características:**
Estruturada (relacional).
Escopada por `tenant_id + user_id`.
Chave-valor determinístico.
Governada por MemoryPolicy.
Controla comportamento do agente.

**Conteúdo típico:**
Categoria padrão por palavra-chave.
Conta padrão (PF/PJ).
Moeda preferida.
Formato de resposta (resumido/detalhado).
Idioma.

---

### User Memory Profile (perfil agregado do usuário)

**Características:**
Estruturado.
Escopado por `tenant_id + user_id`.
Resultado de inferências consolidadas.
Pode ser atualizado por prioridade de source.
Não é episódico.

**Conteúdo típico:**
Banco mais utilizado.
Categorias recorrentes.
Padrão de horário de uso.
Perfil financeiro (ex.: foco em controle mensal).

---

### User Episodic Memory (memória vetorial do usuário)

**Características:**
Vetorial (RAG-backed).
Escopada por `tenant_id + user_id`.
TTL obrigatório.
Recuperação por similaridade + time-decay.
Governada por MemoryPolicy.

**Conteúdo típico:**
Observações declaradas pelo usuário.
Padrões aprendidos.
Contextos relevantes de decisões passadas.
Justificativas ou explicações longas.

---

### Session Context (memória de curto prazo)

**Características:**
Persistida via `graph_state`.
Escopada por `session_id`.
Multi-turn.
Não vetorial.
Sempre carregada quando há continuidade.

**Conteúdo típico:**
Slots já preenchidos.
Entidades resolvidas.
Referências anafóricas (“aquele”, “essa”).
Estado do fluxo atual.

---

### MemoryPolicy

**Características:**
Versionada.
Escopada por tenant.
Define:

* allowed_schemas
* allowed_sources
* retention_ttl
* prioridades de source
* regras de overwrite

Controla escrita e recuperação de memória.

---

### RagConfig

**Características:**
Define comportamento de retrieval vetorial.
Controla:

* top_k
* similarity_threshold
* half_life (time-decay)
* escopo (TenantKnowledge vs UserMemory)

Pode existir múltiplos por tenant.

---

### UserContextEnrichmentNode

**Características:**
Pode enriquecer state.
Pode controlar o que entra no prompt.
Respeita flags de AITask + Policy.
Não executa persistência.

---

### MemoryWriteService

**Características:**
Valida contra MemoryPolicy.
Roteia para:

* UserPreference
* UserMemoryProfile
* Vector Memory
  Emite eventos de auditoria.
  Determinístico.

---

### MemoryRetrievalService

**Características:**
Filtra por `tenant_id` e `user_id`.
Aplica TTL via `expires_at`.
Aplica similarity + time-decay.
Respeita flags da AITask.

---