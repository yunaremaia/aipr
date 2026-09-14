"""Tests for gh-aipr GitHub CLI extension wrapper."""

import subprocess
import sys
from pathlib import Path

import pytest

GH_AIPR = Path(__file__).parent.parent / "gh-aipr"


class TestGhAiprWrapper:
    """Test the gh-aipr extension entry point."""

    def test_help_works(self):
        """gh-aipr --help shows usage."""
        result = subprocess.run(
            [sys.executable, str(GH_AIPR), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "aipr" in result.stdout.lower()

    def test_classify_repo(self):
        """gh-aipr apache/maka returns expected output with valid exit code."""
        result = subprocess.run(
            [sys.executable, str(GH_AIPR), "apache/maka"],
            capture_output=True, text=True,
        )
        assert result.returncode in (0, 1, 2)
        assert "apache/maka" in result.stdout

    def test_json_output(self):
        """gh-aipr --json produces valid JSON."""
        result = subprocess.run(
            [sys.executable, str(GH_AIPR), "--json", "apache/maka"],
            capture_output=True, text=True,
        )
        assert result.returncode in (0, 1, 2)
        import json
        data = json.loads(result.stdout)
        assert "verdict" in data

    def test_exit_codes_preserved(self):
        """Exit codes match aipr CLI (0/1/2)."""
        result = subprocess.run(
            [sys.executable, str(GH_AIPR), "apache/maka"],
            capture_output=True, text=True,
        )
        assert result.returncode in (0, 1, 2)
