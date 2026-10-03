# Changelog

All notable changes to aipr will be documented in this file.

## [Unreleased]

### Fixed
- `tests/test_cache.py` had two assertions that could not fail: `test_corrupt_cache_entry_is_ignored` short-circuited its only call to `fetch_policy_text` behind `if False`, so the corrupt-cache recovery path was never exercised, and `test_clear_cache_removes_dir` ended in `or True`. Both now assert real outcomes and fail if the corresponding source behavior regresses.
- `test_corrupt_cache_entry_is_ignored` also wrote its corrupt payload to `bad.json` while `_cache_get` looks up `owner__repo-x.json`, so it could not have read the damaged entry even without the dead guard.

### Added
- A `lint` job in CI running `ruff check .` against a committed `ruff.toml` (pyflakes `F` rules), covering `src/` and `tests/`. Pre-existing `F401`/`F811`/`F841` violations were fixed rather than exempted, and `src/aipr/cache.py` now annotates its cache values as `Policy` instead of `object`.

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
