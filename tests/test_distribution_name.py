"""Regression guard: install targets must use the real PyPI distribution name.

``aipr`` is the repo name, the CLI command and the Python module -- but the
PyPI *distribution* is ``aipr-py``. When the project was renamed (#142) only
``pyproject.toml`` and the README were updated, leaving ``action.yml`` and
``.pre-commit-hooks.yaml`` installing ``aipr``. That name does not exist on PyPI
(HTTP 404), so every consumer of the composite Action and every user of the
pre-commit hook failed with a package-not-found error.

Nothing in CI caught it, because CI installs the project from source with
``pip install -e .`` and never exercises the published distribution name. These
tests pin every install target to the ``[project] name`` declared in
``pyproject.toml``, so the next rename cannot silently break them again.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# The authoritative PyPI distribution name. Read rather than hardcoded so this
# test keeps working across future renames.
DIST_NAME = re.search(
    r'^name\s*=\s*"([^"]+)"', (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M
).group(1)

# `pip install "<name><specifier>"` and `pip install <name><specifier>`.
PIP_INSTALL = re.compile(
    r'pip install ["\']?(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)'
    r'(?P<spec>[<>=!~][^"\'\s]*)?'
)

# pre-commit `additional_dependencies` entries, e.g. `- "<name><specifier>"`.
PRECOMMIT_DEP = re.compile(
    r'^\s*-\s*["\']?(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)'
    r'(?P<spec>[<>=!~][^"\'\s]*)?["\']?\s*$',
    re.M,
)

# Files that install this project from PyPI by distribution name.
INSTALL_TARGET_FILES = ("action.yml", ".pre-commit-hooks.yaml")


def install_targets(path):
    """Return every version-pinned distribution name the file installs.

    A version specifier is required so that non-installing metadata (such as
    pre-commit's ``- id: aipr`` or ``- uses: actions/setup-python@v6``) is not
    mistaken for an install target, while real pins such as ``- "aipr>=0.1.0"``
    are caught.
    """
    text = path.read_text(encoding="utf-8")
    targets = []
    for pattern in (PIP_INSTALL, PRECOMMIT_DEP):
        for match in pattern.finditer(text):
            if match.group("spec"):
                targets.append(match.group("name"))
    return targets


class TestDistributionName:
    """Install targets must name the distribution that actually exists."""

    def test_install_targets_use_distribution_name(self):
        """No file installs a PyPI name other than the one in pyproject.toml."""
        offenders = {}
        for name in INSTALL_TARGET_FILES:
            wrong = [t for t in install_targets(REPO_ROOT / name) if t != DIST_NAME]
            if wrong:
                offenders[name] = wrong

        assert not offenders, (
            f"install target(s) do not match pyproject name {DIST_NAME!r}: {offenders}. "
            f"`pip install <name>` resolves against PyPI, so the distribution name must "
            f"be {DIST_NAME!r} -- not the repo/module name."
        )

    def test_action_installs_distribution(self):
        """The composite Action installs the distribution (not a git URL)."""
        assert f'pip install "{DIST_NAME}' in (REPO_ROOT / "action.yml").read_text(
            encoding="utf-8"
        ), f'action.yml must run `pip install "{DIST_NAME}...` for the Action to work'

    def test_bare_name_not_used_as_install_target(self):
        """The bare `aipr` name is never used where pip resolves a package."""
        bare = DIST_NAME.removesuffix("-py")
        offenders = {
            name: [t for t in install_targets(REPO_ROOT / name) if t == bare]
            for name in INSTALL_TARGET_FILES
        }
        offenders = {k: v for k, v in offenders.items() if v}
        assert not offenders, (
            f"`pip install {bare}` 404s on PyPI; install {DIST_NAME!r} instead. "
            f"Found in: {offenders}"
        )