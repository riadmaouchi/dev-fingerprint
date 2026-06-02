# Findings

> **Measurement protocol:** 5,426 commits total · 120 commits/year × 8 years (2018–2025) = up to 960 commits per developer,  
> aggregated into quarterly windows (BehaviorWindow). Mann-Whitney U per Level-A signal,  
> combined via Fisher's method. Minimum 10 windows required for a statistical verdict.  
> All raw profiles auditable in `reports/real/`. Reproduce: `GITHUB_TOKEN=... python run_analysis.py`.

---

## Summary Table

| Developer | Commits | Windows | Fisher p | Sig. | CPs-A | AI declared | LLM instr files | Process verdict |
|-----------|--------:|--------:|---------:|:----:|------:|:-----------:|:---------------:|-----------------|
| Dan Abramov | 465 | 22 | **0.0002** | ★★★ | 17 | — | none | Strong drift (role exit) |
| Guido van Rossum | 230 | 24 | **0.0022** | ★★★ | 4 | — | none | Strong drift (BDFL exit) |
| Sindre Sorhus | 521 | 32 | **0.0022** | ★★★ | 13 | — | none | Strong drift (portfolio shift) |
| DHH | 429 | 23 | **0.0301** | ★ | 1 | ❌ no AI | AGENTS.md (6.8 KB) | Moderate drift (role evolution) |
| Evan You | 841 | 12 | **0.0457** | ★ | 3 | — | copilot-instr (1.6 KB) | Moderate drift (fragile baseline) |
| Andrej Karpathy | 284 | 10 | **0.0495** | ★ | 5 | ✅ "vibe coding" | none | Marginal (thin baseline) |
| Ryan Dahl | 540 | 24 | 0.0775 | ~ | 17 | — | copilot-instr (12 KB) + CLAUDE.md (11.9 KB) | Trend (non-sig.) |
| Rich Harris | 960 | 20 | 0.2483 | — | 3 | — | CLAUDE.md + AGENTS.md + copilot-instr (4.3 KB each) | No significant drift |
| **Simon Willison** | **960** | **19** | **0.7473** | **—** | **1** | **✅ heavy user** | none (llm: 425B setup only) | **Null — strongest negative control** |
| Linus Torvalds | 960 | 8 | n/a | — | 1 | ❌ skeptic | none | Insufficient windows |
| Salvatore Sanfilippo | 480 | 6 | n/a | — | 11 | — | none | Insufficient windows (4-yr gap) |
| TJ Holowaychuk | — | — | — | — | — | — | — | No attributable commits |

`★★★ p < 0.01   ★ p < 0.05   ~ p < 0.10   — not significant / insufficient data`  
`✅ publicly declared AI usage  ❌ publicly declared non-usage  — no declaration found`

**Level-A signals** (6 total): `median_files_per_commit`, `large_commit_ratio`, `cross_module_ratio`,  
`refactor_ratio`, `median_inter_commit_hours`, `commits_per_week`.

---

## Per-Developer Analysis

### Dan Abramov (`gaearon`) — Strong process drift, p = 0.0002 ★★★

**465 commits · 22 quarterly windows · 2018-08 → 2025-12**

4 of 6 Level-A signals show statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `commits_per_week` | 1.976 | 0.098 | −95.1% | 0.0090 ★ |
| `median_inter_commit_hours` | 321 h | 3,389 h | +956% | 0.0043 ★ |
| `cross_module_ratio` | 0.049 | 0.000 | −100% | 0.0164 ★ |
| `refactor_ratio` | 0.091 | 0.000 | −100% | 0.0356 ★ |
| `median_files_per_commit` | 2.53 | 1.75 | −30.8% | 0.3276 |
| `large_commit_ratio` | 0.135 | 0.375 | +178% | 0.8305 |

**Combined Fisher p = 0.0002.** This is the strongest statistical signal in the corpus.

**Key change points:**
- `2021-07` — `commits_per_week` (Δ 2.65, PELT) — nearest: Copilot Technical Preview
- `2021-07` — `refactor_ratio` (Δ 0.107, PELT)
- `2022-07` — `median_inter_commit_hours` (Δ 2,391 h, CUSUM) — nearest: Copilot GA
- `2023-01` — `commits_per_week` (Δ 2.12, CUSUM) — nearest: ChatGPT Launch
- (+12 additional change points across 2021–2025)

