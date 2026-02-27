"""Unit tests for fn_index.chunker — Markdown splitting by headers."""

from pathlib import Path

import pytest

from fn_index.chunker import Chunk, chunk_article

# ---------------------------------------------------------------------------
# Paths to the real article.md outputs from fn-convert
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SERVING = _REPO_ROOT / "kb" / "serving"
_CLEAN_ARTICLE = _SERVING / "content-understanding-overview-html_en-us" / "article.md"


def _read(path: Path) -> str:
    if not path.exists():
        pytest.skip(f"Article not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Clean HTML article (content-understanding...) — 1 H1 + 7 H2/H3, 2 images
# ---------------------------------------------------------------------------


class TestCleanArticle:
    """Chunking the clean HTML article output."""

    @pytest.fixture(scope="class")
    def chunks(self) -> list[Chunk]:
        return chunk_article(_read(_CLEAN_ARTICLE))

    def test_chunk_count(self, chunks):
        # 1 H1 + 1 H2 + 5 H3 + 1 extra = at least 7 sections
        assert len(chunks) >= 7

    def test_article_title_populated(self, chunks):
        for chunk in chunks:
            assert chunk.title

    def test_multiple_sections_present(self, chunks):
        # Article has several top-level sections producing multiple chunks
        assert len(chunks) >= 3

    def test_total_image_refs(self, chunks):
        all_refs = [ref for c in chunks for ref in c.image_refs]
        assert len(all_refs) == 2

    def test_no_content_lost(self, chunks):
        all_text = " ".join(c.content for c in chunks)
        assert "Content Understanding" in all_text
        assert "RAG" in all_text


# ---------------------------------------------------------------------------
# Edge cases — synthetic Markdown
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_document(self):
        assert chunk_article("") == []

    def test_no_headers(self):
        md = "Just a paragraph of text.\n\nAnother paragraph."
        chunks = chunk_article(md)
        assert len(chunks) == 1
        assert chunks[0].content == md.strip()
        assert chunks[0].section_header == ""

    def test_single_section(self):
        md = "# My Title\n\nSome content here."
        chunks = chunk_article(md)
        assert len(chunks) == 1
        assert chunks[0].title == "My Title"

    def test_image_ref_extraction(self):
        md = (
            "# Article\n\n## Section\n\n"
            "> **[Image: test_img](images/test_img.png)**\n"
            "> Description of image.\n"
        )
        chunks = chunk_article(md)
        section_chunks = [c for c in chunks if c.section_header]
        assert section_chunks
        assert "test_img.png" in section_chunks[0].image_refs

    def test_no_images(self):
        md = "# Title\n\n## Section A\n\nText.\n\n## Section B\n\nMore text."
        chunks = chunk_article(md)
        for chunk in chunks:
            assert chunk.image_refs == []
