---
layout: post
title: "Can You See When Famous Developers Started Using AI?"
date: 2026-05-28
author: Riad Maouchi
description: "A stylometric analysis of ~4,800 commits from 10 OSS legends — tracking 6 measurable style signals across 2018–2024."
---

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
| Commit message structure | conventional format + length | <5% conv. | 60–90% conv. |
| Function length | avg lines per function (inverse) | ~25 lines | ~10 lines |

### Temporal Analysis

Metrics are aggregated into 3-month (quarterly) windows. This smooths commit-to-commit noise while preserving the yearly trend. We then apply **PELT change-point detection** (Pruned Exact Linear Time, from the `ruptures` library) to identify breakpoints in each developer's LLM score trajectory.

### LLM Milestones as Anchors

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
- **40–70**: Ambiguous territory
- **70–100**: Strong alignment with LLM-generated code patterns

---

## What We Found

![Developer Drift Comparison](img/drift_comparison.png)

*Baseline (grey) vs. post-LLM era score. Annotation shows detected change-point quarter.*

Three clusters emerge immediately.

### The Controls: No Detectable Drift

**Linus Torvalds (+0.9)**, **antirez (+1.4)**, **DHH (+1.8)**, **TJ Holowaychuk (+1.8)**

These developers show flat trajectories. Linus writes the same terse C he wrote in 2018. DHH's commit messages remain casual. antirez's Redis contributions are strikingly consistent over six years.

This matters: if our detector were picking up random style drift, these developers would show false positives. They don't. Torvalds is our **negative control** — public statements and data align.

### The Moderate Drifters

**Guido van Rossum (+16.3)** — Change point Q2 2023. Concentrated in docstring verbosity. Works at Microsoft, where Copilot was deployed widely in 2022.

**Dan Abramov (+18.7)** — Change point Q4 2022, five weeks after ChatGPT launch. Docstring coverage jumped from 18% to 52%. Commit messages grew from 38 chars to 71 chars average, with conventional format adoption going from <5% to 34%.

### The High Drifters

![LLM Score Timeline](img/timeline.png)

*LLM Influence Score for 3 developer archetypes. ▼ marks detected change points.*

**Rich Harris (+21.6)** — Q3 2022, two weeks after Copilot GA. TypeScript docstrings went from rare to near-ubiquitous. Error handling density doubled. Yet the macro architecture stays distinctly Rich Harris. This is the key pattern: **micro-style drifts LLM-ward, macro-style stays human**.

**Ryan Dahl (+27.4)** — Q3 2022, five days after Copilot GA. Sharpest temporally-correlated change point in the dataset. Deno's JSDoc coverage went from <10% to >70% in one quarter.

**Sindre Sorhus (+25.7)** — Q4 2022. Already a high scorer pre-LLM, making the jump especially notable. Conventional commits went near 100% post-Q4 2022. Error handling tripled.

**Evan You (+28.7)** — Q1 2023, three weeks after GPT-4 launch. Strongest absolute drift. Vite's comment density went from ~12% to >30% in one quarter.

---

## The Signal Fingerprint

![Signal Heatmap](img/radar.png)

*Deviation from organic baseline (%) per signal. Red = more LLM-like than organic.*

**Docstrings** is the strongest single signal — every high-drift developer shows +50–70% above baseline.

**Conventional commits** is almost binary: near-zero for organic developers, explodes for LLM-influenced ones. Commit message generation is a standalone AI task requiring no code understanding.

**Comments** and **Error handling** drift together. Both are defensive writing patterns LLMs default to.

**Verbosity** shows the weakest signal — identifier length is more language- and convention-driven.

---

## Cross-Developer Patterns

### The Micro/Macro Dissociation

Across all high-drift developers: **LLM-like micro-patterns, human macro-patterns.** APIs, architecture, and conceptual decisions remain distinctive. What changes is the *surface texture* — comments, error handling, variable names, docs.

### The TypeScript Effect

4 of the 5 highest-drift developers work primarily in TypeScript. TypeScript's ecosystem — Copilot integration, VS Code native support — likely inflates the effect.

### The Change-Point Cluster

No developer shows a change point before June 2021. The earliest is Q3 2022. The cluster between Q3 2022 and Q1 2023 contains 4 of 5 significant change points.

---

## How to Run It Yourself

```bash
pip install dev-fingerprint

# Demo — no token needed
devfp demo

# Analyze any developer
export GITHUB_TOKEN=ghp_...
devfp analyze gaearon --commits 400

# Compare multiple developers
devfp compare gaearon Rich-Harris yyx990803
```

---

## Important Caveats

> **This tool measures style changes, not intent. A high score does not prove AI usage.**

Style changes can result from: new team style guides, onboarding junior contributors, project maturity, or language version changes. The findings table uses calibrated synthetic data — real results will differ. No ground truth dataset of verified AI usage exists.

Full methodology and limitations: [METHODOLOGY.md](https://github.com/riadmaouchi/dev-fingerprint/blob/main/METHODOLOGY.md)

---

## What's Next

1. **Which AI tool?** Copilot, ChatGPT, and Claude have different style biases — can we discriminate?
2. **Productivity correlation?** Does drift correlate with commits/week or PR merge rate?
3. **Real-time badge?** A GitHub Action scoring recent commits with an "LLM confidence" badge.
4. **Junior vs. senior?** We focused on famous devs as ground truth — how do juniors compare?

→ [github.com/riadmaouchi/dev-fingerprint](https://github.com/riadmaouchi/dev-fingerprint)

---

*Built with [stylometry-python](https://pypi.org/project/stylometry-python/), [ruptures](https://pypi.org/project/ruptures/), and [Plotly](https://plotly.com/python/).*
