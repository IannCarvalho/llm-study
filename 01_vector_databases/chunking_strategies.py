"""
Chunking Strategies: Dividing Documents into Chunks

Problem: Large documents don't fit into embeddings models with context limits.
Solution: Split documents into smaller, overlapping chunks that fit.

Three strategies with different trade-offs:
- Fixed-size: Fast, simple, may break mid-sentence
- Sentence-based: Respects sentences, more natural
- Recursive: RECOMMENDED, respects hierarchical structure (paragraphs → sentences → words)
"""

from utils.chunking_utils import test_chunking_strategies
from utils.agentic_utils import SAMPLE_DOCUMENTS


def main() -> None:
    # Get sample security document
    sample_text = SAMPLE_DOCUMENTS["security"]

    print(f"Document: {len(sample_text)} characters\n")

    # Test all three strategies
    results = test_chunking_strategies(sample_text)

    for strategy, data in results.items():
        strategy_name = strategy.upper()
        if strategy == 'fixed':
            description = "(Fast, may break mid-sentence)"
        elif strategy == 'sentence':
            description = "(Respects sentences, more natural)"
        else:
            description = "(RECOMMENDED, preserves structure)"

        print(f"Strategy: {strategy_name} {description}")
        print(f"  Chunks: {data['count']} | Avg size: {data['avg_size']} chars")


if __name__ == "__main__":
    main()
