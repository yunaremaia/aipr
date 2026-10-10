# Usage

## Synopsis

```
usage: aipr [-h] [--text FILE] [--json] [--sarif] [--root ROOT] [--explain]
            [--no-cache] [--version]
            [repo ...]
```

| Flag | Effect |
|---|---|
| `repo ...` | `owner/repo` to inspect. Accepts several for batch mode. |
| `--text FILE` | Classify a local file instead of fetching from GitHub. |
| `--json` | JSON output. |
| `--sarif` | SARIF 2.1.0 output, for GitHub Code Scanning. |
| `--root ROOT` | Repository root used to resolve SARIF paths. Defaults to the current directory for `--text`. |
| `--explain` | Explain the verdict with the contributing policy sources and snippets. |
| `--no-cache` | Fetch policy files fresh even if a cached copy exists. |
| `--version` | Print the version and exit. |

As a GitHub CLI extension, `gh aipr` takes exactly the same arguments.

## Classifying Repositories

```bash
aipr OWNER/REPO
```

### Batch Mode

Pass several repositories and one block is printed per repo:

```bash
aipr owner/repo1 owner/repo2 owner/repo3
```

With `--json` the output is a single JSON array. The exit code reflects the
**worst** result, so an unverified repository can never pass a gate silently.

## Output Formats

### Human-readable (default)

```
aipr: asciimoo/hister
[BLOCKED] human-only policy
sources: CONTRIBUTING.md, README.md
confidence: 1.0  score: 19.0
```

### JSON

```bash
aipr --json OWNER/REPO
```

### SARIF 2.1.0

```bash
aipr --sarif OWNER/REPO > aipr-results.sarif
```

Upload with `github/codeql-action/upload-sarif` and the verdict surfaces as an
alert in the GitHub Security tab. Verdict mapping:

| Verdict | SARIF level | Meaning |
|---|---|---|
| `human_only`, `restrictive` | `error` | blocks contribution |
| `unknown` | `warning` | needs manual review |
| `permissive`, `disclose_ok` | `note` | safe to proceed |

`--root` sets the repository root that SARIF paths are resolved against, so the
reported locations point at real files rather than bare names.

## `init` - Scaffold Policy Files

Generate `AI_POLICY.md` and `AI_TOOL_POLICY.md`:

```bash
aipr init [--dir .] [--type disclose|permissive|human_only] [--org ORG]
```

| Option | Default | Effect |
|---|---|---|
| `--dir` | `.` | Directory to create the files in. |
| `--type` | `disclose` | Policy preset. |
| `--org` | unset | Organization name for centralized policies. |

Presets:

- `permissive` - explicitly welcomes AI-assisted contributions (autonomous-safe)
- `disclose` (default) - allowed with an `Assisted-by: AI` disclosure trailer
- `human_only` - AI must not be the main author (not autonomous-safe)

## Verdict to Exit Code

| Code | Meaning |
|---|---|
| 0 | all inspected repos are autonomous-safe |
| 1 | at least one repo is restricted or human-only |
| 2 | at least one repo is unknown / no policy found (outranked by 1) |
| 64 | usage error |

## How Classification Works

Weighted regex matching over the concatenated governance text. Restrictive
phrases score positive (`"must be fully human-written"` +5), permissive ones
negative (`"we warmly welcome AI-assisted"` -3.5). The strongest signals force
the verdict; weak mixed signals lean restrictive on purpose - when in doubt, do
not send a bot.

Known limits: English-only patterns; phrase matching cannot understand nuance; a
repository can carry its policy in a file `aipr` does not probe. Treat
`unknown` as "read it yourself".

## Caching

Policy text is cached on disk for 24 hours in `~/.cache/aipr`, so repeated
scans cost zero API calls.

| Variable | Default | Effect |
|---|---|---|
| `AIPR_CACHE_DIR` | `~/.cache/aipr` | Where the cache lives. |
| `AIPR_CACHE_TTL` | `86400` | Seconds before an entry expires. |
| `AIPR_CACHE_SIZE` | `1024` | Maximum number of cached repositories. |
| `GH_TOKEN` / `GITHUB_TOKEN` | unset | Token for GitHub API calls. |

Use `--no-cache` to force a fresh fetch.

## CI Integration

### Block a pull request against a restricted policy

```yaml
name: AI Policy Check
on:
  pull_request:
    branches: [main, master]

jobs:
  aipr:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install aipr-py
      - name: Check AI policy
        run: |
          # Exit 1 = human_only/restrictive (block), exit 2 = unknown (warn).
          aipr "$GITHUB_REPOSITORY" --json \
            | jq -e '.verdict == "human_only" or .verdict == "restrictive"' \
            && exit 1 || exit 0
```

### Surface the verdict as a code-scanning alert

```yaml
name: AI Policy Check (SARIF)
on:
  pull_request:
    branches: [main]

jobs:
  aipr-check:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: pip install aipr-py
      - run: aipr --sarif "${{ github.event.pull_request.head.repo.full_name }}" > aipr-results.sarif
      - uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: aipr-results.sarif
```

## License

MIT