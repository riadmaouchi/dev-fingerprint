# Findings

> Real measurements from 3,009 commits across 9 developers (2018–2025).  
> Year-windowed sampling: 60 commits × 8 years per developer.  
> DHH: client-side name filtering recovers pre-2021 history (old email not linked to GitHub account).  
> Profiles auditable in `reports/real/`. Reproduce with `python run_analysis.py`.

---

## Summary Table

| Developer | Commits | Pre-2022 Q | Post-2022 Q | Baseline | Post-LLM | Drift | Signal |
|-----------|---------|-----------|------------|----------|----------|-------|--------|
| Rich Harris | 480 | 11 | 4 | 5.7 | **12.5** | **+6.8** | Clear drift |
| antirez | 240 | 3 | 1 | 6.1 | **14.0** | **+7.9** | Returned 2025, confounded |
| Ryan Dahl | 300 | 10 | 12 | 6.5 | 7.4 | +0.8 | Flat |
| Evan You | 421 | 4 | 5 | 4.3 | 4.0 | −0.3 | Flat |
| Dan Abramov | 285 | 13 | 8 | 6.1 | 5.2 | −0.8 | Flat (sparse post-2022) |
| Sindre Sorhus | 379 | 18 | 13 | 3.7 | 1.6 | −2.1 | Flat |
| DHH | 249 | 10 | 11 | 8.7 | 4.6 | −4.2 | Negative drift |
| Guido van Rossum | 175 | 13 | 9 | 7.8 | 4.0 | −3.8 | Flat |
| Linus Torvalds | 480 | 4 | 4 | 11.5 | 10.5 | −1.0 | Flat (control) |
| TJ Holowaychuk | — | — | — | — | — | — | No attributable commits |

**Baseline** = mean LLM Score (quarterly) pre–Jun 2022.  
**Post-LLM** = mean LLM Score post–Jun 2022 (Copilot GA).

---

## Interpretation

### Rich Harris — clear positive drift (+6.8)

The strongest and most reliable finding. 480 commits across 8 years, 11 pre-LLM quarters and 4 post-LLM quarters. Both repos (sveltejs/svelte and sveltejs/kit) show the same gradual upward trend from ~5 to ~12 between 2022 and 2025. No single sharp change point — the shift is gradual, consistent with incremental AI tooling adoption.

This is the only developer where the pre/post LLM distributions are clearly separated with sufficient data in both periods.

### antirez — apparent drift (+7.9), but confounded

antirez was completely inactive on his tracked repos from 2021 to 2024, then returned in 2025 with 60 commits. His 2025 code scores at 14.0 vs a 6.1 pre-2021 baseline — a gap of +7.9. However, this comparison spans a 3-year hiatus, during which his entire coding context may have changed (different projects, different contributors, different norms). The temporal gap makes causal attribution to LLM tools unreliable. Reported for transparency, not as a finding.

### Linus Torvalds — flat (−1.0, negative control)

480 commits, perfect coverage. Scores hover around 10–11/100 throughout 2018–2025. Zero change points. The tool correctly detects no drift in a developer who has publicly stated he does not use AI tools. This validates the methodology at the baseline.

### Evan You — flat (−0.3)

421 commits, strong coverage. vuejs/core and vitejs/vite are high-volume repos. No drift despite being one of the most active TypeScript developers in the ecosystem. The "TypeScript Effect" hypothesis — that TypeScript developers show stronger drift due to Copilot support — is not confirmed here.

### Ryan Dahl — flat (+0.8)

300 commits, 22 quarters. Deno activity dropped sharply post-2022 (from 60/year to 8–12/year), suggesting Deno became more team-driven. The small positive drift (+0.8) is within noise given the sparse post-2022 quarters.

### Dan Abramov — flat (−0.8)

285 commits but critically sparse post-2022: 3 commits in 2023, 11 in 2024, 3 in 2025. PELT detected a change point at 2023-04 (Δ8.1) — but this quarter has only 3 commits, making it statistically unreliable. Insufficient data for any conclusion.

### Sindre Sorhus — flat (−2.1)

379 commits, 31 quarters — the best temporal coverage in the dataset. Score consistently around 3–4/100 throughout. Small negative drift reflects package maturity (less churn, more stable APIs). No LLM influence detected.

### Guido van Rossum — flat (−3.8)

175 commits across cpython. Very sparse 2018–2021 (1–15 commits/year). The negative drift reflects Guido's shift toward narrower, more focused contributions to CPython. No detectable LLM influence.

### DHH — negative drift (−4.2)

249 commits across 21 quarters. The GitHub `?author=dhh` filter only returns commits where the git email is linked to the account — it missed DHH's pre-2021 history, which used `david@loudthinking.com`. Client-side name filtering on `commit.author.name` ("David Heinemeier Hansson") recovered 86 additional commits across 2018–2020.

With the corrected baseline of 8.7 (vs post-LLM 4.6), DHH shows a clear negative drift of −4.2. This is consistent with his public position — he has repeatedly criticised AI-assisted development and published pieces against "AI slop" in codebases. The data aligns with his stated practice.

### TJ Holowaychuk — no attributable commits

Both `tj/commander.js` and `tj/git-extras` returned zero commits attributed to the `tj` login via the GitHub API filter. TJ's commit history may use a different email or login. Excluded from analysis.

---

## What the Data Tells Us

**1. The effect, if present, is smaller than commonly claimed.**  
Frequently cited blog posts attribute +20 to +30 point drifts to developers like Evan You and Ryan Dahl. Our real measurements show +0.8 and −0.3 respectively. The gap between claimed and measured is large.

**2. Only Rich Harris shows a clear, reproducible signal (+6.8).**  
Consistent across two repos, gradual over 4 years, supported by 480 commits. This is the most defensible finding in the dataset.

**3. Low post-2022 commit frequency is a major confound.**  
Several developers (Dan Abramov, Ryan Dahl) shifted to lower personal commit frequency after 2022 — possibly because more code goes through AI tools and is committed by others, or because team workflows changed. This makes their post-LLM estimates unreliable.

**4. The metric has limited sensitivity on commit diffs.**  
All scores fall in 3–12/100. The `copilot_score()` function is calibrated on complete code files; commit diffs are partial views. A developer adding one AI-assisted function to a 200-line PR will have that signal diluted. Individual signals (docstrings, comments) may be more sensitive than the composite — see `docs/img/signals.png`.

---

## Known Limitations

| Limitation | Impact |
|-----------|--------|
| Author filter via GitHub login | Misses commits with unlinked email — mitigated by client-side name filtering for DHH; TJ still unreachable |
| 60 commits/year cap | Sparse devs get good coverage; active devs get sampled |
| Diff-level metric | Lower sensitivity than full-file analysis — all scores fall in 3–12/100 range |
| No ground truth | Cannot confirm AI usage, only measure style signals |
| Single composite score | May average out real per-signal movement |

Full methodology: [METHODOLOGY.md](METHODOLOGY.md)  
Raw profiles: [`reports/real/`](reports/real/)  
Collection script: [`run_analysis.py`](run_analysis.py)  
Figure script: [`generate_figures.py`](generate_figures.py)
