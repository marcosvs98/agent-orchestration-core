# Análise atual (formatada e consolidada)

---

## 1. RagChunk — ponto crítico

Estado atual:

```text
embedding
embedding_512
embedding_model
embedding_dimension
```

Problema:

```text
- governança de embedding no nível do dado
- inconsistência dentro do mesmo índice
- quebra garantias de retrieval
```

Risco prático:

```text
chunk A → 1536 (model X)
chunk B → 512  (model Y)
```

Impacto:

```text
- busca vetorial inconsistente
- degradação de ivfflat (dimensão fixa)
- tuning de recall comprometido
```

Direção:

```text
RagChunk NÃO decide embedding
→ responsabilidade do VectorStore
```

Manter:

```text
embedding (único)
```

Remover:

```text
embedding_512
embedding_model
embedding_dimension
```

---

## 2. VectorStore — gap estrutural

Estado atual:

```text
name
tenant_id
```

Faltando:

```text
embedding_model_id
dimension
metric
version
```

Impacto:

```text
- ausência de contrato do índice
- impossibilidade de validar runtime
- reindex sem controle
```

---

## 3. RagConfig — governança consistente

Pontos fortes:

```text
- versionamento semântico
- vínculo com chunking_rule e vector_store
- multi-tenant bem definido
```

Ajustes:

```text
- corpus_kind → enum real
- options → evitar uso genérico excessivo
```

---

## 4. RagChunkingRule — flexível e correto

Modelo:

```text
strategy + params (JSONB)
```

Ponto de atenção:

```text
config_hash → tornar NOT NULL se usado para deduplicação
```

---

## 5. RagDocument — orientado ao pipeline

Pontos fortes:

```text
embedding_status
embedding_attempts
erro
timestamps
```

Gap:

```text
relação indireta com VectorStore (via RagConfig)
```

Trade-off:

```text
funciona, mas aumenta acoplamento indireto
```

---

## 6. RagQueryCache — bom conceito, risco estrutural

Estado atual replica problema do RagChunk:

```text
embedding
embedding_512
embedding_model
embedding_dimension
```

Risco:

```text
- cache inconsistente com índice
- invalidação difícil após troca de modelo
```

Direção:

```text
- adicionar vector_store_id
- remover múltiplas dimensões
```

---

## 7. RagUsageCounter — consistente

Pontos positivos:

```text
- constraints corretos
- suporte a multi-scope
```

Atenção:

```text
- crescimento de cardinalidade
```

---

## 8. Gap estrutural — ausência de “chunk index” explícito

Hoje implícito em:

```text
RagChunk + VectorStore
```

Problema:

```text
falta de enforcement de contrato
```

---

## 9. Problema central do design

Situação atual:

```text
governança de embedding distribuída
```

Espalhado em:

```text
- RagChunk
- RagQueryCache
- (ausente no VectorStore)
```

Impacto:

```text
storage permite divergência
```

Desalinhamento com runtime:

```text
Selector decide modelo
→ storage não garante consistência
```

---

## 10. Ajuste mínimo (sem refactor massivo)

Direção:

```text
1. VectorStore como fonte da verdade:
   - embedding_model
   - dimension
   - metric

2. RagChunk:
   - 1 embedding único

3. RagQueryCache:
   - vincular a vector_store_id
   - alinhar dimensão

4. Runtime:
   - validar antes de persistir
```

---

## 11. Leitura executiva

Estado:

```text
+ forte em pipeline
+ maduro operacionalmente
- inconsistente no domínio vetorial
```

Risco aparece quando:

```text
- troca de modelo
- aumento de volume
- tuning de busca
```

---

## Problemas em rag_repository.py

---

### Caching — inconsistente

Aplicado:

```text
get_rag_config
```

Não aplicado:

```text
get_vector_store
get_chunking_rule
```

Direção:

```text
- cachear configs (baixo churn)
- evitar cache em dados operacionais
```

---

### Search — bem implementado

Pontos fortes:

```text
- filtros ricos
- multi-tenant
- suporte a user memory
- score derivado de distância
```

Ajustes:

```text
1. similarity_threshold pós-query
→ mover para o banco

2. order_by distance
→ validar impacto com índice

3. JSONB intensivo
→ exigir índice GIN
```

---

## Sugestões objetivas

```text
1. Centralizar embedding no VectorStore
2. Remover dual embedding
3. Padronizar cache para configs
4. Reduzir lógica de dimensão no repository
5. Indexar JSONB crítico
```
