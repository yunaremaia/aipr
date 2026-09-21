# Changelog

All notable changes to aipr will be documented in this file.

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
