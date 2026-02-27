"""Tests for fn_convert_mistral.merge — link recovery and article assembly."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from fn_convert_mistral.merge import (
    _clean_description,
    extract_link_map,
    merge_article,
    recover_links,
)


# ---------------------------------------------------------------------------
# recover_links
# ---------------------------------------------------------------------------


class TestRecoverLinks:
    """Tests for hyperlink re-injection into markdown."""

    def test_single_link_injected(self):
        md = "For details, see Adding or Changing Roles in the help center."
        link_map = [("Adding or Changing Roles", "https://example.com/roles")]
        result = recover_links(md, link_map)
        assert "[Adding or Changing Roles](https://example.com/roles)" in result

    def test_existing_link_not_doubled(self):
        md = "See [Adding Roles](https://example.com/roles) for details."
        link_map = [("Adding Roles", "https://example.com/roles")]
        result = recover_links(md, link_map)
        assert result.count("[Adding Roles]") == 1

    def test_multiple_links(self):
        md = "Use Feature A and Feature B for best results."
        link_map = [
            ("Feature A", "https://example.com/a"),
            ("Feature B", "https://example.com/b"),
        ]
        result = recover_links(md, link_map)
        assert "[Feature A](https://example.com/a)" in result
        assert "[Feature B](https://example.com/b)" in result

    def test_missing_text_skipped(self):
        md = "This text has no matching link labels."
        link_map = [("nonexistent", "https://example.com")]
        result = recover_links(md, link_map)
        assert result == md

    def test_empty_link_map(self):
        md = "Some markdown content."
        result = recover_links(md, [])
        assert result == md

    def test_word_boundary_prevents_partial_match(self):
        md = "Use the Foundry Tools for setup."
        link_map = [("Foundry Tool", "https://example.com")]
        result = recover_links(md, link_map)
        # Should NOT match "Foundry Tool" inside "Foundry Tools"
        assert "[Foundry Tool]" not in result


# ---------------------------------------------------------------------------
# extract_link_map
# ---------------------------------------------------------------------------


class TestExtractLinkMap:
    """Tests for HTML link extraction."""

    def test_basic_link(self):
        html = '<a href="https://example.com">Example</a>'
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html)
            f.flush()
            result = extract_link_map(Path(f.name))
        assert ("Example", "https://example.com") in result

    def test_anchor_links_excluded(self):
        html = '<a href="#section">Jump</a>'
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html)
            f.flush()
            result = extract_link_map(Path(f.name))
        assert len(result) == 0

    def test_image_wrapper_links_excluded(self):
        html = '<a href="big.png"><img src="thumb.png"></a>'
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html)
            f.flush()
            result = extract_link_map(Path(f.name))
        assert len(result) == 0

    def test_multiple_links(self):
        html = '<a href="https://a.com">A</a> <a href="https://b.com">B</a>'
        with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
            f.write(html)
            f.flush()
            result = extract_link_map(Path(f.name))
        assert len(result) == 2


# ---------------------------------------------------------------------------
# merge_article
# ---------------------------------------------------------------------------


class TestMergeArticle:
    """Tests for the full article assembly."""

    def test_markers_replaced_with_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            staging.mkdir()
            (staging / "images").mkdir()
            # Create a dummy image
            (staging / "images" / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            output = Path(tmp) / "output"

            merge_article(
                ocr_markdown="Intro text\n\n[[IMG:shot.png]]\n\nMore text",
                source_filenames=["shot.png"],
                descriptions={"shot.png": "A screenshot showing the dashboard."},
                staging_dir=staging,
                output_dir=output,
            )

            article = (output / "article.md").read_text()
            assert "> **[Image: shot](images/shot.png)**" in article
            assert "> A screenshot showing the dashboard." in article
            assert "[[IMG:" not in article
            assert (output / "images" / "shot.png").exists()

    def test_link_recovery_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            staging.mkdir()

            output = Path(tmp) / "output"

            merge_article(
                ocr_markdown="See the Azure portal for details.",
                source_filenames=[],
                descriptions={},
                staging_dir=staging,
                output_dir=output,
                link_map=[("Azure portal", "https://portal.azure.com")],
            )

            article = (output / "article.md").read_text()
            assert "[Azure portal](https://portal.azure.com)" in article

    def test_missing_image_warns_but_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp) / "staging"
            staging.mkdir()

            output = Path(tmp) / "output"

            # Should not raise even though image file doesn't exist
            merge_article(
                ocr_markdown="[[IMG:missing.png]]",
                source_filenames=["missing.png"],
                descriptions={"missing.png": "Missing image."},
                staging_dir=staging,
                output_dir=output,
            )

            article = (output / "article.md").read_text()
            assert "> **[Image: missing](images/missing.png)**" in article


# ---------------------------------------------------------------------------
# _clean_description
# ---------------------------------------------------------------------------


class TestCleanDescription:
    """Tests for the GPT description cleanup helper."""

    def test_structured_description_extracted(self):
        raw = (
            "1. **Description**: A diagram showing the data flow.\n"
            "2. **UIElements**: None.\n"
            "3. **NavigationPath**: N/A."
        )
        result = _clean_description(raw)
        assert result == "A diagram showing the data flow"

    def test_ui_elements_included_when_meaningful(self):
        raw = (
            "1. **Description**: A screenshot of the settings page.\n"
            "2. **UIElements**: Save button, Cancel button.\n"
            "3. **NavigationPath**: Settings > General."
        )
        result = _clean_description(raw)
        assert "A screenshot of the settings page" in result
        assert "**UI Elements**: Save button, Cancel button" in result
        assert "**Navigation Path**: Settings > General" in result

    def test_ui_elements_excluded_when_none(self):
        raw = (
            "1. **Description**: An architecture diagram.\n"
            "2. **UIElements**: None.\n"
            "3. **NavigationPath**: N/A."
        )
        result = _clean_description(raw)
        assert "UI Elements" not in result
        assert "Navigation Path" not in result

    def test_unstructured_text_returned_as_is(self):
        raw = "This is just a plain description with no structured headers."
        result = _clean_description(raw)
        assert result == raw.strip()

    def test_empty_string(self):
        result = _clean_description("")
        assert result == ""

    def test_without_numbering(self):
        raw = (
            "**Description**: A flowchart.\n"
            "**UIElements**: None.\n"
            "**NavigationPath**: N/A."
        )
        result = _clean_description(raw)
        assert "A flowchart" in result
        assert "UI Elements" not in result
