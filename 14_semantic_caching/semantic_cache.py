"""
Cache Semantico de Respostas (Semantic Caching)

Em vez de cache por chave exata (exact-match), guardamos o EMBEDDING de cada
query atendida. Numa nova consulta, embedamos a query e procuramos o vizinho
mais proximo por similaridade de cosseno: se a similaridade for >= threshold,
servimos a resposta cacheada (HIT) e evitamos uma chamada cara ao LLM; senao,
e um MISS e a resposta precisa ser gerada.

Por que isso importa: "RCE no handler" e "remote code execution in the request
handler" sao a MESMA pergunta escrita de formas diferentes. Um cache exato nunca
casaria as duas; o cache semantico casa, porque compara SIGNIFICADO.

Determinismo: os embeddings vem de utils.semantic_embeddings.embed_text, que usa
sentence-transformers (roda offline, sem Ollama/LLM). Este modulo NAO chama
nenhum LLM; a "resposta" cacheada e so uma string de demonstracao.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from utils.semantic_embeddings import embed_text


@dataclass
class CacheEntry:
    """Uma entrada do cache: a query original, seu embedding e a resposta."""

    query: str
    embedding: np.ndarray
    response: str


@dataclass
class CacheStats:
    """Metricas acumuladas de uso do cache."""

    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Fracao de consultas servidas pelo cache (0.0 a 1.0)."""
        return self.hits / self.total if self.total else 0.0


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Similaridade de cosseno entre dois vetores (1.0 = identico em direcao)."""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class SemanticCache:
    """
    Cache de respostas por similaridade de query.

    Args:
        threshold: similaridade minima de cosseno (0.0 a 1.0) para considerar HIT.
                   Alto (ex: 0.9) = mais preciso, menos hits.
                   Baixo (ex: 0.7) = mais hits, risco de servir resposta errada.
        model: nome do modelo de embedding passado a embed_text.
    """

    def __init__(self, threshold: float = 0.85, model: str = "all-MiniLM-L6-v2") -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold deve estar entre 0.0 e 1.0")
        self.threshold = threshold
        self.model = model
        self._entries: List[CacheEntry] = []
        self.stats = CacheStats()

    def __len__(self) -> int:
        return len(self._entries)

    def set(self, query: str, response: str) -> None:
        """Adiciona (ou re-adiciona) uma query e sua resposta ao cache."""
        emb = embed_text(query, model=self.model)
        self._entries.append(CacheEntry(query=query, embedding=emb, response=response))

    def _nearest(self, query: str) -> Tuple[Optional[CacheEntry], float]:
        """Retorna a entrada mais similar a query e a similaridade dela."""
        if not self._entries:
            return None, 0.0
        q_emb = embed_text(query, model=self.model)
        best_entry: Optional[CacheEntry] = None
        best_sim = -1.0
        for entry in self._entries:
            sim = _cosine_similarity(q_emb, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry
        return best_entry, best_sim

    def get(self, query: str) -> Optional[str]:
        """
        Procura a query no cache por similaridade.

        Retorna a resposta cacheada (HIT) se o vizinho mais proximo tiver
        similaridade >= threshold; senao None (MISS). Atualiza as metricas.
        """
        entry, sim = self._nearest(query)
        if entry is not None and sim >= self.threshold:
            self.stats.hits += 1
            return entry.response
        self.stats.misses += 1
        return None

    def lookup(self, query: str) -> Tuple[Optional[str], float]:
        """
        Como get(), mas tambem devolve a similaridade do melhor candidato.
        Util para demos/debug. NAO atualiza metricas (nao conta hit/miss).
        """
        entry, sim = self._nearest(query)
        if entry is not None and sim >= self.threshold:
            return entry.response, sim
        return None, sim


def _demo() -> int:
    """
    Demo deterministica (sem Ollama): popula o cache com queries sobre CVEs,
    mostra HIT em query parafraseada e MISS em query distante, e imprime metricas.
    """
    print("=" * 64)
    print("DEMO — Cache Semantico de Respostas (sem LLM, so embeddings)")
    print("=" * 64)

    cache = SemanticCache(threshold=0.65)

    # Popula o cache: cada query foi "respondida" por um LLM caro no passado.
    seed = [
        (
            "remote code execution in the request handler",
            "Resposta cacheada: a RCE no handler permite executar codigo arbitrario; aplique o patch.",
        ),
        (
            "SQL injection in the login form",
            "Resposta cacheada: use consultas parametrizadas para mitigar a SQL injection no login.",
        ),
        (
            "how to rotate TLS certificates",
            "Resposta cacheada: rotacione os certificados TLS antes do vencimento e recarregue o servico.",
        ),
    ]
    for q, r in seed:
        cache.set(q, r)
    print(f"\nCache populado com {len(cache)} entradas.\n")

    # Consultas de teste: parafrases (mesmo significado, outra forma -> HIT) e
    # uma distante (MISS). As parafrases estao na mesma lingua do seed de propósito:
    # a similaridade do MiniLM e sensivel a mistura de idioma e a abreviacoes, entao
    # uma parafrase honesta ("arbitrary code execution via the HTTP request handler"
    # ~ "remote code execution in the request handler") e o teste justo do mecanismo.
    probes = [
        (
            "arbitrary code execution via the HTTP request handler",
            "HIT esperado (parafrase de RCE no handler)",
        ),
        (
            "injecting malicious SQL through the sign-in form",
            "HIT esperado (parafrase de SQL injection no login)",
        ),
        (
            "qual a receita de bolo de cenoura",
            "MISS esperado (topico totalmente distante)",
        ),
    ]

    for query, nota in probes:
        response, sim = cache.lookup(query)  # peek para imprimir a similaridade
        result = cache.get(query)            # conta hit/miss nas metricas
        status = "HIT " if result is not None else "MISS"
        print(f"[{status}] sim={sim:.3f}  query={query!r}  ({nota})")
        if result is not None:
            print(f"        -> {result}")

    s = cache.stats
    print("\n" + "-" * 64)
    print("Metricas:")
    print(f"  consultas : {s.total}")
    print(f"  hits      : {s.hits}")
    print(f"  misses    : {s.misses}")
    print(f"  hit_rate  : {s.hit_rate:.1%}")
    print(f"  chamadas de LLM evitadas: {s.hits} (uma por HIT)")
    print("-" * 64)

    # exit 0 enquanto a demo rodar; nenhuma assercao de rede/LLM.
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
