"""Regenerate all static figures for docs/img/ from real collected profiles.

Run AFTER python run_analysis.py has completed:
    python generate_figures.py

Reads:  reports/real/*.json   (computed by run_analysis.py from GitHub API data)
Writes: docs/img/timeline.png
        docs/img/drift_comparison.png
        docs/img/radar.png
        docs/img/signals.png      ← per-signal trends (new)

Each figure embeds a "Data collected YYYY-MM-DD" annotation for auditability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Design system ─────────────────────────────────────────────────────────────

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

# GitHub-dark palette — one colour per developer
PALETTE = {
    "torvalds":     "#8B949E",   # muted grey — organic control
    "dhh":          "#8B949E",
    "antirez":      "#8B949E",
    "tj":           "#8B949E",
    "gaearon":      "#E3B341",   # amber — moderate drift
    "gvanrossum":   "#E3B341",
    "Rich-Harris":  "#FF7B72",   # red-orange — high drift
    "yyx990803":    "#D2A8FF",   # purple
    "ry":           "#58A6FF",   # blue
    "sindresorhus": "#3FB950",   # green
}

MILESTONES = {
    "Copilot\nPreview": 2021.49,
    "Copilot GA":       2022.47,
    "ChatGPT":          2022.91,
    "GPT-4":            2023.20,
}

RESULTS_DIR = Path("docs/img")
PROFILES_DIR = Path("reports/real")

# ── Data loading ──────────────────────────────────────────────────────────────

def _decimal_quarter(period_start: str) -> float:
    """Convert '2022-07-01T00:00:00Z' → 2022.5"""
    dt = datetime.fromisoformat(period_start.replace("Z", "+00:00"))
    return dt.year + (dt.month - 1) / 12.0


def load_profiles() -> dict[str, dict]:
    """Load all real JSON profiles. Returns {login: profile_dict}."""
    profiles = {}
    for f in sorted(PROFILES_DIR.glob("*.json")):
        if f.stem == "summary":
            continue
        d = json.loads(f.read_text())
        if d.get("score_timeline"):
            profiles[d["github_login"]] = d
    return profiles


def _drift(profile: dict) -> tuple[float | None, float | None, float | None]:
    qs = profile.get("score_timeline", [])
    pre  = [q["llm_score"] for q in qs if q["period_start"] < "2022-06-01"]
    post = [q["llm_score"] for q in qs if q["period_start"] >= "2022-06-01"]
    if not pre or not post:
        return None, None, None
    b = sum(pre) / len(pre)
    p = sum(post) / len(post)
    return round(b, 1), round(p, 1), round(p - b, 1)


def _collection_date(profiles: dict[str, dict]) -> str:
    """Infer the collection date from the latest last_commit_date across profiles."""
    dates = [
        p.get("last_commit_date", "")
        for p in profiles.values()
        if p.get("last_commit_date")
    ]
    return max(dates)[:10] if dates else datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def _watermark(ax: plt.Axes, collection_date: str, n_commits: int) -> None:
    ax.text(
        0.99, 0.01,
        f"Real GitHub data  ·  collected {collection_date}  ·  {n_commits:,} commits",
        transform=ax.transAxes, ha="right", va="bottom",
        color=THEME["text_muted"], fontsize=7, alpha=0.7,
    )


def _save(fig: plt.Figure, name: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / name
    fig.savefig(path, dpi=THEME["dpi"], bbox_inches="tight",
                facecolor=THEME["bg"], edgecolor="none")
    plt.close(fig)
    kb = path.stat().st_size // 1024
    print(f"  ✓ {path}  ({kb} KB)")


# ── Figure 1 — LLM Score Timeline ─────────────────────────────────────────────

def fig_timeline(profiles: dict[str, dict], collection_date: str) -> None:
    """Timeline: one line per developer, milestone verticals, threshold bands."""

    # Pick developers with at least 8 quarters spanning both eras
    eligible = {
        login: p for login, p in profiles.items()
        if len([q for q in p["score_timeline"] if q["period_start"] < "2022-06-01"]) >= 2
        and len([q for q in p["score_timeline"] if q["period_start"] >= "2022-06-01"]) >= 2
    }

    if not eligible:
        print("  [SKIP] timeline — not enough profiles with pre+post data yet")
        return

    fig, ax = plt.subplots(figsize=(11, 5.5))
    fig.patch.set_facecolor(THEME["bg"])
    _ax_style(ax, xlabel="Year", ylabel="LLM Influence Score (0–100)")

    # Threshold bands
    ax.axhspan(40, 70,  alpha=0.06, color="#E3B341", zorder=0)
    ax.axhspan(70, 100, alpha=0.06, color="#FF7B72", zorder=0)

    # Milestone verticals
    for x, label in MILESTONES.items():
        ax.axvline(label, color=THEME["spine"], lw=0.8, ls="--", zorder=1)
        ax.text(label + 0.02, 96, x, color=THEME["text_muted"], fontsize=7,
                va="top", ha="left", linespacing=1.3)

    total_commits = 0
    for login, p in sorted(eligible.items()):
        qs = sorted(p["score_timeline"], key=lambda q: q["period_start"])
        xs = [_decimal_quarter(q["period_start"]) for q in qs]
        ys = [q["llm_score"] for q in qs]
        color = PALETTE.get(login, "#8B949E")
        name = p["display_name"].split(" (")[0].split(" — ")[0][:20]

        # Smooth only if enough points
        ax.plot(xs, ys, color=color, lw=2.0, zorder=3, solid_capstyle="round",
                marker="o", markersize=3, markerfacecolor=color)
        ax.fill_between(xs, ys, alpha=0.08, color=color, zorder=2)
        ax.text(xs[-1] + 0.08, ys[-1], name, color=color,
                fontsize=8.5, va="center", fontweight="bold")
        total_commits += p.get("total_commits_analyzed", 0)

    # Change-point markers
    for login, p in eligible.items():
        color = PALETTE.get(login, "#8B949E")
        for cp in p.get("change_points", []):
            cp_date = cp["date"] if "T" in cp["date"] else cp["date"] + "T00:00:00Z"
            cp_x = _decimal_quarter(cp_date)
            ax.axvline(cp_x, color=color, lw=0.6, ls=":", alpha=0.5, zorder=1)
            ax.annotate("▼", xy=(cp_x, 98), color=color,
                        fontsize=9, ha="center", va="top", zorder=4)

    # Zone labels
    ax.text(2018.1, 55, "Ambiguous", color="#E3B341", fontsize=7.5, va="center", alpha=0.8)
    ax.text(2018.1, 85, "LLM-influenced", color="#FF7B72", fontsize=7.5, va="center", alpha=0.8)
    ax.text(2018.1, 20, "Organic", color="#3FB950", fontsize=7.5, va="center", alpha=0.8)

    ax.set_xlim(2017.8, max(
        max(_decimal_quarter(q["period_start"]) for p in eligible.values() for q in p["score_timeline"]),
        2025.0,
    ) + 0.8)
    ax.set_ylim(0, 100)
    years = list(range(2018, 2026))
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years])

    ax.set_title(
        "LLM Influence Score timeline — real GitHub commit data\n"
        "▼ = detected style change point  ·  dashed = LLM milestones",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )
    _watermark(ax, collection_date, total_commits)
    _save(fig, "timeline.png")


# ── Figure 2 — Drift Comparison ───────────────────────────────────────────────

def fig_drift_comparison(profiles: dict[str, dict], collection_date: str) -> None:
    """Horizontal bar: baseline vs post-LLM, sorted by drift."""

    rows = []
    for login, p in profiles.items():
        b, post, d = _drift(p)
        if b is None:
            continue
        rows.append({
            "login": login,
            "name": p["display_name"].split(" (")[0][:24],
            "baseline": b,
            "post": post,
            "drift": d,
            "cp": p.get("change_points", []),
            "commits": p.get("total_commits_analyzed", 0),
        })

    if not rows:
        print("  [SKIP] drift_comparison — no profiles with pre+post data")
        return

    rows.sort(key=lambda r: r["drift"])

    names    = [r["name"]     for r in rows]
    baseline = [r["baseline"] for r in rows]
    post     = [r["post"]     for r in rows]
    drifts   = [r["drift"]    for r in rows]

    bar_colors = [
        PALETTE.get(r["login"], "#8B949E")
        for r in rows
    ]

    fig, ax = plt.subplots(figsize=(10, max(4, len(rows) * 0.6)))
    fig.patch.set_facecolor(THEME["bg"])
    _ax_style(ax, xlabel="LLM Influence Score (0–100)")

    y = np.arange(len(names))
    bar_h = 0.38

    ax.barh(y + bar_h / 2, baseline, height=bar_h * 0.6,
            color=THEME["grid"], zorder=3, label="Pre-LLM baseline")
    ax.barh(y - bar_h / 2, post, height=bar_h,
            color=bar_colors, zorder=3, label="Post-LLM era")

    for i, (r, p_val) in enumerate(zip(rows, post)):
        sign = "+" if r["drift"] >= 0 else ""
        cp_str = ""
        if r["cp"]:
            cp_str = f"  [{r['cp'][0]['date'][:7]}]"
        ax.text(p_val + 0.6, i - bar_h / 2,
                f"{sign}{r['drift']:.1f}{cp_str}",
                color=bar_colors[i], fontsize=8, va="center",
                fontweight="bold" if abs(r["drift"]) >= 5 else "normal")

    ax.axvline(40, color="#E3B341", lw=0.8, ls="--", alpha=0.6, zorder=2)
    ax.axvline(70, color="#FF7B72", lw=0.8, ls="--", alpha=0.6, zorder=2)
    ax.text(40.5, len(names) - 0.3, "40", color="#E3B341", fontsize=7.5)
    ax.text(70.5, len(names) - 0.3, "70", color="#FF7B72", fontsize=7.5)

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=9, color=THEME["text_primary"])
    ax.set_xlim(0, max(max(post) + 15, 85))

    legend_elements = [
        mpatches.Patch(color=THEME["grid"],        label="Pre-LLM baseline (pre Jun 2022)"),
        mpatches.Patch(color="#FF7B72",             label="Post-LLM era score"),
    ]
    ax.legend(handles=legend_elements, loc="lower right",
              facecolor=THEME["surface"], edgecolor=THEME["spine"],
              labelcolor=THEME["text_muted"], fontsize=8)

    total = sum(r["commits"] for r in rows)
    ax.set_title(
        "Style drift — pre vs post Copilot GA (Jun 2022)\n"
        "Annotation: detected change-point quarter",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )
    _watermark(ax, collection_date, total)
    _save(fig, "drift_comparison.png")


# ── Figure 3 — Per-signal heatmap ────────────────────────────────────────────

def fig_radar(profiles: dict[str, dict], collection_date: str) -> None:
    """Diverging heatmap: per-signal % deviation from organic baseline.

    Organic baseline = mean of developers with |drift| < 5 pts.
    """
    signals = ["comment_score", "docstring_score", "verbosity_score",
               "error_handling_score", "commit_style_score"]
    labels  = ["Comments", "Docstrings", "Verbosity", "Error hdlg", "Conv. commit"]

    # Compute latest-quarter signal averages per developer
    dev_signals: dict[str, dict[str, float]] = {}
    for login, p in profiles.items():
        post_qs = [q for q in p["score_timeline"] if q["period_start"] >= "2022-06-01"]
        if not post_qs:
            continue
        avgs = {sig: sum(q[sig] for q in post_qs) / len(post_qs) for sig in signals}
        dev_signals[login] = avgs

    if len(dev_signals) < 2:
        print("  [SKIP] radar — not enough post-LLM data")
        return

    # Organic baseline = mean of low-drift devs
    low_drift = [
        login for login in dev_signals
        if profiles[login].get("change_points") == []
        or (_drift(profiles[login])[2] or 99) < 5
    ]
    if not low_drift:
        low_drift = list(dev_signals.keys())[:2]

    organic: dict[str, float] = {
        sig: sum(dev_signals[l][sig] for l in low_drift) / len(low_drift)
        for sig in signals
    }

    # Build matrix (all devs including organic baseline row)
    devs_ordered = sorted(dev_signals.keys(),
                          key=lambda l: _drift(profiles[l])[2] or 0)
    rows_data = []
    row_labels = []
    for login in devs_ordered:
        row = [(dev_signals[login][sig] - organic[sig]) * 100 for sig in signals]
        rows_data.append(row)
        name = profiles[login]["display_name"].split(" (")[0][:18]
        row_labels.append(name)

    matrix = np.array(rows_data)

    fig, ax = plt.subplots(figsize=(9, max(3, len(devs_ordered) * 0.55 + 1.2)))
    fig.patch.set_facecolor(THEME["bg"])
    ax.set_facecolor(THEME["surface"])

    vmax = max(60, float(np.abs(matrix).max()) * 0.9)
    im = ax.imshow(matrix, cmap=plt.cm.RdBu_r, vmin=-vmax, vmax=vmax, aspect="auto")

    for i in range(len(devs_ordered)):
        for j in range(len(signals)):
            val = matrix[i, j]
            text_color = "white" if abs(val) > vmax * 0.5 else THEME["text_primary"]
            sign = "+" if val >= 0 else ""
            ax.text(j, i, f"{sign}{val:.0f}%",
                    ha="center", va="center", fontsize=9,
                    color=text_color, fontweight="bold")

    ax.set_xticks(range(len(signals)))
    ax.set_xticklabels(labels, fontsize=THEME["label_size"], color=THEME["text_primary"])
    ax.set_yticks(range(len(devs_ordered)))
    ax.set_yticklabels(row_labels, fontsize=9, color=THEME["text_primary"])

    for spine in ax.spines.values():
        spine.set_edgecolor(THEME["spine"])
    ax.tick_params(colors=THEME["tick"])
    for x in np.arange(-0.5, len(signals), 1):
        ax.axvline(x, color=THEME["grid"], lw=0.6)
    for y in np.arange(-0.5, len(devs_ordered), 1):
        ax.axhline(y, color=THEME["grid"], lw=0.6)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Deviation from organic baseline (%pts)",
                   color=THEME["text_muted"], fontsize=8)
    cbar.ax.tick_params(colors=THEME["tick"], labelsize=8)
    cbar.outline.set_edgecolor(THEME["spine"])

    ax.set_title(
        "Style signal fingerprint — deviation from organic baseline (post-LLM era)\n"
        "Red = more LLM-like  ·  Blue = less",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        pad=10, fontweight="semibold",
    )
    total = sum(p.get("total_commits_analyzed", 0) for p in profiles.values())
    _watermark(ax, collection_date, total)
    _save(fig, "radar.png")


# ── Figure 4 — Per-signal trends ─────────────────────────────────────────────

def fig_signals(profiles: dict[str, dict], collection_date: str) -> None:
    """Small multiples: one panel per signal, all developers overlaid.

    Reveals which specific signals drive drift (or not) without the composite
    score masking individual movement.
    """
    signals = [
        ("comment_score",       "Comment density"),
        ("docstring_score",     "Docstring coverage"),
        ("commit_style_score",  "Conventional commits"),
        ("verbosity_score",     "Identifier verbosity"),
        ("error_handling_score","Error handling"),
    ]

    # Only developers with >= 6 quarters total
    eligible = {
        login: p for login, p in profiles.items()
        if len(p["score_timeline"]) >= 6
    }
    if not eligible:
        print("  [SKIP] signals — not enough profiles")
        return

    fig, axes = plt.subplots(1, len(signals), figsize=(14, 4.2), sharey=False)
    fig.patch.set_facecolor(THEME["bg"])

    copilot_ga = 2022.47

    for ax, (sig_key, sig_label) in zip(axes, signals):
        _ax_style(ax, title=sig_label)
        ax.axvline(copilot_ga, color=THEME["spine"], lw=0.8, ls="--", zorder=1)
        ax.axhline(0, color=THEME["spine"], lw=0.4, zorder=1)

        for login, p in eligible.items():
            qs = sorted(p["score_timeline"], key=lambda q: q["period_start"])
            xs = [_decimal_quarter(q["period_start"]) for q in qs]
            ys = [q[sig_key] * 100 for q in qs]   # → percentage
            color = PALETTE.get(login, "#8B949E")
            lw = 2.2 if login == "Rich-Harris" else 1.2
            alpha = 0.95 if login == "Rich-Harris" else 0.55
            ax.plot(xs, ys, color=color, lw=lw, alpha=alpha,
                    solid_capstyle="round", zorder=3)

        ax.set_ylabel("% of commits", fontsize=8)
        ax.yaxis.label.set_color(THEME["text_muted"])
        years = list(range(2018, 2026))
        ax.set_xticks([y for y in years if y % 2 == 0])
        ax.set_xticklabels([str(y) for y in years if y % 2 == 0], fontsize=8)
        ax.tick_params(labelsize=8)

    # Shared legend
    handles = [
        plt.Line2D([0], [0], color=PALETTE.get(login, "#8B949E"),
                   lw=2 if login == "Rich-Harris" else 1.2,
                   label=p["display_name"].split(" (")[0][:20])
        for login, p in sorted(eligible.items())
    ]
    fig.legend(handles=handles, loc="lower center", ncol=min(len(eligible), 5),
               facecolor=THEME["surface"], edgecolor=THEME["spine"],
               labelcolor=THEME["text_muted"], fontsize=8,
               bbox_to_anchor=(0.5, -0.08))

    fig.suptitle(
        "Per-signal trends over time — dashed line = Copilot GA (Jun 2022)",
        color=THEME["text_primary"], fontsize=THEME["title_size"],
        fontweight="semibold", y=1.02,
    )

    total = sum(p.get("total_commits_analyzed", 0) for p in eligible.values())
    axes[-1].text(
        1.0, -0.18,
        f"Real GitHub data  ·  collected {collection_date}  ·  {total:,} commits",
        transform=axes[-1].transAxes, ha="right", va="bottom",
        color=THEME["text_muted"], fontsize=7, alpha=0.7,
    )

    _save(fig, "signals.png")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    plt.rcParams.update({
        "font.family":      "sans-serif",
        "font.size":        THEME["tick_size"],
        "axes.titlesize":   THEME["title_size"],
        "axes.labelsize":   THEME["label_size"],
        "figure.facecolor": THEME["bg"],
    })

    profiles = load_profiles()
    if not profiles:
        print(f"No profiles found in {PROFILES_DIR}/")
        print("Run: python run_analysis.py")
        return

    total_commits = sum(p.get("total_commits_analyzed", 0) for p in profiles.values())
    collection_date = _collection_date(profiles)
    print(f"Loaded {len(profiles)} profiles  ({total_commits:,} total commits)")
    print(f"Collection date: {collection_date}")
    print("Generating figures …")

    fig_timeline(profiles, collection_date)
    fig_drift_comparison(profiles, collection_date)
    fig_radar(profiles, collection_date)
    fig_signals(profiles, collection_date)

    print("Done.")


if __name__ == "__main__":
    main()
