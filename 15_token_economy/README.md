# 15 — Economia de Tokens (Token Economy)

> Pré-requisitos: roda **sem LLM**, sem Ollama, sem chave e sem pacote extra.
> O núcleo usa só a stdlib + `utils.*` do próprio repo. `tiktoken` é **opcional**
> (import lazy) e só muda a contagem de tokens de estimativa para exata.

Como medir o custo de uma chamada a um LLM, orçar esse custo, e cortar tokens
**sem** acabar gastando mais no fim da tarefa. O módulo liga três ideias:
a *anatomia da conta* (para onde vão os tokens), um *compressor de saída de
ferramenta* no estilo [RTK](https://github.com/rtk-ai/rtk), e a *armadilha da
métrica local* — o resultado do GitHub de que comprimir demais pode encarecer a
tarefa inteira.

## Por que importa

Token é dinheiro e é janela de contexto. Mas "usar menos tokens" não é o
objetivo certo: uma resposta de ferramenta curta demais faz o agente **reabrir
o original ou re-rodar o comando** para recuperar o que faltou — e aí a tarefa
usa *mais* tokens e demora mais. O GitHub mediu exatamente isso ao avaliar o RTK
no Copilot: *"We saved tokens locally and spent more globally"* (economizamos
localmente e gastamos mais globalmente). O objetivo é otimizar a **tarefa
inteira**, não a chamada isolada. Saber medir antes de cortar — e cortar só o
ruído, preservando o que o modelo precisa — é a diferença entre economia real e
economia de araque.

## Conceitos

### Anatomia da conta
Uma chamada ao modelo soma várias partes: **system prompt**, **histórico** da
conversa, **contexto RAG** recuperado, **saída de ferramenta** (o que o RTK
comprime) e a **saída do modelo**. Em modelos que expõem raciocínio, os **tokens
de raciocínio** (hidden "thinking") contam como saída mesmo sem o usuário os ver.
A saída de ferramenta é **uma fatia da entrada**, que é **uma fatia da conta** —
por isso comprimir a saída de bash em 90% **não** corta a conta em 90% (o próprio
README do RTK é explícito nisso, e estima tokens como `bytes/4`, sem tokenizer:
percentuais confiáveis, números absolutos aproximados).

### Medir antes de cortar
`token_budget.py` estima tokens (`bytes/4`, igual ao RTK; `tiktoken` opcional) e
monta a anatomia a partir de dados **reais** do repo: o prompt `RAG_SYSTEM` de
`utils.prompts` e os documentos de `utils.data_loader.get_cve_documents`. Com a
anatomia na mão, um `RequestBudget` diz se a requisição cabe no orçamento de
entrada/saída, e um `RateLimiter` (token bucket determinístico, relógio
injetável) limita o gasto por cliente.

### Compressão seletiva + caminho de recuperação
`output_compressor.py` é uma reimplementação **didática** do RTK em Python,
seguindo a política seletiva que o GitHub adotou depois de avaliá-lo:
1. **Preservar** saída tipo código/arbitrária (`cat`, `git diff`, `git show`,
   scripts) — devolvida intacta.
2. **Reorganizar** resultados de busca (`grep`) **sem perder** nenhuma linha.
3. **Comprimir ruído** repetitivo (`pytest`, `git status`, `git log`, `ls`,
   `ruff check`) — e só manter a compressão quando a economia é **substancial**.
Toda compressão guarda o **original** e devolve um ponteiro (`.recover()`),
espelhando o caminho de recuperação do RTK/GitHub.

### Catálogo de técnicas (ligado aos módulos do repo)
- **Comprimir saída de ferramenta** = o que o RTK faz (este módulo).
- **Cache semântico** de respostas = [`14_semantic_caching`](../14_semantic_caching/README.md).
- **Prompt caching do provedor** — reaproveita o prefixo estável (system prompt +
  contexto fixo) entre chamadas; o RTK documenta que a compressão dele não quebra
  o cache do Claude porque filtra uma vez e o resultado entra no histórico.
- **Sumarização / memória** com janela deslizante = [`11_memory`](../11_memory/README.md).
- **Recorte de contexto** — top-k do RAG (menos documentos no prompt) via
  `utils.search.create_search_engine`; menos é mais quando o excedente é ruído.
- **Orçamento e saída estruturada** = [`10_structured_output`](../10_structured_output/README.md)
  (saída curta e validada evita re-tentativas que inflam a conta).
- **Roteamento por custo** — mandar a chamada barata para um modelo menor e só o
  que precisa de capacidade para o modelo caro.

### A lição do GitHub (a armadilha da métrica local)
`task_cost_sim.py` simula, de forma determinística, "por chamada vs por tarefa":
compressão leve só tira ruído e **baixa** o total; compressão agressiva corta
informação necessária, dispara **recuperação** (reabrir original + re-rodar +
carregar o contexto de novo) e o total **sobe acima** de não comprimir nada. É a
"local metric trap" do post do GitHub, em números.

## Segurança — OWASP LLM10:2025 Unbounded Consumption
O risco [LLM10:2025 Unbounded Consumption](https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/)
do [OWASP Top 10 para LLM](https://genai.owasp.org/llm-top-10/) trata do consumo
sem limites de recursos de um LLM — um cliente que dispara chamadas (ou saídas)
sem teto estoura custo e disponibilidade. O `RateLimiter` deste módulo é a
mitigação direta: um teto de tokens por janela, determinístico e testável, para
que nenhuma requisição isolada consuma o orçamento inteiro.

## Como instalar/usar o RTK (OPCIONAL)
O RTK é uma ferramenta externa, **não é dependência** deste repo nem deste
módulo. Se você quiser usá-lo no seu próprio fluxo de agente (fora daqui):

```bash
brew install rtk            # macOS / Linux
winget install rtk-ai.rtk   # Windows
```

O README oficial pede para **conferir se o pacote instalado é o certo** (existe
outro "rtk" no crates.io): rode `rtk --version` e `rtk gain` (tem que mostrar o
painel de economia, não "command not found"). Licença: Apache-2.0 (CLI) + BUSL-1.1
(engine/proxy). Alegações de 60-90% de redução e `<10ms` de overhead são **do
fornecedor** (README do RTK), medidas sobre a saída de bash — não sobre a conta.

## Como plugar no módulo 13 (sem editar o 13)
O [`13_deployment`](../13_deployment/README.md) expõe o pipeline como API
FastAPI. Para orçar/limitar por requisição **sem tocar no 13**, embrulhe os
helpers deste módulo em volta do endpoint, do lado de fora:

```python
from importlib import import_module

token_budget = import_module("15_token_economy.token_budget")
serve = import_module("13_deployment.serve")  # NÃO é editado

# Um limitador global (ou por-cliente, com uma chave na requisição).
limiter = token_budget.RateLimiter(capacity=10_000, refill_per_sec=200)

def answer_with_budget(query: str, top_k: int = 3):
    # 1) orça a saída esperada e barra se o cliente estourou a cota
    cost = token_budget.estimate_tokens(query) + 512  # +saída estimada
    if not limiter.allow(cost):
        return {"error": "rate limited (OWASP LLM10: Unbounded Consumption)"}
    # 2) delega ao pipeline original do módulo 13, intacto
    return serve.answer_query(query, top_k=top_k)
```

## Arquivos

- `token_budget.py` — `estimate_tokens` (bytes/4; `tiktoken` opcional lazy),
  `RequestAnatomy` + `sample_rag_anatomy` (anatomia com prompts/documentos reais),
  `RequestBudget`/`BudgetReport` e `RateLimiter` (token bucket, relógio injetável).
- `output_compressor.py` — `compress(command, output)` com a política seletiva
  (preserve / reorganize / compress) e `Compressed.recover()` (caminho de volta
  ao original).
- `task_cost_sim.py` — `simulate_task(...)`: por chamada vs por tarefa, mostrando
  quando a conta total sobe.
- `samples/*.txt` — saídas **reais** capturadas neste repo (pytest verboso, git
  log, git status, ruff check com regras extras, grep, git diff), com o caminho
  absoluto trocado por `<repo>`.
- `__init__.py` — torna a pasta um pacote.
- `README.md` — este arquivo.

## Como rodar

Da **raiz do repositório** (o nome da pasta começa com dígito, use `python -m`):

```powershell
$env:PYTHONPATH = "."   # na raiz do projeto

python -m 15_token_economy.token_budget       # anatomia + budget + rate limiter
python -m 15_token_economy.output_compressor  # compressor nos samples reais
python -m 15_token_economy.task_cost_sim       # por-chamada vs por-tarefa
```

Nenhum precisa de Ollama/chave. Para a contagem exata via `tiktoken` (opcional):
`pip install tiktoken` no seu venv e passe `use_tiktoken=True` a `estimate_tokens`.

## O que a demo mostra

`token_budget` (anatomia de uma requisição RAG real, estimativa bytes/4):

```
  system prompt          94 tok     4.9%
  history                31 tok     1.6%
  RAG context           878 tok    45.9%
  tool output           878 tok    45.9%
  model output           32 tok     1.7%
  reasoning output        0 tok     0.0%
  input tokens : 1881   output tokens: 32   TOTAL: 1913
  rate limiter (cap=2, 1 tok/s): first-three=[True, True, False], after 2s=True
```

`output_compressor` (política seletiva sobre os samples reais):

```
  pytest       strategy=compress   1411 ->  110 tok (saved 92%)
  git status   strategy=noop         80 ->   80 tok (saved 0%)   # abaixo do limiar
  git log      strategy=compress    402 ->  102 tok (saved 75%)
  ruff check   strategy=compress    575 ->   26 tok (saved 95%)
  grep         strategy=reorganize  250 ->  202 tok (saved 19%)  # sem perda
  git diff     strategy=preserve     81 ->   81 tok (saved 0%)   # source-like intacto
```

`task_cost_sim` (a conta total vira contra você quando a compressão é agressiva):

```
   compression   tool tok   recovery  recov#    TOTAL
            0%       4500          0       0     4500
           30%       3150          0       0     3150
           50%       2250          0       0     2250
           70%       1350       6200       2     7550  <- costs MORE than no compression
           90%        450       6200       2     6650  <- costs MORE than no compression
```

## Exercícios

1. **Tokenizer de verdade:** instale `tiktoken`, rode `sample_rag_anatomy(use_tiktoken=True)`
   e compare com o bytes/4. Quão longe fica a estimativa? Em qual parte da conta?
2. **Ajuste o limiar:** mude `_SUBSTANTIAL_SAVING` em `output_compressor.py` e veja
   `git status`/`grep` virarem `compress` ou `noop`. Qual limiar você escolheria
   para um agente que lê muito `grep`?
3. **Rate limit por cliente:** estenda o `RateLimiter` para um dicionário de
   buckets por chave de cliente e escreva um teste determinístico (relógio
   injetável) provando que um cliente agressivo não afeta os outros.
4. **Novo comando no compressor:** adicione um filtro para `docker ps` (só os
   campos essenciais, como o RTK) com teste de recuperação do original.
5. **Mude a tarefa simulada:** em `task_cost_sim`, aumente o peso dos passos
   `needed` e ache o ponto exato de compressão onde o total cruza o baseline.

## Referências

- RTK (Rust Token Killer) — README oficial: [github.com/rtk-ai/rtk](https://github.com/rtk-ai/rtk)
- GitHub Blog (02/09/2026), "How we make AI coding more cost efficient without sacrificing task quality": [github.blog](https://github.blog/ai-and-ml/github-copilot/how-we-make-ai-coding-more-cost-efficient-without-sacrificing-task-quality/)
- OWASP Top 10 para LLM — LLM10:2025 Unbounded Consumption: [genai.owasp.org](https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/)
