# 12 — Agentic RAG: recuperação multi-etapa

> Pré-requisitos: a decisão e a recuperação rodam **sem LLM** (sem Ollama, sem rede, sem chave); só a **geração final** da resposta em linguagem natural usa o LLM, e ela degrada com elegância quando o LLM não está disponível. Configuração de provedor em [../LLM_SETUP.md](../LLM_SETUP.md).

RAG ingênuo recupera **uma vez**: embute a pergunta, puxa os top-k documentos, injeta no prompt e gera. Agentic RAG põe um **laço de decisão** em volta da recuperação: o agente decide *se* precisa buscar, *o que* buscar, roda sub-queries uma a uma, acumula o contexto e só então gera a resposta. Este módulo demonstra isso sobre a base de CVEs do projeto.

## Por que importa

Uma pergunta composta puxa **sinais diferentes** e muitas vezes exige uma **comparação** que só faz sentido depois de reunir as duas pontas. Exemplo:

> "Which RCE CVEs affect request handlers, and which one is the most severe?"

"RCE request handler" e "most severe" não cabem numa única recuperação; um laço resolve. É quando a pergunta exige **mais de uma recuperação ou uma comparação entre documentos** que o agentic RAG ganha do ingênuo — para lookup simples, o ingênuo basta.

```
RAG ingênuo (single-shot):
  query ──► retrieve top_k ──► stuff into prompt ──► generate
  Bom quando a resposta está num único trecho.

Agentic RAG (multi-step):
  query ──► DECIDE: precisa recuperar? ──► PLANEJA sub-queries
        ──► loop: busca sub-query ──► acumula evidência ──► DECIDE: suficiente?
        ──► gera a resposta do contexto acumulado
  Bom para pergunta composta, em que nenhuma recuperação isolada responde.
```

## Conceitos

### O que torna isto "agêntico"

A parte agêntica é a **decisão**, não o modelo. Aqui a decisão é determinística (regras), por dois motivos:

1. **Reprodutibilidade** — os mesmos CVEs são recuperados sempre, sem depender de um LLM não-determinístico.
2. **Roda offline** — o caminho de busca funciona sem Ollama; a geração final é a única parte que precisa do LLM.

O controlador faz três decisões por regra (funções em `agentic_rag.py`):

- **`needs_retrieval(query)`** — a pergunta precisa da base? Uma saudação não precisa; qualquer menção a CVE/vulnerabilidade precisa (casa `cve-\d`, cues de tópico, ou vocabulário genérico como `vulnerability`, `exploit`, `attack`, `severe`).
- **`plan_sub_queries(query)`** — decompõe a pergunta em sub-queries focadas, uma por cue de tópico detectado (RCE, request handler, SQL injection, auth, cripto, XSS, CSRF), de-duplicadas e preservando a ordem. Sem nenhum cue, cai na própria query crua.
- **`wants_comparison(query)`** — a pergunta pede ranqueamento ("most severe", "compare", "mais severo", ...)? Se sim, o laço acrescenta uma varredura extra de severidade (`"critical high severity CVSS score vulnerability"`) e a síntese ordena por CVSS.

### Degradação graciosa na geração

A geração final (`generate_answer`) tenta o LLM via `utils.llm_client` (import **lazy**, dentro da função — o stack de LLM é opcional e não pode derrubar o caminho determinístico). Em **qualquer** falha (Ollama fora do ar, dependência/credencial ausente, timeout, ou saída vazia), ela cai em `deterministic_conclusion` — a resposta baseada só nas evidências recuperadas e nos scores CVSS do dataset — imprimindo `LLM unavailable — showing retrieved context and deterministic conclusion instead`.

### Quando usar agentic RAG

| Situação | RAG ingênuo | Agentic RAG |
|----------|-------------|-------------|
| Resposta num único trecho | ✅ Ideal | Exagero |
| Pergunta composta (vários fatos) | ❌ Falha | ✅ Ideal |
| Precisa comparar/ranquear | ❌ Falha | ✅ Ideal |
| Latência mínima | ✅ 1 busca | ⚠️ N buscas |
| Custo por consulta | Baixo | Maior (mais buscas) |

## Arquivos

- [`agentic_rag.py`](agentic_rag.py) — o laço agêntico: planner determinístico (`plan_sub_queries`), controlador de iteração (`run_agentic_retrieval`, no máximo `MAX_ITERATIONS=4` buscas, `top_k=3`), acumulador de evidências (`AgentState`, que mantém o melhor score por CVE), síntese determinística (`deterministic_conclusion`) e geração via LLM com fallback (`generate_answer`).
- `__init__.py` — marca o módulo como pacote (import via `python -m`).

Reutiliza os utilitários do projeto (`utils/search.py`, `utils/data_loader.py`, `utils/llm_client.py`) exatamente como os módulos [04](../04_advanced_workflows/README.md) e [06](../06_evals/README.md).

## Como rodar

A partir da **raiz do repositório**, com o `PYTHONPATH` apontando para a raiz:

**PowerShell**
```powershell
$env:PYTHONPATH = "."
python -m 12_agentic_rag.agentic_rag
```

**Bash**
```bash
export PYTHONPATH="."
python -m 12_agentic_rag.agentic_rag
```

