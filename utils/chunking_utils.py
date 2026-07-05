"""
Chunking Utilities - Document splitting strategies

Provides unified interface for text chunking with multiple strategies:
- fixed: Simple fixed-size chunks
- sentence: Respects sentence boundaries
- recursive: Hierarchical splitting (RECOMMENDED)
"""

import re
from typing import List


def chunk_text(
    text: str,
    strategy: str = 'recursive',
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    Unified interface for text chunking.
    
    Args:
        text: Document to chunk
        strategy: 'fixed', 'sentence', or 'recursive' (default)
        chunk_size: Target size per chunk (characters). Must be > 0.
        overlap: Overlap between consecutive chunks. Must be < chunk_size.
        
    Returns:
        List of text chunks with specified overlap
        
    Raises:
        ValueError: If strategy is unknown or parameters are invalid
        TypeError: If text is not a string
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
    
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError(f"overlap must be in [0, {chunk_size}), got {overlap}")
    
    if not text:
        return []
    
    if strategy == 'fixed':
        return _fixed_size_chunking(text, chunk_size, overlap)
    elif strategy == 'sentence':
        return _sentence_chunking(text, chunk_size, overlap)
    elif strategy == 'recursive':
        return _recursive_chunking(text, chunk_size, overlap)
    else:
        raise ValueError(f"Unknown strategy: {strategy}. Use 'fixed', 'sentence', or 'recursive'")


def _fixed_size_chunking(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    Simple fixed-size chunking.
    
    Splits text into chunks of approximately chunk_size characters,
    with overlap between consecutive chunks.
    
    Pros: Fast, simple
    Cons: May break sentences/concepts
    """
    chunks = []
    step = chunk_size - overlap
    
    for i in range(0, len(text), step):
        chunk = text[i:i + chunk_size]
        if chunk:
            chunks.append(chunk)
    
    return chunks


def _sentence_chunking(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    Sentence-aware chunking.
    
    Splits on sentence boundaries to avoid breaking mid-sentence.
    Attempts to keep chunk sizes near chunk_size.
    
    Pros: Respects sentence structure
    Cons: Slower than fixed, may have variable sizes
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # Add overlap: append last overlap chars of previous chunk to current
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1]
            overlap_text = prev_chunk[-overlap:] if len(prev_chunk) >= overlap else prev_chunk
            overlapped.append(overlap_text + " " + chunks[i])
        return overlapped
    
    return chunks


def _recursive_chunking(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    Recursive hierarchical chunking (RECOMMENDED).
    
    Attempts to split text respecting structure:
    1. Try paragraphs (double newline)
    2. Try sentences
    3. Try words
    4. Fall back to characters
    
    Pros: Respects logical structure, maintains context
    Cons: Slower than fixed-size
    """
    
    def _split_and_chunk(
        text: str,
        separators: List[str],
        chunk_size: int,
        overlap: int,
        depth: int = 0
    ) -> List[str]:
        """Recursively split text using progressively smaller separators."""
        if depth >= len(separators):
            # Fall back to simple fixed-size if no separators left
            return _fixed_size_chunking(text, chunk_size, overlap)
        
        separator = separators[depth]
        splits = text.split(separator)
        good_splits = [s for s in splits if s]
        
        # If no splits occurred, try next separator
        if len(good_splits) <= 1:
            return _split_and_chunk(
                text, separators, chunk_size, overlap, depth + 1
            )
        
        # Group splits into chunks
        chunks = []
        current = ""
        
        for split in good_splits:
            if len(current) + len(split) + len(separator) < chunk_size:
                if current:
                    current += separator + split
                else:
                    current = split
            else:
                if current:
                    chunks.append(current)
                current = split
        
        if current:
            chunks.append(current)
        
        # Add overlap if needed
        if overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for i in range(1, len(chunks)):
                prev_chunk = chunks[i - 1]
                overlap_text = prev_chunk[-overlap:] if len(prev_chunk) >= overlap else prev_chunk
                overlapped.append(overlap_text + separator + chunks[i])
            return overlapped
        
        return chunks
    
    # Separators to try in order
    separators = [
        "\n\n",  # Paragraph
        "\n",    # Line
        ". ",    # Sentence
        " ",     # Word
        ""       # Character
    ]
    
    return _split_and_chunk(text, separators, chunk_size, overlap, depth=0)


def test_chunking_strategies(
    text: str,
    strategies: List[str] = None,
    chunk_sizes: dict = None
) -> dict:
    """
    Test multiple chunking strategies on a document.
    
    Helper function to compare different chunking approaches.
    
    Args:
        text: Document to test
        strategies: List of strategy names to test. Defaults to all: ['fixed', 'sentence', 'recursive']
        chunk_sizes: Dict mapping strategy to chunk_size. Defaults to {'fixed': 200, 'sentence': 300, 'recursive': 500}
        
    Returns:
        Dict with results for each strategy: {strategy: {'chunks': [...], 'count': int, 'avg_size': int}}
    """
    if strategies is None:
        strategies = ['fixed', 'sentence', 'recursive']
    
    if chunk_sizes is None:
        chunk_sizes = {'fixed': 200, 'sentence': 300, 'recursive': 500}
    
    results = {}
    
    for strategy in strategies:
        size = chunk_sizes.get(strategy, 500)
        chunks = chunk_text(text, strategy=strategy, chunk_size=size, overlap=50)
        
        avg_size = len(text) // len(chunks) if chunks else 0
        
        results[strategy] = {
            'chunks': chunks,
            'count': len(chunks),
            'avg_size': avg_size,
            'strategy_config': {
                'chunk_size': size,
                'overlap': 50
            }
        }
    
    return results
