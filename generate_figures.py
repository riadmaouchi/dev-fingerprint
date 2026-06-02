"""Generate all static figures for docs/img/ from real collected profiles.

Run after python run_analysis.py:
    python generate_figures.py

Produces 4 figures — one clear message each:
  fig1_significance.png  — who drifted, ranked by Fisher p
  fig2_stories.png       — three activity trajectories (small multiples)
  fig3_calendar.png      — annual change-point density heatmap
  fig4_dumbbell.png      — commits/week before vs. after
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Design ─────────────────────────────────────────────────────────────────────
BG      = "#0D1117"
SURFACE = "#161B22"
GRID    = "#21262D"
BORDER  = "#30363D"
TEXT_HI = "#E6EDF3"
TEXT_LO = "#8B949E"
DPI     = 160

SIG = {
    "p001": "#e74c3c",
    "p005": "#e67e22",
    "p010": "#f1c40f",
    "ns":   "#3fb950",
    "na":   "#484F58",
}

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

PROFILES_DIR = Path("reports/real")
IMG_DIR      = Path("docs/img")


# ── Helpers ─────────────────────────────────────────────────────────────────────
def _dq(iso: str) -> float:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.year + (dt.month - 1) / 12.0


def load() -> list[dict]:
    profiles = []
    for f in sorted(PROFILES_DIR.glob("*.json")):
        if f.stem == "summary":
            continue
        d = json.loads(f.read_text())
        if "behavior_timeline" in d:
            profiles.append(d)
    profiles.sort(key=lambda p: (
        p.get("drift_result") is None,
        p["drift_result"]["combined_p_value"]
        if p.get("drift_result") else 1.0,
    ))
    return profiles


def _sig_color(p: float | None) -> str:
    if p is None:  return SIG["na"]
    if p < 0.01:   return SIG["p001"]
    if p < 0.05:   return SIG["p005"]
    if p < 0.10:   return SIG["p010"]
    return SIG["ns"]


def _name(profile: dict) -> str:
    name = profile.get("display_name", profile.get("github_login", "?"))
    name = name.split(" (")[0]
    return {"David Heinemeier Hansson": "DHH"}.get(name, name)


def _watermark(fig: plt.Figure, n: int) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fig.text(0.99, 0.005, f"Real GitHub data · {n:,} commits · {today}",
             ha="right", va="bottom", color=TEXT_LO, fontsize=7, alpha=0.6)


def _save(fig: plt.Figure, name: str) -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    path = IMG_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    plt.close(fig)
    print(f"  ✓ {path}  ({path.stat().st_size // 1024} KB)")


def _ax_dark(ax: plt.Axes) -> None:
    ax.set_facecolor(SURFACE)
    for sp in ax.spines.values():
        sp.set_edgecolor(BORDER)
    ax.tick_params(colors=TEXT_LO, labelsize=10)


def _milestone_lines(ax: plt.Axes, ymax: float, label: bool = False) -> None:
    for x, lbl in LLM_MILESTONES:
        ax.axvline(x, color=BORDER, lw=0.9, ls="--", alpha=0.5, zorder=1)
        if label:
            ax.text(x + 0.03, ymax * 0.97, lbl, color=TEXT_LO,
                    fontsize=7, va="top", ha="left", linespacing=1.3, alpha=0.75)


# ── Fig 1: Who drifted? ────────────────────────────────────────────────────────
def fig1_significance(profiles: list[dict]) -> None:
    """Horizontal bar chart — Fisher combined p, one bar per developer.

    Single clear question: who changed the most relative to their own baseline?
    Non-testable developers shown separately with reason.
    """
    testable = [
        (p, p["drift_result"]["combined_p_value"])
        for p in profiles
        if p.get("drift_result") and p["drift_result"].get("combined_p_value") is not None
    ]
    non_testable = [
        p for p in profiles
        if not p.get("drift_result") or p["drift_result"].get("combined_p_value") is None
    ]
    testable.sort(key=lambda x: x[1])   # most significant first

    names   = [_name(p) for p, _ in testable]
    ps      = [v for _, v in testable]
    logps   = [-np.log10(v) for v in ps]
    colors  = [_sig_color(v) for v in ps]

    n_t = len(testable)
    n_nt = len(non_testable)
    total_rows = n_t + n_nt + 0.5

    fig, ax = plt.subplots(figsize=(12, max(5, total_rows * 0.72)), facecolor=BG)
    _ax_dark(ax)

    # ── Bars ─────────────────────────────────────────────────────────────────
    bars = ax.barh(range(n_t), logps, color=colors, alpha=0.88,
                   height=0.55, zorder=3)

    for i, (bar, p, lp) in enumerate(zip(bars, ps, logps)):
        stars = "★★★" if p < 0.01 else ("★" if p < 0.05 else ("~" if p < 0.10 else "—"))
        ax.text(lp + 0.12, i, f"p = {p:.4f}  {stars}",
                va="center", ha="left", color=_sig_color(p),
                fontsize=11, fontweight="bold")

    # Significance thresholds
    for thresh, lbl in [(1.30, "p = 0.05"), (2.0, "p = 0.01")]:
        ax.axvline(thresh, color=TEXT_LO, lw=1.0, ls="--", alpha=0.45, zorder=2)
        ax.text(thresh, -0.55, lbl, color=TEXT_LO, fontsize=8.5,
                ha="center", va="top", alpha=0.8)

    # ── Non-testable ─────────────────────────────────────────────────────────
    NT_REASONS = {
        "Linus Torvalds": "8 windows only — Q4 merge-window clustering artifact",
        "Salvatore Sanfilippo": "3-year gap 2021–2024 — structural absence, not drift",
    }
    for j, p in enumerate(non_testable):
        y = n_t + j + 0.3
        ax.barh([y], [0.08], color=SIG["na"], alpha=0.5, height=0.45)
        reason = NT_REASONS.get(_name(p), "< 10 quarterly windows")
        ax.text(0.2, y, f"{_name(p)}  —  not testable:  {reason}",
                va="center", ha="left", color=TEXT_LO,
                fontsize=10, style="italic")

    # ── Axes & labels ─────────────────────────────────────────────────────────
    ax.set_yticks(range(n_t))
    ax.set_yticklabels(names, fontsize=12.5, color=TEXT_HI)
    ax.set_ylim(-0.65, n_t + n_nt + 0.1)
    ax.invert_yaxis()
    ax.set_xlabel("− log₁₀ (Fisher combined p-value)", color=TEXT_LO, fontsize=11)
    ax.set_xlim(0, max(logps) * 1.55)
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.8, zorder=0)
    ax.set_axisbelow(True)

    legend_items = [
        mpatches.Patch(color=SIG["p001"], label="p < 0.01  ★★★  strong drift"),
        mpatches.Patch(color=SIG["p005"], label="p < 0.05  ★    moderate drift"),
        mpatches.Patch(color=SIG["p010"], label="p < 0.10  ~    marginal"),
        mpatches.Patch(color=SIG["ns"],   label="p > 0.10  —    no significant drift"),
    ]
    ax.legend(handles=legend_items, loc="lower right",
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=9.5, framealpha=0.9)

    ax.set_title(
        "Mann-Whitney U per Level-A signal · Fisher combined p · "
        "self-baseline comparison (historical vs. last 4 quarters)",
        color=TEXT_LO, fontsize=9.5, pad=8,
    )
    fig.suptitle("How much did each developer's commit process change?",
                 color=TEXT_HI, fontsize=14, fontweight="bold", y=1.015)

    _watermark(fig, sum(p.get("total_commits_analyzed", 0) for p in profiles))
    _save(fig, "fig1_significance.png")


# ── Fig 2: Three stories ───────────────────────────────────────────────────────
def fig2_stories(profiles: list[dict]) -> None:
    """Small multiples — 3 representative commits/week trajectories.

    Left:   Dan Abramov  — activity withdrawal (p = 0.0002)
    Center: Rich Harris  — process stability   (p = 0.248)
    Right:  Ryan Dahl    — moderate decline    (p = 0.077)

    These three cover the full range of findings.
    """
    STORIES = [
        ("gaearon",    "Dan Abramov",  "Activity withdrawal\np = 0.0002  ★★★"),
        ("Rich-Harris","Rich Harris",  "Process stability\np = 0.248   —"),
        ("ry",         "Ryan Dahl",    "Moderate decline\np = 0.077   ~"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), facecolor=BG,
                             sharey=False)
    fig.subplots_adjust(wspace=0.18, left=0.06, right=0.97,
                        top=0.82, bottom=0.12)

    by_login = {p.get("github_login", p.get("login", "")): p for p in profiles}

    for ax, (login, label, subtitle) in zip(axes, STORIES):
        _ax_dark(ax)
        prof = by_login.get(login)
        if not prof:
            continue

        tl    = prof.get("behavior_timeline", [])
        color = DEV_COLORS.get(login, "#8b949e")
        dr    = prof.get("drift_result")
        fp    = dr["combined_p_value"] if dr else None

        xs = [_dq(w["period_start"]) for w in tl]
        ys = [w.get("commits_per_week", 0.0) for w in tl]

        ax.fill_between(xs, ys, alpha=0.18, color=color, zorder=1)
        ax.plot(xs, ys, color=color, lw=2.2, solid_capstyle="round", zorder=3)

        ymax = max(ys) if ys else 1.0
        _milestone_lines(ax, ymax)

        ax.set_xlim(2018, 2026)
        ax.set_ylim(0, ymax * 1.25)
        ax.set_xticks(range(2018, 2026, 2))
        ax.set_xticklabels([str(y) for y in range(2018, 2026, 2)],
                           color=TEXT_LO, fontsize=10)
        ax.grid(axis="y", color=GRID, lw=0.5, alpha=0.6)
        ax.set_axisbelow(True)

        ax.set_title(subtitle, color=_sig_color(fp), fontsize=11,
                     fontweight="bold", pad=10, linespacing=1.5)
        ax.set_xlabel("Year", color=TEXT_LO, fontsize=10)

        if ax is axes[0]:
            ax.set_ylabel("commits / week  (quarterly median)",
                          color=TEXT_LO, fontsize=10)

        # Developer name inside panel
        ax.text(0.04, 0.96, label, transform=ax.transAxes,
                color=TEXT_HI, fontsize=12, fontweight="bold",
                va="top", ha="left")

        # Key change-point annotation (commits_per_week only)
        cps = [cp for cp in prof.get("change_points", [])
               if cp.get("signal") == "commits_per_week"
               and cp.get("signal_level") == "A"]
        for cp in cps[:3]:
            x_cp = _dq(cp["date"])
            ax.axvline(x_cp, color=color, lw=1.2, ls=":", alpha=0.7, zorder=2)

    # Shared LLM milestone legend
    milestone_handles = [
        plt.Line2D([0], [0], color=BORDER, lw=1.2, ls="--",
                   label=lbl.replace("\n", " "))
        for _, lbl in LLM_MILESTONES
    ]
    axes[1].legend(handles=milestone_handles, loc="upper right",
                   facecolor=SURFACE, edgecolor=BORDER,
                   labelcolor=TEXT_LO, fontsize=8, ncol=2,
                   title="LLM milestones (for reference — not causal)",
                   title_fontsize=7.5)

    fig.suptitle(
        "Three representative trajectories — commits / week, 2018–2025\n"
        "Dotted verticals = detected change points on commits/week",
        color=TEXT_HI, fontsize=13, fontweight="bold",
    )
    _watermark(fig, sum(p.get("total_commits_analyzed", 0) for p in profiles))
    _save(fig, "fig2_stories.png")


# ── Fig 3: Annual change-point heatmap ────────────────────────────────────────
def fig3_calendar(profiles: list[dict]) -> None:
    """Annual heatmap: how many Level-A change points per developer per year?

    Simple grid, one cell = one year × one developer.
    Color intensity = number of Level-A CPs that calendar year.
    Honest caveat: antirez 2025 is a return-from-gap artifact, not a trend.
    """
    years  = list(range(2018, 2026))
    names  = [_name(p) for p in profiles]
    n_dev  = len(profiles)
    n_yr   = len(years)

    matrix = np.zeros((n_dev, n_yr), dtype=int)
    for i, prof in enumerate(profiles):
        cps_a = [cp for cp in prof.get("change_points", [])
                 if cp.get("signal_level") == "A"]
        for cp in cps_a:
            yr = datetime.fromisoformat(cp["date"].replace("Z", "+00:00")).year
            if yr in years:
                j = years.index(yr)
                matrix[i, j] += 1

    fig, ax = plt.subplots(figsize=(12, 5.5), facecolor=BG)
    ax.set_facecolor(BG)
    for sp in ax.spines.values():
        sp.set_edgecolor(BORDER)

    # ── LLM milestone background shading ────────────────────────────────────
    LLM_ERA_COLS = {
        2021: "#1f6feb",   # Copilot Preview
        2022: "#3fb950",   # ChatGPT / Copilot GA
        2023: "#d29922",   # GPT-4
        2024: "#f0883e",   # Copilot Chat / Claude 3
        2025: "#bc8cff",   # ongoing
    }
    for yr, color in LLM_ERA_COLS.items():
        if yr in years:
            j = years.index(yr)
            ax.axvspan(j - 0.5, j + 0.5, color=color, alpha=0.08, zorder=0)

    # ── Heatmap cells ────────────────────────────────────────────────────────
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list(
        "cp_heat", [SURFACE, "#e67e22", "#e74c3c"], N=256
    )

    for i in range(n_dev):
        for j in range(n_yr):
            v = matrix[i, j]
            intensity = min(v / 4.0, 1.0)  # 4+ = full saturation
            facecolor = cmap(intensity)
            rect = plt.Rectangle((j - 0.45, i - 0.42), 0.9, 0.84,
                                  facecolor=facecolor, edgecolor=BORDER,
                                  linewidth=0.5, zorder=2)
            ax.add_patch(rect)
            if v > 0:
                text_color = "white" if intensity > 0.35 else TEXT_LO
                ax.text(j, i, str(v), ha="center", va="center",
                        fontsize=11, color=text_color, fontweight="bold",
                        zorder=3)

    # Developer row labels
    ax.set_yticks(range(n_dev))
    ax.set_yticklabels(names, fontsize=11, color=TEXT_HI)

    # Year labels + LLM event marks
    ax.set_xticks(range(n_yr))
    ax.set_xticklabels([str(y) for y in years], fontsize=11, color=TEXT_LO)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")

    # LLM milestone lines between year columns
    LLM_YEAR_LINES = {
        "Copilot Preview (Jun 2021)":   2021.0,
        "ChatGPT (Nov 2022)":           2022.0,
        "GPT-4 (Mar 2023)":             2023.0,
        "Claude 3 (Mar 2024)":          2024.0,
    }
    for lbl, yr in LLM_YEAR_LINES.items():
        if yr in years:
            j = years.index(int(yr))
            ax.axvline(j - 0.5, color=TEXT_LO, lw=1.2, ls="--",
                       alpha=0.4, zorder=4)

    ax.set_xlim(-0.55, n_yr - 0.45)
    ax.set_ylim(-0.6, n_dev - 0.4)
    ax.invert_yaxis()
    ax.tick_params(colors=TEXT_LO, length=0)

    # Colorbar (manual legend instead of a full colorbar)
    for count, label in [(0, "0"), (1, "1"), (2, "2"), (3, "3"), ("4+", "4+")]:
        v_int = min(int(str(count).rstrip("+")), 4) if str(count).rstrip("+").isdigit() else 4
        intensity = min(v_int / 4.0, 1.0)
        ax.add_patch(plt.Rectangle(
            (-0.55 + (int(str(count).rstrip("+")) if str(count).rstrip("+").isdigit() else 4) * 0.0,
             n_dev + 0.05), 0, 0,  # invisible; legend via text below
            facecolor=cmap(intensity)))

    # Honest footnote about antirez
    fig.text(0.01, 0.01,
             "⚠  antirez 2025: 11 change points = return after 3-year gap (2021–2024), "
             "not a continuous drift signal.  Torvalds: only 8 windows (Q4 only), not testable.",
             color=TEXT_LO, fontsize=8, ha="left", va="bottom",
             style="italic", alpha=0.8)

    # Color scale legend
    legend_handles = [
        mpatches.Patch(facecolor=cmap(min(k / 4.0, 1.0)), edgecolor=BORDER,
                       label=f"{k} Level-A change point{'s' if k != 1 else ''} that year")
        for k in [0, 1, 2, 3, 4]
    ]
    legend_handles[-1].set_label("4+ change points that year")
    ax.legend(handles=legend_handles, loc="lower right",
              bbox_to_anchor=(1.0, -0.22), ncol=5,
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=9)

    fig.suptitle(
        "Level-A change points per developer per year  —  shaded columns = LLM release years",
        color=TEXT_HI, fontsize=13, fontweight="bold", y=1.06,
    )
    _watermark(fig, sum(p.get("total_commits_analyzed", 0) for p in profiles))
    _save(fig, "fig3_calendar.png")


# ── Fig 4: Before vs. After dumbbell ─────────────────────────────────────────
def fig4_dumbbell(profiles: list[dict]) -> None:
    """Dumbbell chart: commits/week in historical baseline vs. last 4 quarters.

    Open circle = baseline mean. Filled circle = recent mean.
    Line connecting them shows direction and magnitude.
    Only testable developers (those with drift_result).

    Note: the 120 commits/year collection cap means baseline values
    may underestimate true historical frequency. The direction is reliable;
    exact magnitudes should be read from reports/real/*.json.
    """
    rows = []
    for prof in profiles:
        dr = prof.get("drift_result")
        if not dr:
            continue
        sigs = {s["signal"]: s for s in dr.get("signals", [])}
        cpw = sigs.get("commits_per_week")
        if not cpw:
            continue
        rows.append({
            "name":     _name(prof),
            "login":    prof.get("github_login", ""),
            "baseline": cpw["baseline_mean"],
            "recent":   cpw["recent_mean"],
            "p":        dr.get("combined_p_value"),
        })

    # Sort by baseline descending
    rows.sort(key=lambda r: r["baseline"], reverse=True)

    fig, ax = plt.subplots(figsize=(11, 6), facecolor=BG)
    _ax_dark(ax)

    y_pos = list(range(len(rows)))

    for y, row in zip(y_pos, rows):
        b, r = row["baseline"], row["recent"]
        color = _sig_color(row["p"])

        # Line
        ax.plot([b, r], [y, y], color=color, lw=2.0, alpha=0.7,
                solid_capstyle="round", zorder=2)
        # Baseline (open circle)
        ax.scatter([b], [y], s=80, color=color, alpha=0.5,
                   facecolors="none", edgecolors=color, lw=2.0,
                   zorder=3)
        # Recent (filled circle)
        ax.scatter([r], [y], s=90, color=color, alpha=0.95,
                   zorder=4, edgecolors="white", linewidths=0.5)

        # Δ% label
        if b > 0:
            pct = (r - b) / b * 100
            sign = "+" if pct > 0 else ""
            ax.text(max(b, r) + 0.08, y, f"  {sign}{pct:.0f}%",
                    va="center", ha="left", color=color,
                    fontsize=9.5, fontweight="bold")

    ax.set_yticks(y_pos)
    ax.set_yticklabels([r["name"] for r in rows],
                       fontsize=11.5, color=TEXT_HI)
    ax.invert_yaxis()
    ax.set_xlabel("commits / week  (quarterly median)", color=TEXT_LO, fontsize=11)
    ax.grid(axis="x", color=GRID, lw=0.5, alpha=0.7, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlim(-0.15, max(r["baseline"] for r in rows) * 1.45)

    legend_items = [
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor="none", markeredgecolor=TEXT_LO,
                   markeredgewidth=2.0, markersize=10,
                   label="historical baseline mean"),
        plt.Line2D([0], [0], marker="o", color="none",
                   markerfacecolor=TEXT_HI, markeredgecolor="white",
                   markeredgewidth=0.5, markersize=10,
                   label="recent mean (last 4 quarters)"),
        mpatches.Patch(color=SIG["p001"], label="p < 0.01"),
        mpatches.Patch(color=SIG["p005"], label="p < 0.05"),
        mpatches.Patch(color=SIG["p010"], label="p < 0.10"),
        mpatches.Patch(color=SIG["ns"],   label="no significant drift"),
    ]
    ax.legend(handles=legend_items, loc="lower right",
              facecolor=SURFACE, edgecolor=BORDER,
              labelcolor=TEXT_LO, fontsize=9.5, ncol=2)

    fig.text(0.01, 0.01,
             "Note: collection cap = 120 commits/year. Baseline values may "
             "underestimate true historical frequency. Direction is reliable; "
             "see reports/real/*.json for full signal breakdown.",
             color=TEXT_LO, fontsize=7.5, ha="left", va="bottom",
             style="italic", alpha=0.75)

    ax.set_title(
        "Open circle = historical baseline · Filled = last 4 quarters · "
        "Color = Fisher p significance",
        color=TEXT_LO, fontsize=9.5, pad=8,
    )
    fig.suptitle("Commits / week: historical baseline vs. recent",
                 color=TEXT_HI, fontsize=14, fontweight="bold", y=1.01)

    _watermark(fig, sum(p.get("total_commits_analyzed", 0) for p in profiles))
    _save(fig, "fig4_dumbbell.png")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    plt.rcParams.update({
        "font.family":       "DejaVu Sans",
        "font.size":         10,
        "axes.titlesize":    12,
        "axes.labelsize":    11,
        "figure.facecolor":  BG,
        "savefig.facecolor": BG,
    })

    profiles = load()
    if not profiles:
        print(f"No profiles in {PROFILES_DIR}/  —  run: python run_analysis.py")
        return

    total = sum(p.get("total_commits_analyzed", 0) for p in profiles)
    print(f"Loaded {len(profiles)} profiles  ({total:,} commits)")
    print("Generating figures …")

    fig1_significance(profiles)
    fig2_stories(profiles)
    fig3_calendar(profiles)
    fig4_dumbbell(profiles)

    print("Done.")


if __name__ == "__main__":
    main()
