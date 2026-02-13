"""fn-convert — Stage 1: HTML → Markdown + images.

Orchestrates the conversion of a source KB article (HTML + images) into
clean Markdown with AI-generated image descriptions.
"""


def run(article_path: str, output_path: str) -> None:
    """Convert a single KB article from HTML to Markdown with image descriptions.

    Args:
        article_path: Path to the source article folder (contains index.html + *.image files).
        output_path: Path to write the processed article (article.md + images/).
    """
    raise NotImplementedError("fn-convert will be implemented in Stories 3-6")
