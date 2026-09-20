"""Tests for User-Agent header in GitHub API requests (fixes #96)."""

from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
from aipr.http import fetch_with_retry, _build_request


def test_build_request_sets_user_agent():
    """_build_request should set a custom User-Agent header."""
    req = _build_request("https://api.github.com/repos/owner/repo/contents/CONTRIBUTING.md")
    # urllib normalizes headers to title-case or lowercase depending on Python version
    user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
    assert user_agent is not None, f"User-Agent not found in headers: {req.headers}"
    assert "aipr/" in user_agent


def test_build_request_user_agent_contains_version():
    """User-Agent should include the aipr version."""
    from aipr import __version__
    req = _build_request("https://api.github.com/repos/owner/repo/contents/CONTRIBUTING.md")
    user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
    assert __version__ in user_agent


def test_fetch_with_retry_sends_user_agent():
    """fetch_with_retry should send the User-Agent header."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"test content"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        result = fetch_with_retry("https://api.github.com/repos/owner/repo/contents/CONTRIBUTING.md")
        
        assert result == "test content"
        # Verify the request was made with User-Agent
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
        assert user_agent is not None
        assert "aipr/" in user_agent


def test_user_agent_without_token():
    """User-Agent should be set even without authentication token."""
    with patch.dict("os.environ", {}, clear=True):
        req = _build_request("https://api.github.com/test")
        user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
        assert user_agent is not None
        assert "aipr/" in user_agent

