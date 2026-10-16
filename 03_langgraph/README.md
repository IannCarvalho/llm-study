# 03 — LangGraph

> Pré-requisitos: **precisa de LLM** e do pacote **`langgraph`** (instalado pelo `requirements.txt`). Os dois scripts montam o grafo sem LLM, mas o nó `summarize` chama o modelo via `utils.llm_client`; sem o [Ollama](../LLM_SETUP.md) no ar eles param nesse nó com `OpenAIConnectionError: Connection error.`. Rodar como módulo a partir da raiz, com `PYTHONPATH="."`.

Introdução ao **LangGraph**: modelar um fluxo de agente como um **grafo de estado**. Depois das estratégias baseadas em texto do módulo [02_agentic_ai_basics](../02_agentic_ai_basics/README.md) (tool use e ReAct), aqui a mesma tarefa — buscar e resumir um CVE — é escrita como uma máquina de estados explícita: um `State` tipado (`TypedDict`), nós que transformam esse estado e arestas (fixas ou condicionais) que decidem o próximo passo.

## Por que importa

Em tool use/ReAct a lógica de controle vive **no texto** que o modelo escreve. Isso é simples, mas difícil de auditar e de reproduzir. O LangGraph move o controle para **o grafo**:

- **Estado explícito** (`TypedDict`), não uma lista de mensagens.
- **Grafo como estrutura de dados**, que dá para visualizar e versionar.
- **Roteamento condicional** no nível do grafo, não "escondido" na saída do LLM.
- **Compilação**: o grafo é transformado numa máquina de estados executável antes de rodar.

### Comparação com o módulo 02

| Aspecto | Tool use | ReAct | LangGraph |
|---------|----------|-------|-----------|
| Decisão | Uma | Loop (texto) | Condicional (grafo) |
| Estado | Mensagens | Mensagens | `TypedDict` (estruturado) |
| Visibilidade do fluxo | Baixa | Média | **Alta** (grafo explícito) |
| Produção | Consultas simples | Investigação | Fluxos com várias etapas |

## Conceitos

No LangGraph você define três coisas e depois **compila**: o `State` (esquema compartilhado, aqui um `TypedDict`), os **nós** (funções que recebem o estado, fazem o trabalho e devolvem o estado atualizado) e as **arestas** (fixas com `add_edge`, ou condicionais com `add_conditional_edges`). `set_entry_point` marca o primeiro nó e o nó especial `END` encerra o fluxo. É preciso chamar `.compile()` antes de invocar o grafo.

### 1. LangGraph Basics (`langgraph_basics.py`)

**Conceito:** pipeline **linear** — um caminho fixo de nó em nó.

```
fetch_cve → summarize → END
```

- `CVEState` é um `TypedDict` com `cve_id`, `cve_data` e `summary`.
- `fetch_cve` chama `search_cve` (de `utils/tools.py`) e guarda o resultado no estado.
- `summarize` pede ao LLM um resumo em uma frase (é aqui que o LLM é necessário).
- As arestas são lineares: `set_entry_point("fetch_cve")`, `add_edge("fetch_cve", "summarize")`, `add_edge("summarize", END)`.

**Quando usar:** fluxos determinísticos, sem variações de caminho.

### 2. LangGraph Conditional (`langgraph_conditional.py`)

**Conceito:** **roteamento** — caminhos diferentes conforme o estado.

```
fetch_cve → (route_by_status) → summarize (encontrou)  ou  not_found (não encontrou)
```

- Acrescenta um **router** `route_by_status(state) -> str`, que devolve `"summarize"` se o CVE foi encontrado (`status == "success"`) ou `"not_found"` caso contrário.
- `add_conditional_edges("fetch_cve", route_by_status, {"summarize": "summarize", "not_found": "not_found"})` liga a saída do router aos nós de destino.
- Os dois caminhos convergem para `END`.
- O `main()` roda dois casos: um CVE que existe (`CVE_ID`) e um inexistente (`CVE-9999-99999`), para exercitar os dois ramos.

**Quando usar:** fluxos com decisões claras (retry, escalação, fallback).

## Arquivos

| Arquivo | O que faz |
|---------|-----------|
| [`langgraph_basics.py`](langgraph_basics.py) | Pipeline linear `fetch_cve → summarize → END` sobre um `TypedDict`. |
| [`langgraph_conditional.py`](langgraph_conditional.py) | Adiciona `add_conditional_edges` + a função de roteamento `route_by_status`, com o ramo `not_found`. |

