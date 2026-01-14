## Planning (19) — Validação, Compilação e Snapshot do Flow Graph

Objetivo: **garantir que apenas grafos estruturalmente válidos, determinísticos e reexecutáveis cheguem ao runtime**.

Runtime não valida grafo.
Runtime executa **snapshot compilado**.

---

### Tese central

Grafo configurável **não é** grafo executável.

Antes de qualquer execução, o grafo deve ser:
• validado
• compilado
• congelado

O resultado é um **artefato imutável**, versionado e auditável.

---

### Posição na arquitetura

Este planning vive **entre**:
• P15 (versionamento e governança)
• P17 (configuração de grafo)
• P18 (semântica de execução)

Ele fecha o ciclo de authoring.

---

## Pipeline de publicação do grafo

### Estados formais do grafo

1. DRAFT
   Grafo editável, sem garantias.

2. VALIDATED
   Estruturalmente válido, mas ainda mutável.

3. COMPILED
   Compilado em snapshot determinístico.

4. ACTIVE
   Elegível para execução pelo runtime.

Publish ≠ Activate continua válido.

---

## Validação estrutural (fail-fast)

Executada na transição **DRAFT → VALIDATED**.

### Regras obrigatórias

• existe exatamente 1 StartNode
• existe ao menos 1 ResponseNode ou FallbackNode
• todo node é alcançável a partir do Start
• não existem nós órfãos
• não existem edges sem condição
• não existem edges com condição inválida
• não existem dois edges válidos simultaneamente para o mesmo node (regra P18)
• ciclos só são permitidos se explicitamente marcados como LOOP

Falhou qualquer regra → validação abortada.

Nada segue adiante.

---

## Compilação do grafo

Executada na transição **VALIDATED → COMPILED**.

### O que significa compilar

Compilar **não é** gerar código.

Compilar é:
• resolver referências
• congelar estrutura
• pré-processar decisões

---

### Transformações realizadas

1. Normalização
   • IDs substituem nomes
   • edges recebem ordem explícita
   • defaults são materializados

2. Pré-parse das condições
   • DSL de edge é parseada
   • AST é gerado
   • erros sintáticos morrem aqui

3. Resolução de contratos
   • input/output de cada node é verificado
   • edge só pode referenciar campos existentes

4. Congelamento
   • nenhuma dependência externa
   • nenhum lookup dinâmico

---

## Flow Graph Snapshot

Resultado da compilação.

### Propriedades

• imutável
• versionado
• referenciado por hash
• reexecutável
• auditável

Runtime **só enxerga isso**.

---

### Estrutura conceitual do snapshot

• snapshot_id
• flow_version_id
• graph_hash
• compiled_at
• nodes (flat, indexados)
• edges (resolvidos, ordenados)
• parsed_conditions (AST ou bytecode simples)
• metadata (autor, origem, policy)

---

## Hash e integridade

O snapshot gera um hash determinístico baseado em:
• nodes
• edges
• condições compiladas

Qualquer mudança → novo hash → nova versão.

Sem exceção.

---

## Persistência

Introdução de nova entidade:

**FlowGraphSnapshot**
• 1:1 com flow_version ativa
• somente leitura
• nunca atualizada, apenas criada

Grafo cru (editável) pode viver em:
• flow_graph_draft (opcional)
ou
• JSON versionado associado ao flow_version

Mas runtime ignora isso.

---

## Integração com versionamento (P15)

• snapshot só existe para flow_version publicada
• ativação aponta para snapshot_id
• rollback troca ponteiro
• histórico preservado

---

## Responsabilidade do runtime

Runtime:
• carrega snapshot
• executa nodes
• avalia AST de edge
• não valida
• não interpreta texto
• não faz fallback

Se snapshot não existe → falha imediata.

---

## Anti-patterns proibidos

• runtime avaliando DSL textual
• runtime resolvendo nomes
• runtime acessando grafo draft
• validação tardia
• “vamos deixar passar e ver no log”

---

## Resultado esperado do Planning (19)

Ao final deste planning, o sistema terá:

• Separação absoluta entre authoring e execução
• Garantia de previsibilidade em produção
• Base sólida para auditoria, replay e billing
• Rollback trivial e seguro
• Runtime simples e burro (como deve ser)

---

## Critério de conclusão

> Se um flow_version não possui FlowGraphSnapshot, ele **não pode executar**.

Aqui termina o planejamento estrutural do grafo.
Daqui em diante, qualquer problema é de execução — não de modelo.
