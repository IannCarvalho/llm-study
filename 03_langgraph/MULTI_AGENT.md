# 03 — Multi-agente (Supervisor + Handoff)

> Pré-requisitos: a parte central roda **sem LLM** (determinística, offline). O
> passo de redação por LLM é **opcional** (precisaria de Ollama); sem ele, o grafo
> degrada para o relatório determinístico. Precisa do pacote `langgraph` apenas
> para montar/rodar o grafo — a lógica de roteamento roda sem ele.

Os scripts anteriores do módulo mostram um grafo linear (`langgraph_basics.py`) e
um grafo com um ponto de decisão (`langgraph_conditional.py`). Aqui damos o passo
seguinte: um nó **supervisor** que, a cada hop, decide qual agente especialista
roda em seguida — a arquitetura "supervisor" de sistemas multi-agente.

## Por que importa

Nem toda tarefa complexa precisa de multi-agente: um único agente com as
ferramentas e o prompt certos muitas vezes resolve. Multi-agente ganha valor
quando um agente só acumula ferramentas demais e decide mal qual usar, quando a
tarefa exige conhecimento especializado com muito contexto, ou quando é preciso
impor restrições sequenciais (destravar um passo só depois de outro). O coração
do desenho é **context engineering**: decidir o que cada agente enxerga, para não
afogar o modelo com contexto irrelevante.

Neste módulo isso aparece em miniatura: três especialistas (triagem de
severidade, recuperação de CVE, redação de relatório) coordenados por um
supervisor, sobre a base de CVEs do repositório.

## Conceitos

### Um agente só vs. multi-agente

Comece com **um agente**. Troque para multi-agente quando houver dor real:
muitas ferramentas confundindo a decisão, domínios distintos com contexto longo,
ou necessidade de paralelismo/desenvolvimento distribuído (times mantendo partes
independentes). Multi-agente agrega orquestração e latência — só vale quando paga
por isso.

### Supervisor vs. handoff

São dois padrões relacionados, não opostos:

- **Supervisor**: um nó central controla o fluxo e decide, a cada passo, qual
  especialista invocar com base no estado atual. Todo o roteamento passa por ele.
  É o padrão deste script: `supervisor_decide(state)` nomeia o próximo agente, e
  o grafo ramifica por `add_conditional_edges`.
- **Handoff**: o comportamento muda **dinamicamente a partir do estado**. Uma
  transição grava uma variável de estado (ex.: `active_agent` / `current_step`)
  que passa a reger o próximo passo — transferindo o controle a outro agente ou
  reconfigurando o atual. O termo "handoffs" foi cunhado pela OpenAI para
  transferir controle via chamadas de ferramenta (ex.: `transfer_to_specialist`).

No script, o supervisor é a espinha dorsal e o handoff aparece como a decisão
baseada em estado: se a triagem **não** identifica um CVE, o fluxo pula a
recuperação e vai direto ao relatório (`triage -> report`), em vez de fingir que
tem dado para resumir.

### Outros padrões (para situar)

A documentação da LangChain lista ainda **Subagents** (um agente principal chama
subagentes como ferramentas — todo roteamento passa pelo principal), **Router**
(um passo classifica a entrada e direciona a especialistas, sintetizando o
resultado), **Skills** (prompts/conhecimento carregados sob demanda, um agente só
no controle) e **Custom workflow** (fluxos sob medida em LangGraph, misturando
lógica determinística e agêntica — é onde este script se encaixa). "Network" é o
caso em que qualquer agente pode falar com qualquer outro, sem hierarquia central.

## Custo e latência

Cada hop entre agentes é, em produção, uma chamada de LLM a mais: mais tokens,
mais latência, mais pontos de falha. O supervisor em si costuma ser a chamada mais
cara (ele lê o contexto e decide a rota a cada passo). Por isso:

- comece com um agente; só fragmente quando a decisão de ferramentas degrada ou o
  contexto estoura;
- mantenha a rota determinística onde der — aqui o roteamento é por **regras puras
  sobre o estado** (`supervisor_decide`), sem gastar LLM para decidir o caminho,
  reservando o modelo só para o passo de redação (e ainda assim opcional);
