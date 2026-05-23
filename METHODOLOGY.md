# Methodology

## Overview

dev-fingerprint measures **code style evolution** across time. It does not directly detect LLM usage — it detects style patterns that are statistically overrepresented in LLM-generated code, then measures whether a developer's code has drifted toward those patterns.

---

## Signal Definitions

### 1. Comment Density Ratio
**Definition:** `comment_lines / total_code_lines` per commit's diff additions.

**Why it matters:** LLMs have a strong prior toward adding explanatory comments. This is reinforced by training on documentation-heavy code and by the fact that completions are often shown in context where a human is asking "explain what this does." Organic expert code (especially in C, kernel land, high-performance systems) often has comment rates below 5%.

**Thresholds:**
- Organic baseline (pre-2022 OSS): ~8% median
- LLM-assisted estimate: ~22% median
- Normalized to [0, 1] linearly

---

### 2. Docstring Coverage
**Definition:** `functions_with_docstring / total_functions` per commit.

**Detection:** Language-specific patterns:
- Python: `def foo():` followed by `"""` or `'''`
- JS/TS: JSDoc `/** ... */` before `function`/arrow
- Go: comment immediately before `func`
- Rust: `/// ...` before `pub fn`

**Why it matters:** LLMs almost always add docstrings when asked to write a function. Human developers, especially on fast-moving projects, often skip them. A sudden jump in docstring coverage is one of the strongest individual signals.

---

### 3. Identifier Verbosity
**Definition:** Average length of identifiers (variable names, function names) in added code lines.

**Regex:** `\b([a-zA-Z_][a-zA-Z0-9_]{2,})\b` — minimum 3 chars to filter out `i`, `x`, `fn`.

**Why it matters:** LLMs generate descriptive, self-documenting names (`user_authentication_token` vs `auth`). This correlates strongly with LLM usage and weakly with developer experience/language conventions.

**Thresholds:**
- Organic: ~7.5 chars
- LLM-assisted: ~11.0 chars

---

### 4. Error Handling Density
**Definition:** `error_handling_constructs / code_lines * 100`

**What counts:**
- Python: `try:`, `except`, `raise`
- JS/TS: `try {`, `catch(`, `throw`
- Go: `if err != nil`, `return ... err`
- Rust: `?` suffix, `.unwrap_or`, `match`

**Why it matters:** LLMs are trained on code review feedback that emphasizes error handling. They tend to over-engineer defensive code that humans would shortcut in practice.

---

### 5. Commit Message Structure
**Definition:** Composite of:
- `commit_message_length`: Length of first line (chars)
- `has_conventional_commit`: Boolean — matches `^(feat|fix|docs|...)(scope)?!?: ` (Conventional Commits spec)

**Weight:** 60% message length + 40% conventional format

**Why it matters:** LLMs generate commit messages in structured formats, especially after Copilot Chat and git-related prompts became common. Humans write shorter, more casual messages.

---

### 6. Function Style Score
**Definition:** Inverse of average function length in added code (shorter functions = more LLM-like).

**Note:** Currently not fully implemented (zero weight in v0.1). Added as extension point.

---

## Temporal Analysis

### Quarterly Bucketing
Metrics are aggregated into 3-month windows (Q1-Q4 per year). Within each quarter:
- All per-commit signal scores are averaged
- Commits with no code changes (merges, empty diffs) are excluded

### Change-Point Detection
We use the **PELT (Pruned Exact Linear Time)** algorithm from the `ruptures` library with an RBF (Radial Basis Function) cost model. Parameters:

```python
rpt.Pelt(model="rbf", min_size=3).fit(signal).predict(pen=10)
```

- `min_size=3`: requires at least 3 quarters in each segment (avoids noise spikes)
- `pen=10`: penalty for adding a breakpoint (tuned to avoid over-segmentation)
- Change points below Δ5 LLM score points are filtered as noise

### Milestone Correlation
Detected change points are matched to the nearest LLM milestone within ±180 days:

| Milestone | Date |
|-----------|------|
| GitHub Copilot Technical Preview | 2021-06-29 |
| GitHub Copilot GA | 2022-06-21 |
| ChatGPT Launch | 2022-11-30 |
| GPT-4 Release | 2023-03-14 |
| GitHub Copilot Chat GA | 2023-12-19 |
| Claude 3 Opus | 2024-03-04 |

---

## Score Calibration

Thresholds were manually calibrated against:
1. The pre-2022 commit history of Linus Torvalds and antirez (strong "organic" baselines)
2. GPT-4 generated code samples for equivalent tasks (strong "LLM" baselines)

The LLM Score is **not** a probability. It is an index on [0, 100] where:
- **0–40**: Style consistent with pre-LLM organic OSS patterns
- **40–70**: Style drift into ambiguous territory
- **70–100**: Strong alignment with known LLM-generated code patterns

---

## Limitations

1. **Language bias:** Signal calibration is strongest for Python and TypeScript. C and Ruby patterns are coarser.

2. **Repository bias:** Analyzing only a developer's public, owner repos misses contributions to others' repos and private work.

3. **Confounders:** Style changes can result from:
   - New collaborators / code review culture
   - Personal style evolution unrelated to LLMs
   - Project maturity (mature projects get more documentation)
   - Language version changes (e.g., Python type hints post-3.10)

4. **Commit granularity:** We analyze diffs, not full files. A developer may write LLM-assisted code but squash commits, reducing signal.

5. **Survivorship:** Famous developers with declining activity (TJ Holowaychuk) have fewer post-2022 data points, making drift estimates less reliable.

---

## Reproducibility

All analyses are cached to `~/.cache/dev-fingerprint/` (SQLite via diskcache). To re-run from scratch:

```bash
rm -rf ~/.cache/dev-fingerprint/
devfp analyze <login> --commits 500
```

Sample reports in `reports/sample/` were generated with commit SHA pinned at repo HEAD on 2024-01-15 for reproducibility.
