# We Measured 2,608 Real Commits to See If Famous Developers Changed Style After ChatGPT. Here's What We Actually Found.

*A stylometric analysis of 9 OSS developers across 2018–2024 — year-windowed sampling, real GitHub API data, auditable profiles.*

---

The narrative goes like this: since Copilot launched in 2022, developers started writing more comments, longer variable names, conventional commits, docstrings everywhere. Style drifted toward what LLMs produce.

We decided to measure it instead of assuming it.

---

## The Setup

We built a tool that extracts 6 style signals from commit diffs and aggregates them into a quarterly **LLM Influence Score (0–100)**:

| Signal | What we measure |
|--------|----------------|
| Comment density | comment lines / total lines |
| Docstring coverage | functions with docs / total functions |
| Identifier verbosity | avg identifier length |
| Error handling density | try/catch constructs per 100 lines |
| Commit message structure | conventional format + length |
| Function length | avg lines per function (inverse) |

We then applied **PELT change-point detection** to each developer's quarterly timeline and checked for breakpoints correlated with LLM milestones (Copilot Preview, Copilot GA, ChatGPT, GPT-4).

**The data is real.** 2,608 commits from 9 developers, year-windowed sampling (60 commits/year, 2018–2024) to ensure uniform temporal coverage. Every profile is a JSON file in the repo at `reports/real/`. You can reproduce or audit the collection with `python run_analysis.py`.

---

## What We Found

![Developer Drift Comparison](docs/img/drift_comparison.png)

*Baseline (grey) vs. post-Copilot-GA era score per developer, sorted by drift.*

The headline result: **most developers show no detectable drift.**

| Developer | Commits | Baseline | Post-LLM | Drift |
|-----------|---------|----------|----------|-------|
| Rich Harris | 420 | 5.7 | 10.6 | **+4.9** |
| Ryan Dahl | 292 | 6.5 | 7.0 | +0.5 |
| Evan You | 420 | 4.3 | 4.2 | −0.1 |
| Dan Abramov | 282 | 6.1 | 5.0 | −1.1 |
| Sindre Sorhus | 319 | 3.7 | 1.3 | −2.4 |
| Guido van Rossum | 173 | 7.8 | 5.1 | −2.6 |
| DHH | 102 | 7.3 | 5.1 | −2.2 |
| Linus Torvalds | 420 | 11.5 | 10.7 | −0.7 |
| antirez | 180 | 6.1 | — | inactive post-2021 |

---

## The Timeline

![LLM Score Timeline](docs/img/timeline.png)

*Quarterly LLM Influence Score per developer. Dashed lines = LLM release milestones.*

A few things stand out immediately.

**Torvalds is flat** across 7 years. His C kernel code scores 10–12/100 throughout. No change points, no trend. This is our negative control working exactly as expected.

**Rich Harris is the exception.** His score climbs gradually from ~5 to ~10 between 2022 and 2024 — a +4.9 drift that is consistent across both of his repos (Svelte and SvelteKit). Notably, PELT did not detect a single sharp change point — the shift is gradual, suggesting incremental adoption rather than a sudden tool switch.

**Everyone else is flat or slightly declining.** Evan You, Ryan Dahl, Dan Abramov — the developers we might have expected to show the strongest signal based on their public statements — show essentially nothing in the data.

---

## The Signal Fingerprint

![Signal Heatmap](docs/img/radar.png)

*Per-signal deviation from organic baseline (Torvalds + DHH + antirez). Red = more LLM-like.*

Looking at individual signals, the pattern is muted for most developers. The signals that move are comments and docstrings — predictably the easiest for AI tools to add. Commit style (conventional commits) stays low across the board, which is surprising given how frequently people attribute structured commit messages to AI tooling.

---

## Why the Results Are Modest — And Why That's Interesting

The synthetic numbers that circulate in blog posts about "AI drift in famous developers" — +18 for Abramov, +28 for Evan You — are not what we observe. The gap between those claims and our measurements tells us something important.

**Commit diffs are partial views.** Our metric was designed for complete code files. A developer who asks AI to draft one function in a 200-line PR will have that signal diluted across the entire diff. The metric loses sensitivity.

**High-volume repos blur individual style.** React, cpython, vuejs/core — these have many contributors. Even with the `?author=login` GitHub filter, the diffs may include review-driven changes that don't reflect the developer's native style.

**Low commit frequency post-2022 = unreliable estimates.** Dan Abramov made 3 commits in 2023 and 11 in 2024 across our tracked repos. That's not enough data per quarter for stable estimates.

**The absence of signal is also a finding.** If Evan You and Ryan Dahl — both working primarily in TypeScript with strong Copilot support — show no drift in our metric, that either means they don't use AI tools in ways that change these 6 signals, or the tools have become invisible in their workflow.

---

## What We Can Claim

**One developer (Rich Harris) shows a real, consistent +4.9 pt drift post-2022.** It's modest but reproducible: it appears in both sveltejs/svelte and sveltejs/kit, it's gradual rather than noisy, and it's the strongest positive signal in the dataset.

**Linus Torvalds is a clean negative control.** The tool correctly identifies no change in his style over 7 years, which validates the methodology at the edges.

**The tool works, but its sensitivity at the commit-diff level is limited.** Future work should apply the metric to full file snapshots rather than diffs — that's where the signal is stronger and the calibration holds.

---

## Reproduce It

```bash
git clone https://github.com/riadmaouchi/dev-fingerprint
cd dev-fingerprint
pip install -e ".[dev]"

# Profiles already collected — regenerate figures:
python generate_figures.py

# Or re-collect from GitHub API:
export GITHUB_TOKEN=ghp_...
python run_analysis.py          # all 10 developers
python run_analysis.py --logins Rich-Harris,torvalds  # specific developers
python run_analysis.py --force  # ignore cached profiles and re-fetch
```

The raw profiles are in [`reports/real/`](reports/real/). Each JSON file is a complete auditable record: every quarterly score, every signal value, every detected change point, commit count and date range.

---

## What's Next

1. **Full-file metric** — apply the score to file snapshots at 6-month intervals rather than commit diffs. Should give 3–5× stronger signal.
2. **Per-signal analysis** — rather than one composite score, track each signal separately. The composite may be averaging out real movement.
3. **More developers** — 9 is a small sample. The tool is designed to scale; adding 50 developers with `configs/developers.yaml` is straightforward.
4. **Language-stratified comparison** — comparing C developers to TypeScript developers on the same scale is misleading. A language-adjusted baseline would be more rigorous.

→ [github.com/riadmaouchi/dev-fingerprint](https://github.com/riadmaouchi/dev-fingerprint)

---

*2,608 commits · 9 developers · 2018–2024 · year-windowed sampling · real GitHub API data*  
*Tool: [stylometry-python](https://pypi.org/project/stylometry-python/) + [ruptures](https://pypi.org/project/ruptures/) + [Plotly](https://plotly.com/python/)*
