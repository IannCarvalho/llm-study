# 03 LangGraph

Introdução ao **LangGraph**: Framework para construir workflows determinísticos e previsíveis.

Diferente dos padrões anteriores (Tool Use, ReAct), LangGraph oferece:
- **Estado explícito**: TypedDict tipado, não conversas de mensagens
- **Grafo visual**: Workflow como estrutura de dados
- **Roteamento condicional**: Decisões no nível do grafo, não dentro do LLM
- **Compilação**: Grafo transformado em máquina de estados executável

**Comparação com 01_agentic_ai_basics/:**

| Aspecto | Tool Use | ReAct | LangGraph |
|---------|----------|-------|-----------|
| Decisão | Uma | Loop (texto) | Condicional (grafo) |
| Estado | Mensagens | Mensagens | TypedDict (estruturado) |
| Visibilidade | Baixa | Média | **Alta** (grafo explícito) |
| Produção | Consultas simples | Investigação | Workflows complexos |

---

## 1. **LangGraph Basics** (`langgraph_basics.py`)

**Conceito**: Pipeline linear — um caminho fixo de nó em nó.

```
fetch_cve → summarize → END
```

**O que aprender:**
- TypedDict como estado
- Nós como funções que retornam estado
- Edges lineares

**Quando útil**: Workflows determin ísticos sem variações.

---

## 2. **LangGraph Conditional** (`langgraph_conditional.py`)

**Conceito**: Roteamento — múltiplos caminhos baseados em lógica.

```
fetch_cve → (route_by_status) → summarize (sucesso) ou not_found (falha)
```

**O que aprender:**
- `add_conditional_edges()` para ramificação
- Router function retorna string identificando próximo nó
- Múltiplos caminhos convertem ou vão ao END

**Quando útil**: Workflows com decisões claras (retry, escalação, fallback).

---

## Como rodar

```bash
# Ativar ambiente
. venv/Scripts/Activate.ps1
$env:PYTHONPATH = "."

# Linear pipeline
python -m 03_langgraph.langgraph_basics

# Conditional routing
python -m 03_langgraph.langgraph_conditional
```

---

## Dados Compartilhados

Ambos os scripts usam:
- **CVE_ID**: `"CVE-2024-1234"` (de `utils.agentic_data`)
- **Tool**: `search_cve()` (de `utils/tools.py`)

Resultado: **mesma tarefa, mesmos dados, estratégias diferentes** (linear vs condicional).

---

## Progressão de estudo

1. ✅ **02_agentic_ai_basics/** — Tool Use + ReAct
2. 📍 **03_langgraph/** — LangGraph Basics + Conditional (você está aqui)
3. 📌 **04_advanced_workflows/** — Chroma, Pinecone com dados compartilhados
4. 📌 **05_observability/** — LangSmith, Langfuse

---

## Próximos passos

Após dominar LangGraph:
- **Humano no loop**: Adicione `add_edge("summarize", "approval_node")`
- **Retries**: Adicione caminho condicional para retry em falhas
- **Multi-agente**: Múltiplos grafos comunicando via estado compartilhado
- **Persistência**: Salve estado em DB entre invocações

Veja `03_vector_databases/` para RAG com grafos.
