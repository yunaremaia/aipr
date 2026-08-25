# aipr

**AI Policy Read** - read an open-source repository's AI contribution policy
before you (or your agent) contribute.

`aipr` fetches the governance files that usually carry AI rules
(`CONTRIBUTING.md`, `AI_POLICY.md`, `AGENTS.md`, `CLAUDE.md`, ...), classifies
the repository's stance with weighted phrase matching, and answers one
question: **can an AI-assisted or autonomous contribution land here?**

```
$ aipr asciimoo/hister
aipr: asciimoo/hister
[BLOCKED] human-only policy
sources: CONTRIBUTING.md, README.md
confidence: 1.0  score: 19.0
autonomous contribution: NOT SAFE - require human co-authorship
  [+5.0] ...Issues and PR descriptions must be fully human-written...
  [+5.0] ...AI should never be the main author of the PR...

$ aipr apache/maka
aipr: apache/maka
[UNKNOWN] no explicit AI policy found
exit=2
```

## Why

More repositories are publishing explicit AI policies - from "we welcome
AI-assisted work" to "agents are strictly forbidden". Violating one burns the
contributor (and, for autonomous agents, the operator): rejected PRs at best,
blocks at worst. `aipr` makes the check mechanical and cheap, for humans
deciding where to spend review effort and for agents deciding where to spend
their quota.

## Install

```bash
pip install git+https://github.com/yunaremaia/aipr.git
# requires Python 3.10+; GH_TOKEN recommended (anonymous API calls rate-limit fast)
export GH_TOKEN=ghp_xxx   # classic token with public repo read access
```

No dependencies beyond the standard library. `pytest` only to develop.

## Usage

```bash
aipr OWNER/REPO            # classify a GitHub repository
aipr --text FILE           # classify a local governance file
aipr --json OWNER/REPO     # machine-readable output
```

### Verdicts

| Verdict | Meaning | Autonomous-safe? |
|---|---|---|
| `human_only` | AI must not be the main author / human-written only / bans agents | no |
| `restrictive` | heavy process: mandatory disclosure + human-in-the-loop requirements | no |
| `disclose_ok` | allowed with a disclosure trailer (`Assisted-by: AI`) | yes* |
| `permissive` | explicitly welcomes AI-assisted contributions | yes |
| `unknown` | no explicit policy found | ask first |

\* still follow the disclosure rules - "safe" means *no human co-authorship
required by policy*, not *no obligations*.

### Exit codes (for CI and agents)

| Code | Meaning |
|---|---|
| 0 | autonomous-safe verdict |
| 1 | restricted or human-only |
| 2 | unknown / no policy found |
| 64 | usage error |

## How classification works

Weighted regex matching over concatenated governance text. Restrictive phrases
score positive ("must be fully human-written" +5), permissive ones negative
("we warmly welcome AI-assisted" -3.5). The strongest signals force the
verdict; weak mixed signals lean restrictive on purpose - when in doubt, do
not send a bot.

Known limits: English-only patterns; phrase matching cannot understand nuance;
a repo can carry policy in unusual files we don't probe. Treat UNKNOWN as
"read it yourself".

## Status

Early beta - battle-tested against a handful of real policies (hister,
modular, polars, MDAnalysis, maka). Rule additions welcome: open an issue with
the policy text and the verdict you expected.

## License

MIT
