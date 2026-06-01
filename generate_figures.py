"""Generate all static figures for docs/img/ from real collected profiles.

Run AFTER python run_analysis.py has completed:
    python generate_figures.py

Reads:  reports/real/*.json
Writes: docs/img/level_a_heatmap.png       ← Level-A signal Δ% heatmap
        docs/img/activity_timeline.png      ← commits/week trajectories (2018-2025)
        docs/img/changepoint_calendar.png   ← when did change points occur
        docs/img/process_scatter.png        ← baseline vs recent activity scatter

Each figure embeds an auditability watermark.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

# ── Design system ──────────────────────────────────────────────────────────────

BG        = "#0D1117"
SURFACE   = "#161B22"
GRID      = "#21262D"
BORDER    = "#30363D"
TEXT_HI   = "#E6EDF3"
TEXT_LO   = "#8B949E"
DPI       = 160

# Significance palette
SIG_COLORS = {
    "p001": "#e74c3c",   # p < 0.01  — strong
    "p005": "#e67e22",   # p < 0.05  — moderate
    "p010": "#f1c40f",   # p < 0.10  — trend
    "ns":   "#27ae60",   # not significant
    "na":   "#484F58",   # not testable
}

# Per-developer accent colour
DEV_COLORS = {
    "gaearon":      "#e74c3c",
    "gvanrossum":   "#e67e22",
    "sindresorhus": "#f1c40f",
    "dhh":          "#d2a8ff",
    "yyx990803":    "#58a6ff",
    "ry":           "#79c0ff",
    "Rich-Harris":  "#3fb950",
    "torvalds":     "#8b949e",
    "antirez":      "#6e7681",
}

LLM_MILESTONES = [
    (2021.49, "Copilot\nPreview"),
    (2022.47, "Copilot GA"),
    (2022.91, "ChatGPT"),
    (2023.20, "GPT-4"),
    (2023.97, "Copilot\nChat GA"),
    (2024.17, "Claude 3"),
]

LEVEL_A_SIGNALS = [
    ("median_files_per_commit",   "Files /\ncommit"),
    ("large_commit_ratio",        "Large\ncommit"),
    ("cross_module_ratio",        "Cross-\nmodule"),
    ("refactor_ratio",            "Refactor\nratio"),
    ("median_inter_commit_hours", "Inter-commit\nhours"),
    ("commits_per_week",          "Commits\n/ week"),
]

PROFILES_DIR = Path("reports/real")
IMG_DIR      = Path("docs/img")

# ── Data loading ───────────────────────────────────────────────────────────────

def _dq(iso: str) -> float:
    """ISO timestamp → decimal year (e.g. '2022-07-01T…' → 2022.5)."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.year + (dt.month - 1) / 12.0


def load() -> list[dict]:
    """Load all profiles, newest-schema only, sorted by Fisher p."""
    profiles = []
    for f in sorted(PROFILES_DIR.glob("*.json")):
        if f.stem == "summary":
            continue
        d = json.loads(f.read_text())
        if "behavior_timeline" in d:
            profiles.append(d)
    profiles.sort(key=lambda p: (
        p.get("drift_result", {}) is None or p["drift_result"] is None,
        p.get("drift_result", {}).get("combined_p_value", 1.0)
        if p.get("drift_result") else 1.0,
    ))
    return profiles


def _sig_color(p: float | None) -> str:
    if p is None:    return SIG_COLORS["na"]
    if p < 0.01:     return SIG_COLORS["p001"]
    if p < 0.05:     return SIG_COLORS["p005"]
    if p < 0.10:     return SIG_COLORS["p010"]
    return SIG_COLORS["ns"]


