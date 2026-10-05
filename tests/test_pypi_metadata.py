"""The published metadata is the project's only shop window — keep it complete.

A package can be installable and still be invisible. PyPI indexes
``keywords`` for search, renders ``project.urls`` as the only navigational
links on the landing page, and shows a README badge to tell a visitor which
release is current. Each of those fields was empty or missing here at least
once, so an omission is now a test failure instead of something nobody
notices until the next release is cut.
"""

from __future__ import annotations

import re
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
README = (REPO_ROOT / "README.md").read_text(encoding="utf-8")


def test_keywords_are_indexed():
    """An empty keyword list makes the package unfindable by topic."""
    keywords = PROJECT.get("keywords") or []
    assert keywords, (
        "project.keywords is empty; PyPI indexes these for search, so an empty "
        "list hides the package from every topic query"
    )
    assert all(k.strip() for k in keywords), f"blank keyword in {keywords!r}"


def test_authors_are_declared():
    authors = PROJECT.get("authors") or []
    assert authors, "project.authors is empty: the landing page shows no maintainer"
    for author in authors:
        assert author.get("name"), f"author without a name: {author!r}"


@pytest.mark.parametrize(
    "label", ["Homepage", "Issues", "Funding", "Changelog", "Source"]
)
def test_project_url_is_present(label: str) -> None:
    urls = PROJECT.get("urls") or {}
    assert label in urls, (
        f"project.urls is missing {label!r}; the landing page offers only "
        f"{sorted(urls) or 'no links at all'}"
    )
    assert urls[label].startswith("https://"), f"{label} must be an https URL, got {urls[label]!r}"


def test_every_supported_python_version_is_advertised():
    """`requires-python` allows 3.10+ but the page listed no 3.x, so the
    interpreter badge showed nothing for anyone checking compatibility.

    The expected set is derived, not written out: a hand-typed list is what
    let 3.14 go missing in the first place, and it rots again at 3.15. Every
    minor version from the `requires-python` floor up to the highest declared
    classifier must be advertised.
    """
    declared = {
        c.rsplit(" ", 1)[-1]
        for c in PROJECT["classifiers"]
        if c.startswith("Programming Language :: Python :: 3.")
    }
    floor = int(PROJECT["requires-python"].removeprefix(">=").split(".")[1])
    highest = max(int(v.split(".")[1]) for v in declared)
    expected = {f"3.{minor}" for minor in range(floor, highest + 1)}
    missing = expected - declared
    assert not missing, f"missing Python version classifiers: {sorted(missing)}"
    assert f"3.{floor}" in declared, (
        f"requires-python allows {PROJECT['requires-python']} but no classifier "
        f"advertises 3.{floor}"
    )


def test_latest_python_classifier_is_in_the_ci_matrix():
    """A classifier nobody tests is a claim, not support.

    Python 3.14 shipped as stable while `requires-python` already allowed it,
    so the package was installable on 3.14 with no test ever running there and
    no classifier admitting it. Pinning the *newest* declared version to the CI
    matrix is the check that catches the next release cycle; the older
    versions may legitimately be sampled rather than all tested.
    """
    declared = [
        c.rsplit(" ", 1)[-1]
        for c in PROJECT["classifiers"]
        if c.startswith("Programming Language :: Python :: 3.")
    ]
    newest = max(declared, key=lambda v: tuple(int(p) for p in v.split(".")))
    ci_yml = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    matrix = re.search(r"python:\s*\[(.*?)\]", ci_yml)
    assert matrix, "could not find a python-version matrix in .github/workflows/ci.yml"
    tested = set(re.findall(r'"([0-9.]+)"', matrix.group(1)))
    assert newest in tested, (
        f"{newest} is advertised as supported but the CI matrix only tests "
        f"{sorted(tested)}"
    )


def test_topic_classifiers_are_declared():
    """Topic classifiers are a primary browse filter on the PyPI index."""
    topics = [c for c in PROJECT["classifiers"] if c.startswith("Topic ::")]
    assert len(topics) >= 4, f"only {len(topics)} Topic classifiers: {topics}"


def test_readme_shows_the_pypi_version_badge() -> None:
    """The version badge is the first thing a visitor reads before installing."""
    dist = PROJECT["name"]
    assert f"img.shields.io/pypi/v/{dist}" in README, (
        f"README has no PyPI version badge for {dist!r}; add "
        f"![PyPI](https://img.shields.io/pypi/v/{dist})"
    )
    assert f"pypi.org/project/{dist}" in README, (
        f"the {dist!r} badge should link to its PyPI project page"
    )
