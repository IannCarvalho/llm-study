# 🗄️ Módulo 4: RAG Databases

## Contexto: Dados Unificados

Ambos os scripts usam o mesmo data source: `utils/data/cves.json` (CVE database unificado).

```python
from utils.data_loader import load_cves, get_cve_documents

cves = load_cves()
documents = get_cve_documents(cves)  # Formatted for RAG
```

Isso permite comparar diferentes vector databases sem lidar com setup de dados.

---

## O que está aqui?

Dois vector databases mais usados em produção para RAG:

### 1. **chroma_rag.py** — MVP Local ⭐
```
Quando usar: Prototipar, desenvolver, testar localmente
Setup: pip install chromadb
Características:
  ✅ Zero setup
  ✅ Funciona offline
  ✅ Perfeito para prototipagem
  ❌ Não escala para produção
```

### 2. **pinecone_rag.py** — Produção Cloud
```
Quando usar: Aplicações em produção, escala
Setup: 
  1. Conta em https://www.pinecone.io
  2. pip install pinecone-client
  3. PINECONE_API_KEY no .env
Características:
  ✅ Managed (sem administração)
  ✅ Escalável (bilhões de vetores)
  ✅ Rápido (índices otimizados)
  ❌ Requer API key
  ❌ Custo mensal
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
# 2. Criar índice chamado "qubika-rag" no Pinecone
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