def _short_name(profile: dict) -> str:
    name = profile.get("display_name", profile.get("github_login", "?"))
    # Strip parenthetical suffixes like "(DHH)" or "(antirez)"
    name = name.split(" (")[0]
    # Abbreviate long names that exceed display budget
    ABBREVS = {
        "David Heinemeier Hansson": "DHH (D. Heinemeier Hansson)",
        "Salvatore Sanfilippo": "Salvatore Sanfilippo",
    }
    return ABBREVS.get(name, name[:26])


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _setup_ax(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for sp in ax.spines.values():
        sp.set_edgecolor(BORDER)
    ax.tick_params(colors=TEXT_LO, labelsize=9)
    ax.xaxis.label.set_color(TEXT_LO)
    ax.yaxis.label.set_color(TEXT_LO)
    ax.grid(color=GRID, lw=0.5, alpha=0.9, zorder=0)
    ax.set_axisbelow(True)


def _milestone_lines(ax: plt.Axes, y_annot: float | None = None,
                     alpha_vline: float = 0.35) -> None:
    for x, lbl in LLM_MILESTONES:
        ax.axvline(x, color=BORDER, lw=0.8, ls="--", alpha=alpha_vline, zorder=1)
        if y_annot is not None:
            ax.text(x + 0.03, y_annot, lbl, color=TEXT_LO,
                    fontsize=7, va="top", ha="left", linespacing=1.3, alpha=0.7)


def _watermark(fig: plt.Figure, n_commits: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fig.text(0.99, 0.005,
             f"Real GitHub data · {n_commits:,} commits · generated {today}",
             ha="right", va="bottom", color=TEXT_LO, fontsize=7, alpha=0.6)


def _save(fig: plt.Figure, name: str) -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    path = IMG_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    print(f"  ✓ {path}  ({path.stat().st_size // 1024} KB)")


# ── Figure 1 — Level-A Signal Heatmap ─────────────────────────────────────────

def fig_level_a_heatmap(profiles: list[dict]) -> None:
    """Heatmap: 9 developers × 6 Level-A signals — Δ% baseline→recent.

    Diverging colormap: red = increase, blue = decrease.
    Significance stars overlaid on each cell.
    Right axis: Fisher p-value bar.
    """
    n_dev = len(profiles)
    n_sig = len(LEVEL_A_SIGNALS)

    matrix     = np.full((n_dev, n_sig), np.nan)
    sig_matrix = np.zeros((n_dev, n_sig), dtype=bool)

    dev_names  = []
    fisher_ps  = []

    for i, prof in enumerate(profiles):
        dev_names.append(_short_name(prof))
        dr = prof.get("drift_result")
        fisher_ps.append(dr["combined_p_value"] if dr else None)

        if not dr:
            continue
        sigs = {s["signal"]: s for s in dr.get("signals", [])}
        for j, (sig_key, _) in enumerate(LEVEL_A_SIGNALS):
            s = sigs.get(sig_key)
            if s is None:
                continue
            raw_pct = s["delta_pct"]
            # Cap display range at ±200% (Sindre's large_commit_ratio: +4.5e9%)
            matrix[i, j] = float(np.clip(raw_pct, -200, 200))
            sig_matrix[i, j] = s.get("significant_at_05", False)

    # ── Layout ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(12, 6.5), facecolor=BG)
    # Main heatmap + colorbar + p-value bar
    gs = fig.add_gridspec(1, 3, width_ratios=[10, 0.4, 1.2],
                          left=0.18, right=0.94, wspace=0.06)
    ax_heat = fig.add_subplot(gs[0, 0])
    ax_cbar = fig.add_subplot(gs[0, 1])
    ax_p    = fig.add_subplot(gs[0, 2])

    # ── Heatmap ───────────────────────────────────────────────────────────────
    ax_heat.set_facecolor(SURFACE)

    cmap = plt.cm.RdBu_r
    norm = Normalize(vmin=-200, vmax=200)

    img = ax_heat.imshow(matrix, cmap=cmap, norm=norm, aspect="auto",
                         interpolation="nearest")

    # Cell annotations
    for i in range(n_dev):
        for j in range(n_sig):
            val = matrix[i, j]
            if np.isnan(val):
                ax_heat.text(j, i, "n/a", ha="center", va="center",
                             fontsize=8, color=TEXT_LO)
                continue
            intensity = abs(val) / 200
            text_color = "white" if intensity > 0.5 else TEXT_HI
            sign = "+" if val > 0 else ""
            star = "★" if sig_matrix[i, j] else ""
            ax_heat.text(j, i, f"{sign}{val:.0f}%{star}",
                         ha="center", va="center",
                         fontsize=8.5, fontweight="bold" if sig_matrix[i, j] else "normal",
                         color=text_color)

    # Grid lines
    for x in np.arange(-0.5, n_sig, 1):
        ax_heat.axvline(x, color=BG, lw=1.5)
    for y in np.arange(-0.5, n_dev, 1):
        ax_heat.axhline(y, color=BG, lw=1.5)

    ax_heat.set_xticks(range(n_sig))
    ax_heat.set_xticklabels([lbl for _, lbl in LEVEL_A_SIGNALS],
                             fontsize=9, color=TEXT_HI)
    ax_heat.set_yticks(range(n_dev))
    ax_heat.set_yticklabels(dev_names, fontsize=9.5, color=TEXT_HI)
    for sp in ax_heat.spines.values():
        sp.set_edgecolor(BORDER)
    ax_heat.tick_params(colors=TEXT_LO, length=0)
    ax_heat.xaxis.tick_top()
    ax_heat.xaxis.set_label_position("top")

    # ── Colorbar ──────────────────────────────────────────────────────────────
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=ax_cbar)
    cb.set_label("Δ% (baseline → recent)", color=TEXT_LO, fontsize=8)
    cb.ax.tick_params(colors=TEXT_LO, labelsize=8)
    cb.outline.set_edgecolor(BORDER)
    cb.ax.yaxis.label.set_color(TEXT_LO)

    # ── Fisher p-value bar ────────────────────────────────────────────────────
    ax_p.set_facecolor(BG)
    for sp in ax_p.spines.values():
        sp.set_visible(False)

    y_pos = np.arange(n_dev)
    for i, (name, fp) in enumerate(zip(dev_names, fisher_ps)):
        color = _sig_color(fp)
        bar_val = -np.log10(fp) if fp and fp > 0 else 0
        bar_val = min(bar_val, 5)  # cap at 5 = p=1e-5
        ax_p.barh(i, bar_val, height=0.6, color=color, alpha=0.9)
        label = f"p={fp:.4f}" if fp else "n/a"
        ax_p.text(bar_val + 0.08, i, label, color=color,
                  fontsize=8, va="center", fontweight="bold")

    ax_p.set_xlim(0, 5.8)
    ax_p.set_ylim(-0.5, n_dev - 0.5)
    ax_p.set_yticks([])
    ax_p.set_xticks([0, 1.3, 2, 3])
    ax_p.set_xticklabels(["1", "0.05", "0.01", "0.001"], fontsize=7.5, color=TEXT_LO)
    ax_p.set_xlabel("Fisher p", fontsize=8, color=TEXT_LO)
    ax_p.tick_params(colors=TEXT_LO, length=3)
    ax_p.axvline(1.3, color=TEXT_LO, lw=0.8, ls="--", alpha=0.5)
    ax_p.set_title("Fisher\np-value", color=TEXT_HI, fontsize=8, pad=6)
    ax_p.invert_yaxis()
    ax_p.set_facecolor(SURFACE)

    # Legend for stars
    legend_elements = [
        mpatches.Patch(color=_sig_color(0.001), label="p < 0.01  ★"),
        mpatches.Patch(color=_sig_color(0.03),  label="p < 0.05  ★"),
        mpatches.Patch(color=_sig_color(0.08),  label="p < 0.10"),
        mpatches.Patch(color=_sig_color(0.5),   label="not significant"),
        mpatches.Patch(color=_sig_color(None),  label="insufficient data"),
    ]
    ax_heat.legend(handles=legend_elements, loc="lower left",
                   bbox_to_anchor=(0, -0.22), ncol=5,
                   facecolor=SURFACE, edgecolor=BORDER,
                   labelcolor=TEXT_LO, fontsize=8)

    fig.suptitle(
        "Level-A Process Signal Δ% — baseline vs. recent (4 most recent quarters)\n"
        "★ = significant at α=0.05 (Mann-Whitney U) · Δ% capped at ±200% for display",
        color=TEXT_HI, fontsize=11, fontweight="bold", y=1.02,
    )
    _watermark(fig, sum(p.get("total_commits_analyzed", 0) for p in profiles))
    _save(fig, "level_a_heatmap.png")


# ── Figure 2 — Commit Activity Timeline ───────────────────────────────────────

def fig_activity_timeline(profiles: list[dict]) -> None:
    """commits/week trajectory for all developers, 2018–2025.

    Each line coloured by Fisher p significance.
    Change points marked with ▼.
    LLM milestones as vertical reference lines.
    """
    fig, ax = plt.subplots(figsize=(13, 6), facecolor=BG)
    _setup_ax(ax)

    max_y = 0.0
    total_commits = 0

    for prof in profiles:
        login = prof.get("github_login", "")
        name  = _short_name(prof)
        tl    = prof.get("behavior_timeline", [])
        dr    = prof.get("drift_result")
        fp    = dr["combined_p_value"] if dr else None
        color = DEV_COLORS.get(login, "#8b949e")

        if not tl:
            continue

        xs = [_dq(w["period_start"]) for w in tl]
        ys = [w.get("commits_per_week", 0) for w in tl]
        max_y = max(max_y, max(ys))
        total_commits += prof.get("total_commits_analyzed", 0)

        # Line width / alpha driven by significance
        lw    = 2.5 if fp and fp < 0.01 else (2.0 if fp and fp < 0.05 else 1.5)
        alpha = 1.0 if fp and fp < 0.05 else 0.65

        ax.plot(xs, ys, color=color, lw=lw, alpha=alpha,
                solid_capstyle="round", zorder=3)
        ax.fill_between(xs, ys, alpha=0.07, color=color, zorder=2)

        # Developer label at last non-zero point
        last_nonzero = [(x, y) for x, y in zip(xs, ys) if y > 0.05]
        if last_nonzero:
            lx, ly = last_nonzero[-1]
            ax.text(lx + 0.07, ly, name, color=color, fontsize=8.5,
                    va="center", fontweight="bold", zorder=5)

        # Level-A change points for commits_per_week
        cps = [cp for cp in prof.get("change_points", [])
               if cp.get("signal_level") == "A"
               and cp.get("signal") == "commits_per_week"]
        for cp in cps:
            cp_x = _dq(cp["date"])
            cp_y = cp.get("value_after", 0)
            ax.annotate("▼", xy=(cp_x, cp_y + max_y * 0.04),
                        color=color, fontsize=10, ha="center",
                        va="bottom", zorder=6, alpha=0.9)

    # LLM milestones
    for x, lbl in LLM_MILESTONES:
        ax.axvline(x, color=BORDER, lw=0.9, ls="--", alpha=0.55, zorder=1)
        ax.text(x + 0.04, max_y * 0.97, lbl, color=TEXT_LO,
                fontsize=7.5, va="top", ha="left", linespacing=1.3, alpha=0.85)

    ax.set_xlim(2018.0, 2026.2)
    ax.set_ylim(0, max_y * 1.15)
    ax.set_xticks(range(2018, 2026))
    ax.set_xticklabels([str(y) for y in range(2018, 2026)], color=TEXT_LO)
    ax.set_xlabel("Year", color=TEXT_LO)
    ax.set_ylabel("commits / week  (quarterly median)", color=TEXT_LO)

    # Significance legend
    legend_elements = [
        plt.Line2D([0], [0], color=SIG_COLORS["p001"], lw=2.5, label="p < 0.01 ★★★"),
        plt.Line2D([0], [0], color=SIG_COLORS["p005"], lw=2.0, label="p < 0.05 ★"),
        plt.Line2D([0], [0], color=SIG_COLORS["ns"],   lw=1.5, label="no significant drift", alpha=0.7),
        plt.Line2D([0], [0], color=SIG_COLORS["na"],   lw=1.5, label="insufficient windows", alpha=0.5),
        plt.Line2D([0], [0], color=TEXT_LO, marker="v", lw=0, markersize=9,
                   label="▼ change point (commits/week)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right",
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=8.5)

    ax.set_title(
        "Commit activity trajectory — commits / week (quarterly windows, 2018–2025)\n"
        "Line weight ∝ statistical significance · ▼ = Level-A change point"
        " · Torvalds flat line = 120-commit/year cap artifact (merge-window clustering)",
        color=TEXT_HI, fontsize=10, fontweight="bold", pad=10,
    )
    _watermark(fig, total_commits)
    _save(fig, "activity_timeline.png")


# ── Figure 3 — Change-Point Calendar ──────────────────────────────────────────

def fig_changepoint_calendar(profiles: list[dict]) -> None:
    """Dot calendar: when did Level-A change points occur, for each developer.

    X = time, Y = developer, dot = change point.
    Size ∝ magnitude. Color = signal type. LLM milestones overlaid.
    """
    # Signal-to-colour mapping
    SIGNAL_COLORS = {
        "commits_per_week":          "#e74c3c",
        "median_inter_commit_hours": "#e67e22",
        "cross_module_ratio":        "#3498db",
        "refactor_ratio":            "#9b59b6",
        "median_files_per_commit":   "#1abc9c",
        "large_commit_ratio":        "#f1c40f",
    }

    fig, ax = plt.subplots(figsize=(13, 5.5), facecolor=BG)
    _setup_ax(ax)
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.7)
    ax.grid(axis="y", visible=False)

    dev_names = [_short_name(p) for p in profiles]
    n_dev = len(dev_names)

    # Background bands for each developer row
    for i in range(n_dev):
        ax.axhspan(i - 0.45, i + 0.45, color=SURFACE if i % 2 == 0 else BG,
                   alpha=1.0, zorder=0)

    # LLM milestone bands (faint)
    for x, lbl in LLM_MILESTONES:
        ax.axvline(x, color="#58a6ff", lw=0.8, ls="--", alpha=0.35, zorder=1)
        ax.text(x, n_dev - 0.05, lbl, color="#58a6ff",
                fontsize=7, va="top", ha="center", linespacing=1.3, alpha=0.65)

    total_commits = 0
    plotted_signals: set[str] = set()

    for i, prof in enumerate(profiles):
        total_commits += prof.get("total_commits_analyzed", 0)
        cps_a = [cp for cp in prof.get("change_points", [])
                 if cp.get("signal_level") == "A"]

        for cp in cps_a:
            x = _dq(cp["date"])
            sig = cp.get("signal", "")
            mag = min(float(cp.get("magnitude", 0.1)), 10.0)
            color = SIGNAL_COLORS.get(sig, "#8b949e")

            # Size: log-scaled magnitude
            size = 30 + 120 * min(mag / 5.0, 1.0)

            ax.scatter(x, i, s=size, color=color, alpha=0.85,
                       zorder=3, edgecolors="white", linewidths=0.4)
            plotted_signals.add(sig)

        # Fisher p annotation at right
        dr = prof.get("drift_result")
        fp = dr["combined_p_value"] if dr else None
        p_txt = f"p={fp:.4f}" if fp else "n/a"
        p_color = _sig_color(fp)
        ax.text(2026.0, i, p_txt, color=p_color, fontsize=8.5,
                va="center", ha="left", fontweight="bold")

    ax.set_xlim(2017.9, 2026.5)
    ax.set_ylim(-0.7, n_dev - 0.3)
    ax.set_yticks(range(n_dev))
    ax.set_yticklabels(dev_names, fontsize=10, color=TEXT_HI)
    ax.set_xticks(range(2018, 2026))
    ax.set_xticklabels([str(y) for y in range(2018, 2026)], color=TEXT_LO)
    ax.set_xlabel("Year", color=TEXT_LO)
    ax.invert_yaxis()

    # Signal legend
    legend_elements = [
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor=SIGNAL_COLORS[sig_key],
                   markeredgecolor="white", markeredgewidth=0.4,
                   markersize=9, label=sig_key.replace("_", " "))
        for sig_key, _ in reversed(LEVEL_A_SIGNALS)
        if sig_key in plotted_signals and sig_key in SIGNAL_COLORS
    ]
    legend_elements += [
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor="white", markersize=6,
                   label="size ∝ magnitude"),
    ]
    ax.legend(handles=legend_elements, title="Level-A signal",
              title_fontsize=8,
              loc="lower left", bbox_to_anchor=(0, -0.28), ncol=4,
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=8)

    ax.set_title(
        "Level-A change-point calendar — when did each developer's process shift?\n"
        "Each dot = one Level-A change point · Size ∝ magnitude · Color = signal",
        color=TEXT_HI, fontsize=11, fontweight="bold", pad=10,
    )
    _watermark(fig, total_commits)
    _save(fig, "changepoint_calendar.png")