**Interpretation:** The signal is unambiguous — Abramov's personal OSS activity collapsed progressively from 2021 onward. Commits per week fell from 5.69 in 2018-Q3 to 0.08 in 2025-Q4. This trajectory predates Copilot GA and aligns precisely with his gradual departure from the React core team and Meta (officially announced 2023). Cross-module and refactor ratios reaching exactly zero in the recent window reflects near-complete disengagement. **Attributing this to AI assistance would be wrong; role exit is the dominant explanation.**

---

### Guido van Rossum (`gvanrossum`) — Strong process drift, p = 0.0022 ★★★

**230 commits · 24 quarterly windows · 2018-01 → 2025-11**

2 of 6 Level-A signals show statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `median_files_per_commit` | 3.875 | 1.500 | −61.3% | 0.0276 ★ |
| `cross_module_ratio` | 0.418 | 0.093 | −77.8% | 0.0296 ★ |
| `large_commit_ratio` | 0.168 | 0.000 | −100% | 0.0695 |
| `median_inter_commit_hours` | 727 h | 3,261 h | +349% | 0.0811 |
| `commits_per_week` | 0.825 | 0.333 | −59.7% | 0.1555 |
| `refactor_ratio` | 0.123 | 0.018 | −85.6% | 0.2994 |

**Combined Fisher p = 0.0022.** Fisher amplifies the joint signal of two individually marginal tests.

**Key change points:**
- `2022-10` — `commits_per_week` (CUSUM) — nearest: ChatGPT Launch
- `2023-01` — `commits_per_week` (CUSUM) — nearest: ChatGPT Launch
- `2023-07` — `commits_per_week` (CUSUM) — nearest: GPT-4 Release
- `2024-01` — `commits_per_week` (CUSUM) — nearest: Copilot Chat GA

**Interpretation:** Guido's contributions to CPython have become **narrower and more focused**: fewer files touched per commit (−61%), much less cross-module reach (−78%), and commits now separated by months rather than weeks. This is consistent with the BDFL-Emeritus role evolution — he stepped down as BDFL in 2018, joined Microsoft in 2020, and increasingly concentrates on typing, PEPs, and targeted CPython improvements rather than broad maintenance. The change-point cluster around late 2022/2023 may reflect increased delegation within the CPython team as LLM-assisted contributions from other committers rose. **No ground truth confirms personal AI adoption.**

---

### Sindre Sorhus (`sindresorhus`) — Strong process drift, p = 0.0022 ★★★

**521 commits · 32 quarterly windows · 2018-01 → 2025-12**

1 of 6 Level-A signals shows statistically significant change; the corpus of 32 windows (longest coverage) amplifies Fisher's combination:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `large_commit_ratio` | 0.000 | 0.045 | +∞ | **0.0002** ★ |
| `refactor_ratio` | 0.138 | 0.036 | −73.6% | 0.0797 |
| `cross_module_ratio` | 0.120 | 0.301 | +151% | 0.1164 |
| `median_files_per_commit` | 1.161 | 1.500 | +29.2% | 0.1443 |
| `median_inter_commit_hours` | 152 h | 364 h | +139% | 0.8047 |
| `commits_per_week` | 1.110 | 2.312 | +108% | 1.0000 |

**Combined Fisher p = 0.0022.** The dominant signal is `large_commit_ratio`: Sindre's historical baseline was 0.000 (no commit exceeded 200 net lines); his recent window shows 4.5% of commits above that threshold.

**Key change points (selected):**
- `2021-10` — `commits_per_week` (PELT) — nearest: Copilot Technical Preview
- `2022-04` — `median_inter_commit_hours` (CUSUM)
- `2024-04` — `cross_module_ratio` (CUSUM) — nearest: Claude 3 Opus
- `2025-07` — `large_commit_ratio` (CUSUM) — recent period
- (+8 additional change points)

**Interpretation:** Sindre's evolution reflects a **project portfolio shift** more than a personal coding style change. Early Sindre (2018–2021) maintained hundreds of micro-packages — each commit was tiny and single-file. Recent Sindre (2024–2025) maintains fewer but larger projects (`execa`, `got`, `p-queue` v8+), where structural changes naturally span more files and exceed the 200-line threshold. The cross-module ratio increase (+151%) is consistent with this consolidation. The 32-window coverage gives the highest statistical power in the corpus. **The structural evolution of his package portfolio is the primary confound.**

