# 13 — Deployment: servindo o agente como API HTTP com streaming

Este módulo mostra o passo **"da ideia ao ar"**: pegar o pipeline de busca/RAG
sobre CVEs do projeto e expô-lo como uma **API HTTP** com [FastAPI](https://fastapi.tiangolo.com/),
incluindo **streaming** de resposta via SSE.

## O que é "serving"?

Durante o estudo, rodamos os scripts como `python -m NN_modulo.arquivo`. Isso é
ótimo pra aprender, mas um agente só vira *produto* quando outra aplicação
consegue falar com ele por rede. **Serving** é justamente isso: embrulhar a
lógica num servidor que escuta requisições HTTP e devolve respostas.

Aqui usamos FastAPI (framework ASGI) + Uvicorn (servidor ASGI) — a dupla padrão
do ecossistema Python pra APIs assíncronas.

## O que é streaming via SSE?

Um LLM gera a resposta **token a token**. Em vez de esperar a resposta inteira
pra só então mostrar algo, podemos ir enviando os pedaços conforme chegam — é o
efeito "digitando" que você vê no ChatGPT. 

A técnica usada aqui é **SSE (Server-Sent Events)**: a resposta tem
`Content-Type: text/event-stream` e o servidor empurra uma sequência de eventos
`data: <pedaço>`, terminando com um evento `data: [DONE]`. É mais simples que
WebSocket e perfeito pra fluxo unidirecional servidor→cliente.

## Endpoints

| Método | Rota      | Descrição                                                       |
|--------|-----------|-----------------------------------------------------------------|
| `GET`  | `/health` | Healthcheck. Devolve `{"status": "ok"}`.                        |
| `POST` | `/query`  | Resposta **não-streaming** (JSON). Body: `{"query": "...", "top_k": 3}`. |
| `POST` | `/stream` | Resposta **streaming** (SSE). Body: `{"query": "...", "top_k": 3}`. |
| `GET`  | `/stream` | Mesma resposta SSE, via querystring: `/stream?query=...&top_k=3`. |

A resposta do `/query` traz `query`, `answer`, `used_llm` (se o LLM foi usado ou
se caiu no fallback) e `sources` (os IDs dos CVEs recuperados).

## Funciona sem Ollama (fallback determinístico)

O cliente LLM (`utils.llm_client`) é importado de forma **lazy**, dentro da
função que o usa. Se o Ollama não estiver no ar (ou o `langchain_openai` faltar),
a API **não quebra**: ela cai num fallback determinístico que devolve os CVEs
mais relevantes da **busca híbrida** (BM25 + semântica).

- No `/query`, o `answer` passa a ser o contexto top-k formatado e `used_llm=false`.
- No `/stream`, o texto do CVE top-1 é fatiado em pedaços e enviado pelos mesmos
  eventos SSE — ou seja, você vê o **mecanismo de streaming funcionando mesmo
  sem LLM**.

A busca semântica usa `sentence-transformers` (já instalado), então o fallback
roda 100% offline.

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

## Nota de segurança: `127.0.0.1`, nunca `0.0.0.0`

O `__main__` liga o servidor em `host="127.0.0.1"` de propósito. Isso restringe o
acesso à própria máquina (loopback). Usar `0.0.0.0` exporia a porta pra toda a
rede — adequado só dentro de um container com rede controlada e um proxy na
frente, nunca num exemplo de estudo rodando no seu laptop.

## Arquivos

- `serve.py` — app FastAPI com `/query`, `/stream` (SSE) e `/health`, import lazy
  do LLM e fallback determinístico de busca híbrida.
- `__init__.py` — marca a pasta como pacote.
- `README.md` — este arquivo.
