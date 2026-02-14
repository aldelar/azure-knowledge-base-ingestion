"""Integration tests for fn_index.embedder — verify embedding returns 1536-dim vectors."""

from pathlib import Path

import pytest

from fn_index.chunker import Chunk, chunk_article
from fn_index.embedder import embed_chunks, embed_text

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SERVING = _REPO_ROOT / "kb" / "serving"
_DITA_ARTICLE = _SERVING / "ymr1770823224196_en-us" / "article.md"


class TestEmbedText:
    """Test single-text embedding."""

    def test_returns_1536_dim_vector(self):
        vector = embed_text("Hello world, this is a test sentence.")
        assert isinstance(vector, list)
        assert len(vector) == 1536
        assert all(isinstance(v, float) for v in vector)

    def test_non_empty_vectors(self):
        vector = embed_text("Azure AI Search enables vector search.")
        # At least some values should be non-zero
        assert any(v != 0.0 for v in vector)


class TestEmbedChunks:
    """Test batch chunk embedding."""

    def test_batch_embedding(self):
        chunks = [
            Chunk(content="First chunk.", title="Test", section_header="", image_refs=[]),
            Chunk(content="Second chunk.", title="Test", section_header="S2", image_refs=["img.png"]),
        ]
        results = embed_chunks(chunks)
        assert len(results) == 2
        for r in results:
            assert "content_vector" in r
            assert len(r["content_vector"]) == 1536
            assert "content" in r
            assert "title" in r
            assert "section_header" in r
            assert "image_refs" in r

    def test_real_article_embedding(self):
        if not _DITA_ARTICLE.exists():
            pytest.skip("DITA article not available")
        md = _DITA_ARTICLE.read_text(encoding="utf-8")
        chunks = chunk_article(md)
        # Embed just first 2 to keep test fast
        results = embed_chunks(chunks[:2])
        assert len(results) == 2
        for r in results:
            assert len(r["content_vector"]) == 1536
