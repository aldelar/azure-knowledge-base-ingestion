"""Integration tests for fn_index.embedder — verify embedding returns 1536-dim vectors."""

import pytest

from fn_index.chunker import Chunk, chunk_article
from fn_index.embedder import embed_chunks, embed_text


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


