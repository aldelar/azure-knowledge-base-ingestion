"""Tests for fn_convert_mistral.describe_images — GPT-4.1 vision image descriptions.

These are unit tests verifying the module's structure and helpers.
Integration tests that call GPT-4.1 are not included here (they require
live Azure credentials and a deployed model).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fn_convert_mistral.describe_images import IMAGE_PROMPT, describe_all_images


class TestImagePrompt:
    """Tests for the image analysis prompt."""

    def test_prompt_mentions_description(self):
        assert "Description" in IMAGE_PROMPT

    def test_prompt_mentions_ui_elements(self):
        assert "UIElements" in IMAGE_PROMPT

    def test_prompt_mentions_navigation_path(self):
        assert "NavigationPath" in IMAGE_PROMPT


class TestDescribeAllImages:
    """Tests for describe_all_images orchestration."""

    @patch("fn_convert_mistral.describe_images.describe_image")
    def test_finds_images_in_images_subdir(self, mock_describe):
        """Verify it looks for images in staging_dir/images/ first."""
        mock_describe.return_value = "A description"

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            (staging / "images").mkdir()
            (staging / "images" / "shot.png").write_bytes(b"\x89PNG")

            result = describe_all_images(
                image_mapping={"shot.png": "shot.png"},
                staging_dir=staging,
                endpoint="https://test.cognitiveservices.azure.com",
                deployment="gpt-4.1",
            )

            assert "shot.png" in result
            mock_describe.assert_called_once()

    @patch("fn_convert_mistral.describe_images.describe_image")
    def test_fallback_to_root_dir(self, mock_describe):
        """Verify it falls back to staging_dir/ if images/ subdir has no match."""
        mock_describe.return_value = "Fallback description"

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)
            (staging / "shot.png").write_bytes(b"\x89PNG")

            result = describe_all_images(
                image_mapping={"shot.png": "shot.png"},
                staging_dir=staging,
                endpoint="https://test.cognitiveservices.azure.com",
                deployment="gpt-4.1",
            )

            assert "shot.png" in result

    def test_missing_image_skipped(self):
        """Verify missing images are skipped without raising."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            staging = Path(tmp)

            result = describe_all_images(
                image_mapping={"missing.png": "missing.png"},
                staging_dir=staging,
                endpoint="https://test.cognitiveservices.azure.com",
                deployment="gpt-4.1",
            )

            assert len(result) == 0