# ── Figure 4 — Before vs After Scatter ────────────────────────────────────────

def fig_process_scatter(profiles: list[dict]) -> None:
    """Scatter: baseline commits/week vs recent commits/week.

    Diagonal = no change. Below diagonal = activity declined.
    Point size ∝ total commits. Color = Fisher p significance.
    """
    fig, ax = plt.subplots(figsize=(8, 7), facecolor=BG)
    _setup_ax(ax)

    xs, ys, sizes, colors, labels, fps = [], [], [], [], [], []
    total_commits = 0

    for prof in profiles:
        dr = prof.get("drift_result")
        if not dr:
            continue

        sigs = {s["signal"]: s for s in dr.get("signals", [])}
        cpw  = sigs.get("commits_per_week")
        if not cpw:
            continue

        baseline = cpw["baseline_mean"]
        recent   = cpw["recent_mean"]
        fp       = dr.get("combined_p_value")
        commits  = prof.get("total_commits_analyzed", 100)
        total_commits += commits

        xs.append(baseline)
        ys.append(recent)
        sizes.append(40 + commits / 8)
        colors.append(_sig_color(fp))
        labels.append(_short_name(prof))
        fps.append(fp)

    if not xs:
        print("  [SKIP] process_scatter — no drift results")
        return

    # Diagonal reference (no change)
    all_vals = xs + ys
    lim_max = max(all_vals) * 1.15
    lim_max = max(lim_max, 8)
    diag = np.linspace(0, lim_max, 100)
    ax.plot(diag, diag, color=BORDER, lw=1.2, ls="--",
            alpha=0.7, zorder=1, label="no change")
    ax.fill_between(diag, 0, diag, alpha=0.04, color="#3fb950", zorder=0)
    ax.fill_between(diag, diag, lim_max, alpha=0.04, color="#e74c3c", zorder=0)

    # Zone labels
    ax.text(lim_max * 0.72, lim_max * 0.10,
            "Activity declined\n(recent < baseline)",
            color="#e74c3c", fontsize=8.5, alpha=0.7, ha="center")
    ax.text(lim_max * 0.18, lim_max * 0.82,
            "Activity increased\n(recent > baseline)",
            color="#3fb950", fontsize=8.5, alpha=0.7, ha="center")

    # Scatter
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.90,
               zorder=4, edgecolors="white", linewidths=0.6)

    # Labels — stagger vertically when points cluster near y≈0
    # Sort by x to apply deterministic offsets
    label_data = sorted(zip(xs, ys, labels, fps), key=lambda t: t[0])
    prev_y_text = -999.0
    for x, y, name, fp in label_data:
        offset_x = lim_max * 0.025
        offset_y = lim_max * 0.03
        y_text = y + offset_y
        # Push label up if it would overlap with previous
        if y_text - prev_y_text < lim_max * 0.07:
            y_text = prev_y_text + lim_max * 0.07
        prev_y_text = y_text
        ax.annotate(
            name,
            xy=(x, y), xytext=(x + offset_x, y_text),
            arrowprops=dict(arrowstyle="-", color=_sig_color(fp), lw=0.6, alpha=0.5)
            if abs(y_text - y) > lim_max * 0.05 else None,
            color=_sig_color(fp), fontsize=8.5, fontweight="bold",
            zorder=5,
        )

    ax.set_xlim(-0.1, lim_max)
    ax.set_ylim(-0.1, lim_max)
    ax.set_xlabel("Baseline commits / week  (historical windows)", color=TEXT_LO, fontsize=10)
    ax.set_ylabel("Recent commits / week  (last 4 quarters)", color=TEXT_LO, fontsize=10)

    legend_elements = [
        mpatches.Patch(color=SIG_COLORS["p001"], label="Fisher p < 0.01  ★★★"),
        mpatches.Patch(color=SIG_COLORS["p005"], label="Fisher p < 0.05  ★"),
        mpatches.Patch(color=SIG_COLORS["p010"], label="Fisher p < 0.10  ~"),
        mpatches.Patch(color=SIG_COLORS["ns"],   label="not significant"),
        plt.Line2D([0], [0], color=BORDER, ls="--", lw=1.2, label="no change (y = x)"),
    ]
    ax.legend(handles=legend_elements, loc="upper left",
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=8.5)

    ax.set_title(
        "Process change: baseline activity vs. recent activity\n"
        "Point size ∝ total commits analyzed · Color = Fisher p significance",
        color=TEXT_HI, fontsize=11, fontweight="bold", pad=10,
    )
    _watermark(fig, total_commits)
    _save(fig, "process_scatter.png")


