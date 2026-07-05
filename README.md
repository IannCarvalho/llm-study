# AI Engineering Study Repository: LangGraph, Vector Databases & Observability

A **completely free** educational repository for learning production AI engineering patterns.

- ✅ **Local LLM**: Ollama + Mistral (no API keys required)
- ✅ **Vector Database**: Chroma (local) + Pinecone (cloud-ready)
- ✅ **5 Learning Modules**: Vector Databases, Agentic AI, LangGraph, Advanced Workflows, Observability
- ✅ **Unified Data Source**: CVE vulnerability data across all examples
- ✅ **Modern Fusion**: Reciprocal Rank Fusion (RRF) for hybrid search
- ✅ **Centralized Utilities**: Reusable components in `utils/` folder
- ✅ **Practical Examples**: Production-ready Python with LangChain

---

## 📦 What's Inside

| Module | Topics | Files |
|--------|--------|-------|
| **01_vector_databases** | Embeddings, Chunking, RAG, Hybrid Search | embeddings_basics.py, chunking_strategies.py, hybrid_search.py, rag_pipeline.py |
| **02_agentic_ai_basics** | ReAct, Tool Use, Conversation Management | react_pattern.py, tool_use.py |
| **04_advanced_workflows** | RAG + Agents, Production DBs | chroma_rag.py, pinecone_rag.py, setup_pinecone.py |
| **05_observability** | LangSmith, LangFuse, Tracing & Debugging | langsmith_example.py, langfuse.py |
| **utils/** | 🎯 Shared utilities | 5 reusable modules |

---

## ⚡ Quick Start (5 minutes)

```powershell
# 1. Terminal 1: Start Ollama (keep running)
ollama serve

# 2. Terminal 2: Run example (starts with vector databases - the foundation)
cd c:\Users\carva\Desktop\qubika
venv\Scripts\activate
python 01_vector_databases/embeddings_basics.py
```

That's it! See embeddings and vector operations in action.

---

## Getting Started

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.ai) installed
- ~10GB free disk space

### Step 1: Configure Python

```powershell
cd c:\Users\carva\Desktop\qubika

# Create virtual environment (if needed)
python -m venv venv

# Activate
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Start Ollama

Open **a separate PowerShell** and run:

```powershell
# Download model (first time only)
ollama pull mistral

# Start server (keep it running)
ollama serve
```

You'll see:
```
Starting Ollama server...
Listening on 127.0.0.1:11434
```

✓ Ollama is ready!

### Step 3: Learn

In **another PowerShell**:

```powershell
cd c:\Users\carva\Desktop\qubika
venv\Scripts\activate

# Quick test
python verify_setup.py

# Run first example (vector databases - the foundation)
python 01_vector_databases/embeddings_basics.py
```

---

## Repository Structure

```
01_vector_databases/            # Embeddings & RAG
├── embeddings_basics.py
├── chunking_strategies.py
├── hybrid_search.py           # Semantic + keyword search with RRF
├── rag_pipeline.py            # Complete RAG workflow
└── README.md

02_agentic_ai_basics/           # Agent patterns
├── tool_use.py                # LLM calling tools
├── react_pattern.py           # ReAct: Thought → Action → Observe
└── README.md

03_langgraph/                   # LangGraph workflows
├── langgraph_basics.py        # Linear pipeline
├── langgraph_conditional.py   # Conditional routing
└── README.md

04_advanced_workflows/          # Vector DB implementations
├── chroma_rag.py              # Local vector DB
├── pinecone_rag.py            # Cloud vector DB
└── README.md

05_observability/               # LangSmith, LangFuse
├── langsmith_demo.py          # LangSmith tracing example
├── langfuse_demo.py           # LangFuse integration
└── README.md

data/
├── chroma/                    # Local Chroma database

utils/                          # 🎯 Shared utilities (centralized)
├── __init__.py
├── llm_client.py              # LLM integration (Ollama/OpenAI)
├── agentic_utils.py           # Agent utilities
├── semantic_embeddings.py     # Neural embeddings (Sentence Transformers)
├── chunking_utils.py          # Document splitting strategies
├── rag_pipeline.py            # RAG utilities
├── search.py                  # Search utilities
├── tools.py                   # Tool definitions
├── data_loader.py             # Data loading
├── models.py                  # Data models
├── constants.py               # Configuration constants
├── logging.py                 # Logging setup
├── config.py                  # Config management
├── data/
│   └── cves.json              # CVE database (unified data source)
└── prompts/                   # LLM prompts
    ├── assistant.txt
    ├── assistant_qa.txt
    ├── react.txt
    ├── tool_use.txt
    ├── langgraph.txt
    ├── rag.txt
    └── vulnerability_analysis.txt

requirements.txt                # Dependencies
README.md                       # This file
```

---

## 📊 Unified Data Source: CVE Database

All examples use a single, centralized CVE database (`utils/data/cves.json`) for consistency:

```python
from utils.data_loader import load_cves, get_cve_documents

# Load CVE data
cves = load_cves()

# Get formatted documents for RAG
documents = get_cve_documents(cves)
```

**Benefits:**
- ✅ Single source of truth
- ✅ Consistent data across all examples
- ✅ Easy to swap for production data
- ✅ Simplified setup and maintenance

---

## 🛠️ Utils Folder — Centralized Utilities

All shared utilities are organized in a single `utils/` folder for maximum code reuse:

**Why centralize?**
- ✅ Single source of truth for each utility
- ✅ Easy to find and reuse functions
- ✅ Consistent imports across all modules
- ✅ Easy to maintain and update

**Key components:**

| Utility | Purpose | Usage |
|---------|---------|-------|
| `llm_client.py` | LLM integration | `from utils.llm_client import get_llm_client` |
| `semantic_embeddings.py` | Embeddings + ranking | `from utils.semantic_embeddings import SemanticEmbedder` |
| `chunking_utils.py` | Document splitting | `from utils.chunking_utils import chunk_text` |
| `data_loader.py` | CVE data loading | `from utils.data_loader import load_cves` |
| `search.py` | Search utilities | `from utils.search import hybrid_search` |
| `tools.py` | Agent tools | `from utils.tools import search_cve` |

---

## LLM Configuration

All LLM calls use a centralized client (`utils.llm_client`) for consistency and easy switching between providers:

```python
from utils.llm_client import get_llm_client

# Get LLM client (singleton)
client = get_llm_client()

# For simple generation
response = client.generate("Your prompt here")
print(response)

# For chat conversations
response = client.chat(
    messages=[{"role": "user", "content": "Hello!"}],
    temperature=0.7,
    max_tokens=512
)
print(response)

# For LangChain LCEL chains
from langchain_core.prompts import ChatPromptTemplate
llm = client.get_chat_model()  # Returns LangChain ChatOpenAI
chain = ChatPromptTemplate.from_template("...") | llm
```

**Benefits:**
- Single point of configuration (change `OLLAMA_URL` in `.env` → affects entire project)
- Seamless switching: Ollama ↔ OpenAI (just change environment variables)
- Centralized settings: temperature, max_tokens, model name
- Lazy loading: Only imports LangChain when actually used

---

## Environment Variables (.env)

```
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OPENAI_API_KEY=ollama

LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_PROJECT=qubika

LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_secret
```

---

## What You'll Learn

### Module 1: Vector Databases
- **Embeddings**: Neural representations for semantic search
- **Keyword Search**: TF-IDF and BM25 algorithms
- **Chunking**: Document splitting strategies (fixed-size, sentence-based, recursive)
- **Hybrid Search**: Combining keyword + semantic with Reciprocal Rank Fusion (RRF)
- **RAG Pipeline**: Complete retrieval-augmented generation workflow

### Module 2: Agentic AI Basics
- **Tool Use**: LLMs calling functions with JSON arguments
- **ReAct Pattern**: Iterative reasoning with explicit thoughts and actions

### Module 3: LangGraph
- **Linear Workflows**: Simple deterministic pipelines
- **Conditional Routing**: Multi-path workflows with decisions
- **State Management**: TypedDict for structured state

### Module 4: Advanced Workflows
- **Chroma RAG**: Local vector database for prototyping
- **Pinecone RAG**: Cloud vector database for production

### Module 5: Observability
- **LangSmith**: LLM tracing and debugging
- **LangFuse**: Detailed analytics and evaluation

---

## Architecture Decisions

### Why LangChain?
- Already integrated for observability (LangSmith)
- Unified abstraction for local + cloud LLMs
- Rich ecosystem for RAG, agents, chains
- Production-proven in AI engineering teams

### Why Ollama?
- Zero cloud cost during development
- Same API as OpenAI (easy migration)
- Runs models locally with minimal setup
- Perfect for learning

### Modern Retrieval Strategy
- **Keyword Search (TF-IDF)**: Fast and effective for exact matches ("CVE-2024-1234")
- **Semantic Search**: Neural embeddings for conceptual matches ("remote code execution")
- **Reciprocal Rank Fusion (RRF)**: Intelligent fusion combining both rankings
  - Formula: `score = 1/(k+rank_keyword) + 1/(k+rank_semantic)`
  - Rewards documents appearing in both rankings
  - No parameter tuning required
- (Production: Add dense vector retrieval with OpenAI embeddings + Pinecone)

---

## Common Issues

**Issue**: Ollama connection refused
```
Solution: Run 'ollama serve' in a separate terminal first
```

**Issue**: Module not found errors
```
Solution: pip install -r requirements.txt in activated venv
```

**Issue**: "Empty response from LLM"
```
Solution: Check Ollama is running, model loaded (ollama pull mistral)
```

---

## Next Steps

1. Run `verify_setup.py` to confirm everything works
2. Study Module 1: Start with `01_vector_databases/embeddings_basics.py`
3. Read the `notes.md` in each module for detailed concepts
4. Experiment: Modify prompts, add new tools, build custom workflows
5. Deploy: Use these patterns in production with cloud LLMs

---

## Resources

- [LangChain Documentation](https://python.langchain.com/)
- [Ollama Models](https://ollama.ai/library)
- [LangSmith Docs](https://docs.smith.langchain.com/)
- [LangFuse Docs](https://langfuse.com/docs)

---

**Last Updated**: 2024  
**Status**: Production-ready educational material  
**License**: Free to use and modify

---

## 🎯 Learning Roadmap (Suggested Study Order)

### Day 1 — Foundation: Vector Databases

**Morning:**
```powershell
# Understand embeddings and vectors first
python 01_vector_databases/embeddings_basics.py
python 01_vector_databases/chunking_strategies.py
```

**Afternoon:**
```powershell
# See it all come together in RAG
python 01_vector_databases/hybrid_search.py
python 01_vector_databases/rag_pipeline.py
# Read: 01_vector_databases/README.md
```

### Day 2 — Basics: Agentic AI (Simple Patterns)

**Morning:**
```powershell
# ReAct: Reasoning + Action pattern
python 02_agentic_ai_basics/react_pattern.py
```

**Afternoon:**
```powershell
# Tool use: Function calling
python 02_agentic_ai_basics/tool_use.py
# Read: 02_agentic_ai_basics/README.md
```

### Day 3 — Advanced: LangGraph + Production

**Morning:**
```powershell
# State machines with LangGraph
python 03_advanced_workflows/langgraph_example.py
```

**Afternoon:**
```powershell
# RAG with local DB
python 03_advanced_workflows/chroma_rag.py
python 03_advanced_workflows/inspect_chroma.py
# Optional: python 03_advanced_workflows/setup_pinecone.py (requires API key)
```

### Day 4 — Observability: Debugging & Monitoring

**All Day:**
```powershell
# Monitor your agents
python 04_observability/langsmith_example.py
python 04_observability/langfuse.py
# Read: 04_observability/README.md
```

**Advanced Practice:**
```powershell
# Build custom workflows combining everything
# Experiment, modify code, understand deeply
```

---

## 🔧 Configuração Detalhada

### Instalação Completa (passo-a-passo)

**1. Instale Ollama:**
- Acesse: https://ollama.ai
- Download e execute o instalador (Windows/Mac/Linux)
- Deixe instalar (leva ~2 minutos)

**2. Baixe um modelo:**
```powershell
# Mistral (recomendado - rápido, 4GB)
ollama pull mistral

# Ou Llama2 (mais poderoso, 13GB)
ollama pull llama2

# Ou Neural-Chat (menor, 2GB)
ollama pull neural-chat
```

**3. Inicie o servidor:**
```powershell
ollama serve
```

Deve mostrar: `Listening on 127.0.0.1:11434`

**4. Teste a conexão (em outro terminal):**
```powershell
curl http://localhost:11434/api/tags
# Deve listar os modelos baixados
```

**5. Configure Python:**
```powershell
cd c:\Users\carva\Desktop\qubika

# Crie venv
python -m venv venv

# Ative
venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt
```

---

## ⚙️ Como Funciona

Cada script usa o seguinte padrão:

```python
from openai import OpenAI

# Conecta ao Ollama (não precisa de API key!)
client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama"
)

# Chama o modelo
response = client.chat.completions.create(
    model="mistral",
    messages=[{"role": "user", "content": "Hello!"}]
)

print(response.choices[0].message.content)
```

---

## 🆘 Troubleshooting

| Problema | Solução |
|----------|---------|
| `ollama: command not found` | Feche e reabra PowerShell após instalar Ollama |
| `Connection refused localhost:11434` | Execute `ollama serve` em outro terminal |
| `model not found` | Execute `ollama pull mistral` |
| Muito lento | Tente modelo menor: `ollama pull neural-chat` |
| `ModuleNotFoundError` | Execute `pip install -r requirements.txt` |
| Porta 11434 já em uso | Mude no `.env`: `OLLAMA_BASE_URL=http://localhost:11435` |

### Testes Rápidos

```powershell
# 1. Verificar Ollama instalado
ollama --version

# 2. Verificar modelos
ollama list

# 3. Testar Python + Ollama
python -c "
from openai import OpenAI
client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
response = client.chat.completions.create(
    model='mistral',
    messages=[{'role': 'user', 'content': 'Hi!'}],
    max_tokens=50
)
print('✅ Funciona!'); print(response.choices[0].message.content)
"
```

---

## 📚 Conceitos-Chave

### Agentic AI
- ✅ ReAct pattern (Reason → Act → Observe)
- ✅ Tool use / Function calling
- ✅ State machines (LangGraph)
- ✅ Agent loops e feedback

### Vector Databases
- ✅ O que são embeddings
- ✅ Estratégias de chunking
- ✅ RAG pipeline completo
- ✅ Busca semântica vs. keyword
- ✅ Re-ranking e scoring

### Observability
- ✅ LangSmith / LangFuse integration
- ✅ Traces e spans
- ✅ Debugging de agentes

### AppSec
- ✅ Prompt injection defenses
- ✅ Input validation
- ✅ Rate limiting

---

## 📖 Referências

- [Ollama](https://github.com/ollama/ollama)
- [LangChain](https://python.langchain.com)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Chroma](https://docs.trychroma.com)
- [OpenAI API](https://platform.openai.com/docs)

---

## 💡 Dicas

1. **Deixe Ollama rodando** enquanto estuda — use dois terminais
2. **Comece com Mistral** — mais rápido que Llama2
3. **Leia os `notes.md`** — explicam conceitos importantes
4. **Modifique os exemplos** — entender é mexer no código
5. **Grave suas explicações** — simule a entrevista

---

**Objetivo:** Entender os conceitos e conseguir falar sobre eles naturalmente. 🚀