Dados e utilitários compartilhados:

- `CVE_ID = "CVE-2024-1234"`, de `utils/agentic_utils.py`.
- A tool `search_cve` (de `utils/tools.py`), que consulta `utils/data/cves.json` via `utils.data_loader`.

A base é de **3 CVEs sintéticos** (produtos fictícios) — nunca CVEs reais. Detalhes no [README raiz](../README.md#base-de-dados-cves-sintéticos).

## Como rodar

A partir da raiz do repositório, com `langgraph` instalado e o Ollama no ar (veja [LLM_SETUP.md](../LLM_SETUP.md)):

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "."
python -m 03_langgraph.langgraph_basics       # pipeline linear
python -m 03_langgraph.langgraph_conditional  # roteamento condicional
```

**Bash (Linux/macOS):**
```bash
export PYTHONPATH="."
python -m 03_langgraph.langgraph_basics
python -m 03_langgraph.langgraph_conditional
```

## O que a demo mostra

A montagem do grafo e o nó `fetch_cve` rodam **sem LLM** — a busca na base é determinística. A chamada ao modelo acontece só no nó `summarize`. Por isso, **sem o Ollama no ar**, os dois scripts avançam até `fetch_cve` (que imprime `Result: success`) e param em `summarize` com `OpenAIConnectionError: Connection error.` (exit 1).

Saída real de `langgraph_basics.py` sem LLM:

```
======================================================================
LangGraph Basics: Linear Pipeline
======================================================================

Node: fetch_cve
  Result: success

Node: summarize
...
langchain_openai.chat_models.base.OpenAIConnectionError: Connection error.
```

Saída real de `langgraph_conditional.py` sem LLM (repare o router disparando antes de parar no `summarize`):

```
======================================================================
LangGraph: Conditional Routing
======================================================================

--- Case 1: CVE Found ---

Node: fetch_cve
  Result: success

Routing -> summarize (CVE found)

Node: summarize
...
langchain_openai.chat_models.base.OpenAIConnectionError: Connection error.
```

Com o Ollama no ar, `summarize` preenche `state["summary"]` e o script imprime o estado final (`Final State:` / `Final:`); no condicional, o Caso 2 (CVE inexistente) segue pelo ramo `not_found`, que não chama o LLM e produz `No data available for CVE-9999-99999.`. O texto do resumo varia conforme o modelo.

## Exercícios

1. **Leia o estado fluindo.** Em `langgraph_basics.py`, adicione um `print(state)` no início de cada nó e rode (com LLM) para ver o `CVEState` sendo preenchido campo a campo (`cve_id` → `cve_data` → `summary`).
2. **Exercite o ramo `not_found` sem LLM.** No condicional, o Caso 2 usa `CVE-9999-99999` e nunca chama o modelo. Rode e confirme que esse ramo funciona **offline** — útil para entender por que separar busca (determinística) de geração (LLM).
3. **Adicione um terceiro caminho.** Estenda `route_by_status` para um caso novo (ex.: severidade alta → um nó `escalate`) e ligue-o com `add_conditional_edges`, convergindo em `END`. Teste com um CVE da base.
4. **Humano no loop.** Insira um nó `approval` entre `summarize` e `END` (`add_edge("summarize", "approval")`, `add_edge("approval", END)`) que só imprime o resumo e pede confirmação. Observe como o grafo torna esse ponto de parada explícito.
5. **`set_entry_point` vs. `add_edge(START, ...)`.** A doc oficial trata `set_entry_point(n)` como equivalente a `add_edge(START, n)` e recomenda a forma com `START`/`END`. Reescreva `build_graph()` usando `from langgraph.graph import START` e `add_edge(START, "fetch_cve")` e confirme que o comportamento é idêntico.

## Referências

- [LangGraph — Graph API (doc oficial)](https://docs.langchain.com/oss/python/langgraph/graph-api) — `StateGraph`, nós, `add_edge`, `add_conditional_edges`, `set_entry_point`, `END` e `.compile()`.
- [Documentação do LangChain](https://python.langchain.com/)
- [LLM_SETUP.md](../LLM_SETUP.md) — como subir Ollama / LM Studio / OpenAI.
- [README raiz](../README.md) — mapa dos módulos, base de CVEs e utilitários compartilhados.
