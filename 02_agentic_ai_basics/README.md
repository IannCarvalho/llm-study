# 01 Agentic AI Basics

Progressão didática de **mesma tarefa, estratégias diferentes**.

Ambos os scripts resolvem o mesmo problema: **buscar informações sobre um CVE e analisar**.

A diferença está em **como o modelo estrutura a decisão**:

## 1. **Tool Use** (`tool_use.py`)
- **Fluxo**: Uma decisão pontual
- **Como funciona**: Modelo recebe instrução JSON, retorna qual tool chamar
- **Estado**: Lista de mensagens (implícito)
- **Branching**: Nenhum — sempre executa a mesma sequência
- **Melhor para**: Consultas simples, one-shot

```
Modelo → "use search_cve" (JSON) → Executa → Analisa
```

**Quando estudar**: Começa aqui. É o caso de uso mais direto.

---

## 2. **ReAct** (`react_pattern.py`)
- **Fluxo**: Loop iterativo com raciocínio explícito
- **Como funciona**: Modelo escreve `Thought: ... Action: tool[arg]`, a gente parseia e executa
- **Estado**: Lista de mensagens + conversação
- **Branching**: Implícito no texto (modelo decide continuar ou parar)
- **Melhor para**: Tarefas sequenciais, investigação, quando precisar pensar em voz alta

```
Thought → Action[tool] → Observe → (Repeat?) → Final Answer
```

**Quando estudar**: Após Tool Use. Mostra como adicionar raciocínio ao loop.

---

## Comparação

| Aspecto | Tool Use | ReAct |
|---------|----------|-------|
| Decisão | Uma | Loop iterativo |
| Estado | Mensagens | Mensagens |
| Branching | Não | Implícito (no texto) |
| Complexidade | Mínima | Média |
| Ordem de estudo | 1º | 2º |

---

## Como rodar

```bash
# Ativar ambiente
. venv/Scripts/Activate.ps1
$env:PYTHONPATH = "c:\Users\carva\Desktop\qubika"

# Tool Use: decisão direta
python -m 01_agentic_ai_basics.tool_use

# ReAct: loop com raciocínio explícito
python -m 01_agentic_ai_basics.react_pattern
```

---

## Dados Compartilhados

Ambos os scripts usam:
- **Query**: `"What is CVE-2024-1234?"` (de `utils.agentic_data`)
- **CVE_ID**: `"CVE-2024-1234"` (de `utils.agentic_data`)
- **Tool**: `search_cve()` (de `utils/tools.py`)
- **Prompts**: `REACT_SYSTEM`, `TOOL_USE_SYSTEM` (de `utils/prompts/`)

Isso permite comparar **estratégias**, não dados.

---

## Progressão de estudo

1. 📍 **02_agentic_ai_basics/** — Tool Use + ReAct (você está aqui)
2. 📌 **03_langgraph/** — LangGraph Basics + Conditional
3. 📌 **04_advanced_workflows/** — Chroma, Pinecone com dados compartilhados
4. 📌 **05_observability/** — LangSmith, Langfuse

---

## Próximo passo

Após entender Tool Use + ReAct, veja:
- **03_langgraph/**: Workflows determinísticos com estado explícito (TypedDict)

---

## When to Use Each Pattern

### Use ReAct when:
- You need simple iterative reasoning
- Tool invocation is simple/linear
- You're prototyping or learning
- **Production readiness:** Low (no explicit error handling)

### Use Tool Use (Function Calling) when:
- LLM needs to choose among multiple tools
- Tool results need immediate analysis
- You want simple, clear tool interactions
- **Production readiness:** Medium (industry standard)

### Use LangGraph when:
- You have multiple steps with complex dependencies
- You need conditional routing based on state
- You want deterministic, reproducible workflows
- You need to persist and resume execution
- **Production readiness:** High (enterprise pattern)

---

## Architecture Diagram

```
User Query
    ↓
┌─────────────────────────────────────────┐
│       LLM Client (llm_client.py)        │
│  • Single source of truth for LLM calls │
│  • Temperature, max_tokens config       │
│  • Supports Ollama + OpenAI             │
└─────────────────────────────────────────┘
    ↓
┌─ ReAct Pattern ─┐  ┌─ Tool Use ─┐  ┌─ LangGraph ─┐
│                 │  │             │  │              │
│ Conversation    │  │ Tool        │  │ State        │
│ + Iteration     │  │ Selection   │  │ Graph        │
│ Loop            │  │ + Parsing   │  │ + Routing    │
└─────────────────┘  └─────────────┘  └──────────────┘
    ↓
┌─────────────────────────────────────────┐
│      Shared Utilities (agentic_utils.py)│
│  • MockDatabases (CVE, ports, certs)    │
│  • ConversationManager                  │
│  • PromptTemplates                      │
│  • parse_tool_call()                    │
└─────────────────────────────────────────┘
```

---

## Next Steps

After completing this module:

1. **Move to Module 02: Vector Databases** — Learn how to store and retrieve information efficiently
2. **Combine patterns** — Use RAG (Retrieval-Augmented Generation) with agentic patterns
3. **Add observability** — See what your agents are doing with LangSmith/Langfuse (Module 03)
4. **Deploy to production** — Combine agents + RAG + observability (Module 04)

---

## Troubleshooting

**Q: "ModuleNotFoundError: No module named 'agentic_utils'"**
A: Ensure you're running from the `02_agentic_ai_basics/` directory or add it to PYTHONPATH

**Q: "Error: Ollama is not running"**
A: Start Ollama in a separate terminal: `ollama serve`

**Q: "LLM returns empty response"**
A: Check `.env` - OLLAMA_MODEL should be set to a valid model like `mistral:latest`

**Q: Graph visualization doesn't show**
A: This is normal - ASCII art requires optional dependencies. Focus on the execution output instead.

---

## Summary Checklist

- [ ] Run `react_pattern.py` and understand the think-act-observe loop
- [ ] Modify ReAct to search for a different CVE
- [ ] Run `tool_use.py` and see tool selection in action
- [ ] Add a new tool and update `parse_tool_call()`
- [ ] Run `langgraph_example.py` with all three test cases
- [ ] Understand when to use each pattern
- [ ] Ready to move to Module 02!