---

### David Heinemeier Hansson / DHH (`dhh`) — Moderate drift, p = 0.0301 ★

**429 commits · 23 quarterly windows · 2018-09 → 2025-12**  
*Note: pre-2021 history recovered via client-side name filter on `david@loudthinking.com` — the `?author=dhh` GitHub API filter misses commits with this unlinked email.*

1 of 6 Level-A signals shows statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `median_inter_commit_hours` | 231 h | 957 h | +314% | **0.0315** ★ |
| `commits_per_week` | 1.683 | 0.290 | −82.8% | 0.0563 |
| `median_files_per_commit` | 4.684 | 3.875 | −17.3% | 0.1865 |
| `cross_module_ratio` | 0.094 | 0.027 | −71.0% | 0.1785 |
| `refactor_ratio` | 0.100 | 0.028 | −72.3% | 0.2041 |
| `large_commit_ratio` | 0.038 | 0.083 | +120.6% | 0.9620 |

**Combined Fisher p = 0.0301.** The signal is borderline, driven by a single significant predictor.

**Key change point:**
- `2023-07` — `cross_module_ratio` (CUSUM, Δ 0.035) — nearest: GPT-4 Release (2023-03)

**Interpretation:** DHH's commit frequency has declined sharply over the study period (−83% commits/week), and the time between commits has quadrupled (231 h → 957 h). This is consistent with his transition from active Rails committer to engineering leader and product owner at 37signals (Basecamp, Hey, Kamal). His public anti-AI stance is well-documented; it is the *only* declared position in this corpus regarding AI tool abstention, and the data shows reduced personal coding output — not an AI-like style change. **The moderate drift is explained by role evolution, not AI adoption.** The `large_commit_ratio` increase (+121%) with widened commit intervals is consistent with batch-working rather than daily contributions.

---

### Evan You (`yyx990803`) — Moderate drift, p = 0.0457 ★

**841 commits · 12 quarterly windows · 2018-10 → 2025-01**  
*Note: only 12 windows because 2025 data is sparse (1 commit fetched). Statistical power is lower than other profiles.*

1 of 6 Level-A signals shows statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `refactor_ratio` | 0.168 | 0.047 | −72.2% | **0.0084** ★ |
| `median_inter_commit_hours` | 1.0 h | 325 h | +31,637% | 0.2004 |
| `cross_module_ratio` | 0.084 | 0.042 | −50.0% | 0.2688 |
| `large_commit_ratio` | 0.028 | 0.015 | −45.8% | 0.4884 |
| `commits_per_week` | 5.774 | 4.635 | −19.7% | 0.4892 |
| `median_files_per_commit` | 2.000 | 1.875 | −6.2% | 0.2159 |

**Combined Fisher p = 0.0457.** Driven by a single strongly significant predictor; Fisher amplification inflates the combined score.

**Key change points:**
- `2024-10` — `median_inter_commit_hours` (CUSUM)
- `2024-10` — `refactor_ratio` (CUSUM)
- `2025-01` — `median_inter_commit_hours` (CUSUM)

**Interpretation:** The dominant signal is a **reduction in refactoring behavior** (−72%), concentrated in the most recent quarters. With 12 windows and only 4 in the "recent" category, the baseline covers only 8 quarters (2018–2020) — too short for a reliable historical baseline. The `median_inter_commit_hours` explosion in 2025 (1 commit fetched for the year) is a data sparsity artifact, not a real behavioral signal. **Verdict: insufficient temporal coverage to draw a reliable conclusion. Moderate caution warranted.**

---

### Ryan Dahl (`ry`) — Trend (non-significant), p = 0.0775

**540 commits · 24 quarterly windows · 2018-10 → 2025-10**

1 of 6 Level-A signals shows nominal significance:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `cross_module_ratio` | 0.271 | 0.127 | −53.4% | **0.0398** ★ |
| `median_inter_commit_hours` | 588 h | 1,195 h | +103% | 0.2101 |
| `large_commit_ratio` | 0.049 | 0.100 | +103% | 0.5964 |
| `median_files_per_commit` | 3.725 | 2.125 | −43.0% | 0.1084 |
| `refactor_ratio` | 0.140 | 0.100 | −28.4% | 0.7784 |
| `commits_per_week` | 2.038 | 0.253 | −87.6% | 0.1398 |

