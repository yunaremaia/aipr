# aipr

**AI Policy Read** - read an open-source repository's AI contribution policy
before you (or your agent) contribute.

`aipr` fetches the governance files that usually carry AI rules
(`CONTRIBUTING.md`, `AI_POLICY.md`, `AGENTS.md`, `CLAUDE.md`, ...), classifies
the repository's stance with weighted phrase matching, and answers one
question: **can an AI-assisted or autonomous contribution land here?**

## Quick Start

```bash
pip install aipr-py

aipr asciimoo/hister   # classify a GitHub repository
aipr --text AI_POLICY.md   # classify a local governance file
```

## What it does

- **Reads the policy, not the vibes.** Fetches the candidate governance files
  from GitHub and classifies the repository's stance from their text.
- **Machine-readable.** `--json` for scripts, `--sarif` for GitHub Code
  Scanning.
- **CI-friendly.** Exit codes carry the verdict: 0 safe, 1 blocked, 2 unknown.
- **Scaffolding.** `aipr init` writes `AI_POLICY.md` and `AI_TOOL_POLICY.md`
  for repositories that have none.
- **Cached.** Policy text is cached on disk for 24h, so repeated scans cost
  zero API calls.
- **No runtime dependencies** beyond `regex`.

## Verdicts at a glance

| Verdict | Meaning | Autonomous-safe? |
|---|---|---|
| `human_only` | AI must not be the main author / human-written only / bans agents | no |
| `restrictive` | heavy process: mandatory disclosure + human-in-the-loop | no |
| `disclose_ok` | allowed with a disclosure trailer (`Assisted-by: AI`) | yes* |
| `permissive` | explicitly welcomes AI-assisted contributions | yes |
| `unknown` | no explicit policy found | ask first |

\* "safe" means *no human co-authorship required by policy*, not *no
obligations*.

## Where to go next

- [Getting Started](getting-started.md) - install, first scan, reading the output
- [Usage](usage.md) - every flag, `init`, exit codes, caching, CI integration

## License

MIT