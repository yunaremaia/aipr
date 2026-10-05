# Getting Started

## Install

```bash
pip install aipr-py
```

The distribution on PyPI is `aipr-py`. From source:

```bash
pip install git+https://github.com/yunaremaia/aipr.git
```

Requires Python 3.10+.

As a GitHub CLI extension:

```bash
gh extension install yunaremaia/aipr
```

After install, `gh aipr OWNER/REPO` works identically and exit codes are
preserved for CI conditionals.

Verify:

```bash
aipr --version
```

## Authentication

Policy fetches go through the GitHub API. Anonymous calls rate-limit fast, so
set a token if you are scanning more than a couple of repositories:

```bash
export GH_TOKEN=ghp_xxx   # classic token with public repo read access
```

`GITHUB_TOKEN` is accepted as a fallback. Without a token the tool still works,
it just makes more unauthenticated requests.

## First Scan

```bash
aipr asciimoo/hister
```

Output:

```
aipr: asciimoo/hister
[BLOCKED] human-only policy
sources: CONTRIBUTING.md, README.md
confidence: 1.0  score: 19.0
autonomous contribution: NOT SAFE - require human co-authorship
```

A repository with no discoverable policy:

```
aipr: apache/maka
[UNKNOWN] no explicit AI policy found
```

and exits 2.

## Reading the Output

- **`sources`** - the files the verdict was drawn from.
- **`confidence` / `score`** - how strongly the matched phrases agree.
- The verdict line (`human_only`, `restrictive`, `disclose_ok`, `permissive`,
  `unknown`) is the classification itself.

## Explain the Verdict

When you disagree with the classification, ask for the evidence:

```bash
aipr --explain asciimoo/hister
```

```
autonomous contribution: NOT SAFE - require human co-authorship
  [+5.0] ...Issues and PR descriptions must be fully human-written...
  [+5.0] ...AI should never be the main author of the PR...
```

Each line is a phrase that matched, with the weight it contributed.

## Classify a Local File

To check a policy file before you commit it, or one you already have on disk:

```bash
aipr --text AI_POLICY.md
```

`--text` reads the file directly and makes no network calls.

## Gate a Contribution

Because the verdict is in the exit code, a pre-submission check is one line:

```bash
aipr "$GITHUB_REPOSITORY" || echo "check the AI policy before contributing"
```

- exit 0 - autonomous-safe
- exit 1 - restricted or human-only, do not send a bot
- exit 2 - unknown, read the policy yourself

See [Usage](usage.md) for batch mode, SARIF output and CI integration.