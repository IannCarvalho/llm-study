# 01 — Vector Databases (busca para RAG)

> Pré-requisitos: roda **sem LLM**, sem rede e sem chave de API. Python 3.11.
> Os três scripts são determinísticos. As partes de **embeddings** (semantic/hybrid)
> baixam um modelo do Sentence Transformers na primeira execução — isso exige o
> pacote `sentence-transformers` e, no primeiro uso, acesso à internet para o
> download do modelo; depois ele fica em cache e roda offline. Nenhum passo precisa
> do Ollama.

Este módulo mostra como recuperar os documentos certos para alimentar um sistema de
RAG (*retrieval-augmented generation*): busca por palavra-chave (BM25), busca por
significado (embeddings) e a combinação das duas (busca híbrida). Todos os exemplos
usam a mesma base de três **registros sintéticos** de vulnerabilidades fictícias
(`utils/data/cves.json`), para você focar nas estratégias de busca em vez de no setup
dos dados.

## Por que importa

A geração de um LLM é tão boa quanto o contexto que você entrega a ele. Recuperar os
trechos errados (ou trechos demais) degrada a resposta e gasta tokens. As três técnicas
deste módulo cobrem os dois lados do problema de recuperação:

- **BM25 (palavra-chave)** acerta identificadores exatos — um ID de CVE, um nome de
  função, um número de versão — que um modelo semântico costuma diluir.
- **Embeddings (semântico)** acertam paráfrases e sinônimos — "as chaves são
  previsíveis porque a aleatoriedade é fraca" encontra a CVE de criptografia mesmo
  sem repetir nenhuma palavra da descrição.
- **Busca híbrida** funde as duas, premiando documentos que aparecem bem ranqueados
  em qualquer um dos métodos.

## Conceitos

