"""Tests for main.py helper functions (context management, agent client)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.main import (
    _DEFAULT_USER_GROUP,
    Citation,  # re-exported from app.main
    _append_inline_image_fallbacks,
    _append_reference_tokens,
    _build_citation_content,
    _build_filename_lookup,
    _build_ref_map,
    _create_agent_client,
    _extract_tool_results,
    _expand_ref_markers,
    _get_user_groups,
    _get_user_id,
    _is_oauth_configured,
    _normalise_inline_images,
    _normalise_ref_mentions,
    _remap_ref_numbers,
    _rewrite_image_refs,
    _strip_md_images,
)


# ---------------------------------------------------------------------------
# Agent client creation
# ---------------------------------------------------------------------------

class TestCreateAgentClient:
    """Test _create_agent_client — HTTP (no auth) and HTTPS (Entra auth)."""

    @patch("app.main.config")
    def test_local_endpoint_no_auth(self, mock_config: MagicMock) -> None:
        mock_config.agent_endpoint = "http://localhost:8088"

        client = _create_agent_client()

        assert client.api_key == "local"
        assert client.base_url.host == "localhost"

    @patch("app.main.config")
    def test_internal_fqdn_no_auth(self, mock_config: MagicMock) -> None:
        mock_config.agent_endpoint = "http://agent-myproj.internal.cae-domain.eastus2.azurecontainerapps.io"

        client = _create_agent_client()

        assert client.api_key == "local"
        assert "agent-myproj" in str(client.base_url)

    @patch("app.main.DefaultAzureCredential")
    @patch("app.main.config")
    def test_https_endpoint_acquires_entra_token(self, mock_config: MagicMock, mock_cred_cls: MagicMock) -> None:
        mock_config.agent_endpoint = "https://apim-myproj-dev.azure-api.net/kb-agent"
        mock_cred = mock_cred_cls.return_value
        mock_cred.get_token.return_value = MagicMock(token="fake-entra-token")

        client = _create_agent_client()

        mock_cred.get_token.assert_called_once_with("https://ai.azure.com/.default")
        assert client.api_key == "fake-entra-token"
        assert "apim-myproj-dev" in str(client.base_url)

    @patch("app.main.DefaultAzureCredential")
    @patch("app.main.config")
    def test_https_endpoint_uses_correct_scope(self, mock_config: MagicMock, mock_cred_cls: MagicMock) -> None:
        mock_config.agent_endpoint = "https://some-gateway.azure-api.net/agent"
        mock_cred = mock_cred_cls.return_value
        mock_cred.get_token.return_value = MagicMock(token="another-token")

        _create_agent_client()

        mock_cred.get_token.assert_called_once_with("https://ai.azure.com/.default")

    @patch("app.main.config")
    def test_local_endpoint_with_user_groups(self, mock_config: MagicMock) -> None:
        """User groups are sent as X-User-Groups default header."""
        mock_config.agent_endpoint = "http://localhost:8088"

        client = _create_agent_client(user_groups=["group-a", "group-b"])

        assert client._custom_headers.get("X-User-Groups") == "group-a,group-b"

    @patch("app.main.config")
    def test_local_endpoint_no_groups_header(self, mock_config: MagicMock) -> None:
        """When user_groups is empty, no X-User-Groups header is set."""
        mock_config.agent_endpoint = "http://localhost:8088"

        client = _create_agent_client(user_groups=[])

        assert "X-User-Groups" not in (client._custom_headers or {})

    @patch("app.main.DefaultAzureCredential")
    @patch("app.main.config")
    def test_https_endpoint_with_user_groups(self, mock_config: MagicMock, mock_cred_cls: MagicMock) -> None:
        """HTTPS endpoint sends X-User-Groups header."""
        mock_config.agent_endpoint = "https://apim.azure-api.net/agent"
        mock_cred = mock_cred_cls.return_value
        mock_cred.get_token.return_value = MagicMock(token="tok")

        client = _create_agent_client(user_groups=["guid-1"])

        assert client._custom_headers.get("X-User-Groups") == "guid-1"


# ---------------------------------------------------------------------------
# Ref mapping
# ---------------------------------------------------------------------------

class TestBuildRefMap:
    """Test citation de-duplication."""

    def test_deduplicates_same_section(self) -> None:
        cits = [
            Citation("a1", "Title", "Section 1", 0),
            Citation("a1", "Title", "Section 1", 1),
            Citation("a1", "Title", "Section 2", 0),
        ]
        unique, mapping = _build_ref_map(cits)
        assert len(unique) == 2
        assert mapping == {1: 1, 2: 1, 3: 2}

    def test_empty_list(self) -> None:
        unique, mapping = _build_ref_map([])
        assert unique == []
        assert mapping == {}


class TestRemapRefNumbers:
    """Test ref number rewriting."""

    def test_remaps_numbers(self) -> None:
        text = "See Ref #1 and [Ref #3] for details."
        mapping = {1: 1, 2: 1, 3: 2}
        result = _remap_ref_numbers(text, mapping)
        assert "Ref #1" in result
        assert "Ref #2" in result
        assert "#3" not in result


class TestExpandRefMarkers:
    """Test bracket removal and combined ref expansion."""

    def test_single_ref(self) -> None:
        assert _expand_ref_markers("[Ref #1]") == "Ref #1"

    def test_combined_refs(self) -> None:
        result = _expand_ref_markers("[Ref #1, #5]")
        assert result == "Ref #1, Ref #5"

    def test_expands_ref_markers_with_and(self) -> None:
        result = _expand_ref_markers("[Refs #1 and #5]")
        assert result == "Ref #1 and Ref #5"


class TestNormaliseRefMentions:
    """Test canonicalisation of mixed bare ref formats."""

    def test_expands_mixed_bare_ref_list(self) -> None:
        text = "See ref#1, #2 and #3 for details."
        result = _normalise_ref_mentions(text)
        assert result == "See Ref #1, Ref #2 and Ref #3 for details."

    def test_expands_slash_separated_refs(self) -> None:
        text = "Supported by Refs #1/#2."
        result = _normalise_ref_mentions(text)
        assert result == "Supported by Ref #1 / Ref #2."


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

class TestStripMdImages:
    """Test markdown image removal."""

    def test_strips_images(self) -> None:
        text = "Before ![alt](http://example.com/img.png) after"
        assert "![" not in _strip_md_images(text)

    def test_preserves_non_images(self) -> None:
        text = "No images here"
        assert _strip_md_images(text) == text


class TestRewriteImageRefs:
    """Test [Image: name](images/file.png) rewriting."""

    def test_rewrites_to_proxy(self) -> None:
        text = "[Image: diagram](images/arch.png)"
        result = _rewrite_image_refs(text, "my-article")
        assert result == "![diagram](/api/images/my-article/images/arch.png)"


class TestNormaliseInlineImages:
    """Test comprehensive image URL normalisation."""

    def test_normalises_api_path(self) -> None:
        text = "![fig](api/images/article/images/f.png)"
        result = _normalise_inline_images(text, [])
        assert result == "![fig](/api/images/article/images/f.png)"

    def test_strips_hallucinated_domain(self) -> None:
        text = "![fig](https://learn.microsoft.com/api/images/article/images/f.png)"
        result = _normalise_inline_images(text, [])
        assert result == "![fig](/api/images/article/images/f.png)"

    def test_unresolvable_becomes_italic(self) -> None:
        text = "![fig](https://unknown.example.com/random.png)"
        result = _normalise_inline_images(text, [])
        assert "*[Image: fig]*" in result

    def test_resolves_filename_using_citations(self) -> None:
        text = "![fig](attachment:fig.png)"
        citations = [Citation("a1", "Title", "Section", 0, image_urls=["images/fig.png"])]
        result = _normalise_inline_images(text, citations)
        assert result == "![fig](/api/images/a1/images/fig.png)"


class TestAppendReferenceTokens:
    """Test fallback reference tokens for weak local model output."""

    def test_injects_reference_tokens_inline_when_missing(self) -> None:
        citations = [Citation("a1", "Title", "Section", 0)]
        result = _append_reference_tokens("Grounded answer.", citations)
        assert result == "Grounded answer. (Ref #1)"

    def test_injects_reference_tokens_into_first_bullet(self) -> None:
        citations = [Citation("a1", "Title", "Section", 0), Citation("a2", "Title", "Section", 1)]
        text = "- First supported point\n- Second supported point"
        result = _append_reference_tokens(text, citations)
        assert result.splitlines()[0].endswith("(Ref #1, Ref #2)")

    def test_preserves_existing_reference_tokens(self) -> None:
        citations = [Citation("a1", "Title", "Section", 0)]
        text = "Grounded answer with Ref #1 already present."
        assert _append_reference_tokens(text, citations) == text


class TestAppendInlineImageFallbacks:
    """Test inline image fallback rendering from citations."""

    def test_appends_images_from_citations_when_missing(self) -> None:
        citations = [Citation("a1", "Title", "Section", 0, image_urls=["images/fig1.png"])]
        result = _append_inline_image_fallbacks("Grounded answer.", citations)
        assert "![Ref #1 — Title](/api/images/a1/images/fig1.png)" in result

    def test_skips_fallback_when_answer_already_has_image(self) -> None:
        citations = [Citation("a1", "Title", "Section", 0, image_urls=["images/fig1.png"])]
        text = "Grounded answer.\n\n![existing](/api/images/a1/images/fig1.png)"
        assert _append_inline_image_fallbacks(text, citations) == text


class TestBuildFilenameLooup:
    """Test filename → proxy URL map building."""

    def test_builds_lookup(self) -> None:
        cits = [
            Citation("a1", "T", "S", 0, image_urls=["images/fig1.png", "images/fig2.png"]),
        ]
        lookup = _build_filename_lookup(cits)
        assert "fig1.png" in lookup
        assert "fig2.png" in lookup
        assert lookup["fig1.png"] == "/api/images/a1/images/fig1.png"

    def test_empty_citations(self) -> None:
        assert _build_filename_lookup([]) == {}


class TestExtractToolResults:
    """Test tool output parsing for streamed Responses API events."""

    def test_extracts_results_from_json_string(self) -> None:
        payload = '{"results": [{"ref_number": 1, "article_id": "a1"}]}'
        assert _extract_tool_results(payload) == [{"ref_number": 1, "article_id": "a1"}]

    def test_extracts_results_from_list_of_json_strings(self) -> None:
        payload = ['{"results": [{"ref_number": 1, "article_id": "a1"}]}']
        assert _extract_tool_results(payload) == [{"ref_number": 1, "article_id": "a1"}]

    def test_extracts_legacy_list_of_result_dicts(self) -> None:
        payload = [{"ref_number": 1, "article_id": "a1"}]
        assert _extract_tool_results(payload) == [{"ref_number": 1, "article_id": "a1"}]


# ---------------------------------------------------------------------------
# OAuth configuration detection
# ---------------------------------------------------------------------------


class TestIsOauthConfigured:

    def test_true_when_env_set(self) -> None:
        with patch.dict("os.environ", {"OAUTH_AZURE_AD_CLIENT_ID": "some-client-id"}):
            assert _is_oauth_configured() is True

    def test_false_when_env_unset(self) -> None:
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OAUTH_AZURE_AD_CLIENT_ID", None)
            assert _is_oauth_configured() is False

    def test_false_when_env_empty(self) -> None:
        with patch.dict("os.environ", {"OAUTH_AZURE_AD_CLIENT_ID": ""}):
            assert _is_oauth_configured() is False


# ---------------------------------------------------------------------------
# User identity helper  (_get_user_id)
# ---------------------------------------------------------------------------


class TestGetUserId:
    """Covers the three code paths in _get_user_id()."""

    def test_returns_chainlit_user_identifier(self) -> None:
        """Path 1: authenticated Chainlit user (OAuth or header callback)."""
        import chainlit as cl

        mock_user = MagicMock(spec=cl.User)
        mock_user.identifier = "oid-abc-123"
        mock_user.metadata = {}  # override MagicMock auto-attr so .get("oid") isn't truthy

        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = lambda key: {
                "user": mock_user,
            }.get(key)
            assert _get_user_id() == "oid-abc-123"

    def test_returns_easy_auth_header(self) -> None:
        """Path 2: no Chainlit user, but Easy Auth header present."""
        with patch("chainlit.user_session") as mock_session:
            def side_effect(key):
                if key == "user":
                    return None
                if key == "http_headers":
                    return {"x-ms-client-principal-id": "header-principal-456"}
                return None
            mock_session.get.side_effect = side_effect
            assert _get_user_id() == "header-principal-456"

    def test_returns_local_user_fallback(self) -> None:
        """Path 3: no auth at all — local dev mode."""
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = lambda key: None
            assert _get_user_id() == "local-user"

    def test_returns_local_user_on_exception(self) -> None:
        """Edge: user_session raises — treat as local dev."""
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = RuntimeError("no session")
            assert _get_user_id() == "local-user"


# ---------------------------------------------------------------------------
# User groups extraction
# ---------------------------------------------------------------------------

class TestGetUserGroups:
    """Test _get_user_groups extracts groups from user metadata."""

    def test_extracts_groups_from_metadata(self) -> None:
        mock_user = MagicMock()
        mock_user.metadata = {"groups": ["guid-1", "guid-2"]}
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = mock_user
            assert _get_user_groups() == ["guid-1", "guid-2"]

    def test_returns_default_group_when_no_entra_groups(self) -> None:
        mock_user = MagicMock()
        mock_user.metadata = {"provider": "header"}
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = mock_user
            assert _get_user_groups() == [_DEFAULT_USER_GROUP]

    def test_returns_empty_when_no_user(self) -> None:
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.return_value = None
            assert _get_user_groups() == []

    def test_returns_empty_on_exception(self) -> None:
        with patch("chainlit.user_session") as mock_session:
            mock_session.get.side_effect = RuntimeError("no session")
            assert _get_user_groups() == []
