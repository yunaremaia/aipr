"""Tests for User-Agent header in GitHub API requests (fixes #96)."""

from unittest.mock import patch, MagicMock
import urllib.request
import urllib.error
from aipr.http import fetch_with_retry


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
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"test"
        
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
            mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
            
            result = fetch_with_retry("https://api.github.com/test")
            
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
            assert user_agent is not None
            assert "aipr/" in user_agent


def test_user_agent_contains_version():
    """User-Agent should include the aipr version."""
    from aipr import __version__
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"test"
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = MagicMock(return_value=mock_resp)
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        
        fetch_with_retry("https://api.github.com/test")
        
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        user_agent = req.get_header("User-agent") or req.get_header("User-Agent")
        assert __version__ in user_agent

