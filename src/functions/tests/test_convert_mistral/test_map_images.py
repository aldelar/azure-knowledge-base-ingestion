"""Tests for fn_convert_mistral.map_images — marker extraction from OCR markdown."""

from __future__ import annotations

import pytest

from fn_convert_mistral.map_images import MARKER_RE, find_image_markers


class TestMarkerRegex:
    """Tests for the marker regex pattern."""

    def test_matches_basic_marker(self):
        assert MARKER_RE.search("text [[IMG:screenshot.png]] more")

    def test_extracts_filename(self):
        m = MARKER_RE.search("[[IMG:diagram.image]]")
        assert m.group(1) == "diagram.image"

    def test_strips_whitespace_in_group(self):
        # find_image_markers strips whitespace from the captured group
        _, filenames = find_image_markers(["[[IMG: test.png ]]"])
        assert filenames == ["test.png"]

    def test_no_match_without_brackets(self):
        assert not MARKER_RE.search("[IMG:file.png]")

    def test_no_match_empty(self):
        assert not MARKER_RE.search("no markers here")


class TestFindImageMarkers:
    """Tests for find_image_markers function."""

    def test_single_page_single_marker(self):
        pages = ["Some text [[IMG:a.png]] more text"]
        full_md, filenames = find_image_markers(pages)
        assert filenames == ["a.png"]
        assert "[[IMG:a.png]]" in full_md

    def test_multiple_pages_concatenated(self):
        pages = ["Page 1 [[IMG:a.png]]", "Page 2 [[IMG:b.png]]"]
        full_md, filenames = find_image_markers(pages)
        assert filenames == ["a.png", "b.png"]
        assert "\n\n" in full_md  # Pages joined with double newline

    def test_duplicate_markers_preserved(self):
        pages = ["[[IMG:a.png]] text [[IMG:a.png]]"]
        _, filenames = find_image_markers(pages)
        assert filenames == ["a.png", "a.png"]

    def test_no_markers_returns_empty(self):
        pages = ["Just plain text", "More text"]
        full_md, filenames = find_image_markers(pages)
        assert filenames == []
        assert "Just plain text" in full_md

    def test_marker_with_path(self):
        pages = ["[[IMG:images/screenshot.png]]"]
        _, filenames = find_image_markers(pages)
        assert filenames == ["images/screenshot.png"]

    def test_empty_pages(self):
        full_md, filenames = find_image_markers([])
        assert full_md == ""
        assert filenames == []
