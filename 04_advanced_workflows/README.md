# 04 — Workflows avançados: RAG com bancos vetoriais e reranking

> Pré-requisitos: **reranking** roda sem LLM (degrada sem `sentence-transformers`); **chroma_rag** precisa de Ollama para a geração final (a indexação roda offline); **pinecone_rag** precisa de `PINECONE_API_KEY` e de um índice na nuvem, além de Ollama para a geração. Configuração de provedor em [../LLM_SETUP.md](../LLM_SETUP.md).

Três faces da camada de recuperação de produção sobre a mesma base de CVEs: um banco vetorial **local** (Chroma), um banco vetorial **na nuvem** (Pinecone) e a etapa de **reranking** com cross-encoder que normalmente vem depois da primeira busca. Os três carregam os dados de `utils/data/cves.json` por `utils.data_loader`, então dá para comparar as abordagens sobre exatamente os mesmos documentos.

## Por que importa

A busca híbrida (BM25 + semântica, fundidas por RRF) do módulo [01](../01_vector_databases/README.md) é a primeira etapa — rápida e barata. Em produção você raramente para aí: escolhe **onde** armazenar os vetores (um banco embutido para prototipar, um serviço gerenciado para escalar) e **refina** o ranking inicial com um modelo mais preciso. Este módulo mostra as duas decisões: o banco vetorial e o reranking.

## Conceitos

### Chroma × Pinecone

| Aspecto | Chroma | Pinecone |
|---------|--------|----------|
| **Setup** | Nenhum (embutido, local) | Conta + índice na nuvem + chave |
| **Custo** | Grátis | Pago |
| **Escala** | Protótipo / dezenas a centenas de milhares | Produção / bilhões de vetores |
| **Onde roda** | Na sua máquina, em `data/chroma/` | Serviço gerenciado |
| **Melhor para** | MVP, iteração rápida, offline | Produção em escala |

Ambos recebem os **mesmos** documentos vindos de `utils.data_loader`; o que muda é onde os vetores ficam (disco local × serviço na nuvem). Essa simetria é o ponto: trocar de banco não exige repensar o pipeline de dados.

### Reranking em duas etapas

A primeira etapa (busca híbrida) devolve `top_k` candidatos comparando embeddings produzidos **independentemente** para a query e para cada documento — rápido, mas às vezes enganável por sobreposição de palavras. O **cross-encoder** é a segunda etapa: ele lê o par `(query, documento)` **junto** e pontua relevância de verdade. É mais lento por par, e é exatamente por isso que só roda sobre o punhado de candidatos que a primeira etapa já reduziu.

Para tornar o efeito visível no corpus minúsculo de CVEs, `reranking.py` injeta no conjunto de candidatos dois "distratores" rotulados (ids com prefixo `DISTRACTOR-`): texto recheado das palavras da query, mas sem vulnerabilidade real. A primeira etapa lexical se deixa enganar e os ranqueia no topo; o cross-encoder, lendo cada par junto, percebe que são vazios e os rebaixa abaixo do CVE real — que é justamente a falha de produção que o reranking existe para corrigir.

## Arquivos

- [`chroma_rag.py`](chroma_rag.py) — RAG com banco vetorial local. Usa `ChromaRAGPipeline` (busca híbrida, `top_k=3`), indexa os CVEs em `data/chroma/` apenas se a coleção estiver vazia e gera a resposta via LLM.
- [`pinecone_rag.py`](pinecone_rag.py) — RAG com banco vetorial na nuvem. Gera embeddings reais (`all-MiniLM-L6-v2`), faz upsert no índice `llm-study`, consulta por similaridade e monta o prompt RAG. Exige `PINECONE_API_KEY`.
- [`reranking.py`](reranking.py) — pipeline de duas etapas: busca híbrida → rerank dos mesmos candidatos com cross-encoder → impressão lado a lado do antes/depois. Degrada para um reranker determinístico por sobreposição de termos quando `sentence-transformers` não está disponível.
- `__init__.py` — marca o diretório como pacote (import via `python -m`).

Reutiliza os utilitários do projeto: `utils/data_loader.py`, `utils/search.py`, `utils/semantic_embeddings.py`, `utils/rag_pipeline.py`, `utils/llm_client.py`, `utils/prompts/`.

## Como rodar

A partir da **raiz do repositório**, com o `PYTHONPATH` apontando para a raiz:

**PowerShell**
```powershell
$env:PYTHONPATH = "."
python -m 04_advanced_workflows.reranking      # não precisa de LLM
python -m 04_advanced_workflows.chroma_rag     # geração final precisa de Ollama
python -m 04_advanced_workflows.pinecone_rag   # precisa de PINECONE_API_KEY (+ Ollama na geração)
```

**Bash**
```bash
export PYTHONPATH="."
python -m 04_advanced_workflows.reranking
python -m 04_advanced_workflows.chroma_rag
python -m 04_advanced_workflows.pinecone_rag
```

### Chroma
Sem setup de banco. A indexação em `data/chroma/` roda offline; só a **geração da resposta** usa o LLM. Sem Ollama no ar, a indexação acontece e o script para na geração com erro de conexão (veja abaixo). Configure o Ollama como nos outros módulos: [../LLM_SETUP.md](../LLM_SETUP.md).

