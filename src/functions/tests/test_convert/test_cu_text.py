"""Tests for fn_convert.cu_text — CU text extraction via prebuilt-documentSearch.

These are integration tests that call the live Azure Content Understanding
endpoint.  They require:
    - A valid .env with AI_SERVICES_ENDPOINT
    - text-embedding-3-large deployed and registered as a CU default
    - ``az login`` with Cognitive Services User role on the AI Services resource
"""

from pathlib import Path

import pytest

from fn_convert.cu_text import CuTextResult, extract_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_html_file(article_dir: Path) -> Path:
    """Return the first .html file in *article_dir* (skips metadata JSON)."""
    html_files = [
        f
        for f in article_dir.iterdir()
        if f.suffix == ".html" and ".metadata" not in f.name and "base64" not in f.name
    ]
    assert html_files, f"No HTML file found in {article_dir}"
    return html_files[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(params=["content-understanding-html_en-us", "ymr1770823224196_en-us"])
def article_html(staging_path: Path, request: pytest.FixtureRequest) -> Path:
    """Yield the HTML file path for each sample article."""
    article_dir = staging_path / request.param
    if not article_dir.exists():
        pytest.skip(f"Article {request.param} not in staging")
    return _find_html_file(article_dir)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractText:
    """Integration tests for extract_text()."""

    def test_returns_cu_text_result(self, article_html: Path) -> None:
        """extract_text returns a CuTextResult with markdown and summary."""
        result = extract_text(article_html)
        assert isinstance(result, CuTextResult)

    def test_markdown_is_nonempty(self, article_html: Path) -> None:
        """CU should produce non-trivial Markdown from both sample articles."""
        result = extract_text(article_html)
        assert len(result.markdown) > 500, (
            f"Markdown too short ({len(result.markdown)} chars) for {article_html.name}"
        )

    def test_markdown_has_heading(self, article_html: Path) -> None:
        """CU Markdown should contain at least one Markdown heading."""
        result = extract_text(article_html)
        assert result.markdown.startswith("#") or "\n#" in result.markdown, (
            "Expected at least one Markdown heading in CU output"
        )

    def test_summary_is_nonempty(self, article_html: Path) -> None:
        """prebuilt-documentSearch should produce a summary."""
        result = extract_text(article_html)
        assert len(result.summary) > 20, (
            f"Summary too short ({len(result.summary)} chars) for {article_html.name}"
        )

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """extract_text raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            extract_text(tmp_path / "nonexistent.html")
