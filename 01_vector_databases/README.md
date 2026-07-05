# Module 01: Vector Databases

Learn keyword search, semantic embeddings, and hybrid retrieval for RAG applications.

## Overview

Vector databases are the core of modern retrieval-augmented generation (RAG) systems. This module teaches:

1. **Keyword Search**: BM25 for exact and near-exact matches
2. **Semantic Embeddings**: Neural models for meaning-based retrieval
3. **Similarity Search**: Find semantically related documents
4. **Chunking**: Split large documents into manageable pieces
5. **Hybrid Retrieval**: Combine keyword and semantic search
6. **RAG Pipeline**: Complete context-augmented generation flow

## Learning Path

### Part 1: Foundations (Keyword Search)

**[embeddings_basics.py](embeddings_basics.py)** - Understand TF-IDF keyword retrieval
- **Term Frequency (TF)**: How often a term appears in a document
- **Inverse Document Frequency (IDF)**: How rare a term is across all documents
- **TF-IDF Score**: `score = TF × IDF` (prioritizes specific, important terms)
- Exact and near-exact matching
- Ranking documents by relevance
- Clear output labels for understanding

Run: `python embeddings_basics.py`

### Part 2: Document Processing (Chunking)

**[chunking_strategies.py](chunking_strategies.py)** - Text splitting strategies
- Fixed-size chunking: Fast but may break mid-sentence
- Sentence-based: Respects sentence boundaries
- Recursive chunking (RECOMMENDED): Preserves document structure

Uses `chunking_utils.py` unified interface:
```python
from chunking_utils import chunk_text

chunks = chunk_text(text, strategy='recursive', chunk_size=500, overlap=50)
```

Run: `python chunking_strategies.py`

### Part 3: Advanced Retrieval (Hybrid Search)

**[hybrid_search.py](hybrid_search.py)** - Combine keyword and semantic search
- **Keyword Search (TF-IDF)**: Exact matching for identifiers (e.g., "CVE-2024-1234")
- **Semantic Search**: Neural embeddings for conceptual matching (e.g., "remote code execution")
- **Reciprocal Rank Fusion (RRF)**: Intelligent fusion combining both rankings

How it works:
```
TF-IDF Rankings        Semantic Rankings
       ↓                       ↓
[doc1, doc2, doc3]   [doc2, doc1, doc4]
       └────────────┬────────────┘
         RRF Fusion (formula: 1/(k+rank))
              ↓
      [doc1, doc2, doc4] ← Final ranking
```

RRF advantages:
- **No parameter tuning** (unlike weighted averages)
- **Robust** across different score scales
- **Rewards documents** appearing in both rankings
- Formula: `score = 1/(60 + rank_keyword) + 1/(60 + rank_semantic)`

Run: `python hybrid_search.py`

### Part 4: Complete Pipeline (RAG)

**[rag_pipeline.py](rag_pipeline.py)** - End-to-end RAG application
1. **Store**: Add vulnerability knowledge to vector database
2. **Retrieve**: Search for relevant documents
3. **Augment**: Build context-rich prompt
4. **Generate**: LLM answers informed by actual data

Uses `vector_store.py` SimpleVectorStore:
```python
from vector_store import SimpleVectorStore

db = SimpleVectorStore()
db.add_documents({"doc-1": "text...", "doc-2": "text..."})
db.index()
results = db.search("query", top_k=3)
```

Run: `python rag_pipeline.py`

## Shared Data

All examples in this module use the same unified CVE data source (`utils/data/cves.json`):

```python
from utils.data_loader import load_cves, get_cve_documents

# Load CVE vulnerability data
cves = load_cves()

# Get formatted documents for search/RAG
documents = get_cve_documents(cves)
```

This allows you to focus on learning search strategies without worrying about data setup.

## Reciprocal Rank Fusion (RRF)

The hybrid search implementation uses RRF instead of simple weighted averaging because:

1. **No Parameter Tuning**: RRF doesn't require weight adjustment (unlike 60/40 splits)
2. **Robust**: Works across different score scales without normalization
3. **Principled**: Based on information retrieval theory
4. **Educational**: Teaches modern production retrieval techniques

Formula: `score = 1/(k+rank_keyword) + 1/(k+rank_semantic)` where k=60

