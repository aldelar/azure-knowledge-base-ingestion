"""Tests for fn_convert_mistral.render_pdf — HTML → PDF with image markers."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import pytest

from fn_convert_mistral.render_pdf import (
    _inject_print_css,
    _replace_images_with_markers,
)


class TestInjectPrintCSS:
    """Tests for CSS injection into HTML head."""

    def test_injects_before_head_close(self):
        html = "<html><head><title>T</title></head><body></body></html>"
        result = _inject_print_css(html)
        assert "orphans: 3" in result
        assert result.index("orphans") < result.index("</head>")

    def test_no_head_tag_prepends(self):
        html = "<html><body>Hello</body></html>"
        result = _inject_print_css(html)
        assert "orphans: 3" in result


class TestReplaceImagesWithMarkers:
    """Tests for replacing <img> tags with [[IMG:...]] markers."""

    def test_basic_img_replaced(self):
        html = '<p>Text</p><img src="images/screenshot.png" alt="pic"><p>More</p>'
        result = _replace_images_with_markers(html)
        assert "[[IMG:screenshot.png]]" in result
        assert "<img" not in result

    def test_preserves_filename_with_extension(self):
        html = '<img src="path/to/diagram.image">'
        result = _replace_images_with_markers(html)
        assert "[[IMG:diagram.image]]" in result

    def test_unwraps_a_tag_around_img(self):
        html = '<a href="big.png"><img src="images/thumb.png"></a>'
        result = _replace_images_with_markers(html)
        assert "[[IMG:thumb.png]]" in result
        # The <a> wrapper should be gone
        assert "<a " not in result

    def test_multiple_images(self):
        html = '<img src="a.png"><p>gap</p><img src="b.png">'
        result = _replace_images_with_markers(html)
        assert "[[IMG:a.png]]" in result
        assert "[[IMG:b.png]]" in result

    def test_img_without_src_kept(self):
        html = '<img alt="no source">'
        result = _replace_images_with_markers(html)
        # No src → tag is returned unchanged
        assert '<img alt="no source">' in result

    def test_marker_format(self):
        html = '<img src="images/test.png">'
        result = _replace_images_with_markers(html)
        # Should be wrapped in a <p> for rendering
        assert "<p " in result
        assert "[[IMG:test.png]]" in result
