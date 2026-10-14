# AI Engineering Study Repository: LangGraph, Vector Databases & Observability

Educational repository with practical examples for learning LLM engineering patterns:
- Ollama + Mistral for local LLM (no API keys required)
- Chroma (local) + Pinecone (cloud) for vector databases
- 5 learning modules: Vector Databases, Agentic AI, LangGraph, Advanced Workflows, Observability
- Single unified data source (CVE database) across all examples
- Reciprocal Rank Fusion for hybrid keyword + semantic search
- Reusable utilities in `utils/` folder

---

## Contents

| Module | Topics | Files |
|--------|--------|-------|
| **01_vector_databases** | Embeddings, Chunking, Hybrid Search (RRF) | embeddings_basics.py, chunking_strategies.py, hybrid_search.py |
| **02_agentic_ai_basics** | ReAct, Tool Use | react_pattern.py, tool_use.py |
| **03_langgraph** | Linear & Conditional Workflows | langgraph_basics.py, langgraph_conditional.py |
| **04_advanced_workflows** | RAG + Production Vector DBs | chroma_rag.py, pinecone_rag.py |
| **05_observability** | LangSmith, LangFuse, Tracing & Debugging | langsmith_demo.py, langfuse_demo.py |
| **06_evals** | LLM-as-Judge, Offline RAG Metrics | llm_as_judge.py, rag_metrics.py |
| **07_sdd** | Spec-Driven Development | spec_driven_analysis.py, spec_example.md |
| **08_agentic_platforms** | Kiro/Claude: Skills, Hooks, Specs, MCP, Subagents | README.md (conceptual) |
| **utils/** | Shared utilities | centralized reusable modules |

---

## Quick Start

### Prerequisites
- Python 3.8+
- One of the following:
  - **Ollama** (local, free) — Download from https://ollama.ai
  - **LLMStudio** (local, free, GUI) — Download from https://lmstudio.ai
  - **OpenAI API key** (cloud, paid) — Get from https://platform.openai.com

### Step 1: Set Up Environment

**Windows (PowerShell):**
```powershell
# Create virtual environment (if needed)
python -m venv venv

# Activate
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Linux/Mac (Bash):**
```bash
# Create virtual environment (if needed)
python3 -m venv venv

# Activate
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Start Your LLM

**Ollama (Recommended):**
```bash
# Terminal 1: Start Ollama (keep running)
ollama serve

# Terminal 2: Download a model (first time only)
ollama pull mistral
```

**LLMStudio:**
- Download from https://lmstudio.ai
- Launch, download a model, enable "Local Server"

**OpenAI API:**
- Get key from https://platform.openai.com
- Set in `.env` as `OPENAI_API_KEY`

### Step 3: Configure `.env`

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` with your LLM choice (defaults to Ollama):

```
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

### Step 4: Run Examples

Run examples as Python packages:

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "."

# Vector database examples
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search

# Agent patterns
python -m 02_agentic_ai_basics.tool_use
python -m 02_agentic_ai_basics.react_pattern

# LangGraph workflows
python -m 03_langgraph.langgraph_basics
python -m 03_langgraph.langgraph_conditional

# Advanced workflows
python -m 04_advanced_workflows.chroma_rag
python -m 04_advanced_workflows.pinecone_rag

# Observability
python -m 05_observability.langsmith_demo
python -m 05_observability.langfuse_demo
```

**Linux/Mac (Bash):**
```bash
export PYTHONPATH="."

# Vector database examples
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search

# Agent patterns
python -m 02_agentic_ai_basics.tool_use
python -m 02_agentic_ai_basics.react_pattern

# LangGraph workflows
python -m 03_langgraph.langgraph_basics
python -m 03_langgraph.langgraph_conditional

# Advanced workflows
python -m 04_advanced_workflows.chroma_rag
python -m 04_advanced_workflows.pinecone_rag

# Observability
python -m 05_observability.langsmith_demo
python -m 05_observability.langfuse_demo
```

---

## LLM Configuration

All examples support these LLM providers:

| Provider | Setup | Notes |
|----------|-------|-------|
| **Ollama** (Local) | `ollama serve` → `ollama pull mistral` | Free, offline, no API keys |
| **LLMStudio** (Local) | GUI download, enable local server | Free alternative to Ollama |
| **OpenAI** (Cloud) | Set `OPENAI_API_KEY` in `.env` | Production-grade, costs per token |

Configure in `.env` file. See `.env.example` for all options.

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

06_evals/                       # Evaluating LLM & agents
├── llm_as_judge.py            # Score generated output with a second LLM
├── rag_metrics.py             # Offline retrieval metrics (no LLM needed)
└── README.md

07_sdd/                         # Spec-Driven Development
├── spec_driven_analysis.py    # Spec object -> prompt -> validate output
├── spec_example.md            # Human-readable spec artifact
└── README.md

08_agentic_platforms/           # Working with Kiro & Claude (conceptual)
└── README.md                  # Skills, hooks, specs, MCP, subagents

data/
├── chroma/                    # Local Chroma database

utils/                          # Shared utilities (centralized)
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

## Unified Data Source: CVE Database

All examples use a single, centralized CVE database (`utils/data/cves.json`) for consistency:

```python
from utils.data_loader import load_cves, get_cve_documents

# Load CVE data
cves = load_cves()

# Get formatted documents for RAG
documents = get_cve_documents(cves)
```

**Benefits:**
- Single source of truth across all examples
- Consistent data for comparison across different techniques
- Easy to swap for production data
- Simplified setup and maintenance

---

## Utils Folder — Centralized Utilities

All shared utilities are organized in a single `utils/` folder for maximum code reuse.

Centralized utilities provide:
- Single source of truth for each utility
- Easy to find and reuse functions
- Consistent imports across all modules
- Simplified maintenance and updates

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

## LLM Client API

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
- Seamless switching: Local ↔ Cloud LLMs (just change environment variables)
- Centralized settings: temperature, max_tokens, model name
- Lazy loading: Only imports when actually used

---

### Option 1: Local LLM — Ollama (Recommended for Learning)

**Why Ollama?**
- ✅ **Free**: No API keys or subscriptions required
- ✅ **Privacy**: All data stays on your machine
- ✅ **Fast**: Low latency for quick iterations
- ✅ **Offline**: Works without internet
- ✅ **Multiple Models**: Run Mistral, Llama, Neural Chat, etc.

**Setup:**

1. **Install Ollama** from https://ollama.ai

2. **Start Ollama** (in a separate terminal, keep running):
```powershell
ollama serve
```

3. **Download a model** (first time only):
```powershell
ollama pull mistral       # Fast, 7B parameters
ollama pull llama2        # Larger, 7B/13B/70B options
ollama pull neural-chat   # Smaller, chat-optimized
```

4. **Configure in `.env`**:
```
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
```

5. **Verify**:
```bash
curl http://localhost:11434/api/generate -d '{"model":"mistral","prompt":"hello"}'
```

**Popular Ollama Models:**
- `mistral:latest` — Best balance of speed/quality
- `llama2` — Meta's LLaMA 2 (7B/13B)
- `neural-chat` — Small but good at chat
- `dolphin-mixtral` — High quality, multi-task

---

### Option 2: LLMStudio (GUI Alternative to Ollama)

**What is LLMStudio?**
- Visual interface for running local LLMs
- No terminal required
- Better for non-technical users

**Setup:**

1. **Download** from https://lmstudio.ai

2. **Launch and download a model** (GUI-based)

3. **Start local server** (in LLMStudio settings):
   - Enable "Local Server" 
   - Keep it running

4. **Configure in `.env`** (same as Ollama):
```
OLLAMA_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=not-needed
OLLAMA_MODEL=whatever-model-you-loaded
```

---

### Option 3: Cloud LLM — OpenAI (Production)

**When to use:**
- Production applications
- Need GPT-4 capability
- High throughput requirements

**Setup:**

1. **Get API key** from https://platform.openai.com/account/api-keys

2. **Configure in `.env`**:
```
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini  # or gpt-3.5-turbo for cheaper
OLLAMA_BASE_URL=https://api.openai.com/v1
```

**Cost:** ~$0.001-0.01 per 1000 tokens (check pricing)

---

### Option 4: Other Providers (Anthropic, Google, etc.)

The system uses LangChain, which supports many providers:

```python
# For other providers, modify utils/llm_client.py:
# from langchain_anthropic import ChatAnthropic  # Claude
# from langchain_google_genai import ChatGoogleGenerativeAI  # Gemini
# from langchain_cohere import ChatCohere  # Cohere
```

Each provider needs its own configuration — see [LangChain Providers](https://python.langchain.com/docs/integrations/llms/).

---

### 🔐 Credentials Security Best Practices

**DO:**
```
✅ Store in .env file (already .gitignored)
✅ Use environment variables in production
✅ Rotate API keys regularly
✅ Use least-privilege API keys (read-only when possible)
✅ Monitor API usage for unexpected charges
```

**DON'T:**
```
❌ Commit API keys to git
❌ Share .env file
❌ Use same key for multiple projects
❌ Hardcode credentials in code
❌ Log API keys in debug output
```

**For Production:**
- Use secrets manager (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault)
- Set environment variables on server/container
- Rotate keys every 90 days
- Use different keys for dev/staging/production

---

### Switching Between LLMs

The entire project switches LLM providers by changing a few `.env` variables:

**From Ollama → OpenAI:**
```bash
# Change .env:
OPENAI_API_KEY=sk-xxxxxxxxxxxx
OLLAMA_BASE_URL=https://api.openai.com/v1
OLLAMA_MODEL=gpt-4o-mini
```

**From Ollama → Anthropic Claude:**
```bash
# Modify utils/llm_client.py to use ChatAnthropic
# Then set .env:
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

No code changes needed! Just environment variables.

---

## Environment Variables (.env)

Copy `.env.example` to `.env` and fill in your values:

```
# ===== LLM Configuration =====

# Option A: Ollama (Local, Free, Recommended)
OLLAMA_MODEL=mistral:latest
OLLAMA_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama

# Option B: OpenAI (Cloud, Production)
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
# OLLAMA_BASE_URL=https://api.openai.com/v1
# OLLAMA_MODEL=gpt-4o-mini

# LLM Behavior
LLM_TEMPERATURE=0.7          # 0.0 (deterministic) - 2.0 (creative)
LLM_MAX_TOKENS=512           # Max response length

# ===== Observability (Optional) =====

# LangSmith (LangChain Official Tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_xxxxxxxxxxxx
LANGCHAIN_PROJECT=llm-study

# LangFuse (Analytics & Evaluation)
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxx
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com

# ===== Vector Databases (Optional) =====

# Chroma (default, local, no setup needed)
CHROMA_PATH=./data/chroma

# Pinecone (cloud, requires API key)
PINECONE_API_KEY=pcsk_xxxxxxxxxxxxxxxxxxxx

# ===== Other (Optional) =====

# HuggingFace (for embeddings models)
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Debugging
DEBUG=false
LOG_LEVEL=INFO
```

---

## Configuration Reference

All settings are managed in `utils/config.py` using Pydantic:

| Variable | Default | Type | Purpose |
|----------|---------|------|---------|
| `OLLAMA_MODEL` | `mistral` | str | Which LLM to use |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | str | LLM API endpoint |
| `OPENAI_API_KEY` | `ollama` | str | API key or "ollama" |
| `LLM_TEMPERATURE` | `0.7` | float | Creativity (0.0-2.0) |
| `LLM_MAX_TOKENS` | `512` | int | Max response length |
| `CHROMA_PATH` | `./data/chroma` | str | Local vector DB path |
| `PINECONE_API_KEY` | None | str | Pinecone API key (optional) |
| `HF_TOKEN` | None | str | HuggingFace token (optional) |
| `DEBUG` | `false` | bool | Enable debug logging |
| `LOG_LEVEL` | `INFO` | str | Logging level |

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

### Module 6: Evals
- **Offline RAG metrics**: precision@k and a groundedness proxy (deterministic, no LLM)
- **LLM-as-judge**: scoring generated output with a second, rubric-driven LLM call

### Module 7: Spec-Driven Development
- **Spec as artifact**: structured spec that drives and validates the agent's output
- **With-spec vs. without-spec**: the contrast against free-form prompting

### Module 8: Agentic Platforms (Kiro & Claude)
- **Skills, Hooks, Specs/Steering, MCP tools, Subagents**: how you extend and operate coding agents
- **Model vs. agent**: the loop, tools and guardrails that turn a model into an agent

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

## 🐛 Common Issues & Troubleshooting

### LLM Connection Issues

**Issue**: "Connection refused" to Ollama
```
Solution 1: Start Ollama in a separate terminal: ollama serve
Solution 2: Check port is open: curl http://localhost:11434/api/tags
Solution 3: Restart Ollama (it may have crashed)
Solution 4: Check OLLAMA_BASE_URL in .env is correct (http://localhost:11434/v1)
```

**Issue**: "Model not found" or empty responses
```
Solution 1: Check model is installed: ollama list
Solution 2: Download model: ollama pull mistral
Solution 3: Check .env OLLAMA_MODEL matches installed model
Solution 4: Try a different model: ollama pull neural-chat
```

**Issue**: LLM is very slow or uses too much memory
```
Solution 1: Use a smaller model: ollama pull neural-chat (instead of mistral)
Solution 2: Reduce LLM_MAX_TOKENS in .env (less output = faster)
Solution 3: Increase your system RAM or add swap space
Solution 4: Use cloud LLM (OpenAI, Claude) instead of local
```

### Credential Issues

**Issue**: "401 Unauthorized" with OpenAI
```
Solution 1: Verify OPENAI_API_KEY is set: echo $OPENAI_API_KEY
Solution 2: Check API key is valid: https://platform.openai.com/account/api-keys
Solution 3: Key may have been revoked — generate a new one
Solution 4: Ensure key starts with "sk-"
```

**Issue**: "Invalid API key" with Pinecone
```
Solution 1: Check PINECONE_API_KEY in .env
Solution 2: Verify key at https://www.pinecone.io
Solution 3: Create an index named "llm-study"
```

**Issue**: Forgot or lost API key
```
Solution 1: Generate a new one from provider dashboard
Solution 2: Update .env file
Solution 3: Old key may still work temporarily (cache)
```

### Python & Environment Issues

**Issue**: "Module not found" errors
```
Solution: 
1. Activate venv: venv\Scripts\activate (Windows) or source venv/bin/activate (Mac/Linux)
2. Install deps: pip install -r requirements.txt
3. Verify: python -c "import langchain; print('OK')"
```

**Issue**: "No module named 'utils'"
```
Solution 1: Make sure you're in project root: /path/to/llm-study
Solution 2: Set PYTHONPATH:
  - Windows: $env:PYTHONPATH = "."
  - Linux/Mac: export PYTHONPATH="."
Solution 3: Use relative imports correctly
```

**Issue**: Different Python version causing issues
```
Solution: Use Python 3.8 - 3.11
1. Check: python --version
2. Create fresh venv: python -m venv venv
3. Reinstall: pip install -r requirements.txt
```

### Data Issues

**Issue**: Vector DB is empty or has old data
```
Solution: Remove and recreate
- Delete: rm -r data/chroma (or rmdir /s data\chroma on Windows)
- Rerun: python 04_advanced_workflows/chroma_rag.py
```

**Issue**: "CVE data not loading"
```
Solution: Check if utils/data/cves.json exists
- Verify: ls utils/data/cves.json
- If missing: data should be in git
```

### More Help

For detailed troubleshooting of LLM setups, see **[LLM_SETUP.md](LLM_SETUP.md#-troubleshooting)**.

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

> Run each example as a package from the project root (`$env:PYTHONPATH = "."` on PowerShell, `export PYTHONPATH="."` on Bash). The commands below use the module form that works regardless of OS.

### Day 0 — Foundation: Prompting (Pré-requisito)

> **Novo tópico (conceitual + exercício).** Antes de recuperar contexto ou dar
> ferramentas ao modelo, você precisa saber pedir bem. Esta é a camada que todos
> os módulos seguintes assumem. Ainda não há script dedicado no repositório —
> comece pela leitura e faça o exercício sobre a base de CVEs.

**Conceitos:**
- Zero-shot vs. few-shot (k-shot)
- Role prompting (definir papel/persona do modelo)
- Chain-of-Thought (CoT): fazer o modelo "pensar antes de responder"
- Contrato + contraste: dizer o que fazer **e** o que não fazer
- Saída estruturada (JSON mode) para integrar com código

**Exercício prático:**
```powershell
# Compare variações de prompt sobre o MESMO CVE e observe a diferença de saída:
#   1. zero-shot:  "Resuma este CVE."
#   2. role:       "Você é um analista de segurança. Resuma este CVE para um gestor."
#   3. CoT:        "Analise passo a passo a severidade deste CVE e então conclua."
#   4. estruturado:"Responda em JSON: {id, severidade, resumo, acao_recomendada}"
# Use o utils.llm_client (get_llm_client) e um CVE de utils/data/cves.json.
```

### Day 1 — Foundation: Vector Databases

**Morning:**
```powershell
# Understand embeddings and vectors first
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
```

**Afternoon:**
```powershell
# See it all come together in hybrid search (keyword + semantic + RRF)
python -m 01_vector_databases.hybrid_search
# Read: 01_vector_databases/README.md
```

### Day 2 — Basics: Agentic AI (Simple Patterns)

**Morning:**
```powershell
# ReAct: Reasoning + Action pattern
python -m 02_agentic_ai_basics.react_pattern
```

**Afternoon:**
```powershell
# Tool use: Function calling
python -m 02_agentic_ai_basics.tool_use
# Read: 02_agentic_ai_basics/README.md
```

**Extra — MCP (Model Context Protocol):**

> **Novo tópico (conceitual + exercício).** Function calling cru é o "antes";
> o MCP é o padrão de fato (Anthropic, OpenAI e esta própria stack usam) para
> expor ferramentas, recursos e prompts a um agente de forma padronizada e
> reutilizável — em vez de reimplementar o wiring de tool use a cada projeto.

**Conceitos:**
- Por que padronizar a interface agente ↔ sistema (ACI — Agent-Computer Interface)
- Server / Client / Resource / Prompt
- Como nomear e desenhar boas tools (nomes claros, escopo mínimo, erros úteis)

**Exercício prático:**
```powershell
# Exponha o seu utils.tools.search_cve como um MCP server mínimo e chame-o
# por um cliente MCP — reaproveitando a MESMA base de CVEs dos outros módulos.
```

### Day 3 — Orchestration: LangGraph

**Morning:**
```powershell
# State machines with LangGraph — linear pipeline
python -m 03_langgraph.langgraph_basics
```

**Afternoon:**
```powershell
# Conditional routing (multi-path workflows)
python -m 03_langgraph.langgraph_conditional
# Read: 03_langgraph/README.md
```

### Day 3.5 — Context Engineering (Novo)

> **Novo tópico (conceitual + exercício).** Depois de orquestrar fluxos
> (LangGraph) e antes de RAG de produção, entenda **engenharia de contexto** — a
> skill que substituiu "prompt engineering" como diferencial sênior em AI
> Engineering. Você já pratica partes dela sem nomear: RAG é *Select*,
> observabilidade ajuda a enxergar *context rot*.

**Conceitos:**
- Janela de contexto e por que o mecanismo de atenção não escala
- *Context rot* e *lost in the middle* (informação no meio do contexto é ignorada)
- 4 modos de falha: *poisoning*, *distraction*, *confusion*, *clash*
- As 4 estratégias: **Write, Select, Compress, Isolate**

**Exercício prático:**
```powershell
# Demonstre "context distraction" com o SEU dado:
#   1. Pergunte sobre um CVE específico passando só ele no contexto.
#   2. Repita inflando o contexto com dezenas de CVEs irrelevantes.
#   3. Compare qualidade/latência das respostas — veja a degradação.
# Reutilize utils.data_loader para montar os dois cenários.
```

### Day 4 — Advanced: RAG with Production Vector DBs

**Morning:**
```powershell
# RAG with a local vector DB (Chroma)
python -m 04_advanced_workflows.chroma_rag
```

**Afternoon:**
```powershell
# RAG with a cloud vector DB (Pinecone — requires PINECONE_API_KEY)
python -m 04_advanced_workflows.pinecone_rag
# Read: 04_advanced_workflows/README.md
```

### Day 5 — Observability: Debugging & Monitoring

**All Day:**
```powershell
# Monitor and trace your agents
python -m 05_observability.langsmith_demo
python -m 05_observability.langfuse_demo
# Read: 05_observability/README.md
```

**Advanced Practice:**
```powershell
# Build custom workflows combining everything
# Experiment, modify code, understand deeply
```

### Day 6 — Evaluation: Measuring Quality

**Morning:**
```powershell
# Offline retrieval metrics (deterministic, no Ollama needed)
python -m 06_evals.rag_metrics
```

**Afternoon:**
```powershell
# LLM-as-judge: score generated output with a second LLM (requires Ollama)
python -m 06_evals.llm_as_judge
# Read: 06_evals/README.md
```

### Day 7 — Spec-Driven Development

**All Day:**
```powershell
# Spec drives and validates the agent's output (with-spec vs. without-spec)
python -m 07_sdd.spec_driven_analysis
# Read: 07_sdd/README.md and 07_sdd/spec_example.md
```

### Day 8 — Working with Agentic Platforms (Kiro & Claude)

**All Day:**
```powershell
# Conceptual module — no script to run.
# Read: 08_agentic_platforms/README.md
#   Skills, Hooks, Specs/Steering, MCP tools, Subagents
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