# Embed texts
embeddings = embedder.embed_texts(list_of_strings)    # Returns: np.ndarray
single_embedding = embedder.embed_text(single_string)  # Returns: np.ndarray

# Models:
# - all-MiniLM-L6-v2: Small, fast (384 dimensions)
# - all-mpnet-base-v2: Large, high quality (768 dimensions)
```

### chunking_utils.py - Document Splitting

```python
from chunking_utils import chunk_text

chunks = chunk_text(
    text,
    strategy='recursive',    # 'fixed', 'sentence', or 'recursive'
    chunk_size=500,          # Target size per chunk
    overlap=50               # Overlap between consecutive chunks
)
```

Strategies:
- **'fixed'**: Simple fixed-size (fast, may break concepts)
- **'sentence'**: Respect sentence boundaries (slower)
- **'recursive'**: Hierarchical splitting (RECOMMENDED, best preservation of structure)

### vector_store.py - Vector Database

```python
from vector_store import SimpleVectorStore

db = SimpleVectorStore()
db.add_document("doc-id", "Document text...")
db.add_documents({"id1": "text1", "id2": "text2"})
db.index()                          # Build embeddings
results = db.search("query", top_k=3)  # Returns: [{"id", "text", "similarity"}, ...]
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Pipeline                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Documents  ──→  Chunking  ──→  Embeddings  ──→  Storage    │
│                  (chunking_utils)  (semantic)  (DB)          │
│                                                               │
│                        ↓                                      │
│                    Query Input                               │
│                        ↓                                      │
│  BM25 + Semantic ──→  Search  ──→  Fuse  ──→  Retrieve     │
│  (hybrid)             (ranking)   (weight)  (context)        │
│                        ↓                                      │
│                      LLM (answer)                            │
│                                                               │
└─────────────────────────────────────────────────────────────┘

Core Components:
- semantic_embeddings.py: SemanticEmbedder (Sentence Transformers)
- chunking_utils.py: chunk_text() with 3 strategies
- vector_store.py: SimpleVectorStore (in-memory DB)
- hybrid_search.py: BM25 + Semantic fusion
```

## Exercises

### Easy

1. **Modify embeddings_basics.py**: Change search queries and observe BM25 scores. Try exact matches (e.g., "CVE-2024") vs conceptual searches.

2. **Chunking Strategy**: Run chunking_strategies.py and compare number of chunks and sizes for each strategy. Which breaks mid-sentence?

3. **Vector Store**: Create a custom knowledge base (not security) and search it using rag_pipeline.py.

### Medium

4. **Hybrid Search Weight**: In hybrid_search.py, modify the weights dict (0.3 keyword / 0.7 semantic vs 0.7 / 0.3). How do results change?

5. **Semantic vs Keyword**: Add a query to hybrid_search.py that has exact keyword matches (e.g., "CVE-2024") vs conceptual similarity (e.g., "buffer overflow"). How do results differ?

6. **Semantic Model Selection**: In hybrid_search.py, try both "all-MiniLM-L6-v2" and "all-mpnet-base-v2". What's the quality/speed tradeoff?

### Hard

7. **Production Vector Database**: Replace SimpleVectorStore with real ChromaDB/Pinecone. Keep the interface identical. What changes in import statements? What performance improvements do you see?

8. **Semantic Caching**: Cache embeddings for frequently-searched documents to avoid re-computing. Modify vector_store.py to persist embeddings to disk.

9. **Multi-Modal Embeddings**: Use sentence-transformers for multi-modal (text + image) embeddings. Support embedding images and searching across modalities.

10. **RAG Evaluation**: Add metrics to rag_pipeline.py: precision (are retrieved docs relevant?), recall (did we miss important docs?), BLEU score on LLM output.

## Running Examples

Set up environment first:

**Windows (PowerShell):**
```powershell
& .\venv\Scripts\Activate.ps1
$env:PYTHONPATH = "."

# Run examples in order
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search
python -m 01_vector_databases.rag_pipeline
```

**Linux/Mac (Bash):**
```bash
source venv/bin/activate
export PYTHONPATH="."