**Combined Fisher p = 0.0775.** Individually, only cross-module reaches significance; Fisher does not combine to a significant threshold.

**Key change points (17 total — highest in corpus):**
- `2022-01` — `commits_per_week` (PELT, Δ 3.37) — nearest: Copilot GA (2022-06)
- `2022-07` — `median_inter_commit_hours` (CUSUM, Δ 1,311 h) — nearest: Copilot GA
- `2022-10` — `median_inter_commit_hours` — nearest: ChatGPT Launch
- `2023-04` — `median_inter_commit_hours` — nearest: GPT-4 Release
- (+12 additional)

**Interpretation:** Ryan Dahl's 17 Level-A change points (tied highest with Abramov) reflect **Deno's structural maturation** as a project. The PELT breakpoint at 2022-Q1 precedes Copilot GA. Commits per week collapsed from 2.038 to 0.253 (−88%) as Deno transitioned to team-driven development — Dahl's personal commit share decreased while the project grew. Cross-module ratio fell (−53%) because his remaining commits became more focused on architecture and runtime internals. **The non-significant combined p (0.0775) is the honest verdict: a trend that doesn't clear the bar with the current data.**

---

### Rich Harris (`Rich-Harris`) — No significant drift, p = 0.2483 ★

**960 commits · 20 quarterly windows · 2018-12 → 2025-12**

No Level-A signal shows statistically significant change at α = 0.05:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `refactor_ratio` | 0.067 | 0.166 | +148.8% | 0.0379 ★ |
| `cross_module_ratio` | 0.160 | 0.215 | +34.3% | 0.3686 |
| `commits_per_week` | 3.445 | 4.577 | +32.9% | 0.3692 |
| `median_files_per_commit` | 2.562 | 3.750 | +46.3% | 0.1141 |
| `large_commit_ratio` | 0.048 | 0.049 | +2.0% | 1.0000 |
| `median_inter_commit_hours` | 337 h | 10.7 h | −96.8% | 1.0000 |

**Combined Fisher p = 0.2483.** One nominally significant predictor (`refactor_ratio`, p = 0.0379) does not survive Fisher combination with 5 non-significant signals.

**Key change points:**
- `2020-10` — `cross_module_ratio` (PELT, Δ 0.155) — SvelteKit development began
- `2023-04` — `cross_module_ratio` (CUSUM, Δ 0.079) — nearest: GPT-4 Release
- `2023-10` — `median_files_per_commit` (CUSUM, Δ 1.33) — nearest: Copilot Chat GA

**Interpretation:** Rich Harris is the **strongest negative control in the corpus** for process-level drift. 960 commits over 20 windows — the highest commit-density profile — show no statistically significant departure from his own baseline in 5 of 6 Level-A signals. Refactor ratio increased (+149%) nominally, consistent with Svelte v5's major architectural rewrite (Runes, signals-based reactivity). Commits per week are *higher* in the recent period (+33%), the opposite direction of AI-assisted productivity collapse seen in Abramov.

**Critical methodological note:** The v1 finding attributed Rich Harris a style drift of +6.8 (Level-C score). That finding is **not reproduced at the process level** and is not supported by this analysis. The Level-C score was driven by Svelte's evolving JSDoc coverage and TypeScript type annotations — engineering quality improvements unrelated to AI tooling. Level-C signals are not primary evidence.

---

### Linus Torvalds (`torvalds`) — Insufficient windows (n = 8)

**960 commits · 8 quarterly windows · 2018-12 → 2025-12**

The Mann-Whitney test requires a minimum of 10 quarterly windows. Torvalds has only 8 because his commits are structurally concentrated in Q4 of each year — the Linux merge window. The quarterly aggregation collapses 120 sampled commits into 8 windows, all dated `YYYY-10`. With only 6 potential baseline windows and 2 recent windows, the test cannot run.

**1 Level-A change point:**
- `2025-10` — `cross_module_ratio` (CUSUM, Δ 0.078) — this is the most recent window only

