"""fn-index — Stage 2: Markdown → AI Search index.

Orchestrates chunking, embedding, and indexing of a processed KB article.
"""


def run(article_path: str) -> None:
    """Index a single processed KB article into Azure AI Search.

    Args:
        article_path: Path to the processed article folder (contains article.md + images/).
    """
    raise NotImplementedError("fn-index will be implemented in Stories 8-9")
