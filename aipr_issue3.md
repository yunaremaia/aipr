## Problem

`aipr` classifies a repository's AI policy as `human_only`, `restrictive`, `disclose_ok`, `permissive`, or `unknown`, but its only output formats are human-readable text and JSON. For teams running `aipr` in CI/CD to gate autonomous contributions, there's no way to surface policy violations as GitHub Code Scanning alerts — the native GitHub security/compliance dashboard.

## Proposed Solution

Add a `--sarif` flag that outputs SARIF 2.1.0 (Static Analysis Results Interchange Format) to stdout. This enables:

```bash
aipr --sarif owner/repo > aipr-results.sarif
# Upload to GitHub Code Scanning:
#   github/codeql-action/upload-sarif with sarif_file: aipr-results.sarif
```

Each policy classification becomes a SARIF `result`:
- `human_only` / `restrictive` → `error` level (blocks contribution)
- `unknown` → `warning` level (needs manual review)
- `permissive` / `disclose_ok` → `note` level (safe to proceed)

## Acceptance Criteria

- [ ] `aipr --sarif owner/repo` outputs valid SARIF 2.1.0 JSON
- [ ] Each repo inspected becomes a `result` entry with `ruleId`, `level`, `message`, and `locations`
- [ ] `human_only` and `restrictive` map to SARIF `error`
- [ ] `unknown` maps to SARIF `warning`
- [ ] `permissive` and `disclose_ok` map to SARIF `note`
- [ ] SARIF output validates against the [SARIF 2.1.0 schema](https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json)
- [ ] Tests added in `tests/` with a sample SARIF output fixture
- [ ] README updated with CI/CD integration example (GitHub Actions workflow snippet)

## Context

SARIF is the standard format for GitHub Code Scanning alerts. Adding it to `aipr` lets teams enforce AI policy compliance in their CI pipeline — blocking autonomous contributions to repos that forbid them, all visible in the GitHub Security tab. The existing `--json` output already provides the structured data; SARIF is a serialization layer on top.
