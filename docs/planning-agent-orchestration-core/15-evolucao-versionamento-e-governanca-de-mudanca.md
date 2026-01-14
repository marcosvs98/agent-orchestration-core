## Planning (15) — Estratégia de Evolução, Versionamento e Governança de Mudança

Objetivo: **evoluir o sistema sem quebrar execução ativa, contratos externos ou rastreabilidade histórica**.

Mudança sem governança = runtime instável + auditoria frágil.

---

### Tese central

Runtime **nunca aponta para algo mutável**.
Qualquer alteração relevante **materializa uma nova versão endereçável**.

Versionamento não é feature; é fundação.

---

### Princípio de ouro

> *Execução sempre referencia um snapshot fechado.*
> *Authoring sempre ocorre fora do runtime.*

---

### O que é versionado (escopo obrigatório)

Cada item abaixo gera **entidade versionada própria**, com ID imutável:

• Flow (orquestração lógica)
• Node Graph (topologia + edges)
• Agent (configuração + bindings)
• Prompt (conteúdo + parâmetros)
• AIExecutionPolicy (limites, custos, regras)
• Onboarding / Instruction set
• Tool Schema (derivado do OpenAPI, normalizado)

Nenhum desses aceita update direto após publicação.

---

### Imutabilidade operacional

Uma versão publicada é:

• somente leitura
• referenciada explicitamente (FK forte)
• reexecutável no futuro
• auditável isoladamente

Correção, ajuste ou melhoria **sempre = nova versão**.
Não existe “patch rápido”.

---

### Estados de versão (lifecycle)

Cada versão percorre estados explícitos:

1. **Draft**
   • editável
   • não executável
   • sem garantia de consistência

2. **Validated**
   • schema válido
   • policy aplicada
   • limites checados

3. **Published**
   • snapshot imutável
   • ainda não executável

4. **Active**
   • permitido para runtime
   • pode receber tráfego

Estados são persistidos.
Runtime só aceita **Active**.

---

### Publicar ≠ Ativar

Separação intencional.

• **Publish**: congela a versão
• **Activate**: expõe para execução

Permite:
• auditoria prévia
• rollout controlado
• ativação programada

Ativação nunca recompila nada.

---

### Estratégias de rollout

Ativação suporta regras explícitas:

• 100% do tráfego
• por tenant
• por canal (ex: WhatsApp, API)
• percentual (canary)
• regra condicional (policy-based)

Runtime resolve versão ativa por **regra**, não por código.

---

### Rollback seguro

Rollback não altera histórico.

Rollback =
• atualizar ponteiro de ativação
• runtime passa a usar versão anterior

Versões antigas:
• continuam íntegras
• continuam auditáveis
• continuam reexecutáveis

Zero migração. Zero risco.

---

### Compatibilidade de contrato

Regras claras:

• Tool schema é contrato público
• Backward-compatible é default
• Breaking change → nova versão obrigatória

O sistema **não tenta inferir compatibilidade**.
Compatibilidade é declarativa.

---

### Governança de mudança

Toda versão publicada registra:

• autor
• timestamp
• tipo de mudança (prompt, lógica, policy…)
• justificativa obrigatória

Eventos de publicação e ativação são auditáveis.

Sem justificativa → não publica.

---

### Validações estruturais obrigatórias

Antes de permitir **Publish**:

• validação de grafo (nós órfãos, edges inválidas)
• detecção de ciclos proibidos
• verificação de limites (tokens, runs, tempo)
• compatibilidade de schema
• policy enforcement

Falha em qualquer etapa → bloqueio hard.

---

### Execuções históricas

Execuções antigas:

• permanecem associadas à versão original
• nunca são migradas
• nunca “herdam” mudança nova

Histórico é imutável por definição.

---

### Migração de dados (quando existir)

Migração só ocorre em:
• modelos de authoring
• nunca em execution logs

Runtime e histórico são **write-once**.

---

### Anti-patterns explicitamente proibidos

• editar flow ativo
• hotfix direto em produção
• alterar prompt “porque é só texto”
• reapontar execução para versão mutável
• sobrescrever schema existente

Qualquer um desses quebra confiança do sistema.

---

### Resultado esperado do p15

• Runtime previsível
• Auditoria sólida
• Rollback instantâneo
• Evolução contínua sem medo
• Zero dependência de deploy para mudar comportamento

Versionamento aqui não é burocracia.
É o que permite escalar sem colapsar.
