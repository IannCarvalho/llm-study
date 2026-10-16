# 06 — Avaliação de Agentes (trajetória e custo por tarefa)

> Pré-requisitos: roda **sem LLM** e sem Ollama. Precisa dos pacotes que o módulo
> 12 já usa (`numpy`, `rank-bm25`, `sentence-transformers`) porque reutiliza o
> motor híbrido do projeto. A demo (`python -m 06_evals.agent_evals`) carrega o
> modelo de embeddings do caminho híbrido; os testes NÃO baixam modelo (usam
> stub).

`rag_metrics.py` avalia **uma** recuperação: embute a query, puxa o top-k, mede
os acertos. É o certo para RAG ingênuo. É o errado para um **agente**, que decide
*se* busca, planeja várias sub-consultas, roda uma por vez e só para quando julga
a pergunta respondida. Avaliar só o conjunto final de documentos ignora tudo o
que o agente fez para chegar lá. Este arquivo avalia a **trajetória** e a
**tarefa inteira**.

## Por que importa

Em entrevista de AI Engineering, "como você avalia um agente?" é pergunta de
corte. A resposta errada é "conto os tokens de cada chamada de ferramenta". A
resposta certa separa dois níveis:

| Nível | O que mede | Pega o quê |
|-------|-----------|------------|
| Avaliação de **resposta final** | o conjunto de documentos / a resposta gerada | se o resultado está correto |
| Avaliação de **trajetória** | o caminho: quantos passos, quais buscas, quanto desperdício | *como* o agente chegou lá — e quanto custou |

Um agente pode acertar a resposta por sorte, com uma trajetória cara e cheia de
passos redundantes. A avaliação de resposta dá "passou"; a de trajetória mostra
que ele gastou o dobro de buscas e carregou contexto inútil adiante. As duas são
complementares — resposta final é o piso, trajetória é o que distingue um agente
eficiente de um que só não errou.

## Conceitos

### Trajetória vs resposta final
A **resposta final** é o `success` deste harness: todos os CVEs esperados foram
recuperados? A **trajetória** é o resto — `steps` (número de buscas),
`search precision/recall` (o agente planejou as buscas certas?), e
`redundant_calls` (buscas que não trouxeram nenhum CVE novo). Um agente que
recupera o CVE certo em 1 passo e outro que recupera em 4 passos, com 3
redundantes, têm a **mesma** resposta final e trajetórias muito diferentes.

### Custo por tarefa vs custo por chamada
O erro comum é otimizar o custo de **cada chamada de ferramenta** (encurtar a
saída). O GitHub mediu isso no Copilot com o RTK (*Rust Token Killer*), um
utilitário que encurta a saída de shell antes de o agente lê-la, e relatou: ao
cortar texto que depois fazia falta, o modelo às vezes reabria a saída original
ou re-rodava o comando para recuperar o que faltava; esses passos de recuperação
adicionavam turnos e carregavam mais contexto adiante, de modo que, na média, a
**tarefa** usava mais tokens e demorava mais — "economizamos tokens localmente e
gastamos mais globalmente". A conclusão deles, nas palavras do post: *"tokens per
tool call is the wrong objective. An efficiency change has to be evaluated across
the complete task"* — e a 1ª das cinco lições do artigo: *"Optimize the completed
task, not the tool call."* (alegação do fornecedor; ver Referências).

Neste harness, `redundant_calls` é esse mesmo fenômeno em miniatura: uma busca
localmente barata (ela "funciona", retorna resultados) que não move a tarefa —
só gasta um passo e empurra mais contexto adiante. É por isso que a métrica certa
é por tarefa (`total_steps`, `total_redundant_calls`, tokens estimados do
contexto acumulado), não o tamanho de uma resposta isolada.

### Tokens de contexto são uma ESTIMATIVA
`est_context_tokens` é `bytes / 4` do contexto acumulado (evidência + trace). É
um **proxy**, não um tokenizer: ~4 bytes/token é a regra de bolso para inglês, é
determinístico e não depende de `tiktoken`. Serve para comparar o custo
*relativo* das trajetórias (uma que carrega mais evidência estima mais alto), não
para prever uma conta de cobrança. Por isso vem rotulado como "estimate" em todo
lugar onde aparece.

## Relação com observabilidade (Módulo 05)
Tracing (05) responde *o que o agente fez* — a sequência de passos, cada chamada,
cada resultado. A avaliação de trajetória (06) pega essa mesma sequência e
responde *isso foi bom?*: o número de passos foi o esperado? houve chamada
redundante? as buscas cobriram o plano de referência? Em produção o trace vem do
tracer (LangSmith/Langfuse do 05); aqui o "trace" é determinístico, reconstruído
do `state.trace` que o agente do módulo 12 já produz — por isso dá para avaliar a
trajetória inteira sem LLM e sem instrumentação externa.