**Observable trajectory (not tested):**  
- `median_files_per_commit`: 17.0 (2018-Q4) → 5.0 (2025-Q4)  
- `large_commit_ratio`: 0.433 → 0.158  
- `cross_module_ratio`: 0.092 → 0.188  
- `refactor_ratio`: 0.292 → 0.150  

The reduction in files/commit and large-commit ratio over 7 years is consistent with the Linux project's increasing specialization and Torvalds' focus on merge arbitration rather than code authorship. **Statistical testing is not possible with current sampling. A different sampling strategy (monthly windows, or extending back to 2010) would be needed.**

---

### Simon Willison (`simonw`) — Null result, p = 0.7473 — primary negative control

**960 commits · 19 quarterly windows · 2018-04 → 2025-10**  
*Publicly declared heavy Claude Code user since 2023. Built the `llm` CLI. Documented at simonwillison.net/tags/claude-code/.*

No Level-A signal shows statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `median_inter_commit_hours` | 1,014 h | 3,750 h | +270% | 0.0836 |
| `commits_per_week` | 1.010 | 0.577 | −42.9% | 0.1053 |
| `median_files_per_commit` | 2.250 | 1.625 | −27.8% | 0.1613 |
| `large_commit_ratio` | 0.000 | 0.021 | +∞ | 0.2697 |
| `cross_module_ratio` | 0.064 | 0.079 | +22.8% | 0.6561 |
| `refactor_ratio` | 0.014 | 0.021 | +47.3% | 0.8175 |

**Combined Fisher p = 0.7473.** The most statistically stable developer in the corpus, despite being the most documented AI adopter.

**Level B patch signal:**  
`patch_comment_density`: baseline 0.0169 → recent 0.0390, **p = 0.0485** (Mann-Whitney U, increase).  
`patch_blank_line_ratio`: baseline 0.0284 → recent 0.0253, p = 0.664 (stable).

**The only signal to reach significance for simonw is at Level B** — the density of comment lines within the code he actually adds to commits increased significantly in recent quarters. This is directionally consistent with AI assistance (AI tools tend to add inline comments). However, this signal alone cannot distinguish AI adoption from a conscious style change, and it did not survive Fisher combination with the flat Level-A signals.

**Interpretation:** Simon Willison is the central negative result of this study. 960 commits, 19 windows, documented heavy AI use — zero detectable Level-A drift. The Level B patch signal provides a whisper of signal (comment density, p = 0.048) but the overall behavioral fingerprint is unchanged. Two explanations are consistent with this: (1) AI adapts to his established coding style and produces output indistinguishable from his manual commits; (2) his primary development workflow changed in ways that aren't captured by commit-level process signals. His analyzed repos (datasette, llm, sqlite-utils) have no LLM style-instruction files of substance, ruling out instruction-driven style normalization as the explanation here.

---

### Andrej Karpathy (`karpathy`) — Marginal result, p = 0.0495 ★ (interpret with caution)

**284 commits · 10 quarterly windows · 2022-04 → 2025-10**  
*Coined "vibe coding" (X, February 2025). Minimal public GitHub activity before 2022 — most prior work in private repos at OpenAI and Tesla.*

1 of 6 Level-A signals shows statistically significant change:

| Signal | Baseline | Recent | Δ% | p-value |
|--------|----------:|-------:|---:|--------:|
| `refactor_ratio` | 0.270 | 0.041 | −84.8% | **0.0003** ★ |
| `median_inter_commit_hours` | 52 h | 1,714 h | +3,197% | 0.1042 |
| `median_files_per_commit` | 2.875 | 1.625 | −43.5% | 0.1085 |
| `large_commit_ratio` | 0.059 | 0.025 | −57.9% | 0.6083 |
| `cross_module_ratio` | 0.077 | 0.054 | −30.0% | 0.4701 |
| `commits_per_week` | 0.520 | 0.577 | +11.1% | 0.8461 |

**Combined Fisher p = 0.0495.** Driven by a single strongly significant predictor (`refactor_ratio`); Fisher amplification inflates the combined p past the threshold.

**Level B patch signals:**  
`patch_comment_density`: baseline 0.0758 → recent 0.0109, **p = 0.023** (decrease).  
`patch_blank_line_ratio`: baseline 0.0482 → recent 0.0103, **p = 0.023** (decrease).

