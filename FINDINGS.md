# Findings

> Real measurements from 2,608 commits across 9 developers (2018–2024).  
> Data collected via GitHub API, cached locally, profiles auditable in `reports/real/`.  
> Methodology: `run_analysis.py` — year-windowed sampling (60 commits/year × 2018–2024).

---

## TL;DR

Using our 6-signal LLM Influence Score on real commit history, **most developers show no detectable style drift** correlated with LLM adoption. The one clear exception is Rich Harris.

| Developer | Commits | Baseline | Post-LLM | Drift | Result |
|-----------|---------|----------|----------|-------|--------|
| Rich Harris | 420 | 5.7 | 10.6 | **+4.9** | Detectable drift |
| Ryan Dahl | 292 | 6.5 | 7.0 | +0.5 | Flat |
| Evan You | 420 | 4.3 | 4.2 | −0.1 | Flat |
| Dan Abramov | 282 | 6.1 | 5.0 | −1.1 | Flat |
| DHH | 102 | 7.3 | 5.1 | −2.2 | Flat |
| Sindre Sorhus | 319 | 3.7 | 1.3 | −2.4 | Flat |
| Guido van Rossum | 173 | 7.8 | 5.1 | −2.6 | Flat |
| Linus Torvalds | 420 | 11.5 | 10.7 | −0.7 | Flat (control) |
| antirez | 180 | 6.1 | — | — | Inactive post-2021 |

**Baseline** = mean LLM Score pre–Jun 2022.  
**Post-LLM** = mean LLM Score post–Jun 2022 (Copilot GA).

---

## Developer Profiles

### Linus Torvalds — torvalds/linux
**Drift: −0.7 · Negative control**

Flat trajectory across the full period. Scores hover around 10–12/100 — entirely consistent with low-comment, low-docstring C kernel code. No change points detected. Confirms the tool is not picking up spurious drift.

---

### Rich Harris — sveltejs/svelte, sveltejs/kit
**Drift: +4.9 · Detectable drift**

The only developer in our dataset showing a consistent positive shift. Baseline (pre-Copilot) average: 5.7. Post-LLM average: 10.6. The signal is driven mainly by comment density and docstring scores, which gradually increase from 2022 onwards. No single sharp change point was detected by PELT — the shift appears gradual rather than abrupt.

This is consistent with incremental adoption of AI tooling rather than a single moment of change.

---

### Ryan Dahl — denoland/deno, denoland/deno_std
**Drift: +0.5 · Flat**

292 commits across 2018–2024. Scores are stable in the 5–8 range throughout. The post-LLM period shows marginally higher averages (+0.5), but well within noise. The Deno codebase switching from JavaScript to TypeScript/Rust is a significant confound — language conventions differ enough that commit-level signals are unreliable for cross-language comparison.

---

### Evan You — vuejs/core, vitejs/vite
**Drift: −0.1 · Flat**

420 commits, 8 quarters. Essentially zero drift. Both baseline and post-LLM periods score around 4/100. Note: vuejs/core and vitejs/vite are very high-volume repos — our 60-commit/year sample may not capture the specific commits where AI assistance is most visible.

---

### Dan Abramov — facebook/react, reduxjs/redux, pmndrs/valtio
**Drift: −1.1 · Flat**

Strong temporal coverage (18 quarters), but a critical observation: post-2022, Dan's commit frequency dropped sharply (32 commits in 2022, 3 in 2023, 11 in 2024). The post-LLM signal is statistically weak due to low sample size per quarter. No conclusion can be drawn about LLM influence from these repos.

---

### Sindre Sorhus — sindresorhus/execa, got, p-queue
**Drift: −2.4 · Flat**

Sindre's scores are unusually low (baseline 3.7, post-LLM 1.3). This reflects his extremely terse, well-factored JavaScript style — minimal comments, short functions, no defensive error handling. The negative drift may reflect package maturity: smaller, more stable packages need less ongoing documentation churn. No LLM influence detected.

---

### Guido van Rossum — python/cpython
**Drift: −2.6 · Flat**

173 commits across 2018–2024. Good temporal coverage (20 quarters). Scores are consistently low (5–10/100). The small negative drift post-2022 may reflect Guido's shift toward more focused, narrowly-scoped cpython contributions rather than any style change.

---

### DHH — rails/rails
**Drift: −2.2 · Flat (sparse data 2018–2020)**

Only 102 commits, with near-zero activity in our repos for 2018–2020. Rails is a large multi-contributor repo where DHH's individual commits are less frequent. The data is insufficient for strong conclusions. Scores in the 5–8 range throughout.

---

### Salvatore Sanfilippo (antirez) — antirez/redis, kilo
**Not measurable — inactive post-2021**

180 commits, all from 2018–2020. antirez stepped back from Redis in 2020 and has not been active in our tracked repos since. No post-LLM data available.

---

## What the Results Tell Us

### 1. The tool's sensitivity is low for commit diffs

All scores fall in the 3–12/100 range. The `copilot_score()` metric was calibrated on complete code files. Commit diffs are partial views — a developer adding one LLM-assisted function to a hand-written file will produce a blended signal that's hard to distinguish from normal variation.

### 2. Only Rich Harris shows a clear signal

A +4.9 pt drift is modest but consistent across 14 quarters and both repos (Svelte + SvelteKit). It is the only developer where baseline and post-LLM distributions are clearly separated.

### 3. Null results are informative

The flat results for Evan You (+0.1), Ryan Dahl (+0.5), and Dan Abramov (−1.1) do not mean these developers don't use AI tools. They mean our metric, applied to commit diffs from these specific repos, does not detect a signal. High-volume repos with many contributors (vue/core, react) may dilute individual author signals.

### 4. The TypeScript hypothesis is not supported

We hypothesized that TypeScript developers (Rich Harris, Evan You, Ryan Dahl) would show the strongest drift due to Copilot's strong TypeScript support. Only Rich Harris shows drift. This suggests language alone is not a reliable predictor.

---

## Limitations

- **Commit diff vs. full file**: our metric is calibrated on complete files and loses sensitivity when applied to diffs.
- **Author filter**: GitHub's `?author=login` filter matches on the committer's GitHub account. Merge-heavy workflows (React, CPython) may attribute commits differently.
- **Sample size**: 60 commits/year is sufficient for quarterly aggregation but some quarters have n < 5, producing high-variance estimates.
- **No ground truth**: we have no verified dataset of "developer X used AI for commit Y." The +4.9 drift for Rich Harris is real but its cause is unconfirmed.
- **Single metric**: `copilot_score()` is one composite score. Disaggregating individual signals (docstrings, comments, identifier length separately) may reveal patterns the composite obscures.

Full methodology: [METHODOLOGY.md](METHODOLOGY.md)  
Raw profiles: [`reports/real/`](reports/real/)  
Data collection script: [`run_analysis.py`](run_analysis.py)
