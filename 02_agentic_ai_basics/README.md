# 02 — Agentic AI Basics

> Pré-requisitos: **precisa de LLM.** Os dois scripts chamam o modelo via `utils.llm_client`, então exigem um endpoint de LLM no ar (o padrão é o [Ollama](../LLM_SETUP.md) local). Sem ele, cada script para com `OpenAIConnectionError: Connection error.`. Rodar como módulo a partir da raiz, com `PYTHONPATH="."`.

Progressão didática de **mesma tarefa, estratégias diferentes**. Os dois scripts resolvem o mesmo problema — **buscar dados de um CVE e analisá-lo** — usando a mesma ferramenta (`search_cve`) e a mesma query. O que muda é **como o modelo estrutura a decisão**: uma escolha pontual (tool use) ou um loop de raciocínio explícito (ReAct).

## Por que importa

Antes de orquestrar fluxos (módulo [03_langgraph](../03_langgraph/README.md)) ou montar RAG de produção, é preciso entender as duas formas mais básicas de dar ação a um LLM:

- **Function calling / tool use** é o padrão de mercado para o modelo escolher e chamar uma função.
- **ReAct** (Reason + Act) intercala raciocínio e ação num loop, útil para investigação multi-etapa.

Fixando as duas sobre a mesma tarefa e os mesmos dados, dá para comparar as **estratégias**, não os dados.

## Conceitos

### 1. Tool use (`tool_use.py`)

- **Fluxo:** uma decisão pontual, sem loop de raciocínio.
- **Como funciona:** o modelo recebe o prompt de sistema `TOOL_USE_SYSTEM` e responde com uma chamada de ferramenta em JSON, no formato `[{"name": "search_cve", "arguments": {"cve_id": "..."}}]`. O código extrai esse JSON (`extract_tool_call`), executa a tool e devolve o resultado ao modelo para a análise final.
- **Branching:** nenhum — sempre a mesma sequência (decidir → executar → analisar).
- **Melhor para:** consultas simples, de uma rodada.

```
Modelo → chamada de tool (JSON) → executa search_cve → modelo analisa o resultado
```

### 2. ReAct (`react_pattern.py`)

- **Fluxo:** loop iterativo (até `MAX_STEPS = 5`) com raciocínio explícito.
- **Como funciona:** guiado pelo prompt `REACT_SYSTEM`, o modelo escreve em texto `Thought: ...` seguido de `Action: search_cve[<cve_id>]`. O código parseia a linha `Action:` (regex), executa a tool e devolve uma linha `Observation: ...`. O loop repete até o modelo emitir `Final Answer: ...` (ou atingir o limite de passos).
- **Branching:** implícito no texto — o próprio modelo decide continuar ou parar.
- **Melhor para:** tarefas sequenciais, investigação, "pensar em voz alta".

```
Thought → Action[tool] → Observation → (repete?) → Final Answer
```

### Comparação

| Aspecto | Tool use | ReAct |
|---------|----------|-------|
| Decisão | Uma (pontual) | Loop iterativo |
| Formato da resposta do modelo | JSON (`[{"name", "arguments"}]`) | Texto (`Thought/Action/Observation`) |
| Estado | Lista de mensagens | Lista de mensagens |
| Branching | Não | Implícito, no texto |
| Complexidade | Mínima | Média |
| Ordem de estudo | 1º | 2º |

> Prontidão para produção (comparativo didático, não medição): o tool use/function calling é o padrão de mercado; o ReAct manual deste módulo não trata erros e serve para aprendizado. Para fluxos com várias etapas e dependências, roteamento condicional ou persistência, o próximo passo é o LangGraph (módulo [03_langgraph](../03_langgraph/README.md)).

## Arquivos

| Arquivo | O que faz |
|---------|-----------|
| [`tool_use.py`](tool_use.py) | Function calling: o modelo responde com um JSON escolhendo a tool; o código a executa e pede a análise. |
| [`react_pattern.py`](react_pattern.py) | ReAct "manual" do paper original: o modelo escreve `Thought/Action` em texto e o código parseia e executa, em loop. |

Dados e utilitários compartilhados pelos dois:

- `QUERY = "What is CVE-2024-1234?"` e `CVE_ID = "CVE-2024-1234"`, de `utils/agentic_utils.py`.
- A tool `search_cve` (de `utils/tools.py`), que consulta a base `utils/data/cves.json` via `utils.data_loader`.
- Os prompts de sistema `TOOL_USE_SYSTEM` e `REACT_SYSTEM`, de `utils/prompts/`: cada prompt é um arquivo `.txt` (`tool_use.txt`, `react.txt`) carregado pela classe `PromptTemplates`.

A base é de **3 CVEs sintéticos** (produtos fictícios) — nunca CVEs reais. Detalhes no [README raiz](../README.md#base-de-dados-cves-sintéticos).

## Como rodar

A partir da raiz do repositório, com o Ollama no ar (veja [LLM_SETUP.md](../LLM_SETUP.md)):

**PowerShell (Windows):**
```powershell
$env:PYTHONPATH = "."
python -m 02_agentic_ai_basics.tool_use       # decisão direta (function calling)
python -m 02_agentic_ai_basics.react_pattern  # loop com raciocínio explícito
```

**Bash (Linux/macOS):**
```bash
export PYTHONPATH="."
python -m 02_agentic_ai_basics.tool_use
python -m 02_agentic_ai_basics.react_pattern
```

## O que a demo mostra

Os dois scripts dependem do LLM já na primeira chamada. **Sem o Ollama no ar**, eles imprimem o cabeçalho e a etapa inicial e então param com `OpenAIConnectionError: Connection error.` (exit 1). Saída real de `tool_use.py` sem LLM:

```
======================================================================
Tool Use Pattern: What is CVE-2024-1234?
======================================================================

[Request Tool]
...
langchain_openai.chat_models.base.OpenAIConnectionError: Connection error.
```

E de `react_pattern.py` sem LLM:

```
======================================================================
ReAct Pattern: What is CVE-2024-1234?
======================================================================

[Iteration 1]
...
langchain_openai.chat_models.base.OpenAIConnectionError: Connection error.
```

Com o Ollama no ar, `tool_use.py` segue para `[Execute Tool]` (mostrando `search_cve(...)` e o `Result:` da base) e `[Analysis]`, e `react_pattern.py` imprime cada `[Iteration N]` com `Thought/Action`, a linha `Observation:` e, no fim, o `Final answer:`. O texto gerado varia conforme o modelo.

## Exercícios

1. **Troque o alvo da investigação.** Edite `QUERY`/`CVE_ID` em `utils/agentic_utils.py` (ou passe outro CVE da base) e rode os dois scripts. Compare a chamada JSON do `tool_use.py` com a sequência `Thought/Action/Observation` do `react_pattern.py` para o mesmo CVE.
2. **Force o caminho "não encontrado".** Use um ID inexistente (ex.: `CVE-9999-99999`). Observe que `search_cve` devolve `{"status": "not_found", ...}` e veja como cada estratégia reage ao resultado vazio.
3. **Entenda o parser do ReAct.** Em `react_pattern.py`, a regex `ACTION_RE` espera exatamente `Action: nome[arg]`. Faça o modelo (ou um texto de teste) escrever a ação num formato ligeiramente diferente e observe a mensagem "Model didn't request an action...". Explique por que o parser é frágil.
4. **Adicione uma tool nova.** Crie uma função decorada com `@tool` em `utils/tools.py` (ela entra sozinha no `TOOL_REGISTRY`), descreva-a no prompt de sistema correspondente e peça ao modelo que a use. Rode os dois scripts e confira a seleção da tool.
5. **Meça o custo do loop.** No `react_pattern.py`, reduza `MAX_STEPS` e observe a mensagem "Reached max iterations without a final answer." quando o modelo não converge. Discuta o tradeoff entre número de passos e custo/latência.

## Referências

- [Documentação do LangChain](https://docs.langchain.com/oss/python/langchain/tools) — `@tool` e function calling.
- [LLM_SETUP.md](../LLM_SETUP.md) — como subir Ollama / LM Studio / OpenAI.
- [README raiz](../README.md) — mapa dos módulos, base de CVEs e utilitários compartilhados.
