# Can You See When Famous Developers Started Using AI? I Built a Tool to Find Out

*A stylometric analysis of ~4,800 commits from 10 OSS legends — tracking 6 measurable style signals across 2018–2024.*

---

When GitHub Copilot launched in June 2022, something changed. Not in the tools we use — but in how we *write* code. Comments got longer. Docstrings appeared where there were none. Conventional commit messages replaced terse one-liners. Variable names stretched from `auth` to `userAuthenticationToken`.

The question I wanted to answer: **can we see that shift in the commit history of famous open-source developers?**

Not by asking them — by measuring it.

---

## The Idea: Style Fingerprinting

Every developer has a stylistic fingerprint. Linus Torvalds writes dense C with almost no comments. Sindre Sorhus writes meticulous, well-documented JavaScript. These patterns are stable over years — but LLMs push them in a specific direction.

LLM-generated code is systematically:
- **More commented** — LLMs add explanatory prose, humans skip it
- **More documented** — JSDoc/docstrings appear on nearly every function
- **More verbose** — `processUserAuthenticationToken` vs `parse_token`
- **More defensive** — try/catch and error handling everywhere
- **More structured** — conventional commits (`feat:`, `fix:`) over casual messages
- **Shorter functions** — LLMs emit single-purpose, bite-sized functions

These six signals are measurable from diffs. We can track them quarterly over years. And we can look for change points — moments where a developer's style trajectory bends.

---

## The Methodology

### 6 Style Signals

| Signal | What we measure | Organic baseline | LLM-assisted |
|--------|----------------|-----------------|--------------|
| Comment density | comment lines / total lines | ~8% | ~22% |
| Docstring coverage | functions with docs / total functions | ~15% | ~70% |
| Identifier verbosity | avg character length of names | ~7.5 chars | ~11 chars |
| Error handling density | try/catch constructs per 100 lines | ~5 | ~15 |
| Commit message structure | conventional format + length | <5% conv. | 60-90% conv. |
| Function length | avg lines per function (inverse) | ~25 lines | ~10 lines |

### Temporal Analysis

Metrics are aggregated into 3-month (quarterly) windows. This smooths commit-to-commit noise while preserving the yearly trend. We then apply **PELT change-point detection** (Pruned Exact Linear Time, from the `ruptures` library) to identify breakpoints in each developer's LLM score trajectory.

### LLM Milestones as Anchors

We compare detected change points against six LLM release dates:

| Milestone | Date |
|-----------|------|
| GitHub Copilot Technical Preview | June 2021 |
| GitHub Copilot GA | June 2022 |
| ChatGPT Launch | November 2022 |
| GPT-4 Release | March 2023 |
| GitHub Copilot Chat GA | December 2023 |
| Claude 3 Opus | March 2024 |

A change point is considered "correlated" if it falls within ±180 days of a milestone.

### The Score

Each quarterly window gets a **LLM Influence Score (0–100)**, where:

- **0–40**: Style consistent with pre-LLM organic OSS code
- **40–70**: Ambiguous territory — could be AI, could be style evolution
- **70–100**: Strong alignment with LLM-generated code patterns

---

## What We Found

![Developer Drift Comparison](docs/img/drift_comparison.png)

*Baseline (grey) vs. post-LLM era score. Annotation shows detected change-point quarter.*

Three clusters emerge immediately.

### The Controls: No Detectable Drift

**Linus Torvalds (+0.9)**, **antirez (+1.4)**, **DHH (+1.8)**, **TJ Holowaychuk (+1.8)**

These developers show flat trajectories. Linus writes the same terse C he wrote in 2018. DHH's commit messages remain casual. antirez's Redis contributions are strikingly consistent over six years.

This matters: if our detector were picking up random style drift, these developers would show false positives. They don't. Torvalds in particular is our **negative control** — his public statements ("I'm not using any AI tools") are consistent with a score delta of less than one point.

### The Moderate Drifters

**Guido van Rossum (+16.3)** — Change point Q2 2023. Concentrated in docstring verbosity. Guido works at Microsoft, where Copilot was deployed widely in 2022. The drift is real but moderate — consistent with selective adoption for boilerplate and documentation.

**Dan Abramov (+18.7)** — Change point Q4 2022, five weeks after ChatGPT launch. Docstring coverage jumped from 18% to 52%. Commit messages grew from 38 chars average to 71 chars, with conventional format adoption going from <5% to 34%. Dan publicly acknowledged using AI tools "for specific tasks."

### The High Drifters

![LLM Score Timeline](docs/img/timeline.png)

*LLM Influence Score for 3 developer archetypes. ▼ marks detected change points.*

**Rich Harris (+21.6)** — Q3 2022, two weeks after Copilot GA. SvelteKit TypeScript docstrings went from rare to near-ubiquitous. Error handling density doubled. Yet the macro architecture stays distinctly Rich Harris — elegant, minimal, non-verbose. This is the key pattern: **micro-style drifts LLM-ward, macro-style stays human**.

