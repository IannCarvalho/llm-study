"""Unified Search - BM25, Semantic, and Hybrid Search"""

from typing import List, Dict, Optional, Union
import numpy as np
import re
from rank_bm25 import BM25Okapi
from utils.semantic_embeddings import embed_text, embed_texts
from utils.models import SearchResult
from utils.constants import RRF_K, MIN_SEMANTIC_SIMILARITY
from utils.logging import get_logger
from sentence_transformers import util

logger = get_logger(__name__)


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase word tokens."""
    return re.findall(r"\w+", text.lower())


class BM25Search:
    """Keyword-based search using BM25 algorithm."""

    def search(self, query: str, documents: List[Dict], top_k: int = 3) -> List[SearchResult]:
        """Perform BM25 keyword search."""
        if not documents:
            return []
        
        logger.debug(f"BM25 search: query='{query}', docs={len(documents)}, top_k={top_k}")
        
        # Tokenize all documents
        tokenized_docs = [tokenize(doc.get("content", "")) for doc in documents]
        
        # Create BM25 index
        bm25 = BM25Okapi(tokenized_docs)
        
        # Search
        tokenized_query = tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        
        # Clamp to [0, inf) - ensure no negative values
        scores = np.maximum(scores, 0)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        results = [
            SearchResult(
                id=documents[i]["id"],
                content=documents[i].get("content", ""),
                score=min(float(scores[i]) / (1 + float(scores[i])), 1.0),  # Normalize to [0,1]
                metadata=documents[i].get("metadata", {}),
                retrieval_method="bm25"
            )
            for i in top_indices
        ]
        
        logger.debug(f"BM25 found {len(results)} results")
        return results


class SemanticSearch:
    """Meaning-based search using embeddings."""

    def search(self, query: str, documents: List[Dict], top_k: int = 3) -> List[SearchResult]:
        """Perform semantic search using embeddings."""
        if not documents:
            return []
        
        logger.debug(f"Semantic search: query='{query}', docs={len(documents)}, top_k={top_k}")
        
        # Get embeddings
        doc_contents = [doc.get("content", "") for doc in documents]
        doc_embeddings = embed_texts(doc_contents)
        query_embedding = embed_text(query)
        
        # Calculate similarities
        similarities = util.cos_sim(query_embedding, doc_embeddings)[0].numpy()
        
        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        results = [
            SearchResult(
                id=documents[i]["id"],
                content=documents[i].get("content", ""),
                score=float(similarities[i]),
                metadata=documents[i].get("metadata", {}),
                retrieval_method="semantic"
            )
            for i in top_indices
            if similarities[i] > MIN_SEMANTIC_SIMILARITY
        ]
        
        logger.debug(f"Semantic search found {len(results)} results")
        return results


class HybridSearch:
    """Hybrid search combining BM25 and semantic using RRF."""

    def __init__(self, rrf_k: int = RRF_K):
        """Initialize hybrid search."""
        self.rrf_k = rrf_k
        self.bm25 = BM25Search()
        self.semantic = SemanticSearch()

    def search(self, query: str, documents: List[Dict], top_k: int = 3) -> List[SearchResult]:
        """Perform hybrid search combining BM25 and semantic."""
        if not documents:
            return []
        
        logger.debug(f"Hybrid search: query='{query}', docs={len(documents)}, top_k={top_k}")
        
        # Get results from both methods
        bm25_results = self.bm25.search(query, documents, top_k * 2)
        semantic_results = self.semantic.search(query, documents, top_k * 2)
        
        # Apply RRF
        combined = self._reciprocal_rank_fusion(bm25_results, semantic_results)
        
        # Return top-k
        return combined[:top_k]

    def _reciprocal_rank_fusion(
        self,
        bm25_results: List[SearchResult],
        semantic_results: List[SearchResult]
    ) -> List[SearchResult]:
        """Combine BM25 and semantic results using Reciprocal Rank Fusion."""
        # Build rank dictionaries: {doc_id: rank}
        bm25_ranks = {r.id: i + 1 for i, r in enumerate(bm25_results)}
        semantic_ranks = {r.id: i + 1 for i, r in enumerate(semantic_results)}
        
        # Collect all unique document IDs
        all_doc_ids = set(bm25_ranks.keys()) | set(semantic_ranks.keys())
        
        # Calculate RRF scores
        rrf_scores = {}
        for doc_id in all_doc_ids:
            bm25_rank = bm25_ranks.get(doc_id, len(bm25_results) + 1)
            semantic_rank = semantic_ranks.get(doc_id, len(semantic_results) + 1)
            
            rrf_score = 1 / (self.rrf_k + bm25_rank) + 1 / (self.rrf_k + semantic_rank)
            rrf_scores[doc_id] = rrf_score
        
        # Get all documents by ID for reference
        all_results = {r.id: r for r in bm25_results + semantic_results}
        
        # Create combined results sorted by RRF score
        combined = [
            SearchResult(
                id=doc_id,
                content=all_results[doc_id].content,
                score=rrf_scores[doc_id],
                metadata=all_results[doc_id].metadata,
                retrieval_method="hybrid"
            )
            for doc_id in sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        ]
        
        return combined


def create_search_engine(method: str = "hybrid", **kwargs) -> Union[BM25Search, SemanticSearch, HybridSearch]:
    """Create search engine instance."""
    methods = {
        "bm25": BM25Search,
        "semantic": SemanticSearch,
        "hybrid": HybridSearch,
    }
    
    if method not in methods:
        raise ValueError(f"Unknown search method: {method}. Must be one of {list(methods.keys())}")
    
    logger.debug(f"Creating search engine: {method}")
    return methods[method](**kwargs)


__all__ = [
    "BM25Search",
    "SemanticSearch",
    "HybridSearch",
    "create_search_engine",
    "tokenize",
]
