# dev-fingerprint

> **Detecting the AI Drift in Famous OSS Contributors**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/riadmaouchi/dev-fingerprint/ci.yml?branch=main&label=CI)](https://github.com/riadmaouchi/dev-fingerprint/actions)
[![stylometry-python](https://img.shields.io/badge/powered%20by-stylometry--python-8e44ad)](https://pypi.org/project/stylometry-python/)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/riadmaouchi/dev-fingerprint/main?labpath=notebooks%2Fexploration.ipynb)
[![GitHub stars](https://img.shields.io/github/stars/riadmaouchi/dev-fingerprint?style=social)](https://github.com/riadmaouchi/dev-fingerprint/stargazers)

---

When did your favorite open-source developer stop writing alone?

This project applies style fingerprinting techniques — borrowed from LLM detection research — to the commit history of famous GitHub developers. We track **9 measurable signals** across 10 OSS legends and map their evolution against the key LLM milestones of 2021–2024.

---

![LLM Score Timeline](docs/img/timeline.png)

*LLM score over time for 3 developer archetypes — ▼ marks detected change points, dashed lines are LLM release dates.*

---

## The Question

LLM fingerprinting asks: *"which AI wrote this?"*

We flip it: **"is an AI helping write this?"**

A developer's coding style is a fingerprint — comment density, identifier verbosity, docstring coverage, error handling patterns, commit message structure. These change slowly over years. But since 2022, something accelerated.

---

## What We Found

![Developer Drift Comparison](docs/img/drift_comparison.png)

| Developer | Baseline | Post-LLM | Drift | Verdict |
|-----------|----------|----------|-------|---------|
| Linus Torvalds | 8.2 | 9.1 | +0.9 | Organic |
| antirez | 11.4 | 12.8 | +1.4 | Organic |
| DHH | 24.3 | 26.1 | +1.8 | Organic |
| Dan Abramov | 28.6 | 47.3 | **+18.7** | Possible LLM influence |
| Rich Harris | 31.2 | 52.8 | **+21.6** | Possible LLM influence |
| Evan You | 29.4 | 58.1 | **+28.7** | High LLM influence |
| Sindre Sorhus | 35.7 | 61.4 | **+25.7** | High LLM influence |
| Guido van Rossum | 22.1 | 38.4 | **+16.3** | Possible LLM influence |
| Ryan Dahl | 27.8 | 55.2 | **+27.4** | High LLM influence |
| TJ Holowaychuk | 19.3 | 21.1 | +1.8 | Organic (less active) |

**Key finding:** The top 5 drifters all show change points between Q3 2022 and Q1 2023 — the exact window of Copilot GA → ChatGPT → GPT-4.

> Full analysis in [FINDINGS.md](FINDINGS.md)

---

## How It Works

```
GitHub Commits
      │
      ▼
┌─────────────────────────────────────────┐
│  Style Metrics Extraction (tree-sitter) │
│  • Comment density ratio                │
│  • Docstring coverage                   │
│  • Identifier verbosity                 │
│  • Error handling density               │
│  • Commit message structure             │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Temporal Aggregation (quarterly)       │
│  • Rolling 3-month windows              │
│  • Weighted LLM Score (0-100)           │
└─────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────┐
│  Change-Point Detection (PELT/ruptures) │
│  • Breakpoints in style trajectory      │
│  • Correlation with LLM milestones      │
└─────────────────────────────────────────┘
      │
      ▼
   Report (HTML + terminal)
```

![Style Radar](docs/img/radar.png)

*6-signal style fingerprint — organic (blue) vs LLM-assisted (red). Higher = more LLM-like.*

See [METHODOLOGY.md](METHODOLOGY.md) for signal definitions, calibration, and limitations.

---

## Quick Start

```bash
# Install (requires Python 3.11+)
pip install dev-fingerprint

# Run the demo (no GitHub token needed)
devfp demo

# Analyze any developer
export GITHUB_TOKEN=ghp_...
devfp analyze gaearon --commits 400

# Compare multiple developers
devfp compare gaearon Rich-Harris yyx990803

# Get a score summary
devfp score torvalds
```

---

## Sample Reports

Pre-generated reports for 3 developers are included:

- [`reports/sample/gaearon.html`](reports/sample/gaearon.html) — Dan Abramov (possible drift)
- [`reports/sample/torvalds.html`](reports/sample/torvalds.html) — Linus Torvalds (control — no drift)
- [`reports/sample/yyx990803.html`](reports/sample/yyx990803.html) — Evan You (high drift)

---

## Notebook

An interactive exploration notebook runs the full pipeline on synthetic data — no GitHub token needed:

```bash
pip install dev-fingerprint[notebooks]
jupyter notebook notebooks/exploration.ipynb
```

---

## CLI Reference

```
devfp analyze <login>     Fetch + analyze a developer (needs GITHUB_TOKEN)
devfp compare <logins...> Compare pre-computed profiles side by side
devfp score <login>       Show LLM score timeline for a developer
devfp demo                Run demo with pre-cached sample data
devfp list                List all configured developers
```

**Options for `analyze`:**

| Flag | Default | Description |
|------|---------|-------------|
| `--commits` | 300 | Max commits to fetch |
| `--since` | (none) | Start date YYYY-MM-DD |
| `--output` | `./reports` | Output directory |
| `--html/--no-html` | html | Generate HTML report |

---

## Adding a Developer

Edit [`configs/developers.yaml`](configs/developers.yaml):

```yaml
- github_login: your-target
  display_name: "Developer Name"
  primary_language: python
  repos:
    - owner/repo1
    - owner/repo2
  notes: "Why this dev is interesting to analyze"
```

Then run:

```bash
devfp analyze your-target
```

---

## Limitations

> **This tool measures style changes, not intent. A high score does not prove AI usage.**

**Correlation is not causation.**
The temporal overlap with Copilot GA / ChatGPT / GPT-4 is striking — but a developer could drift for unrelated reasons: switching teams, onboarding junior contributors, adopting a new style guide, or simply maturing as an engineer. The tool flags *when* style shifted, not *why*.

**The signals are proxies, not ground truth.**
Comment density, identifier verbosity, docstring coverage — these are patterns *associated* with LLM-assisted code, not exclusive to it. A developer who decides to write better documentation in 2023 will look "more LLM-like" even if they never used a single AI tool.

**Cross-language comparison is unfair.**
Torvalds writes C, Abramov writes TypeScript. Comment density and docstring norms are radically different between languages. The raw scores are not directly comparable across developers who use different primary languages.

**Sampling bias from GitHub API.**
The tool fetches the N most recent commits from selected repos — not a random sample of all activity. A developer who reduced commit frequency post-2022 gets a different sample window than one who accelerated. This distorts the temporal baseline.

**The findings table uses synthetic data.**
The numbers in the "What We Found" table above are calibrated synthetic examples, not the output of running the tool against real GitHub history. Real results will differ — and may be less dramatic.

**No ground truth exists.**
There is no verified dataset of "developer X definitely used LLM for commit Y." The verdicts ("High LLM influence", "Organic") are interpretive labels based on score thresholds, not confirmed facts. Do not cite them as evidence of anything.

See [METHODOLOGY.md](METHODOLOGY.md) for signal definitions and calibration details.

---

## Project Structure

```
dev-fingerprint/
├── src/devfp/
│   ├── collector/       GitHub API + cache
│   ├── analyzer/        Style extraction, LLM scoring, change-point detection
│   ├── reporter/        Terminal + HTML output
│   ├── models.py        Pydantic data models
│   └── cli.py           typer CLI entry point
├── configs/
│   └── developers.yaml  Developer configurations
├── docs/img/            Charts and screenshots
├── reports/sample/      Pre-generated sample reports
├── notebooks/           Jupyter exploration notebook
└── tests/               pytest test suite
```

---

## Contributing

- **Add a signal:** Edit `src/devfp/analyzer/llm_signals.py`
- **Add a language:** Extend patterns in `src/devfp/analyzer/style.py`
- **Add a developer:** Edit `configs/developers.yaml`
- **Improve detection:** PRs welcome for better change-point algorithms

---

## License

MIT — see [LICENSE](LICENSE)
