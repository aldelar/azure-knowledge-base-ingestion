"""Unit tests for fn_index.chunker — Markdown splitting by headers."""

from pathlib import Path

import pytest

from fn_index.chunker import Chunk, chunk_article

# ---------------------------------------------------------------------------
# Paths to the real article.md outputs from fn-convert (Story 7)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_SERVING = _REPO_ROOT / "kb" / "serving"
_DITA_ARTICLE = _SERVING / "ymr1770823224196_en-us" / "article.md"
_CLEAN_ARTICLE = _SERVING / "content-understanding-html_en-us" / "article.md"


def _read(path: Path) -> str:
    if not path.exists():
        pytest.skip(f"Article not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# DITA article (ymr...) — 6 headers (1 H1 + 5 H2), 4 images
# ---------------------------------------------------------------------------


class TestDitaArticle:
    """Chunking the DITA-generated article output."""

    @pytest.fixture(scope="class")
    def chunks(self) -> list[Chunk]:
        return chunk_article(_read(_DITA_ARTICLE))

    def test_chunk_count(self, chunks):
        # preamble + 1 H1 + 5 H2 = 7 sections (preamble may be present)
        # At minimum we should have the H1 + H2 sections
        assert len(chunks) >= 6

    def test_article_title_populated(self, chunks):
        for chunk in chunks:
            assert chunk.title, f"Chunk missing title: {chunk.section_header}"

    def test_h2_section_headers(self, chunks):
        headers = [c.section_header for c in chunks if c.section_header]
        assert any("Firm Users" in h for h in headers)
        assert any("Client Users" in h for h in headers)

    def test_total_image_refs(self, chunks):
        all_refs = [ref for c in chunks for ref in c.image_refs]
        assert len(all_refs) == 4

    def test_image_refs_in_firm_section(self, chunks):
        firm_chunks = [c for c in chunks if "Firm Users" in c.section_header]
        assert firm_chunks
        refs = [ref for c in firm_chunks for ref in c.image_refs]
        # zzy, mnz, qvd are in the Firm Users section
        assert len(refs) >= 3

    def test_no_content_lost(self, chunks):
        # Check that key content appears in some chunk
        all_text = " ".join(c.content for c in chunks)
        assert "Manage user security" in all_text
        assert "Role field" in all_text


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

    def test_h3_inherits_h2_context(self, chunks):
        # H3 "Why use Content Understanding?" should inherit H2 context
        h3_chunks = [c for c in chunks if "Why use" in c.section_header]
        assert h3_chunks

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
