"""Tests for fn_convert_mistral.mistral_ocr — PDF OCR via Mistral on Azure Foundry.

Unit tests for the endpoint derivation helper and mocked tests for the
``ocr_pdf`` function.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fn_convert_mistral.mistral_ocr import _derive_foundry_endpoint, ocr_pdf


# ---------------------------------------------------------------------------
# _derive_foundry_endpoint
# ---------------------------------------------------------------------------


class TestDeriveFoundryEndpoint:
    """Tests for the endpoint URL derivation helper."""

    def test_services_endpoint_returned_as_is(self):
        url = "https://myres.services.ai.azure.com"
        assert _derive_foundry_endpoint(url) == url

    def test_services_endpoint_trailing_slash_stripped(self):
        url = "https://myres.services.ai.azure.com/"
        assert _derive_foundry_endpoint(url) == "https://myres.services.ai.azure.com"

    def test_cognitiveservices_endpoint_converted(self):
        url = "https://myres.cognitiveservices.azure.com"
        assert _derive_foundry_endpoint(url) == "https://myres.services.ai.azure.com"

    def test_openai_endpoint_converted(self):
        url = "https://myres.openai.azure.com"
        assert _derive_foundry_endpoint(url) == "https://myres.services.ai.azure.com"

    def test_trailing_slash_handled(self):
        url = "https://myres.cognitiveservices.azure.com/"
        assert _derive_foundry_endpoint(url) == "https://myres.services.ai.azure.com"

    def test_invalid_endpoint_raises(self):
        with pytest.raises(ValueError, match="Cannot derive Foundry endpoint"):
            _derive_foundry_endpoint("not-a-url")

    def test_empty_string_raises(self):
        with pytest.raises((ValueError, IndexError)):
            _derive_foundry_endpoint("")


# ---------------------------------------------------------------------------
# ocr_pdf
# ---------------------------------------------------------------------------


class TestOcrPdf:
    """Mocked tests for the ocr_pdf function."""

    @patch("fn_convert_mistral.mistral_ocr.httpx.post")
    @patch("fn_convert_mistral.mistral_ocr.DefaultAzureCredential")
    def test_returns_json_response(self, mock_cred_cls, mock_post, tmp_path):
        # Setup credential mock
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "fake-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_cls.return_value = mock_cred

        # Setup httpx response mock
        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {"pages": [{"markdown": "# Title"}]}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        # Create a minimal PDF file
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake content")

        result = ocr_pdf(
            pdf_path,
            endpoint="https://myres.cognitiveservices.azure.com",
            deployment="mistral-doc-ai",
        )

        assert result == {"pages": [{"markdown": "# Title"}]}
        mock_post.assert_called_once()

    @patch("fn_convert_mistral.mistral_ocr.httpx.post")
    @patch("fn_convert_mistral.mistral_ocr.DefaultAzureCredential")
    def test_calls_correct_foundry_url(self, mock_cred_cls, mock_post, tmp_path):
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "fake-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_cls.return_value = mock_cred

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        ocr_pdf(
            pdf_path,
            endpoint="https://myres.cognitiveservices.azure.com",
            deployment="mistral-doc-ai-2512",
        )

        call_args = mock_post.call_args
        url = call_args[0][0]
        assert url == "https://myres.services.ai.azure.com/providers/mistral/azure/ocr"

    @patch("fn_convert_mistral.mistral_ocr.httpx.post")
    @patch("fn_convert_mistral.mistral_ocr.DefaultAzureCredential")
    def test_sends_base64_pdf(self, mock_cred_cls, mock_post, tmp_path):
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "fake-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_cls.return_value = mock_cred

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 content")

        ocr_pdf(pdf_path, endpoint="https://myres.services.ai.azure.com", deployment="model")

        call_args = mock_post.call_args
        body = call_args[1]["json"]
        assert body["document"]["type"] == "document_url"
        assert body["document"]["document_url"].startswith("data:application/pdf;base64,")
        assert body["model"] == "model"

    @patch("fn_convert_mistral.mistral_ocr.httpx.post")
    @patch("fn_convert_mistral.mistral_ocr.DefaultAzureCredential")
    def test_sends_auth_header(self, mock_cred_cls, mock_post, tmp_path):
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test-bearer-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_cls.return_value = mock_cred

        mock_resp = MagicMock()
        mock_resp.is_success = True
        mock_resp.json.return_value = {}
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        ocr_pdf(pdf_path, endpoint="https://myres.services.ai.azure.com", deployment="m")

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-bearer-token"

    @patch("fn_convert_mistral.mistral_ocr.httpx.post")
    @patch("fn_convert_mistral.mistral_ocr.DefaultAzureCredential")
    def test_http_error_raises(self, mock_cred_cls, mock_post, tmp_path):
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "fake-token"
        mock_cred.get_token.return_value = mock_token
        mock_cred_cls.return_value = mock_cred

        import httpx

        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp
        )
        mock_post.return_value = mock_resp

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        with pytest.raises(httpx.HTTPStatusError):
            ocr_pdf(pdf_path, endpoint="https://myres.services.ai.azure.com", deployment="m")

    def test_missing_pdf_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ocr_pdf(
                tmp_path / "nonexistent.pdf",
                endpoint="https://myres.services.ai.azure.com",
                deployment="m",
            )
