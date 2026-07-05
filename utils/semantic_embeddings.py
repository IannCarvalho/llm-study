"""
Semantic Embeddings - Neural-based text embeddings

Uses Sentence Transformers for true semantic understanding.
Works offline, CPU-friendly, and produces high-quality embeddings.

Installation:
    pip install sentence-transformers

Available models:
    - all-MiniLM-L6-v2 (small, 384-dim, fast)
    - all-mpnet-base-v2 (large, 768-dim, best quality)
    - paraphrase-MiniLM-L6-v2 (good for paraphrases)
"""
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np
from utils.config import get_config


# Cache model to avoid reloading
_model = None
_current_model_name = None


def embed_texts(texts: List[str], model: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """
    Embed multiple texts.
    
    Args:
        texts: List of text strings
        model: Sentence Transformer model name
               - all-MiniLM-L6-v2: Small, fast (384-dim)
               - all-mpnet-base-v2: Large, best quality (768-dim)
               - paraphrase-MiniLM-L6-v2: Good for semantic similarity
    
    Returns:
        Array of embeddings (n_texts, embedding_dim)
    """
    global _model, _current_model_name
    
    # Load model only if not cached or model name changed
    if _model is None or _current_model_name != model:
        config = get_config()
        _model = SentenceTransformer(model, token=config.hf_token)
        _current_model_name = model
    
    embeddings = _model.encode(texts, convert_to_numpy=True)
    return embeddings.astype(np.float32)


def embed_text(text: str, model: str = "all-MiniLM-L6-v2") -> np.ndarray:
    """
    Embed a single text.
    
    Args:
        text: Text string
        model: Sentence Transformer model name
    
    Returns:
        Embedding vector (embedding_dim,)
    """
    return embed_texts([text], model)[0]
