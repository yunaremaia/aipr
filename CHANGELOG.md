# Changelog

All notable changes to aipr will be documented in this file.

## [Unreleased]

### Fixed
- `tests/test_cache.py` had two assertions that could not fail: `test_corrupt_cache_entry_is_ignored` short-circuited its only call to `fetch_policy_text` behind `if False`, so the corrupt-cache recovery path was never exercised, and `test_clear_cache_removes_dir` ended in `or True`. Both now assert real outcomes and fail if the corresponding source behavior regresses.
- `test_corrupt_cache_entry_is_ignored` also wrote its corrupt payload to `bad.json` while `_cache_get` looks up `owner__repo-x.json`, so it could not have read the damaged entry even without the dead guard.

### Added
- A `lint` job in CI running `ruff check .` against a committed `ruff.toml` (pyflakes `F` rules), covering `src/` and `tests/`. Pre-existing `F401`/`F811`/`F841` violations were fixed rather than exempted, and `src/aipr/cache.py` now annotates its cache values as `Policy` instead of `object`.

## [0.2.7] - 2026-10-05

### Added
- Python 3.14 support: the `Programming Language :: Python :: 3.14` classifier is declared and `3.14` joins the CI test matrix. Python 3.14 is the current stable release, so PyPI's `Programming Language :: Python ::` browse filter hid `aipr-py` from anyone checking compatibility against today's Python, even though `requires-python = ">=3.10"` already allowed installing it there.
- `test_latest_python_classifier_is_in_the_ci_matrix` asserts the newest advertised version is actually exercised in CI, so a future release cycle cannot ship a classifier no test ever ran against.
- `test_every_supported_python_version_is_advertised` now derives the expected version set from `requires-python` and the highest declared classifier instead of a hand-typed list. The hardcoded `{"3.10", "3.11", "3.12", "3.13"}` is what let 3.14 go missing unnoticed.

### Verified
- The full suite (141 tests) passes on CPython 3.14.7, matching the count on 3.10, 3.11, 3.12 and 3.13. No source change was needed for 3.14 compatibility.

## [0.2.6] - 2026-10-05

### Added
- Python version classifiers for 3.10 through 3.13 and four `Topic ::` classifiers. `requires-python` already allowed `>=3.10`, but the PyPI page advertised no interpreter versions and a single topic, so the package was invisible to the version and topic browse filters.
- A `Source` project URL. The landing page offered no direct link to the repository it was built from.
- Generic discovery keywords (`policy`, `contribution-policy`, `developer-tools`, `code-review`, `github`, `ai-agents`).

### Changed
- `tests/test_pypi_metadata.py` now gates the Python version classifiers, the topic classifiers and the `Source` URL, so a future release cannot silently drop them again.

## [0.2.3] - 2026-09-21

### Security
- Fixed ReDoS vulnerability in policy regex patterns (#113). The `[^.]{0,80}` quantifier caused catastrophic backtracking on adversarial input. Fix: switched from `re` to `regex` module with 500ms timeout per pattern, added 1MB input truncation.

## [0.2.2] - 2026-09-12

### Added
- `.pre-commit-hooks.yaml` for native pre-commit integration
- CHANGELOG.md

## [0.2.0] - 2026-08-25

### Added
- Initial release: AI contribution policy reader
- Exit codes for CI/agents (0=autonomous-safe, 1=blocked, 2=unknown)
- Detection from CONTRIBUTING/AI_POLICY/AI_TOOL_POLICY/AGENTS/CLAUDE/README
- Weighted phrase matching with permissive/restricted/banned classification
- CI and PyPI publish workflows
