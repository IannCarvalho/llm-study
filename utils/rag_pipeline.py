"""Chroma RAG Pipeline - Local vector database for RAG"""

import os
import time
from typing import List, Dict, Optional, Any
from utils.llm_client import get_llm_client
from utils.models import SearchResult, RAGResponse
from utils.search import create_search_engine
from utils.logging import get_logger
from utils.config import get_config

logger = get_logger(__name__)


class ChromaRAGPipeline:
    """Chroma RAG pipeline for local vector database."""

    def __init__(
        self,
        collection_name: str = "documents",
        search_method: str = "hybrid",
        llm_model: Optional[str] = None,
        temperature: float = 0.7,
        top_k: int = 3,
        data_dir: Optional[str] = None,
    ):
        """Initialize Chroma RAG pipeline."""
        self.collection_name = collection_name
        self.search_method = search_method
        self.top_k = top_k
        self.llm = get_llm_client(model=llm_model, temperature=temperature)
        self.search_engine = create_search_engine(search_method)
        
        try:
            import chromadb
            
            config = get_config()
            data_dir = data_dir or config.chroma_path
            os.makedirs(data_dir, exist_ok=True)
            
            self.client = chromadb.PersistentClient(path=data_dir)
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(name=collection_name)
                logger.info(f"Connected to existing Chroma collection: {collection_name}")
            except Exception:
                self.collection = self.client.create_collection(name=collection_name)
                logger.info(f"Created new Chroma collection: {collection_name}")
        
        except ImportError:
            raise ImportError("chromadb not installed. Install with: pip install chromadb")

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to Chroma collection."""
        if not documents:
            logger.warning("No documents to add")
            return
        
        # Only add if collection is empty
        if self.collection.count() > 0:
            logger.info(f"Collection already has {self.collection.count()} documents")
            return
        
        # Prepare data
        ids = [doc["id"] for doc in documents]
        texts = [doc.get("text") or doc.get("content") or "" for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        
        # Add to Chroma
        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to Chroma collection")

    def delete_collection(self) -> None:
        """Delete the Chroma collection."""
        self.client.delete_collection(name=self.collection_name)
        logger.info(f"Deleted Chroma collection: {self.collection_name}")

    def count_documents(self) -> int:
        """Get number of documents in collection."""
        return self.collection.count()

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[SearchResult]:
        """Retrieve relevant documents."""
        top_k = top_k or self.top_k
        docs = self._get_all_documents()
        return self.search_engine.search(query, docs, top_k)

    def generate_rag_response(
        self,
        query: str,
        system_prompt: str,
        top_k: Optional[int] = None,
    ) -> RAGResponse:
        """Generate RAG response with retrieved context."""
        start_time = time.time()
        retrieved_docs = self.retrieve(query, top_k)
        context = "\n".join([doc.content for doc in retrieved_docs])
        prompt = system_prompt.format(context=context, query=query)
        response_text = self.llm.generate(prompt)
        
        return RAGResponse(
            query=query,
            context=context,
            response=response_text,
            retrieved_documents=retrieved_docs,
            model=self.llm.model,
            elapsed_time=time.time() - start_time
        )

    def _get_all_documents(self) -> List[Dict]:
        """Get all documents from Chroma in search format."""
        results = self.collection.get()
        return [
            {"id": doc_id, "content": results["documents"][i], 
             "metadata": results["metadatas"][i] if results["metadatas"] else {}}
            for i, doc_id in enumerate(results["ids"])
        ]


__all__ = ["ChromaRAGPipeline"]