## Arquivos

### `agent_evals.py` — avaliação de trajetória e custo por tarefa
Reutiliza o agente determinístico de `12_agentic_rag/agentic_rag.py` (via
`importlib.import_module`, porque o pacote começa com dígito) e roda-o no caminho
sem LLM sobre um conjunto de tarefas:

- **tarefas simples e compostas** sobre os CVEs, cada uma com os ids esperados e
  o número esperado de sub-consultas;
- por tarefa: **sucesso** (ids esperados recuperados), **precisão/recall das
  buscas** vs o plano de referência, **número de passos**, **chamadas
  redundantes**, **tokens de contexto estimados** (bytes/4 — estimativa);
- **relatório agregado** da suíte inteira.

Tudo determinístico: a mesma entrada dá o mesmo relatório.

### `test_agent_evals.py` — testes (em `tests/`)
Métricas puras testadas direto; o caminho ponta-a-ponta roda sobre um **motor
stub** (monkeypatch de `create_search_engine`, como em
`tests/test_agentic_rag.py`), sem baixar modelo nem usar rede.

## Como rodar

```powershell
$env:PYTHONPATH = "."   # na raiz do projeto

# Avaliação de agentes (não precisa de Ollama):
python -m 06_evals.agent_evals
```

## O que a demo mostra

Trecho da saída real (`python -m 06_evals.agent_evals`):

```
Agent Evals — trajectory & per-task cost (deterministic, no Ollama)
Corpus: 3 CVE documents | agent: 12_agentic_rag (hybrid)
Context tokens are an ESTIMATE (bytes/4), not a tokenizer count.

Task: simple_sql_injection
  Query: "Is there a SQL injection vulnerability that bypasses authentication?"
  Expected ids:   ['CVE-2024-5678']
  Retrieved ids:  ['CVE-2024-1234', 'CVE-2024-5678', 'CVE-2024-9012']
  Success:        True
  Steps (searches): 2  (expected 2)
  Search precision / recall: 1.00 / 1.00
  Redundant calls: 1
  Est. context tokens: ~1002  (estimate, bytes/4)

Task: compound_rce_plus_severity
  Query: "Which RCE CVEs affect request handlers, and which one is the most severe?"
  Success:        True
  Steps (searches): 3  (expected 3)
  Search precision / recall: 1.00 / 1.00
  Redundant calls: 2
  Est. context tokens: ~1051  (estimate, bytes/4)

--------------------------------------------------------------------------
Aggregate (whole task set)
  tasks:                   4
  success rate:            1.00
  mean search precision:   1.00
  mean search recall:      1.00
  total steps:             10
  total redundant calls:   6
  total est. ctx tokens:   ~4115  (estimate)
```

Leitura: todas as tarefas **passam** na resposta final (`success rate 1.00`), mas
a trajetória revela o custo que a resposta final esconde — **6 chamadas
redundantes** em 10 passos. Cada redundante é uma busca que "funcionou" mas não
trouxe CVE novo: barata por chamada, cara por tarefa. É exatamente a armadilha do
"custo por chamada" aplicada aqui.

## Exercícios

1. Adicione uma tarefa cuja pergunta NÃO precisa de recuperação (ex.: "olá, o que
   você faz?") e confirme que a trajetória tem 0 passos e 0 redundantes.
2. Mude `TOP_K` em `12_agentic_rag/agentic_rag.py` (localmente, sem commitar) de 3
   para 1 e observe o efeito em `search recall` e em `redundant_calls`.
3. Troque a estimativa `bytes/4` por uma contagem real com `tiktoken` (import
   lazy + `pytest.importorskip` no teste) e compare os números — a ordem relativa
   das trajetórias muda?
4. Crie uma tarefa composta de 3 tópicos (ex.: RCE + SQL + crypto) e verifique se
   o planejador respeita o `MAX_ITERATIONS` do módulo 12.
5. Acrescente uma métrica de "passos até o primeiro acerto" (em que busca o
   primeiro id esperado entrou na evidência) e discuta por que ela complementa
   `redundant_calls`.

## Referências

- GitHub Blog — *How we make AI coding more cost efficient without sacrificing
  task quality* (02/09/2026): a armadilha do custo local, o experimento com o RTK
  e a lição "otimize a tarefa completa, não a chamada de ferramenta".
  [github.blog](https://github.blog/ai-and-ml/github-copilot/how-we-make-ai-coding-more-cost-efficient-without-sacrificing-task-quality/)
- RTK (Rust Token Killer) — utilitário citado no post como o encurtador de saída
  avaliado. [rtk-ai.app](https://www.rtk-ai.app/docs)
