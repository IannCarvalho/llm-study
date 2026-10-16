# 06 — Avaliação de LLM (Evals)

> Pré-requisitos: `rag_metrics.py` roda **sem LLM** (determinístico, offline).
> `llm_as_judge.py` precisa de um LLM no ar (Ollama local por padrão — veja
> [../LLM_SETUP.md](../LLM_SETUP.md)); sem ele, degrada com mensagem instrutiva.
> Python 3.11.

"Não dá para melhorar o que não se mede." Os módulos anteriores *constroem*
pipelines (RAG, agentes); este mostra como **medir se eles são bons** — a
contraparte natural da observabilidade (Módulo 05): o tracing responde *o que
aconteceu*, os evals respondem *foi bom?*.

## Por que importa

Avaliar a saída de um LLM é um dos pontos mais cobrados em AI Engineering: sem
evals não há como comparar modelos, detectar regressão de prompt nem justificar
uma mudança. Duas famílias complementares aparecem aqui:

| Abordagem | Precisa de LLM? | Determinística? | Para quê |
|-----------|-----------------|-----------------|----------|
| Métricas offline (reference-based) | Não | Sim | Avaliar *retrieval* (a metade RAG) de forma reproduzível |
| LLM-as-judge | Sim | Aproximada | Avaliar *geração* quando não há label humano nem resposta exata |

Regra prática: use as métricas offline como piso confiável e o LLM-as-judge para
o que elas não alcançam (qualidade da redação, fidelidade semântica), sempre
checando um contra o outro.

## Conceitos

- **precision@k** — dos *k* primeiros documentos recuperados, a fração que é de
  fato relevante. A implementação divide pelo próprio *k* (não pelo número de
  resultados devolvidos): é a definição padrão e evita inflar listas curtas.
- **Ground truth** — para cada query, o conjunto de IDs de CVE que um retriever
  correto deveria trazer. Aqui ele é derivado do próprio dataset (uma RCE, uma
  SQL injection e uma fraqueza criptográfica), então os rótulos não são palpite.
- **groundedness proxy** — sinal barato e sem LLM de "a resposta é sustentada
  pelo contexto?": a fração dos termos de conteúdo da query que aparecem nos
  documentos recuperados (sobreposição léxica). É um *proxy* — não entende
  significado —, mas é instantâneo e pega o erro clássico de recuperar documento
  fora do tema.
- **LLM-as-judge** — usar um *segundo* LLM, com rubrica explícita, para pontuar a
  saída de um primeiro. Serve quando não existe resposta de referência exata.

## Arquivos

- `rag_metrics.py` — métricas offline de retrieval (precision@k + groundedness
  proxy) sobre o motor híbrido do projeto (`create_search_engine("hybrid")`) e a
  base de CVEs. Mesma entrada, mesmo resultado: roda sem nenhum backend de LLM.
- `llm_as_judge.py` — o padrão LLM-as-judge em dois passos:
  1. **GENERATE** — pega um ou dois CVEs e pede ao LLM um resumo de segurança (a
     saída "candidata").
  2. **JUDGE** — envia um segundo prompt (o juiz) com o contexto-fonte + o resumo
     candidato, pedindo nota 1–5 com justificativa em JSON estrito para três
     eixos: **groundedness** (toda afirmação tem suporte na fonte?),
     **completeness** (os fatos-chave estão presentes?) e **clarity** (está
     claro?). A chamada do juiz usa `temperature=0.0` (avaliação o mais
     determinística possível) e um `system_prompt` que exige só JSON.

Por que separar o juiz? O modelo que *escreve* é mau avaliador da própria
resposta no mesmo turno; isolar a avaliação num prompt com rubrica e saída legível
por máquina é o cerne da técnica. As notas ainda são aproximadas (o juiz é um LLM)
— por isso o par com `rag_metrics.py`.

## Como rodar

A partir da raiz do repositório, com o pacote no path:

