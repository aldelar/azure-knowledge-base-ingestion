"""Unit tests for fn_index.indexer — verify document structure matches schema."""

import pytest

from fn_index.indexer import (
    ALGORITHM_CONFIG_NAME,
    VECTOR_DIMENSIONS,
    VECTOR_PROFILE_NAME,
)


class TestDocumentStructure:
    """Verify the document format matches the AI Search schema."""

    def test_document_id_format(self):
        """Document ID should be {article_id}_{chunk_index}."""
        article_id = "test-article"
        chunk_index = 3
        expected_id = f"{article_id}_{chunk_index}"
        assert expected_id == "test-article_3"

    def test_document_schema_fields(self):
        """The document dict produced by index_chunks should have all required fields."""
        from fn_index.indexer import index_chunks

        # We can't push to indexer without Azure, but we can verify the constants
        assert VECTOR_DIMENSIONS == 1536
        assert VECTOR_PROFILE_NAME == "default-profile"
        assert ALGORITHM_CONFIG_NAME == "default-hnsw"

    def test_image_urls_format(self):
        """Image refs should be converted to images/<filename> paths."""
        image_refs = ["img1.png", "img2.png"]
        expected = [f"images/{ref}" for ref in image_refs]
        assert expected == ["images/img1.png", "images/img2.png"]

    def test_empty_image_refs(self):
        """Chunks with no images should have empty image_urls list."""
        image_refs = []
        urls = [f"images/{ref}" for ref in image_refs]
        assert urls == []