# Run examples in order
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search
python -m 01_vector_databases.rag_pipeline
```

## Key Concepts

### BM25 (Best Match 25)
- Industry standard for keyword/full-text search
- Probabilistic ranking function
- Considers term frequency, document length, term rarity
- Fast and interpretable, excellent for exact/near-exact matches
- Used by Elasticsearch, Lucene, most search engines

### Semantic Embeddings
- Transform text to vectors using neural models
- Captures meaning and context (not just keywords)
- Works well for synonyms and conceptual similarity
- Requires a model (e.g., Sentence Transformers)
- Slower than BM25 but much better for semantic understanding

### Cosine Similarity
- Measures angle between vectors (0° = identical, 90° = orthogonal)
- Ranges from -1 to 1 (typically 0 to 1 for normalized vectors)
- High similarity (0.9+) = semantically related
- Low similarity (0.1-) = semantically different

### BM25 (Best Matching 25)
- Probabilistic keyword search algorithm
- Accounts for term frequency, document length, term rarity
- Accounts for document length normalization
- Industry standard for search engines (Elasticsearch, Lucene)

### Hybrid Search
- Combines BM25 (keyword) + semantic (embedding) results
- BM25 finds exact matches, embeddings find conceptual matches
- Alpha parameter controls the balance (0.5 = equal weight)
- Useful for security: CVE IDs matter, but so does vulnerability concept

### Chunking Strategies
- **Fixed**: Simple, uniform, but breaks logical units
- **Sentence**: Respects boundaries, variable sizes
- **Recursive**: Best overall, preserves hierarchical structure
- Overlap preserves context across chunk boundaries

## Troubleshooting

### ImportError: cannot import name 'VectorEmbedder' from 'vector_utils'
**Solution**: Ensure PYTHONPATH is set to workspace root:
```powershell
$env:PYTHONPATH = "."
```

### ValueError: Index not built
**Solution**: Call `db.index()` before calling `db.search()`:
```python
db.add_documents(docs)
db.index()  # Build embeddings
results = db.search("query")
```

### similarity score is 0 for all documents
**Solution**: Check that embeddings have non-zero values. Ensure texts are meaningful (not empty or stop-words only). Debug with:
```python
embedder = VectorEmbedder()
embeddings = embedder.fit_transform(["SQL injection", "database attack"])
print(embeddings)  # Check values are non-zero
```

## Performance Notes

- **BM25**: O(vocabulary size + query terms). ~100K searches/sec on laptop.
- **Semantic Embeddings**: Model inference time + O(n) cosine similarity. ~1-10 searches/sec (model dependent).
- **Hybrid**: Combines both, ~1-10 searches/sec (semantic bottleneck).
- **Chunking**: Recursive is 2-3x slower than fixed, but preserves structure.

For production (1M+ docs), use:
- Pinecone, Weaviate, or Qdrant for vector indexing with FAISS
- Sentence-transformers (all-MiniLM-L6-v2 or all-mpnet-base-v2) for semantic embeddings
- BM25 or Elasticsearch for keyword search
- Hybrid approach with proper weight tuning for best results

## Next Steps

After mastering this module:
- **Module 02**: Learn agentic patterns (ReAct, Tool Use, LangGraph)
- **Module 03**: Add advanced workflows (multi-step retrieval, reranking)
- **Module 04**: Add observability (logging, tracing) to RAG pipelines
- **Production**: Scale with Pinecone, add caching, implement reranking


✅ Respeita estrutura do documento (parágrafos inteiros quando possível)
✅ Cai para frases quando o parágrafo é grande
✅ Mantém contexto importante coeso
```

---
```

---

## 🎯 O que aprender daqui

| Arquivo | Conceito | Tempo | Objetivo |
|---------|----------|-------|----------|
| embeddings_basics.py | Vetores + Similaridade | 5 min | Entender a base |
| chunking_strategies.py | Divisão de documentos | 5 min | Preparar dados |
| rag_pipeline.py | RAG completo | 10 min | Fluxo end-to-end |

**Caminho de Aprendizado**:
```
1. Rodas embeddings_basics.py (entender vetores)
2. Rodar chunking_strategies.py (entender divisão)
3. Rodar rag_pipeline.py (entender RAG)
4. GANHO: Agora consegues usar em Módulo 01 (agentes)!
```

---

## ✅ Próximos Passos

- **Conceitos consolidados**? → Vá para **Módulo 03** (Observability)
- **Quer fazer RAG de verdade**? → Vá para **Módulo 04** (Databases)
- **Quer integrar com agentes**? → Volte para **Módulo 01** (LangGraph)

