"""Regenerate all static figures for docs/img/.

Run:
    python generate_figures.py

Outputs:
    docs/img/timeline.png
    docs/img/drift_comparison.png
    docs/img/radar.png

All figures use synthetic data calibrated against the findings in FINDINGS.md.
No GitHub token or internet access required.
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.patches import FancyArrowPatch

# ── Design system ────────────────────────────────────────────────────────────

THEME = {
    "bg":           "#0D1117",
    "surface":      "#161B22",
    "grid":         "#21262D",
    "text_primary": "#E6EDF3",
    "text_muted":   "#8B949E",
    "spine":        "#30363D",
    "tick":         "#484F58",
    "dpi":          150,
    "title_size":   13,
    "label_size":   10,
    "tick_size":    9,
    "annot_size":   8,
}

PALETTE = {
    "torvalds":   "#8B949E",   # muted — organic control
    "antirez":    "#8B949E",
    "dhh":        "#8B949E",
    "tj":         "#8B949E",
    "gaearon":    "#E3B341",   # amber — moderate drift
    "gvanrossum": "#E3B341",
    "Rich-Harris": "#FF7B72",  # red-orange — high drift
    "yyx990803":  "#D2A8FF",   # purple — high drift
    "Ryan-Dahl":  "#58A6FF",   # blue — high drift
    "sindresorhus": "#3FB950", # green — high drift
}

# Milestone dates as decimal years for easy positioning
MILESTONES = {
    "Copilot\nPreview":  2021.49,   # 2021-06-29
    "Copilot GA":        2022.47,   # 2022-06-21
    "ChatGPT":           2022.91,   # 2022-11-30
    "GPT-4":             2023.20,   # 2023-03-14
    "Copilot\nChat GA":  2023.96,   # 2023-12-19
}

RESULTS_DIR = Path("docs/img")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ax_style(ax: plt.Axes, title: str = "", xlabel: str = "", ylabel: str = "") -> None:
    ax.set_facecolor(THEME["surface"])
    for spine in ax.spines.values():
        spine.set_edgecolor(THEME["spine"])
    ax.tick_params(colors=THEME["tick"], labelsize=THEME["tick_size"])
    ax.xaxis.label.set_color(THEME["text_muted"])
    ax.yaxis.label.set_color(THEME["text_muted"])
    ax.xaxis.label.set_size(THEME["label_size"])
    ax.yaxis.label.set_size(THEME["label_size"])
    if title:
        ax.set_title(title, color=THEME["text_primary"], fontsize=THEME["title_size"],
                     pad=10, fontweight="semibold")
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(color=THEME["grid"], linewidth=0.5, alpha=0.8)
    ax.set_axisbelow(True)


def _save(fig: plt.Figure, name: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    fig.savefig(path, dpi=THEME["dpi"], bbox_inches="tight",
                facecolor=THEME["bg"], edgecolor="none")
    plt.close(fig)
    kb = path.stat().st_size // 1024
    print(f"  ✓ {path}  ({kb} KB)")


def _decimal_year_ticks(ax: plt.Axes, start: int = 2019, end: int = 2025) -> None:
    years = list(range(start, end + 1))
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years])


# ── Synthetic data ────────────────────────────────────────────────────────────

def _make_quarterly(
    start: float,      # decimal year of first quarter
    end: float,        # decimal year of last quarter
    base: float,       # baseline score
    jump_at: float | None = None,   # decimal year of change point
    jump_delta: float = 0.0,        # score increase at change point
    noise: float = 1.5,
    rng: np.random.Generator | None = None,
) -> tuple[list[float], list[float]]:
    """Return (xs, ys) quarterly time series as decimal years."""
    if rng is None:
        rng = np.random.default_rng(42)
    xs: list[float] = []
    ys: list[float] = []
    q = start
    while q <= end + 0.01:
        xs.append(round(q, 3))
        score = base
        if jump_at is not None and q >= jump_at:
            frac = min((q - jump_at) / 0.5, 1.0)
            score = base + jump_delta * frac
        score += rng.normal(0, noise)
        ys.append(float(np.clip(score, 0, 100)))
        q = round(q + 0.25, 3)
    return xs, ys


def synthetic_timeline_data() -> dict[str, tuple[list[float], list[float]]]:
    rng = np.random.default_rng(7)
    return {
        # organic control — stays flat
        "Linus Torvalds": _make_quarterly(2019.0, 2024.75, base=8.5, noise=0.6, rng=rng),
        # moderate drift — jump Q4 2022 (ChatGPT)
        "Dan Abramov": _make_quarterly(
            2019.0, 2024.75, base=28.6, jump_at=2022.75, jump_delta=19.0, noise=1.8, rng=rng),
        # high drift — sharp jump Q1 2023 (GPT-4)
        "Evan You": _make_quarterly(
            2019.0, 2024.75, base=29.4, jump_at=2023.0, jump_delta=30.0, noise=2.2, rng=rng),
    }


def synthetic_drift_data() -> list[dict]:
    return [
        {"name": "Linus Torvalds",    "lang": "C",          "baseline": 8.2,  "post": 9.1,  "cp": None},
        {"name": "antirez",           "lang": "C",          "baseline": 11.4, "post": 12.8, "cp": None},
        {"name": "DHH",               "lang": "Ruby",        "baseline": 24.3, "post": 26.1, "cp": None},
        {"name": "TJ Holowaychuk",    "lang": "JS",          "baseline": 19.3, "post": 21.1, "cp": None},
        {"name": "Guido van Rossum",  "lang": "Python",      "baseline": 22.1, "post": 38.4, "cp": "Q2 2023"},
        {"name": "Dan Abramov",       "lang": "TypeScript",  "baseline": 28.6, "post": 47.3, "cp": "Q4 2022"},
        {"name": "Rich Harris",       "lang": "TypeScript",  "baseline": 31.2, "post": 52.8, "cp": "Q3 2022"},
        {"name": "Ryan Dahl",         "lang": "TypeScript",  "baseline": 27.8, "post": 55.2, "cp": "Q3 2022"},
        {"name": "Sindre Sorhus",     "lang": "JS/TS",       "baseline": 35.7, "post": 61.4, "cp": "Q4 2022"},
        {"name": "Evan You",          "lang": "TypeScript",  "baseline": 29.4, "post": 58.1, "cp": "Q1 2023"},
    ]


def synthetic_signal_data() -> dict[str, dict[str, float]]:
    """Per-signal normalized scores (0–1) for organic vs high-drift devs.

    Values derived from the reported raw metrics in FINDINGS.md and METHODOLOGY.md.
    comment_density: /20, docstring_coverage: raw, verbosity: /20, error_handling: /15
    """
    return {
        # "organic" baseline — average of Torvalds, antirez, DHH
        "Organic\nbaseline": {
            "Comments": 0.08, "Docstrings": 0.15, "Verbosity": 0.37,
            "Error hdlg": 0.20, "Conv. commit": 0.05,
        },
        "Dan\nAbramov": {
            "Comments": 0.22, "Docstrings": 0.52, "Verbosity": 0.54,
            "Error hdlg": 0.38, "Conv. commit": 0.34,
        },
        "Rich\nHarris": {
            "Comments": 0.26, "Docstrings": 0.67, "Verbosity": 0.49,
            "Error hdlg": 0.51, "Conv. commit": 0.55,
        },
        "Evan You": {
            "Comments": 0.30, "Docstrings": 0.82, "Verbosity": 0.56,
            "Error hdlg": 0.42, "Conv. commit": 0.78,
        },
        "Ryan Dahl": {
            "Comments": 0.28, "Docstrings": 0.72, "Verbosity": 0.58,
            "Error hdlg": 0.44, "Conv. commit": 0.89,
        },
    }


# ── Figure 1 — LLM Score Timeline ─────────────────────────────────────────────

def fig_timeline() -> None:
    """Timeline of LLM score for 3 developer archetypes with milestone bands."""
    data = synthetic_timeline_data()

    colors = {
        "Linus Torvalds": PALETTE["torvalds"],
        "Dan Abramov":    PALETTE["gaearon"],
        "Evan You":       PALETTE["yyx990803"],
    }
    change_points = {
        "Dan Abramov": 2022.75,
        "Evan You":    2023.0,
    }

    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor(THEME["bg"])
    _ax_style(ax, xlabel="Year", ylabel="LLM Influence Score (0–100)")

    # Threshold bands
    ax.axhspan(40, 70,  alpha=0.06, color="#E3B341", zorder=0)
    ax.axhspan(70, 100, alpha=0.06, color="#FF7B72", zorder=0)

    # Milestone verticals
    m_labels = list(MILESTONES.keys())
    m_xs = list(MILESTONES.values())
    for x, label in zip(m_xs, m_labels):
        ax.axvline(x, color=THEME["spine"], lw=0.8, ls="--", zorder=1)
        ax.text(x + 0.02, 96, label, color=THEME["text_muted"], fontsize=7,
                va="top", ha="left", rotation=0, linespacing=1.3)

    # Developer lines
    for name, (xs, ys) in data.items():
        color = colors[name]
        ax.plot(xs, ys, color=color, lw=2.2, zorder=3, solid_capstyle="round")
        ax.fill_between(xs, ys, alpha=0.10, color=color, zorder=2)

        # Change-point arrow
        if name in change_points:
            cp_x = change_points[name]
            # Find y at cp
            cp_idx = min(range(len(xs)), key=lambda i: abs(xs[i] - cp_x))
            cp_y = ys[cp_idx]
            ax.annotate(
                "▼", xy=(cp_x, cp_y + 2), color=color,
                fontsize=11, ha="center", va="bottom", zorder=4,
            )

        # Inline end label
        ax.text(xs[-1] + 0.08, ys[-1], name, color=color,
                fontsize=9, va="center", fontweight="bold")

    # Zone labels (right margin)
    ax.text(2024.92, 55, "Ambiguous", color="#E3B341", fontsize=7.5,
            va="center", ha="right", alpha=0.8)
    ax.text(2024.92, 85, "LLM-influenced", color="#FF7B72", fontsize=7.5,
            va="center", ha="right", alpha=0.8)
    ax.text(2024.92, 20, "Organic", color="#3FB950", fontsize=7.5,
            va="center", ha="right", alpha=0.8)

    ax.set_xlim(2018.9, 2025.6)
    ax.set_ylim(0, 100)
    _decimal_year_ticks(ax, 2019, 2024)

    ax.set_title(
        "LLM Influence Score timeline — 3 developer archetypes\n"
        "▼ = detected style change point  ·  dashed lines = LLM release milestones",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )

    _save(fig, "timeline.png")


# ── Figure 2 — Drift Comparison (horizontal diverging bars) ──────────────────

def fig_drift_comparison() -> None:
    """Horizontal bar chart: baseline vs post-LLM LLM score per developer."""
    data = sorted(synthetic_drift_data(), key=lambda d: d["post"] - d["baseline"])

    names    = [d["name"]     for d in data]
    baseline = [d["baseline"] for d in data]
    post     = [d["post"]     for d in data]
    cps      = [d["cp"]       for d in data]
    drifts   = [p - b for p, b in zip(post, baseline)]

    # Color by drift magnitude
    bar_colors = []
    for drift in drifts:
        if drift < 5:
            bar_colors.append(PALETTE["torvalds"])
        elif drift < 20:
            bar_colors.append(PALETTE["gaearon"])
        else:
            bar_colors.append(PALETTE["Ryan-Dahl"])

    fig, ax = plt.subplots(figsize=(10, 5.8))
    fig.patch.set_facecolor(THEME["bg"])
    _ax_style(ax, xlabel="LLM Influence Score (0–100)")

    y = np.arange(len(names))
    bar_h = 0.42

    # Baseline bars (thin, muted)
    ax.barh(y + bar_h / 2, baseline, height=bar_h * 0.7,
            color=THEME["grid"], zorder=3, label="Pre-LLM baseline")

    # Post bars (full color)
    ax.barh(y - bar_h / 2, post, height=bar_h,
            color=bar_colors, zorder=3, label="Post-LLM era")

    # Drift annotation
    for i, (drift, cp, p) in enumerate(zip(drifts, cps, post)):
        if drift >= 5:
            ax.text(p + 0.8, i - bar_h / 2,
                    f"+{drift:.1f}" + (f"  [{cp}]" if cp else ""),
                    color=bar_colors[i], fontsize=8, va="center", fontweight="bold")
        else:
            ax.text(p + 0.8, i - bar_h / 2,
                    f"+{drift:.1f}  organic",
                    color=THEME["text_muted"], fontsize=8, va="center")

    # Threshold lines
    ax.axvline(40, color="#E3B341", lw=0.8, ls="--", alpha=0.6, zorder=2)
    ax.axvline(70, color="#FF7B72", lw=0.8, ls="--", alpha=0.6, zorder=2)
    ax.text(40.5, len(names) - 0.2, "40", color="#E3B341", fontsize=7.5)
    ax.text(70.5, len(names) - 0.2, "70", color="#FF7B72", fontsize=7.5)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9, color=THEME["text_primary"])
    ax.set_xlim(0, 85)

    # Legend
    legend_elements = [
        mpatches.Patch(color=THEME["grid"],          label="Pre-LLM baseline"),
        mpatches.Patch(color=PALETTE["torvalds"],    label="Organic (drift < 5 pts)"),
        mpatches.Patch(color=PALETTE["gaearon"],     label="Possible drift (5–20 pts)"),
        mpatches.Patch(color=PALETTE["Ryan-Dahl"],   label="High drift (> 20 pts)"),
    ]
    ax.legend(handles=legend_elements, loc="lower right",
              facecolor=THEME["surface"], edgecolor=THEME["spine"],
              labelcolor=THEME["text_muted"], fontsize=8)

    ax.set_title(
        "Style drift — baseline vs post-LLM era (Copilot GA, Jun 2022)\n"
        "Annotation shows detected change-point quarter where applicable",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )

    _save(fig, "drift_comparison.png")


# ── Figure 3 — Signal heatmap (replaces radar) ───────────────────────────────

def fig_radar() -> None:
    """Diverging heatmap: per-signal deviation from organic baseline.

    Rows = developers (organic baseline + 4 LLM-influenced devs).
    Columns = 5 style signals.
    Cell value = deviation from organic baseline in percentage points.
    """
    raw = synthetic_signal_data()
    devs = list(raw.keys())
    signals = ["Comments", "Docstrings", "Verbosity", "Error hdlg", "Conv. commit"]

    organic = raw["Organic\nbaseline"]
    matrix = np.zeros((len(devs), len(signals)))
    for i, dev in enumerate(devs):
        for j, sig in enumerate(signals):
            matrix[i, j] = (raw[dev][sig] - organic[sig]) * 100.0

    fig, ax = plt.subplots(figsize=(9, 4.5))
    fig.patch.set_facecolor(THEME["bg"])
    ax.set_facecolor(THEME["surface"])

    vmax = 70
    # Manual RdBu_r colormap rendering on dark background
    cmap = plt.cm.RdBu_r  # type: ignore[attr-defined]

    im = ax.imshow(matrix, cmap=cmap, vmin=-vmax, vmax=vmax, aspect="auto")

    # Cell annotations
    for i in range(len(devs)):
        for j in range(len(signals)):
            val = matrix[i, j]
            text_color = "white" if abs(val) > 30 else THEME["text_primary"]
            sign = "+" if val >= 0 else ""
            ax.text(j, i, f"{sign}{val:.0f}%",
                    ha="center", va="center", fontsize=9,
                    color=text_color, fontweight="bold")

    ax.set_xticks(range(len(signals)))
    ax.set_xticklabels(signals, fontsize=THEME["label_size"],
                       color=THEME["text_primary"])
    ax.set_yticks(range(len(devs)))
    ax.set_yticklabels(devs, fontsize=9, color=THEME["text_primary"])

    for spine in ax.spines.values():
        spine.set_edgecolor(THEME["spine"])
    ax.tick_params(colors=THEME["tick"])

    # Grid lines between cells
    for x in np.arange(-0.5, len(signals), 1):
        ax.axvline(x, color=THEME["grid"], lw=0.6)
    for y in np.arange(-0.5, len(devs), 1):
        ax.axhline(y, color=THEME["grid"], lw=0.6)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Deviation from organic baseline (%pts)",
                   color=THEME["text_muted"], fontsize=8)
    cbar.ax.tick_params(colors=THEME["tick"], labelsize=8)
    cbar.outline.set_edgecolor(THEME["spine"])

    ax.set_title(
        "Style signal fingerprint — deviation from organic baseline\n"
        "Red = more LLM-like than organic  ·  Blue = less",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )

    _save(fig, "radar.png")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    plt.rcParams.update({
        "font.family":    "sans-serif",
        "font.size":      THEME["tick_size"],
        "axes.titlesize": THEME["title_size"],
        "axes.labelsize": THEME["label_size"],
        "figure.facecolor": THEME["bg"],
    })

    print("Generating figures …")
    fig_timeline()
    fig_drift_comparison()
    fig_radar()
    print("Done.")


if __name__ == "__main__":
    main()
