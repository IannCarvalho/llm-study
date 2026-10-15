# Module 12: Agentic RAG — Multi-Step Retrieval

Naive RAG retrieves **once**. Agentic RAG wraps a **decision loop** around
retrieval: the agent decides *whether* to search, *what* to search for, runs
sub-queries iteratively, accumulates context, and only then generates an answer.

This module demonstrates agentic RAG over the project's CVE knowledge base. The
decision + retrieval path is **deterministic and runs without Ollama**; only the
final natural-language generation uses the LLM, and it degrades gracefully when
the LLM is unavailable.

---

## Naive RAG vs Agentic RAG

```
Naive RAG (single-shot):
  query ──► retrieve top_k ──► stuff into prompt ──► generate
  Good when the answer lives in one passage.

Agentic RAG (multi-step):
  query ──► DECIDE: retrieval needed? ──► PLAN sub-queries
        ──► loop: search sub-query ──► accumulate evidence ──► DECIDE: enough?
        ──► generate from accumulated context
  Good when the question is compound ("which RCE CVEs affect request handlers,
  and which is the most severe?") and no single retrieval can answer it.
```

A compound question pulls on **different signals** ("RCE request handler" vs
"most severe") and often needs a **comparison** that only makes sense after both
facets are gathered. One retrieval cannot do that; a loop can.

---

## O que torna isto "agêntico"

A parte agêntica é a **decisão**, não o modelo. Neste módulo a decisão é
determinística (regras), por dois motivos:

1. **Reprodutibilidade** — os mesmos CVEs são recuperados sempre, sem depender
   de um LLM não-determinístico.
2. **Roda offline** — o caminho de busca funciona sem Ollama; a geração final é
   a única parte que precisa do LLM.

O controlador faz três decisões por regra:

- **`needs_retrieval(query)`** — a pergunta precisa da base? (uma saudação não
  precisa; qualquer menção a CVE/vulnerabilidade precisa).
- **`plan_sub_queries(query)`** — decompõe a pergunta em sub-queries focadas, uma
  por tópico detectado (RCE, SQL injection, cripto, request handler, ...).
- **`wants_comparison(query)`** — a pergunta pede ranqueamento ("mais severo",
  "compare")? Se sim, roda uma varredura extra de severidade e a síntese ordena
  por CVSS.

A geração final (`generate_answer`) tenta o `LLMClient.generate`; em **qualquer**
falha (Ollama fora do ar, dependência/credencial ausente, timeout) ela cai no
`deterministic_conclusion` — a resposta baseada só nas evidências recuperadas e
nos scores CVSS do dataset — imprimindo "LLM unavailable — showing retrieved
context and deterministic conclusion instead".

---

## Quando usar agentic RAG

| Situação | Naive RAG | Agentic RAG |
|----------|-----------|-------------|
| Resposta num único trecho | ✅ Ideal | Exagero |
| Pergunta composta (vários fatos) | ❌ Falha | ✅ Ideal |
| Precisa comparar/ranquear | ❌ Falha | ✅ Ideal |
| Latência mínima | ✅ 1 busca | ⚠️ N buscas |
| Custo por consulta | Baixo | Maior (mais buscas) |

Regra prática: use agentic RAG quando a pergunta exige **mais de uma recuperação
ou uma comparação entre documentos**; para lookup simples, naive RAG basta.

---

## Como rodar

A partir da **raiz do repositório** (PYTHONPATH = raiz):

```bash
python -m 12_agentic_rag.agentic_rag
```

O caminho de busca/decisão roda sem Ollama. Para ver a **geração via LLM** em
vez do fallback, configure o LLM como os outros módulos (Ollama local ou OpenAI
via `.env`) e instale o stack de LLM do projeto:

```bash
pip install -r requirements.txt   # inclui o cliente LLM (langchain)
```

Sem esse stack, o módulo roda igual e mostra a conclusão determinística — é o
comportamento esperado de degradação, não um erro.

---

## O que o script faz (exemplo de saída)

Para `"Which RCE CVEs affect request handlers, and which one is the most severe?"`:

```
plan: decomposed into 2 sub-queries ->
      ['remote code execution buffer overflow command injection',
       'request handler HTTP request parsing buffer overflow']
decision: comparison detected -> added severity sweep
iter 1: search 'remote code execution ...'  -> ['CVE-2024-1234', ...]
iter 2: search 'request handler ...'         -> ['CVE-2024-1234', ...]
iter 3: search 'critical high severity ...'  -> ['CVE-2024-1234', ...]
Most severe among the retrieved CVEs: CVE-2024-1234 (CVSS 9.8).
```

O agente **decompôs** a pergunta, **encadeou** três buscas, **acumulou** as
evidências e **concluiu** o item mais severo por CVSS — tudo sem LLM.

---

## Arquivos

- `agentic_rag.py` — o loop agêntico: planner determinístico, controlador de
  iteração, acumulador de evidências, síntese determinística e geração via LLM
  com fallback.
- `__init__.py` — marca o módulo como pacote (import via `python -m`).

Reutiliza os utils do projeto (`utils/search.py`, `utils/data_loader.py`,
`utils/llm_client.py`) exatamente como os módulos 04 e 06.