# ── Figure 5 — Drift Emergence vs. LLM Timeline ───────────────────────────────

def fig_drift_vs_llm_timeline(profiles: list[dict]) -> None:
    """Swimlane + histogram: when did each developer's Level-A signals change,
    relative to LLM milestones?

    Top panel: 9 developer swimlanes. Each needle = one Level-A change point.
      Color = signal type. Height ∝ log(magnitude). Up = signal increased. Down = decreased.
      LLM era background tints + milestone dashed lines overlaid.

    Bottom panel: quarterly histogram of total Level-A change points across all developers.
    """
    SIGNAL_COLORS_LOCAL = {
        "commits_per_week":          "#e74c3c",
        "median_inter_commit_hours": "#e67e22",
        "cross_module_ratio":        "#58a6ff",
        "refactor_ratio":            "#bc8cff",
        "median_files_per_commit":   "#3fb950",
        "large_commit_ratio":        "#f1c40f",
    }

    # LLM eras as tinted background bands
    LLM_ERA_BANDS = [
        (2021.41, 2022.47, "#1f6feb", "Copilot Preview"),
        (2022.47, 2022.91, "#388bfd", "Copilot GA"),
        (2022.91, 2023.20, "#3fb950", "ChatGPT"),
        (2023.20, 2023.97, "#d29922", "GPT-4"),
        (2023.97, 2024.17, "#bc8cff", "Copilot Chat GA"),
        (2024.17, 2026.4,  "#f0883e", "Claude 3+"),
    ]

    n_dev = len(profiles)
    LANE_H = 1.0

    fig = plt.figure(figsize=(15, n_dev * LANE_H + 3.8), facecolor=BG)
    gs = fig.add_gridspec(
        2, 1,
        height_ratios=[n_dev * LANE_H, 2.4],
        hspace=0.0,
        left=0.19, right=0.97,
        top=0.88, bottom=0.13,
    )
    ax_swim = fig.add_subplot(gs[0])
    ax_hist = fig.add_subplot(gs[1], sharex=ax_swim)

    for ax in (ax_swim, ax_hist):
        ax.set_facecolor(BG)
        for sp in ax.spines.values():
            sp.set_edgecolor(BORDER)
        ax.tick_params(colors=TEXT_LO, labelsize=9)

    ax_swim.set_xlim(2017.7, 2026.3)
    ax_swim.set_ylim(n_dev - 0.55, -0.55)   # inverted: 0 at top
    ax_swim.set_yticks([])
    ax_swim.xaxis.set_visible(False)
    ax_swim.grid(axis="x", color=GRID, lw=0.4, alpha=0.5, zorder=1)

    ax_hist.set_facecolor(SURFACE)
    ax_hist.grid(axis="y", color=GRID, lw=0.4, alpha=0.6)
    ax_hist.set_axisbelow(True)

    # ── LLM era background bands ────────────────────────────────────────────────
    x_total = 2026.3 - 2017.7
    for x0, x1, color, label in LLM_ERA_BANDS:
        for ax in (ax_swim, ax_hist):
            ax.axvspan(x0, x1, color=color, alpha=0.07, zorder=0)
        # Label placed just above the swimlane panel using axes-fraction coords
        mid = (x0 + min(x1, 2026.0)) / 2
        x_frac = (mid - 2017.7) / x_total
        ax_swim.text(x_frac, 1.012, label,
                     transform=ax_swim.transAxes,
                     color=color, fontsize=6.8, ha="center", va="bottom",
                     alpha=0.9, fontweight="bold",
                     bbox=dict(boxstyle="round,pad=0.25", facecolor=BG,
                               edgecolor=color, alpha=0.65, linewidth=0.7))

    # LLM milestone dashed lines
    for x, _ in LLM_MILESTONES:
        ax_swim.axvline(x, color=BORDER, lw=0.8, ls="--", alpha=0.45, zorder=2)
        ax_hist.axvline(x, color=BORDER, lw=0.8, ls="--", alpha=0.45, zorder=2)

    # ── Developer swimlanes ─────────────────────────────────────────────────────
    total_commits = 0
    quarter_cp: dict[float, dict[str, int]] = {}

    for i, prof in enumerate(profiles):
        y_ctr = i
        login = prof.get("github_login", "")
        name  = _short_name(prof)
        dr    = prof.get("drift_result")
        fp    = dr["combined_p_value"] if dr else None
        total_commits += prof.get("total_commits_analyzed", 0)

        sig_color = _sig_color(fp)

        # Lane background (alternating)
        ax_swim.axhspan(y_ctr - 0.47, y_ctr + 0.47,
                        color=SURFACE if i % 2 == 0 else BG,
                        alpha=1.0, zorder=0)

        # Significance accent stripe on far left (inside plot area)
        ax_swim.axhspan(y_ctr - 0.47, y_ctr + 0.47,
                        xmin=0.0, xmax=0.004,
                        color=sig_color, alpha=0.9, zorder=3,
                        transform=ax_swim.get_yaxis_transform())

        # Center baseline (thin)
        ax_swim.axhline(y_ctr, color=BORDER, lw=0.5, alpha=0.5,
                        xmin=0.004, zorder=2)

        # Developer name (left of plot)
        ax_swim.text(-0.013, y_ctr - 0.12, name,
                     transform=ax_swim.get_yaxis_transform(),
                     color=TEXT_HI, fontsize=9, fontweight="bold",
                     ha="right", va="center", zorder=6)
        p_str = f"p = {fp:.4f}" if fp else "n/a"
        ax_swim.text(-0.013, y_ctr + 0.22, p_str,
                     transform=ax_swim.get_yaxis_transform(),
                     color=sig_color, fontsize=7.2,
                     ha="right", va="center", zorder=6)

        # ── Change-point needles ──────────────────────────────────────────────
        cps_a = [cp for cp in prof.get("change_points", [])
                 if cp.get("signal_level") == "A"]

        for cp in cps_a:
            x   = _dq(cp["date"])
            sig = cp.get("signal", "")
            mag = float(cp.get("magnitude", 0.0))
            v_after  = float(cp.get("value_after",  0.0))
            v_before = float(cp.get("value_before", 0.0))
            color = SIGNAL_COLORS_LOCAL.get(sig, "#8b949e")

            # Log-scale magnitude → needle height (max ±0.42 of half-lane)
            log_mag = np.log1p(min(mag, 200))
            log_cap = np.log1p(200)
            needle_h = (log_mag / log_cap) * 0.42

            # Up = signal increased, Down = decreased
            direction = -1 if v_after > v_before else +1  # inverted y-axis
            y_tip = y_ctr + direction * needle_h

            ax_swim.plot([x, x], [y_ctr, y_tip],
                         color=color, lw=1.5, alpha=0.88,
                         solid_capstyle="round", zorder=4)
            ax_swim.scatter([x], [y_tip], s=18, color=color,
                            alpha=0.95, zorder=5, linewidths=0)

            # Accumulate for histogram (snap to quarter)
            q = round(x * 4) / 4
            quarter_cp.setdefault(q, {})
            quarter_cp[q][sig] = quarter_cp[q].get(sig, 0) + 1

    # ── Histogram ───────────────────────────────────────────────────────────────
    if quarter_cp:
        sig_order = list(SIGNAL_COLORS_LOCAL.keys())
        quarters  = sorted(quarter_cp.keys())
        bottoms   = np.zeros(len(quarters))

        for sig in sig_order:
            counts = np.array([quarter_cp.get(q, {}).get(sig, 0) for q in quarters],
                               dtype=float)
            if counts.sum() == 0:
                continue
            ax_hist.bar(quarters, counts, bottom=bottoms, width=0.19,
                        color=SIGNAL_COLORS_LOCAL[sig], alpha=0.85,
                        label=sig.replace("_", " "), zorder=3)
            bottoms += counts

        ax_hist.set_ylabel("# change\npoints / quarter", color=TEXT_LO, fontsize=8.5,
                            linespacing=1.3)
        ax_hist.set_xlabel("Year", color=TEXT_LO, fontsize=9)
        ax_hist.set_xticks(range(2018, 2026))
        ax_hist.set_xticklabels([str(y) for y in range(2018, 2026)], color=TEXT_LO)

        legend_handles = [
            plt.Line2D([0], [0], marker="s", color="none",
                       markerfacecolor=SIGNAL_COLORS_LOCAL[s], markersize=8,
                       label=s.replace("_", " "))
            for s in sig_order
            if any(quarter_cp.get(q, {}).get(s, 0) > 0 for q in quarters)
        ]
        ax_hist.legend(handles=legend_handles, ncol=3, loc="upper left",
                       facecolor=SURFACE, edgecolor=BORDER,
                       labelcolor=TEXT_LO, fontsize=7.5,
                       title="Level-A signal", title_fontsize=7.5)

    # ── Legend for needles ──────────────────────────────────────────────────────
    needle_legend = [
        plt.Line2D([0], [0], color=c, lw=2, marker="o", markersize=5,
                   label=s.replace("_", " "))
        for s, c in SIGNAL_COLORS_LOCAL.items()
    ]
    needle_legend += [
        plt.Line2D([0], [0], color=TEXT_LO, lw=0, marker=r"$\uparrow$",
                   markersize=9, label="signal increased"),
        plt.Line2D([0], [0], color=TEXT_LO, lw=0, marker=r"$\downarrow$",
                   markersize=9, label="signal decreased"),
    ]
    # Place legend below the histogram, inside figure bottom margin
    fig.legend(handles=needle_legend, ncol=4,
               loc="lower center", bbox_to_anchor=(0.58, 0.01),
               facecolor=SURFACE, edgecolor=BORDER,
               labelcolor=TEXT_LO, fontsize=8,
               title="Level-A signal  ·  needle height ∝ log(magnitude)",
               title_fontsize=7.5)

    # Honesty note — explicit about correlation vs causation
    fig.text(0.19, 0.01,
             "⚠  Temporal proximity ≠ causation. Each change point has a documented non-AI "
             "explanation (see FINDINGS.md). LLM bands mark release windows for context only.",
             color=TEXT_LO, fontsize=7.2, ha="left", va="bottom", alpha=0.80,
             style="italic")

    fig.suptitle(
        "When did process signals shift? — 9 developers, 5,426 commits, 2018–2025\n"
        "Each needle = one Level-A change point   ↑ signal increased  ↓ decreased   "
        "Shaded bands = LLM release eras  [temporal correlation only — not causal]",
        color=TEXT_HI, fontsize=11, fontweight="bold", y=0.99,
    )
    _watermark(fig, total_commits)
    _save(fig, "drift_vs_llm_timeline.png")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    plt.rcParams.update({
        "font.family":      "DejaVu Sans",
        "font.size":        9,
        "axes.titlesize":   11,
        "axes.labelsize":   10,
        "figure.facecolor": BG,
        "savefig.facecolor": BG,
    })

    profiles = load()
    if not profiles:
        print(f"No profiles with behavior_timeline in {PROFILES_DIR}/")
        print("Run: python run_analysis.py")
        return

    total = sum(p.get("total_commits_analyzed", 0) for p in profiles)
    print(f"Loaded {len(profiles)} profiles ({total:,} commits)")
    print("Generating figures …")

    fig_level_a_heatmap(profiles)
    fig_activity_timeline(profiles)
    fig_changepoint_calendar(profiles)
    fig_process_scatter(profiles)
    fig_drift_vs_llm_timeline(profiles)

    print("Done.")


if __name__ == "__main__":
    main()
