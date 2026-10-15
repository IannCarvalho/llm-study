"""
13_deployment/serve.py — Servindo um agente LLM como API HTTP com streaming.

Este módulo mostra o passo "da ideia ao ar": empacotar o pipeline de RAG/busca
do projeto como uma API FastAPI com três endpoints:

    POST /query   -> resposta não-streaming (JSON)
    GET/POST /stream -> resposta em streaming via SSE (text/event-stream)
    GET  /health  -> healthcheck simples

Princípios de design (iguais aos demais módulos do projeto):

- Autocontido: só depende de utils.* e da própria pasta. Não escreve em utils/.
- Determinístico sem Ollama: o LLM é importado de forma LAZY (dentro das funções
  que o usam). Se o cliente LLM não puder ser inicializado (Ollama fora do ar,
  langchain_openai ausente, etc.), caímos num fallback que devolve/streama o
  resultado da busca híbrida — ou seja, a API responde mesmo sem LLM, só sem a
  camada de geração.
- Em produção se usa um servidor ASGI (uvicorn). O bloco __main__ sobe o uvicorn
  ligado SEMPRE em 127.0.0.1 (loopback), nunca 0.0.0.0, pra não expor a porta.

Como rodar (ver README.md da pasta):
    pip install fastapi uvicorn
    python -m 13_deployment.serve
"""

