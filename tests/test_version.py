"""`__version__` must reflect the installed distribution, not a literal.

The constant is used in three places that leave the machine: the `--version`
flag, the HTTP `User-Agent` header sent to the GitHub API, and the SARIF
report's tool version. While it was hardcoded, a published `aipr-py` 0.2.4
reported and advertised itself as 0.2.3.
"""

from __future__ import annotations

import re
import tomllib
from importlib.metadata import version as metadata_version
from pathlib import Path

import pytest

import aipr

REPO_ROOT = Path(__file__).resolve().parents[1]


def _declared_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def test_version_is_not_a_hardcoded_literal():
    """The module must not carry its own copy of the version string."""
    source = (REPO_ROOT / "src" / "aipr" / "__init__.py").read_text(encoding="utf-8")
    literal = re.search(r'^__version__\s*=\s*[\'"]([\d.]+)[\'"]', source, re.MULTILINE)
    assert literal is None, (
        "__version__ is assigned a literal; read it from the installed "
        "distribution metadata instead so it cannot drift from pyproject.toml"
    )


def test_version_is_wellformed():
    assert re.fullmatch(r"\d+\.\d+\.\d+([.\-+].*)?", aipr.__version__), (
        f"unexpected version string: {aipr.__version__!r}"
    )


@pytest.mark.skipif(
    metadata_version("aipr-py") == "0.0.0.dev0",
    reason="package is not installed; version falls back to the dev placeholder",
)
def test_version_matches_installed_distribution():
    assert aipr.__version__ == metadata_version("aipr-py")


def test_declared_version_is_not_a_placeholder():
    assert _declared_version() != "0.0.0", (
        "pyproject.toml still declares the dev placeholder version"
    )