### BM25 (Best Matching 25)
Função de ranqueamento padrão da indústria para busca por palavra-chave (esparsa),
usada por motores como Elasticsearch e Lucene. É uma evolução do TF-IDF que considera
frequência do termo com **saturação** (repetir uma palavra não aumenta o score
linearmente), **IDF** (termos raros valem mais) e **normalização pelo tamanho do
documento** (evita viés a favor de documentos longos). Os parâmetros `k1` e `b`
controlam, respectivamente, a saturação de frequência e o peso do tamanho. Rápido e
interpretável, é excelente para correspondências exatas e quase-exatas. Fórmula e
derivação em [Referências](#referências).

### Embeddings e similaridade de cosseno
Um modelo neural transforma cada texto em um vetor denso que captura significado, não
só as palavras. A proximidade entre dois textos é medida pela **similaridade de
cosseno** (o cosseno do ângulo entre os vetores): próximo de `1` = muito relacionados,
próximo de `0` = pouco relacionados. Isso faz a busca semântica reconhecer sinônimos e
reformulações que o BM25 não alcança. O modelo usado aqui é o `all-MiniLM-L6-v2`
(pequeno e rápido, **384 dimensões** — ver [Referências](#referências)).

### Reciprocal Rank Fusion (RRF)
A busca híbrida combina os rankings de BM25 e de embeddings com **RRF**, que soma, por
documento, `1/(k + posição)` de cada ranking (com `k = 60`):

```
Ranking BM25          Ranking semântico
     ↓                       ↓
[doc1, doc2, doc3]   [doc2, doc1, doc4]
     └───────────┬───────────┘
      Fusão RRF: 1/(60 + posição)
            ↓
    [doc1, doc2, doc4]  ← ranking final
```

Vantagens do RRF frente a uma média ponderada:
- **Sem ajuste de parâmetro** (não há pesos tipo 70/30 para calibrar);
- **Robusto** a escalas de score diferentes, sem precisar normalizar;
- **Premia** documentos que aparecem bem em ambos os rankings;
- fórmula: `score = 1/(60 + posição_bm25) + 1/(60 + posição_semantic)`.

### Chunking (divisão de documentos)
Documentos grandes não cabem no limite de contexto do modelo de embedding, então são
divididos em pedaços (*chunks*) menores e sobrepostos. As três estratégias têm
compromissos diferentes:
- **fixed**: tamanho fixo — rápido e simples, mas pode cortar no meio de uma frase;
- **sentence**: respeita o limite das frases — mais natural, tamanhos variáveis;
- **recursive** (recomendado): divisão hierárquica (parágrafos → frases → palavras),
  preservando a estrutura do documento.

### Custo e escala
- **BM25** é barato: o custo cresce com o vocabulário e com o número de termos da query.
- **Busca semântica**: o gargalo é a inferência do modelo de embedding; a comparação por
  cosseno contra todos os documentos é linear no tamanho da base.
- **Híbrida**: herda o custo da parte semântica.
- **Chunking**: `recursive` é mais lento que `fixed`, em troca de preservar a estrutura.
- **Em escala** (milhões de documentos), varrer todos os vetores deixa de ser viável: entra
  um banco vetorial com índice aproximado (Pinecone, Weaviate, Qdrant) ou uma biblioteca
  como FAISS, com modelos do Sentence Transformers como `all-MiniLM-L6-v2` (o padrão deste
  repo) ou `all-mpnet-base-v2`. O módulo [04](../04_advanced_workflows/README.md) mostra
  Chroma e Pinecone na prática.

## Arquivos

| Arquivo | O que demonstra |
|---------|-----------------|
| [embeddings_basics.py](embeddings_basics.py) | BM25 (Partes 1–2) e, em seguida, busca semântica por cosseno nos mesmos documentos (Parte 3), lado a lado. |
| [chunking_strategies.py](chunking_strategies.py) | As três estratégias de chunking sobre um documento de exemplo, comparando nº de chunks e tamanho médio. |
| [hybrid_search.py](hybrid_search.py) | BM25 + semântico fundidos com RRF, usando os motores de `utils.search`. |

A base de dados e os motores de busca são compartilhados por todos os módulos:

- `utils/data/cves.json` — três registros sintéticos de produtos fictícios
  (WebServer v2.1, AuthService v1.5, DataEncryption v3.2), carregados por
  `utils.data_loader` (`load_cves`, `get_cve_by_id`, `search_cves`, `get_cve_documents`);
- `utils.search.create_search_engine("bm25" | "semantic" | "hybrid")` — fábrica dos
  motores `BM25Search`, `SemanticSearch` e `HybridSearch` (`hybrid_search.py` usa as
  classes diretamente);
- `utils.chunking_utils` — a lógica de chunking usada por `chunking_strategies.py`;
- `utils.semantic_embeddings` — `embed_text` / `embed_texts` (Sentence Transformers),
  usados pela Parte 3 de `embeddings_basics.py` e pelo motor semântico.

> Observação: `utils/rag_pipeline.py` é uma **biblioteca** (a classe `ChromaRAGPipeline`,
> usada pelo RAG com Chroma do [módulo 04](../04_advanced_workflows/README.md)), não um
> script deste módulo — não há nada dele para rodar aqui.

## Como rodar

A partir da **raiz do repositório**, com o `PYTHONPATH` apontando para a raiz. Para o
setup do provedor de LLM (opcional, não necessário neste módulo), veja
[../LLM_SETUP.md](../LLM_SETUP.md).

**Windows (PowerShell):**
```powershell
$env:PYTHONPATH = "."
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search
```

**Linux/Mac (bash):**
```bash
export PYTHONPATH="."
python -m 01_vector_databases.embeddings_basics
python -m 01_vector_databases.chunking_strategies
python -m 01_vector_databases.hybrid_search
```

## O que a demo mostra

### `embeddings_basics.py` — BM25 e depois cosseno
As Partes 1–2 indexam os três registros e ranqueiam por BM25; a Parte 3 reclassifica os
mesmos documentos por similaridade de cosseno. Saída real (resumida):

```
Part 2: Searching with BM25
Query: "buffer overflow instruction pointer"
  1. CVE-2024-1234

Part 3: Semantic search with embeddings (all-MiniLM-L6-v2)
Query: "buffer overflow instruction pointer"
  BM25 top-1:      CVE-2024-1234
  Embeddings #1:   CVE-2024-1234 (cosine 0.268)
  Embeddings #2:   CVE-2024-9012 (cosine 0.142)
  Embeddings #3:   CVE-2024-5678 (cosine 0.089)

Query: "attackers can guess the secret keys because the randomness is poor"
  BM25 top-1:      CVE-2024-9012
  Embeddings #1:   CVE-2024-9012 (cosine 0.399)
  ...
```

Repare na segunda consulta: a paráfrase não repete nenhuma palavra da descrição, e
ainda assim tanto o BM25 quanto o embedding apontam a CVE de criptografia
(`CVE-2024-9012`) — o cosseno de `0.399` é bem acima dos outros dois.

Se o modelo de embedding não puder ser carregado (offline e sem cache), a Parte 3
degrada com uma mensagem clara e as Partes 1–2 continuam valendo:
```
Embedding model unavailable (<erro>); Parts 1-2 above still ran.
```

### `chunking_strategies.py` — comparação das estratégias
Saída real:
```
Document: 743 characters

Strategy: FIXED (Fast, may break mid-sentence)
  Chunks: 5 | Avg size: 148 chars
Strategy: SENTENCE (Respects sentences, more natural)
  Chunks: 3 | Avg size: 247 chars
Strategy: RECURSIVE (RECOMMENDED, preserves structure)
  Chunks: 2 | Avg size: 371 chars
```
O mesmo documento de 743 caracteres vira 5, 3 ou 2 chunks conforme a estratégia —
`fixed` fragmenta mais (e pode cortar frases), `recursive` preserva mais estrutura.

### `hybrid_search.py` — BM25 + semântico via RRF
Saída real:
```
Query: "buffer overflow instruction pointer"

  BM25 (Keyword) Results:
    1. CVE-2024-1234 (score: 0.7244)
    2. CVE-2024-9012 (score: 0.0000)

  Semantic (Embeddings) Results:
    1. CVE-2024-1234 (score: 0.2677)
    2. CVE-2024-9012 (score: 0.1421)

  RRF Combined Results:
    1. CVE-2024-1234 (RRF score: 0.0328)
    2. CVE-2024-9012 (RRF score: 0.0323)
```
Os três métodos concordam no top-1 (`CVE-2024-1234`), mas os scores do RRF ficam
próximos entre os dois primeiros porque ambos aparecem bem ranqueados nos dois métodos.

## Exercícios

### Fácil
1. **Mexa nas consultas do BM25**: em `embeddings_basics.py`, troque `query` e a
   paráfrase (`paraphrase`) e observe o top-1 do BM25 e o ranking de cosseno. Compare
   uma busca com termo específico ("buffer overflow") com uma paráfrase sem palavras em
   comum. Em qual delas o embedding "ganha" do BM25?
2. **Compare as estratégias de chunking**: rode `chunking_strategies.py` e olhe o nº de
   chunks e o tamanho médio das três estratégias. Qual quebra no meio de uma frase? Troque
   `SAMPLE_DOCUMENTS["security"]` por um texto seu em `utils/agentic_utils.py`... ou, sem
   editar o módulo compartilhado, chame `utils.chunking_utils.test_chunking_strategies`
   com o seu próprio texto num script separado.
3. **Leia a base**: use `from utils.data_loader import get_cve_documents` e imprima
   `get_cve_documents()`. Confirme que são três registros sintéticos e identifique qual
   descrição contém "buffer overflow".

### Médio
4. **Semântico vs. palavra-chave**: em `embeddings_basics.py`, adicione uma consulta com
   correspondência exata (ex.: `"CVE-2024-9012"`) e outra puramente conceitual (ex.:
   `"weak random number generator"`). Como o ranking de BM25 difere do de cosseno em cada
   caso?
5. **Modelo de embedding**: `utils.semantic_embeddings.embed_texts` aceita o argumento
   `model`. Rode um script seu chamando `embed_texts(textos, model="all-mpnet-base-v2")`
   e compare com `all-MiniLM-L6-v2`. Qual é o compromisso entre qualidade e velocidade?
6. **Entenda o RRF**: em `hybrid_search.py`, aumente `top_k` para 3 nos três motores e
   observe como o score RRF (`1/(60+posição)`) ordena documentos que aparecem em apenas
   um dos rankings.

### Difícil
7. **Banco vetorial de produção**: troque o motor semântico/híbrido por um banco vetorial
   real (ChromaDB, Pinecone, Weaviate ou Qdrant), mantendo a mesma interface de busca.
   O que muda nos imports e na inicialização? Confirme números e nomes de API na doc
   oficial do produto antes de documentar.
8. **Cache de embeddings**: embeddings são caros de recalcular. Projete uma camada que
   persista os vetores de `embed_texts` em disco e os reutilize entre execuções para os
   documentos já vistos.
9. **Avaliação do retrieval**: para um conjunto de consultas com documentos "corretos"
   conhecidos, meça **precisão** (os recuperados são relevantes?) e **revocação**
   (deixou passar algum relevante?) de BM25, semântico e híbrido sobre os três registros.
   Qual método vence em consultas exatas e qual vence em paráfrases?

## Referências

- Okapi BM25 — função de ranqueamento, fórmula e parâmetros `k1`/`b`:
  [en.wikipedia.org/wiki/Okapi_BM25](https://en.wikipedia.org/wiki/Okapi_BM25)
- Modelo de embedding `all-MiniLM-L6-v2` (384 dimensões, uso e limites):
  [huggingface.co/sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- Guia de setup do provedor de LLM (Ollama, chaves): [../LLM_SETUP.md](../LLM_SETUP.md)
