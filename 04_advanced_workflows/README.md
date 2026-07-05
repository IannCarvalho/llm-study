# Module 04: RAG with Production Databases

This module demonstrates RAG implementations using two production-grade vector databases.

## Overview

Both scripts use the same data source: `utils/data/cves.json` (CVE database).

```python
from utils.data_loader import load_cves, get_cve_documents

cves = load_cves()
documents = get_cve_documents(cves)  # Formatted for RAG
```

This allows you to compare different vector databases without managing separate data pipelines.

---

## Databases

### 1. Chroma — Local Development
```
Use case: Prototyping and local development
Setup: pip install chromadb
Features:
  - Zero configuration
  - Works offline
  - Ideal for rapid iteration
  - Not suitable for production at scale
```

### 2. Pinecone — Cloud Production
```
Use case: Production applications and scale
Setup:
  1. Create account at https://www.pinecone.io
  2. Install: pip install pinecone-client
  3. Add PINECONE_API_KEY to .env
Features:
  - Managed service (no administration)
  - Scales to billions of vectors
  - Optimized indexing
  - Requires API key and billing
```

---

## Testando

### Chroma (local, sem setup)
```bash
python 04_advanced_workflows/chroma_rag.py
```

### Pinecone (requer configuração)
```bash
# 1. Set PINECONE_API_KEY no .env
# 2. Create an index named "llm-study" in Pinecone
python 04_advanced_workflows/pinecone_rag.py
```

---

## Comparação

| Aspecto | Chroma | Pinecone |
|---------|--------|----------|
| **Setup** | Nenhum | Médio |
| **Custo** | Grátis | Pago |
| **Escala** | 100K docs | 1B+ docs |
| **Performance** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Melhor para** | MVP | Produção |

---

## Como cada um usa os dados

```python
# Ambos carregam CVEs da mesma fonte
from utils.data_loader import load_cves, get_cve_documents
documents = get_cve_documents(load_cves())

# Diferença:
# - Chroma: armazena localmente em data/chroma/
# - Pinecone: envia para cloud (requer API key)
```

---

## Migração Chroma → Pinecone

Quando começar com Chroma e escalar para Pinecone:

```python
# Chroma: Recuperar documentos
results = chroma_collection.get()

# Pinecone: Inserir mesmos documentos
for doc in results["documents"]:
    embedding = embedding_model.encode(doc)
    pinecone_index.upsert([(doc_id, embedding, metadata)])
```

Done! 🚀
