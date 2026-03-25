# Embedding Orchestration Layer

Camada responsável por governar a geração de embeddings no pipeline RAG, separando decisão (selector), construção (builder) e execução (provider). O VectorStore define o contrato do índice (modelo, dimensão, métrica), enquanto o runtime apenas o respeita e valida. Garante consistência entre indexing e retrieval, permitindo otimização de custo/latência sem quebrar compatibilidade.

## Explicação objetiva:

O EmbeddingSelector sugere qual modelo usar com base no contexto do pipeline. Ele não executa nada, apenas aplica regra de negócio (custo vs qualidade vs latência), respeitando o contrato definido pelo VectorStore (fonte da verdade para indexing).

---

## Use cases:

#### indexing

* gerar vetores para armazenar no índice
* roda em batch/offline
* usa **exclusivamente o modelo definido no VectorStore**
* não passa pelo selector
* ex: text-embedding-3-large (3072 dim)

#### retrieval

* gerar vetor da query do usuário
* roda online (cada request)
* pode usar modelo otimizado (latência/custo)
* passa pelo selector
* **deve ser compatível com o modelo do índice**
* ex: text-embedding-3-small (1536 dim)

#### regra obrigatória

* retrieval deve ser compatível com o modelo do índice
* mesma dimensão ou mesma família
* validação ocorre em runtime

---

## Interfaces:

```python
class EmbeddingInferenceInterface:
    def embed(self, input: list[str], context: dict) -> list[list[float]]:
        return EmbeddingExecutor().execute(
            EmbeddingRequest(input=input, context=context)
        ).vectors
```

```python
class EmbeddingRequest:
    def __init__(
        self,
        input: list[str],
        context: dict,
        vector_store: VectorStore | None = None,
    ):
        self.input = input
        self.context = context
        self.vector_store = vector_store
```

```python
class EmbeddingExecutor:
    def __init__(
        self, 
        embedding_selector: EmbeddingSelector,
        embedding_builder: EmbeddingBuilder,
    ):
        self.embedding_selector = embedding_selector
        self.embedding_builder = embedding_builder
    
    async def execute(self, request: EmbeddingRequest) -> EmbeddingResponse:
        model = self.embedding_selector.select(request.context)

        # valida contra o modelo do índice
        if request.vector_store:
            if model.model_id != request.vector_store.embedding_model_id:
                raise Exception("embedding model mismatch with vector store")

        provider = self.embedding_builder.build(model)

        vectors = await provider.embed(request.input)

        if len(vectors[0]) != model.dimensions:
            raise Exception("invalid vector dimension")

        return EmbeddingResponse(
            vectors=vectors,
            model=model.name,
            dimensions=model.dimensions,
            ...
        )
```

```python
class EmbeddingSelector:
    def select(self, context: dict) -> EmbeddingModel:
        # prioridade: modelo explícito do contexto (ex: vindo do VectorStore)
        if context.get("vector_store_model"):
            return context["vector_store_model"]

        use_case = context.get("use_case")

        if use_case == "retrieval":
            return EmbeddingModel(
                name="text-embedding-3-small",
                provider="openai",
                dimensions=1536
            )

        # fallback padrão
        return EmbeddingModel(
            name="text-embedding-3-small",
            provider="openai",
            dimensions=1536
        )
```

```python
class EmbeddingBuilder:
    def build(self, model: EmbeddingModel) -> EmbeddingProvider:
        if model.provider == "openai":
            return OpenAIEmbeddingProvider(model)

        raise Exception("provider not supported")
```

```python
class EmbeddingProvider:
    async def embed(self, input: list[str]) -> list[list[float]]:
        raise NotImplementedError
```

```python
class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model: EmbeddingModel):
        self.model = model

    async def embed(self, input: list[str]) -> list[list[float]]:
        ...
```

---

## Pontos críticos no design:

* sempre batch (list[str])
* validar dimensão
* validar compatibilidade com VectorStore
* versionar modelo no índice
* retry + timeout (embedding vira gargalo fácil)

---

## Regras estruturais:

* VectorStore (RagIndex) fixa:
  → modelo de embedding
  → dimensão
  → métrica

* RagDocument NÃO decide nada
  → só armazena vetor + conteúdo

* Selector NÃO define indexing
  → apenas sugere para retrieval

* version no index permite:
  → reindexação sem downtime
  → trocar modelo com rollout controlado

* embedding_models separado evita poluir LLM config

---