The patch signals for karpathy move in the *opposite* direction from what AI assistance would predict — comment density and blank-line ratio are **lower** in his recent commits. This is consistent with a shift from research code (nanoGPT, micrograd — heavily commented for pedagogical clarity) to production/systems code (llm.c — C code, terse by convention). **The direction of drift contradicts the AI-assistance hypothesis.**

**Interpretation:** Karpathy's result is technically significant but methodologically fragile. Only 10 windows (the bare minimum), a sparse baseline (most pre-2022 work in private repos), and a single driving signal (refactor ratio). His repos have no LLM instruction files. The patch signals decrease rather than increase — the opposite of what AI adoption would predict. The most likely explanation is a genre shift: from high-commentary ML education repos to lower-commentary C/systems work. **Treat as marginal; the evidence does not clearly point to AI adoption as the cause.**

---

### Salvatore Sanfilippo / antirez (`antirez`) — Insufficient windows (n = 6, structural gap)

**480 commits · 6 quarterly windows · 2018-10 → 2025-08**

antirez was active 2018–2020 (3 windows), then completely absent from his tracked repositories (antirez/redis, antirez/kilo) from 2021 through 2024, then returned in 2025 (3 windows). The structural gap of ~4 years means the "recent" and "historical" populations are separated by a long absence, not a gradual trend. Fisher's method cannot be applied (requires ≥ 10 windows; only 6 available).

**11 Level-A change points** — all concentrated in the 2025 return period, reflecting the dramatic contrast between pre-hiatus and post-return behavior (inter-commit hours 0.3 h → 335.9 h; commits/week 9.23 → 0.23).

**Observable contrast (not tested):**  
- Pre-hiatus (2018-Q4): `files/commit` = 1.0, `cpw` = 9.23, `inter_h` = 0.3 h  
- Post-return (2025-Q3): `files/commit` = 3.0, `cpw` = 0.23, `inter_h` = 335.9 h  

The contrast is striking but the 4-year gap is a structural confounder that cannot be controlled. A returning developer's behavior after a long absence reflects accumulated change in context, tools, and priorities — not a drift trajectory. **Reported for transparency; no causal attribution possible.**

---

## LLM Instruction Files as a Confound

A post-hoc check across the corpus: do repos contain explicit AI coding-instruction files (`CLAUDE.md`, `.github/copilot-instructions.md`, `AGENTS.md`)? The presence and content of those files correlates with the Fisher p in a directionally consistent way:

| Developer | Fisher p | Instruction files | Content type |
|-----------|--------:|-------------------|-------------|
| Rich Harris | 0.2483 | sveltejs/kit: CLAUDE.md + AGENTS.md + copilot-instr (4.3 KB each) | Full style + workflow guide |
| Ryan Dahl | 0.0775 | denoland/deno: copilot-instr (12 KB) + CLAUDE.md (11.9 KB) | Full coding style guide |
| DHH | 0.0301 | rails/rails: AGENTS.md (6.8 KB) | Style + setup |
| Evan You | 0.0457 | vitejs/vite: copilot-instr (1.6 KB) | Lightweight guide |
| Karpathy | 0.0495 | none | — |
| van Rossum | 0.0022 | none | — |
| Sorhus | 0.0022 | none | — |
| Abramov | 0.0002 | none | — |
| simonw | 0.7473 | none (llm: 425B setup-only AGENTS.md) | — |

The developers with the largest, most detailed instruction files (Rich Harris, Ryan Dahl) have the highest Fisher p (least detected drift). Those without instruction files span the full range — from strong drift (Abramov, van Rossum, Sorhus) to complete null (simonw).

**The implication:** When AI tools are given explicit style guides, they produce code that follows project conventions — statistically indistinguishable from the developer's manual commits. This is validated more cleanly in the companion [copilot-signal](https://github.com/riadmaouchi/copilot-signal) case-control study, where repos with detailed copilot-instructions.md showed 0/15 significant signals vs. 5/15 for repos without.

simonw remains the anomaly in this pattern: no substantial instruction files, yet the strongest null result. His explanation is different — AI tools adapt to his established style across a decade of open-source work, and the Level B patch signal (comment density, p = 0.048) is the only measurable trace.