from typing import AsyncIterator, List, Optional

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from utils.data_loader import get_cve_documents
from utils.search import create_search_engine
from utils.models import SearchResult
from utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title="llm-study — Deployment Demo",
    description=(
        "Agente LLM de consulta a CVEs exposto como API HTTP com streaming. "
        "Funciona sem Ollama via fallback determinístico de busca híbrida."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Schemas de request/response
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Corpo do POST /query e do POST /stream."""
    query: str
    top_k: int = 3


class QueryResponse(BaseModel):
    """Resposta do POST /query."""
    query: str
    answer: str
    used_llm: bool
    sources: List[str]


# ---------------------------------------------------------------------------
# Camada de recuperação (determinística, sem LLM)
# ---------------------------------------------------------------------------

def _load_documents() -> List[dict]:
    """Carrega os CVEs como lista de documentos no formato que o search espera.

    get_cve_documents() devolve {id: texto}; o motor de busca espera
    [{"id":..., "content":..., "metadata":...}].
    """
    docs = get_cve_documents()
    return [{"id": cid, "content": text, "metadata": {}} for cid, text in docs.items()]


def _retrieve(query: str, top_k: int = 3) -> List[SearchResult]:
    """Roda a busca híbrida (BM25 + semântica). Determinístico, sem LLM."""
    documents = _load_documents()
    engine = create_search_engine(method="hybrid")
    return engine.search(query, documents, top_k=top_k)


def _format_context(results: List[SearchResult]) -> str:
    """Monta um bloco de contexto textual a partir dos resultados de busca."""
    if not results:
        return "Nenhum CVE relevante encontrado."
    blocks = []
    for i, r in enumerate(results, start=1):
        blocks.append(f"[{i}] (score={r.score:.4f})\n{r.content.strip()}")
    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Geração — LLM com import LAZY e fallback determinístico
# ---------------------------------------------------------------------------

def _try_generate_with_llm(query: str, context: str) -> Optional[str]:
    """Tenta gerar uma resposta com o LLM. Devolve None se não for possível.

    O import de utils.llm_client (que no topo importa langchain_openai) é feito
    AQUI DENTRO, lazy, pra que o caminho determinístico nunca dependa do LLM.
    Qualquer falha (import, Ollama fora do ar, erro de rede) vira None e o
    chamador cai no fallback.
    """
    try:
        from utils.llm_client import get_llm_client  # lazy import

        client = get_llm_client()
        system_prompt = (
            "Você é um assistente de segurança. Responda à pergunta do usuário "
            "usando SOMENTE o contexto de CVEs fornecido. Seja conciso."
        )
        prompt = f"Contexto:\n{context}\n\nPergunta: {query}\n\nResposta:"
        return client.generate(prompt, system_prompt=system_prompt)
    except Exception as e:  # pragma: no cover - depende de ambiente externo
        logger.warning(f"LLM indisponível, usando fallback determinístico: {e}")
        return None


def answer_query(query: str, top_k: int = 3) -> QueryResponse:
    """Pipeline não-streaming: recupera -> (tenta LLM) -> responde.

    No fallback sem LLM, a resposta é o contexto top-k da busca híbrida
    formatado — ou seja, a API ainda entrega algo útil e 100% determinístico.
    """
    results = _retrieve(query, top_k=top_k)
    context = _format_context(results)
    sources = [r.id for r in results]

    llm_answer = _try_generate_with_llm(query, context)
    if llm_answer is not None:
        return QueryResponse(query=query, answer=llm_answer, used_llm=True, sources=sources)

    fallback = (
        "LLM indisponível — retornando os CVEs mais relevantes (busca híbrida):\n\n"
        + context
    )
    return QueryResponse(query=query, answer=fallback, used_llm=False, sources=sources)


# ---------------------------------------------------------------------------
# Streaming (SSE)
# ---------------------------------------------------------------------------

def _sse_pack(data: str) -> str:
    """Empacota um pedaço de texto como um evento SSE (text/event-stream).

    Cada linha do payload recebe o prefixo 'data: '. Um evento termina com uma
    linha em branco.
    """
    lines = data.split("\n")
    return "".join(f"data: {line}\n" for line in lines) + "\n"


def _chunk_text(text: str, size: int = 40) -> List[str]:
    """Quebra um texto em pedaços de tamanho fixo pra simular tokens no stream."""
    return [text[i : i + size] for i in range(0, len(text), size)] or [""]


async def stream_query(query: str, top_k: int = 3) -> AsyncIterator[str]:
    """Gera eventos SSE com a resposta em pedaços.

    Tenta o LLM (lazy); se indisponível, streama o texto do CVE top-1 em pedaços
    pra demonstrar o mecanismo de streaming mesmo sem Ollama. O evento final
    carrega '[DONE]', convenção comum de SSE para fim de stream.
    """
    results = _retrieve(query, top_k=top_k)
    context = _format_context(results)

    llm_answer = _try_generate_with_llm(query, context)
    if llm_answer is not None:
        text = llm_answer
    else:
        top = results[0].content.strip() if results else "Nenhum CVE relevante encontrado."
        text = "[fallback sem LLM] " + top

    for piece in _chunk_text(text):
        yield _sse_pack(piece)
    yield _sse_pack("[DONE]")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> JSONResponse:
    """Healthcheck — usado por orquestradores (k8s, Render, etc.)."""
    return JSONResponse({"status": "ok"})


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    """Resposta não-streaming. Body: {"query": "...", "top_k": 3}."""
    return answer_query(req.query, top_k=req.top_k)


@app.post("/stream")
async def stream_endpoint_post(req: QueryRequest) -> StreamingResponse:
    """Resposta em streaming via SSE. Body: {"query": "...", "top_k": 3}."""
    return StreamingResponse(
        stream_query(req.query, top_k=req.top_k),
        media_type="text/event-stream",
    )


@app.get("/stream")
async def stream_endpoint_get(query: str, top_k: int = 3) -> StreamingResponse:
    """Mesma resposta SSE, via GET com querystring: /stream?query=...&top_k=3.

    Conveniente pra testar no browser ou com `curl -N`.
    """
    return StreamingResponse(
        stream_query(query, top_k=top_k),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Execução local
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Em produção se usa `uvicorn pacote.modulo:app` diretamente. Aqui o nome do
    # pacote começa com dígito ("13_deployment"), que não é um módulo importável
    # pelo CLI do uvicorn, então subimos o servidor programaticamente passando o
    # objeto `app` já construído.
    #
    # host=127.0.0.1 (loopback) de propósito: NUNCA 0.0.0.0 — não queremos expor
    # a porta pra fora da máquina neste exemplo de estudo.
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
