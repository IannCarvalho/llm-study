# 13 — Deployment: o agente como API HTTP com streaming

> Pré-requisitos: roda sem LLM (fallback determinístico de busca híbrida). Precisa
> dos pacotes extras `fastapi` e `uvicorn` (não vêm no `requirements.txt` do
> projeto). Com Ollama no ar, a geração passa a usar o modelo automaticamente.

Este módulo mostra o passo **"da ideia ao ar"**: pegar o pipeline de busca/RAG
sobre CVEs do projeto e expô-lo como uma **API HTTP** com
[FastAPI](https://fastapi.tiangolo.com/), incluindo **streaming** de resposta
via SSE.

## Por que importa

Durante o estudo, rodamos os scripts como `python -m NN_modulo.arquivo`. Isso é
ótimo pra aprender, mas um agente só vira *produto* quando outra aplicação
consegue falar com ele por rede. **Serving** é justamente isso: embrulhar a
lógica num servidor que escuta requisições HTTP e devolve respostas.

Aqui usamos FastAPI (framework ASGI) + Uvicorn (servidor ASGI) — a dupla padrão
do ecossistema Python pra APIs assíncronas.

## Conceitos

### Streaming via SSE

Um LLM gera a resposta **token a token**. Em vez de esperar a resposta inteira
pra só então mostrar algo, podemos ir enviando os pedaços conforme chegam — é o
efeito "digitando" que você vê no ChatGPT.

A técnica usada aqui é **SSE (Server-Sent Events)**: a resposta tem
`Content-Type: text/event-stream` e o servidor empurra uma sequência de eventos
`data: <pedaço>`, terminando com um evento `data: [DONE]`. É mais simples que
WebSocket e perfeito pra fluxo unidirecional servidor→cliente.

### Endpoints

| Método | Rota      | Descrição                                                       |
|--------|-----------|-----------------------------------------------------------------|
| `GET`  | `/health` | Healthcheck. Devolve `{"status": "ok"}`.                        |
| `POST` | `/query`  | Resposta **não-streaming** (JSON). Body: `{"query": "...", "top_k": 3}`. |
| `POST` | `/stream` | Resposta **streaming** (SSE). Body: `{"query": "...", "top_k": 3}`. |
| `GET`  | `/stream` | Mesma resposta SSE, via querystring: `/stream?query=...&top_k=3`. |

A resposta do `/query` traz `query`, `answer`, `used_llm` (se o LLM foi usado ou
se caiu no fallback) e `sources` (os IDs dos CVEs recuperados).

### Funciona sem Ollama (fallback determinístico)

O cliente LLM (`utils.llm_client`) é importado de forma **lazy**, dentro da
função que o usa (`_try_generate_with_llm`). Se o Ollama não estiver no ar (ou o
`langchain_openai` faltar), a API **não quebra**: ela cai num fallback
determinístico que devolve os CVEs mais relevantes da **busca híbrida**
(BM25 + semântica).

- No `/query`, o `answer` passa a ser o contexto top-k formatado (prefixado por
  "LLM indisponível — ...") e `used_llm=false`.
- No `/stream`, o texto do CVE top-1 é fatiado em pedaços (prefixado por
  `[fallback sem LLM]`) e enviado pelos mesmos eventos SSE — ou seja, você vê o
  **mecanismo de streaming funcionando mesmo sem LLM**.

A busca semântica usa `sentence-transformers` (já instalado), então o fallback
roda 100% offline. Setup de provedor de LLM: veja [../LLM_SETUP.md](../LLM_SETUP.md).

## Arquivos

- `serve.py` — app FastAPI com `/query`, `/stream` (SSE, via `GET` e `POST`) e
  `/health`, import lazy do LLM e fallback determinístico de busca híbrida. O
  bloco `__main__` sobe o uvicorn ligado em `127.0.0.1`.
- `__init__.py` — marca a pasta como pacote.
- `README.md` — este arquivo.

## Como rodar

Instale as dependências do módulo (não vêm no `requirements.txt` do projeto):

```bash
pip install fastapi uvicorn
```

> **Versões compatíveis:** instale `fastapi` e `uvicorn` juntos num ambiente
> limpo. Um `fastapi` antigo (ex. `0.104`) ao lado de um `starlette` novo (`1.x`)
> é incompatível e nem um `FastAPI()` puro constrói
> (`Router.__init__() got an unexpected keyword argument 'on_startup'`). O
> módulo foi validado end-to-end com `fastapi 0.143` + `starlette 1.8`
> (`/health` → 200, `/query` e `/stream` servindo o fallback de busca híbrida sem
> Ollama).

Suba o servidor. Note que `uvicorn 13_deployment.serve:app` **não funciona**: o
nome do pacote começa com dígito (`13_...`), que o CLI do uvicorn não aceita como
módulo importável. Por isso o `serve.py` sobe o uvicorn pelo próprio `__main__`:

```bash
python -m 13_deployment.serve
```

O servidor escuta em `http://127.0.0.1:8000` (apenas loopback — veja a nota de
segurança abaixo).

### Testando

```bash
# health
curl http://127.0.0.1:8000/health

# query (não-streaming)
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "remote code execution", "top_k": 3}'

# stream (SSE) — -N desliga o buffer do curl pra ver os pedaços chegando
curl -N "http://127.0.0.1:8000/stream?query=sql%20injection"
```

A documentação interativa (Swagger UI) fica em `http://127.0.0.1:8000/docs`.

### Nota de segurança: `127.0.0.1`, nunca `0.0.0.0`

O `__main__` liga o servidor em `host="127.0.0.1"` de propósito. Isso restringe o
acesso à própria máquina (loopback). Usar `0.0.0.0` exporia a porta pra toda a
rede — adequado só dentro de um container com rede controlada e um proxy na
frente, nunca num exemplo de estudo rodando no seu laptop.

## O que a demo mostra

Este módulo é um **servidor**, não um script de demo: a saída não é um texto fixo,
e sim as respostas HTTP dos endpoints. Com o servidor no ar e **sem Ollama**:

- `GET /health` responde `{"status": "ok"}`.
- `POST /query` devolve um JSON com `used_llm=false` e, em `answer`, os CVEs mais
  relevantes da busca híbrida (prefixados por "LLM indisponível — ..."), além dos
  `sources` (IDs dos CVEs).
- `GET /stream` emite eventos `data: ...` com o texto do CVE top-1 fatiado
  (prefixo `[fallback sem LLM]`), encerrando com `data: [DONE]`.

Com Ollama no ar, `used_llm` passa a `true` e `answer` traz a resposta gerada pelo
modelo a partir do mesmo contexto recuperado.

## Exercícios

1. Mude `top_k` de `3` para `1` no corpo do `POST /query` e observe `sources`
   encolher para um único CVE — o pipeline `_retrieve` respeita o `top_k`.
2. Ajuste o `size` em `_chunk_text` (padrão `40`) para `10` e conte quantos
   eventos `data:` a mais o `/stream` passa a emitir para a mesma resposta — é o
   tamanho do "token" simulado no stream.
3. Acrescente um endpoint `GET /` que redireciona para `/docs` e confirme pelo
   Swagger UI que os três endpoints existentes continuam documentados.
4. Suba o servidor sem Ollama e compare o `answer` de `POST /query` para
   `"remote code execution"` com o de `"sql injection"`: veja o fallback escolher
   CVEs diferentes conforme a busca híbrida.
5. Chame `answer_query("...")` diretamente de um `python -c` (sem subir o
   servidor) e confirme que o pipeline não-streaming funciona fora do FastAPI — a
   lógica está desacoplada do framework.

## Referências

- [Documentação do FastAPI](https://fastapi.tiangolo.com/)
- [Modelos do Ollama](https://ollama.com/library)