### Pinecone
1. Crie uma conta e pegue a chave em [pinecone.io](https://www.pinecone.io).
2. Instale o SDK: `pip install pinecone`. **Atenção:** o pacote foi renomeado de `pinecone-client` para `pinecone`; instalar o antigo não traz as atualizações desde a v6 (veja [Referências](#referências)).
3. Coloque `PINECONE_API_KEY` no `.env`.
4. Crie um índice chamado `llm-study` no console do Pinecone.

Sem a chave, o script não quebra: imprime a mensagem de erro e encerra (veja abaixo).

### Reranking
Roda sem rede e sem LLM. Para usar o cross-encoder **real** (baixa um modelo pequeno no primeiro uso), instale:
```bash
pip install sentence-transformers
```
Sem ele, o script cai no reranker determinístico de sobreposição de termos, claramente rotulado na saída.

## O que a demo mostra

### `reranking.py` — saída real (`exit=0`, com o cross-encoder disponível)

```
==============================================================================
Cross-Encoder Reranking (two-stage retrieval, no LLM required)
Corpus: 5 documents (3 real CVEs + 2 labelled distractors) | first-stage top_k: 10
==============================================================================

Query: "attacker runs arbitrary commands remotely by overflowing the request buffer"
Genuinely relevant answer: CVE-2024-1234 (the RCE vulnerability).

==============================================================================
BEFORE (hybrid first stage)        vs.        AFTER (reranked: cross-encoder)
==============================================================================
 1. DISTRACTOR-keyword-stuffed   ->   CVE-2024-1234    score=7.6548  <= promoted
 2. DISTRACTOR-off-topic   ->   DISTRACTOR-keyword-stuffed score=5.4245  <= promoted
 3. CVE-2024-1234      ->   DISTRACTOR-off-topic score=3.6015  <= promoted
 4. CVE-2024-9012      ->   CVE-2024-5678    score=-8.5813  <= promoted
 5. CVE-2024-5678      ->   CVE-2024-9012    score=-10.5240  <= promoted
------------------------------------------------------------------------------
Reranker changed the #1 result: DISTRACTOR-keyword-stuffed -> CVE-2024-1234
==============================================================================
```

A primeira etapa pôs os dois distratores no topo (venceu por sobreposição de palavras); o cross-encoder puxou o CVE real (`CVE-2024-1234`, a RCE) para o #1. Quando `sentence-transformers` não está instalado, a linha do cabeçalho vira `AFTER (reranked: fallback (term overlap))` e o script imprime o aviso `[fallback] sentence-transformers / cross-encoder unavailable — reranking with deterministic query<->document term overlap.`

### `pinecone_rag.py` — saída real sem a chave (`exit=0`)

```
Error: PINECONE_API_KEY not configured in .env
Get it from: https://www.pinecone.io
```

O script detecta a ausência de `PINECONE_API_KEY` e encerra com essa mensagem instrutiva, sem tocar na nuvem.

### `chroma_rag.py` — saída real sem Ollama (`exit=1`)

A indexação local roda normalmente; a geração final é que precisa do LLM:

```
... - utils.rag_pipeline - INFO - Created new Chroma collection: vulnerabilities
... - utils.rag_pipeline - INFO - Added 3 documents to Chroma collection
... - __main__ - INFO - Indexed 3 CVE documents

======================================================================
Query: 'What is CVE-2024-1234?'
======================================================================
```

Com o Ollama desligado, a chamada ao LLM termina em:

```
langchain_openai.chat_models.base.OpenAIConnectionError: Connection error.
```

Suba o Ollama (`ollama serve`) para ver a resposta gerada. *Exemplo ilustrativo de uma execução com o LLM (a resposta varia com o modelo):* depois dos documentos recuperados, o pipeline imprime `RAG Context`, a `LLM Response` com o resumo do CVE e o `Execution time`.

## Exercícios

1. **Reranking sem o modelo:** rode `reranking.py` sem `sentence-transformers` instalado e confirme no cabeçalho que o reranker virou `fallback (term overlap)`. O `#1` ainda é corrigido para `CVE-2024-1234`? Explique por que a sobreposição de termos também rebaixa os distratores.
2. **Mudar a query do reranking:** troque `DEMO_QUERY` em `reranking.py` por uma pergunta sobre SQL injection e observe para qual CVE o cross-encoder promove o `#1`.
3. **Chroma offline:** rode `chroma_rag.py` sem Ollama e confirme que a indexação em `data/chroma/` acontece (os logs `Added ... documents`) mesmo com a geração falhando. Apague `data/chroma/` e rode de novo — o que muda na saída?
4. **Simetria dos dados:** compare como `chroma_rag.py` e `pinecone_rag.py` carregam os documentos (`load_cves` / `get_cve_documents`). Que linhas precisariam mudar para migrar do Chroma para o Pinecone?
5. **Tamanho do corpus:** a base tem só 3 CVEs. Por que isso limita o que o reranking consegue demonstrar sem os distratores? (Dica: `top_k=10` sobre 3 documentos.)

## Referências

- Pinecone — Python SDK (install, `Pinecone`, `Index`, `query`, `upsert`): [docs.pinecone.io/reference/python-sdk](https://docs.pinecone.io/reference/python-sdk)
- PyPI — aviso de depreciação `pinecone-client` renomeado para `pinecone`: [pypi.org/project/pinecone-client](https://pypi.org/project/pinecone-client/)