---

## Level B Patch Signals: What They Add

Two patch-content signals were added based on validation in the [copilot-signal](https://github.com/riadmaouchi/copilot-signal) study: `patch_comment_density` (comment lines / added code lines) and `patch_blank_line_ratio` (blank added lines / total added lines). These are extracted from the diff — measuring only lines the developer wrote in each commit, not surrounding existing code.

Results on the full corpus (not included in Fisher p — Level B only):

| Developer | patch_comment_density p | Direction | patch_blank_line_ratio p | Direction |
|-----------|:-----------------------:|-----------|:------------------------:|-----------|
| simonw | **0.048** | **increase** | 0.664 | stable |
| karpathy | **0.023** | decrease | **0.023** | decrease |
| gvanrossum | **0.007** | decrease | **0.045** | decrease |
| Rich Harris | 0.098 | increase | 0.142 | increase |
| sindresorhus | 1.000 | stable | 0.708 | increase |
| ry | 0.505 | increase | 0.532 | stable |
| dhh | 0.446 | stable | 0.561 | stable |
| gaearon | 0.966 | increase | 1.000 | stable |
| yyx990803 | 0.569 | increase | 0.109 | increase |

Three developers show significant patch signals, but the directions contradict a simple "AI adoption → more comments" hypothesis:
- **simonw**: comments increased (consistent with AI, but only signal for him)
- **karpathy**: comments *decreased* (genre shift: research → C/systems code)
- **van Rossum**: comments *decreased* (CPython role narrowing, less documentation work)

The signal detects real style evolution but is not directionally specific to AI adoption.

---

## What the Data Tells Us

**1. Significant drift is the norm, not the exception — but its causes are not AI.**  
5 of 7 testable developers show statistically significant or near-significant drift at the process level. All five have documented non-AI explanations: career transitions, project maturation, portfolio evolution. The base rate of behavioral change among senior OSS contributors is high regardless of AI tooling.

**2. The strongest signal (Abramov, p = 0.0002) is a disengagement signature, not an AI signature.**  
Activity collapse (−95% commits/week, +956% inter-commit hours) is the opposite of what AI-assisted productivity would predict. The direction of drift matters: AI assistance hypothetically *increases* output velocity, while Abramov's signal is a withdrawal.

**3. Rich Harris invalidates the Level-C finding from v1.**  
The only developer with a "clear positive drift" in v1 (Level-C style, +6.8) shows *no significant drift* at Level A (p = 0.248). This is a methodological finding: style signals on commit diffs are not a reliable proxy for process change. They should not be used as primary evidence.

**4. Statistical significance ≠ practical significance ≠ AI attribution.**  
Fisher's method is sensitive: it can produce p = 0.002 from one strongly significant signal combined with five non-significant ones (Sindre Sorhus). The combined p-value measures self-consistency, not evidence strength for any particular cause.

**5. Sampling strategy is a first-class constraint.**  
The 120-commits/year cap, while appropriate for most developers, creates pathological outcomes for Torvalds (merge-window clustering) and Evan You (sparse 2025). Future iterations should adapt sampling strategy per developer based on their commit density distribution.

---

## Known Limitations

| Limitation | Affected Developers | Mitigation |
|-----------|---------------------|------------|
| 120-commits/year cap → constant `commits_per_week` in active periods | Torvalds, Rich Harris, Evan You | Acknowledged; signal is windowed, not per-commit |
| Quarterly window requires ≥10 windows | Torvalds (8), antirez (6) | No test run; observable trajectory reported |
| 2025 data sparse (year in progress at analysis time) | Most developers | Last window often < 30 commits |
| `?author=login` API filter misses unlinked emails | DHH | Mitigated by client-side name filter |
| Level-C signals measured on diffs, not full files | All | Reduced sensitivity; signals retained for comparison only |
| No verified ground truth | All | Explicit limitation; no causal claim made |

---

Full methodology: [METHODOLOGY.md](METHODOLOGY.md)  
Detection method comparison: METHODOLOGY.md §Méthodes de détection  
Research hypotheses and future experiments: [RESEARCH_AGENDA.md](RESEARCH_AGENDA.md)  
Raw profiles: [`reports/real/`](reports/real/)  
Collection script: [`run_analysis.py`](run_analysis.py)