```powershell
# Windows (PowerShell)
$env:PYTHONPATH = "."
python -m 06_evals.rag_metrics      # métricas offline (não precisa de Ollama)
python -m 06_evals.llm_as_judge     # LLM-as-judge (precisa de Ollama no ar)
```

```bash
# Linux/macOS (Bash)
PYTHONPATH="." python -m 06_evals.rag_metrics
PYTHONPATH="." python -m 06_evals.llm_as_judge
```

Setup de provedor de LLM: veja [../LLM_SETUP.md](../LLM_SETUP.md).

## O que a demo mostra

`rag_metrics.py` roda sem Ollama e reporta precision@1 e o groundedness proxy por
query, mais os agregados. Sobre a base de 3 CVEs sintéticos, cada query recupera o
CVE certo em primeiro lugar:

```
Offline RAG Metrics (deterministic, no LLM / no Ollama required)
Corpus: 3 CVE documents | metric cutoff: k=1

Query: "buffer overflow remote code execution in the request handler"
  Expected relevant: ['CVE-2024-1234']
  Retrieved (ranked): ['CVE-2024-1234', 'CVE-2024-5678', 'CVE-2024-9012']
  precision@1:        1.00
  groundedness proxy:  1.00  (query terms covered by context)
...
Aggregate
  mean precision@1:       1.00
  mean groundedness proxy: 1.00
```

> Com apenas 3 documentos, precision@1 = 1.00 é esperado e **não** mede o quanto
> um retriever é bom — a base é pequena demais para discriminar. O valor didático
> está em ver *como* a métrica é calculada, não no número em si.

`llm_as_judge.py` sem Ollama imprime o cabeçalho e então degrada com uma mensagem
instrutiva, sem travar (exit 0):

```
LLM-as-Judge: generate a summary, then score it with a second prompt
Subject CVEs: ['CVE-2024-1234', 'CVE-2024-5678']

[error] Could not reach the LLM backend. Is Ollama running (e.g. `ollama serve`)
and the configured model pulled?
Details: Connection error.
```

Com o Ollama no ar, ele imprime o resumo gerado e, em seguida, o veredito do juiz
(nota 1–5 por eixo + média). Os valores variam conforme o modelo.

## Exercícios

1. **Afrouxe o ground truth.** Em `EVAL_CASES` (`rag_metrics.py`), acrescente um
   segundo ID a `relevant_ids` de uma query e rode de novo. Explique por que
   `precision@1` não muda enquanto `precision@3` mudaria — e lembre que a métrica
   divide por *k*, não pelo número de acertos possíveis.
2. **recall@k por conta própria.** `rag_metrics.py` só traz `precision_at_k`.
   Escreva `recall_at_k(retrieved_ids, relevant_ids, k)` = acertos no top-k ÷
   `len(relevant_ids)` e discuta onde precision e recall divergem quando uma query
   tem mais de um documento relevante.
3. **MRR.** Implemente o Mean Reciprocal Rank: para cada caso, `1 / (posição do
   primeiro relevante)`; média sobre os casos. Rode e compare com o
   `precision@1` reportado — em que situação os dois discordam?
4. **Teste o groundedness proxy.** Invente uma query cujos termos de conteúdo
   *não* apareçam em nenhum CVE (ex.: "kubernetes pod autoscaling latency") e
   verifique que `groundedness_proxy(...)` cai perto de 0.0. Por que isso é um
   sinal de recuperação fora do tema?
5. **Cruze as duas famílias.** Com o Ollama no ar, rode `llm_as_judge.py` e
   compare a nota de *groundedness* do juiz com o groundedness proxy de
   `rag_metrics.py`. Onde um pega algo que o outro não pega?

## Referências

- [Kiro — Correctness (property-based testing)](https://kiro.dev/docs/specs/correctness/) — avaliação automática de saída de agente dentro de specs.
- [Documentação do LangChain](https://python.langchain.com/) — o cliente de LLM usado pelo juiz vive sobre o `ChatOpenAI` do LangChain.
