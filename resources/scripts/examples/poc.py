import numpy as np
import faiss
from openai import OpenAI
from uuid import uuid4
from decouple import config

client = OpenAI(api_key=config("OPENAI_API_KEY", default="", cast=str))

# ---------------------------
# 1. Documentos simulados
# ---------------------------
documents = [
    {"id": str(uuid4()), "text": "Documento sobre pagamento digital."},
    {"id": str(uuid4()), "text": "Documento sobre regras de RAG."},
    {"id": str(uuid4()), "text": "Documento sobre OpenAI embeddings."},
]

# ---------------------------
# 2. Gerar embeddings Large (indexação)
# ---------------------------
large_embeddings = []
for doc in documents:
    resp = client.embeddings.create(model="text-embedding-3-large", input=doc["text"])
    emb = np.array(resp.data[0].embedding, dtype="float32")
    large_embeddings.append(emb)
large_embeddings = np.stack(large_embeddings)
doc_ids = [doc["id"] for doc in documents]

# Index FAISS full para embeddings large
index_large = faiss.IndexFlatIP(large_embeddings.shape[1])
faiss.normalize_L2(large_embeddings)
index_large.add(large_embeddings)

# ---------------------------
# 3. Redução dimensional para Small embeddings (retrieval)
# ---------------------------
target_dim = 1536
embeddings_small = large_embeddings[:, :target_dim].copy()
index_small = faiss.IndexFlatIP(target_dim)
faiss.normalize_L2(embeddings_small)
index_small.add(embeddings_small)

# ---------------------------
# 4. Embedding da query com small model
# ---------------------------
query = "Como funciona o pagamento digital?"
resp_query = client.embeddings.create(model="text-embedding-3-small", input=query)
query_embedding = np.array(resp_query.data[0].embedding, dtype="float32").reshape(1, -1)
faiss.normalize_L2(query_embedding)

# Truncar para target_dim
query_embedding_small = query_embedding[:, :target_dim]
faiss.normalize_L2(query_embedding_small)

# ---------------------------
# 5. Busca no index small
# ---------------------------
top_k = 2
distances, indices = index_small.search(query_embedding_small, top_k)
retrieved_ids = [doc_ids[i] for i in indices.flatten()]
print("Top docs IDs:", retrieved_ids)
print("Distâncias:", distances)

# ---------------------------
# 6. Recuperar embeddings large completos
# ---------------------------
retrieved_large_embeddings = large_embeddings[indices.flatten()]
print("Shape embeddings large:", retrieved_large_embeddings.shape)