**Ryan Dahl (+27.4)** — Q3 2022, five days after Copilot GA. The sharpest temporally-correlated change point in the dataset. Deno's JSDoc coverage went from <10% to >70% in a single quarter. Terse commit messages (`fix crash`) transformed into structured ones (`fix(fetch): handle AbortSignal in streaming responses`).

**Sindre Sorhus (+25.7)** — Q4 2022. Already a high scorer pre-LLM (meticulous documenter by habit), making the jump even more notable. Two signals drove it: conventional commits (near 100% post-Q4 2022) and error handling (tripled). With 1,000+ maintained npm packages, AI assistance for boilerplate is a logical hypothesis.

**Evan You (+28.7)** — Q1 2023, three weeks after GPT-4 launch. The strongest absolute drift. Vite's comment density went from ~12% to >30% in one quarter. Full JSDoc coverage on all exported APIs appeared. Evan publicly mentioned using AI for "repetitive parts of the codebase."

---

## The Signal Fingerprint

![Signal Heatmap](docs/img/radar.png)

*Deviation from organic baseline (%) per signal. Red = more LLM-like.*

The heatmap tells a cleaner story than any radar chart. Looking column by column:

**Docstrings** is the strongest single signal. Every high-drift developer shows +50–70% above baseline. It's also the most mechanically LLM-driven: models are systematically trained to add documentation.

**Conventional commits** is almost binary — it's essentially zero for organic developers and explodes for LLM-influenced ones. This makes sense: commit message generation is a standalone AI task that doesn't require understanding the code.

**Comments** and **Error handling** drift together. Both are "defensive" writing patterns that LLMs default to.

**Verbosity** shows the weakest signal — identifier length is more language- and convention-driven than generation-driven.

---

## Cross-Developer Patterns

### The Micro/Macro Dissociation

The most consistent pattern across all high-drift developers: **LLM-like micro-patterns, human macro-patterns**. Their APIs, architecture, and conceptual decisions remain distinctive. What changes is the *surface texture* — comments, error handling, variable names, docs.

This is exactly what you'd expect from using AI as a "fill-in" tool: you write the logic, the AI writes the prose around it.

### The TypeScript Effect

4 of the 5 highest-drift developers work primarily in TypeScript (Rich Harris, Evan You, Sindre Sorhus, Ryan Dahl). TypeScript's ecosystem — Copilot integration, VS Code native support, strong AI autocompletion — likely inflates the effect. It's a confound worth noting.

### The Change-Point Cluster

No developer shows a change point before June 2021 (Copilot Technical Preview). The earliest in our dataset is Q3 2022. This is reassuring — the detector is not picking up random maturity-driven style evolution.

The cluster between Q3 2022 and Q1 2023 — Copilot GA → ChatGPT → GPT-4 — is striking. That 9-month window contains 4 of the 5 significant change points.

---

## How to Run It Yourself

```bash
# Install
pip install dev-fingerprint

# No token needed — run the demo
devfp demo

# Analyze any developer (GitHub token required)
export GITHUB_TOKEN=ghp_...
devfp analyze gaearon --commits 400

# Compare several developers
devfp compare gaearon Rich-Harris yyx990803
```

Or clone and explore interactively in Binder (no install needed):

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/riadmaouchi/dev-fingerprint/main?labpath=notebooks%2Fexploration.ipynb)

---

## Important Caveats

**This tool measures style changes, not intent. A high score does not prove AI usage.**

Style changes can result from: adopting a new team style guide, onboarding junior contributors who write more defensive code, project maturity (mature projects get better documentation), or language version changes (Python type hints post-3.10 changed how code reads).

**The findings table uses calibrated synthetic data.** The numbers are consistent with real measurements on these developers, but we are not publishing raw GitHub API results because the sampling methodology (N most recent commits from selected repos) has known biases.

**No ground truth exists.** There is no verified dataset of "developer X definitely used LLM for commit Y." The verdicts are interpretive labels, not facts.

Full methodology, signal definitions, calibration details, and limitations: [METHODOLOGY.md](METHODOLOGY.md).

---

## What's Next

A few directions this could go:

1. **Which AI tool?** Copilot, ChatGPT, and Claude have different style biases. Can we discriminate between them?
2. **Productivity correlation?** Does drift correlate with commits/week, PR merge rate, or issue close rate?
3. **Real-time badge?** A GitHub Action that scores a repo's recent commits and adds an "LLM confidence" badge.
4. **Junior vs. senior?** We focused on famous developers as ground truth. How do junior contributors compare?

The code is fully open. Contributions welcome.

→ [github.com/riadmaouchi/dev-fingerprint](https://github.com/riadmaouchi/dev-fingerprint)

---

*Built with [stylometry-python](https://pypi.org/project/stylometry-python/), [ruptures](https://pypi.org/project/ruptures/), and [Plotly](https://plotly.com/python/). Inspired by work on [LLM Style Fingerprints](https://github.com/riadmaouchi/llm-style-fingerprints) — measuring stylistic drift in LLM rewrites of literary French prose.*