O caminho de busca/decisão roda sem Ollama. Para ver a **geração via LLM** em vez do fallback, configure o LLM como os outros módulos (veja [../LLM_SETUP.md](../LLM_SETUP.md)); sem isso o módulo roda igual e mostra a conclusão determinística — é o comportamento esperado de degradação, não um erro.

## O que a demo mostra

Saída real de `python -m 12_agentic_rag.agentic_rag` com o **Ollama desligado** (`exit=0`). As três perguntas do driver exercitam decomposição, recuperação de um único facet e comparação.

### Pergunta composta (decomposição + comparação)

```
==========================================================================
QUERY: Which RCE CVEs affect request handlers, and which one is the most severe?
==========================================================================

Agent reasoning trace (deterministic, no LLM):
  • plan: decomposed into 2 sub-queries -> ['remote code execution buffer overflow command injection', 'request handler HTTP request parsing buffer overflow']
  • decision: comparison detected -> added severity sweep
  • iter 1: search 'remote code execution buffer overflow command injection' -> ['CVE-2024-1234', 'CVE-2024-5678', 'CVE-2024-9012']
  • iter 2: search 'request handler HTTP request parsing buffer overflow' -> ['CVE-2024-1234', 'CVE-2024-9012', 'CVE-2024-5678']
  • iter 3: search 'critical high severity CVSS score vulnerability' -> ['CVE-2024-5678', 'CVE-2024-1234', 'CVE-2024-9012']
  • stop: plan exhausted after 3 searches; 3 unique CVEs in evidence

Accumulated evidence (ranked by retrieval score):
  - CVE-2024-1234  (score 0.0328)
  - CVE-2024-5678  (score 0.0325)
  - CVE-2024-9012  (score 0.0320)

Final answer:
... - __main__ - WARNING - LLM unavailable (OpenAIConnectionError); using fallback.
LLM unavailable — showing retrieved context and deterministic conclusion instead:

Retrieved CVEs (by CVSS severity):
  - CVE-2024-1234  (CVSS 9.8)
  - CVE-2024-5678  (CVSS 8.2)
  - CVE-2024-9012  (CVSS 6.5)
Most severe among the retrieved CVEs: CVE-2024-1234 (CVSS 9.8).
```

O agente **decompôs** a pergunta em 2 sub-queries, **detectou** a comparação e acrescentou a varredura de severidade (3 buscas no total), **acumulou** as evidências e, sem LLM, **concluiu** o item mais severo por CVSS — tudo determinístico.

### Comparação entre áreas distintas

```
==========================================================================
QUERY: Compare the cryptographic and SQL injection issues — which is more severe?
==========================================================================

Agent reasoning trace (deterministic, no LLM):
  • plan: decomposed into 2 sub-queries -> ['SQL injection authentication bypass login database', 'cryptographic weakness weak random number generator key generation']
  • decision: comparison detected -> added severity sweep
  ...
Accumulated evidence (ranked by retrieval score):
  - CVE-2024-5678  (score 0.0328)
  - CVE-2024-9012  (score 0.0328)
  - CVE-2024-1234  (score 0.0325)
...
Most severe among the retrieved CVEs: CVE-2024-1234 (CVSS 9.8).
```

> **Nota sobre os rankings.** Os scores de recuperação são muito próximos (centésimos de milésimo), porque a busca híbrida desempata de forma **determinística** e as keywords sintéticas de cada documento são escolhidas pelo campo `vulnerability_type` do registro (não por substring da descrição). Por isso a **ordem por score** varia entre as três perguntas (ex.: `CVE-2024-5678` lidera na comparação cripto × SQL), enquanto a **ordem por severidade CVSS** da conclusão é sempre a mesma (`CVE-2024-1234` 9.8 > `CVE-2024-5678` 8.2 > `CVE-2024-9012` 6.5). Rode o script para ver os valores exatos da sua execução.

## Exercícios

1. **Sem recuperação:** chame `needs_retrieval("hello, what can you do?")` e confirme que devolve `False` (nenhum cue de tópico, nenhum token CVE). Que palavra mínima faz virar `True`?
2. **Plano de uma pergunta:** passe `"Is there an XSS or CSRF issue?"` por `plan_sub_queries` e confirme que ele gera **duas** sub-queries (uma por cue), na ordem de `_TOPIC_CUES`.
3. **Gatilho de comparação:** adicione `"mais grave"` a uma pergunta e verifique que `wants_comparison` retorna `True` e que o trace ganha a linha `decision: comparison detected -> added severity sweep`.
4. **Melhor score por CVE:** em `AgentState.add_result`, explique por que reencontrar um CVE numa busca posterior mantém o **maior** score em vez de somar ou sobrescrever. O que mudaria na lista "Accumulated evidence" se fosse sobrescrita?
5. **Severidade × score:** por que a conclusão ordena por CVSS (`_severity_by_id`) e não pelo score de recuperação? Monte uma pergunta em que as duas ordens discordem (a saída real já mostra uma).

## Referências

- Reutiliza os utilitários e a base documentados no [README raiz](../README.md) (busca híbrida/RRF, `get_cve_documents`, cliente LLM). Não há dependência externa nova neste módulo.