- um handoff que pula etapas (saltar a recuperação quando não há CVE) corta
  trabalho e tokens inúteis.

## Relação com os subagents do Módulo 08

O Módulo 08 descreve **subagents / orquestração** no nível de *plataforma*:
delegar trabalho independente a agentes auxiliares (pesquisar, revisar,
implementar em paralelo) e consolidar o resultado. É a mesma ideia — dividir e
coordenar — mas lá a orquestração é a própria plataforma (Kiro/Claude) decidindo
delegar, enquanto aqui ela é uma **máquina de estados explícita e in-process**:
você vê e testa cada aresta. A distinção do 08 vale: *skill* é
conhecimento/procedimento que o mesmo agente aplica; *subagent* é trabalho
independente que vale isolar. O supervisor deste módulo é o "como" de baixo nível
por trás de uma orquestração desse tipo.

## Arquivos

- [`langgraph_multi_agent.py`](langgraph_multi_agent.py) — supervisor que roteia
  entre três especialistas (triagem, recuperação, relatório). Roteamento em
  funções puras; `langgraph` importado só dentro de `build_graph()`; passo de LLM
  opcional com degradação.
- [`MULTI_AGENT.md`](MULTI_AGENT.md) — este documento.
- [`../tests/test_multi_agent.py`](../tests/test_multi_agent.py) — testa o
  roteamento puro sem `langgraph` e a montagem/execução do grafo com
  `pytest.importorskip("langgraph")`.

## Como rodar

A partir da raiz do repositório:

```
# com langgraph instalado (grafo completo):
python -m 03_langgraph.langgraph_multi_agent

# apenas a lógica de roteamento (sem langgraph) é exercida pelos testes:
python -m pytest tests/test_multi_agent.py -q
```

## O que a demo mostra

Trecho da saída real da execução (sem Ollama — o passo de LLM degrada e o grafo
usa o relatório determinístico):

```
Request: Triage CVE-2024-1234 and write it up.
[triage]  -> CVE-2024-1234 selected (CRITICAL)
[retrieve] -> found CVE-2024-1234
[report]  (LLM unavailable: ModuleNotFoundError; using deterministic report)
Final report:
CVE CVE-2024-1234 — severity CRITICAL (CVSS 9.8).
Agents run: triage -> retrieve -> report

Request: What is the most serious SQL injection issue?
[triage]  -> CVE-2024-5678 selected (HIGH)
Final report:
CVE CVE-2024-5678 — severity HIGH (CVSS 8.2).
Agents run: triage -> retrieve -> report

Request: Investigate CVE-0000-0000.
[triage]  -> CVE-0000-0000 selected (not in base)
[retrieve] -> not found
Final report:
CVE-0000-0000 was requested but is not present in the CVE base.
Agents run: triage -> retrieve -> report
```

Repare no handoff: um pedido sem CVE identificável roteia `triage -> report`,
pulando a recuperação.

## Exercícios

1. Acrescente um quarto especialista `remediate` que, para CVEs CRITICAL, anexa
   um passo de mitigação ao relatório; faça o supervisor roteá-lo só nesse caso.
2. Troque a aresta determinística do supervisor por uma decisão via LLM (import
   lazy) e meça quantas chamadas de modelo isso adiciona por requisição.
3. Faça a triagem devolver **vários** CVEs e rode a recuperação em paralelo
   (um nó por CVE), consolidando no relatório — compare com o padrão "Router".
4. Escreva um teste que force `cve_data` vazio e prove que o passo de LLM nunca é
   chamado (o relatório determinístico é retornado).
5. Converta o handoff para o mecanismo de `Command` do LangGraph (uma ferramenta
   que grava `active_agent` no estado) e compare com o roteamento por regra.

## Referências

- LangChain — Multi-agent (visão geral, padrões, quando NÃO usar):
  [docs.langchain.com/oss/python/langchain/multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent)
- LangChain — Handoffs (comportamento guiado por estado, mecanismo `Command`):
  [docs.langchain.com/oss/python/langchain/multi-agent/handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs)
- LangGraph `langgraph-supervisor` (implementação hierárquica de referência):
  [reference.langchain.com/python/langgraph-supervisor](https://reference.langchain.com/python/langgraph-supervisor)
