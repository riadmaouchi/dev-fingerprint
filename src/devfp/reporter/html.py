"""HTML report generator using Plotly."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from devfp.analyzer.temporal import compute_drift
from devfp.models import BehaviorWindow, DevProfile, LLM_MILESTONES, SIGNAL_LABELS


def _add_milestones(fig: go.Figure, row: int = 1, col: int = 1) -> None:
    """Annotate LLM milestones as vertical dotted lines (informational only)."""
    for label, dt in LLM_MILESTONES.items():
        fig.add_vline(
            x=dt.timestamp() * 1000,
            line_dash="dot",
            line_color="rgba(150,150,150,0.5)",
            annotation_text=label.split(" ")[0],
            annotation_textangle=-90,
            annotation_font_size=9,
            row=row,
            col=col,
        )


def build_timeline_chart(profile: DevProfile) -> go.Figure:
    """
    Four-panel chart:
      1. Level A process signals (primary evidence)
      2. Change points annotation
      3. Level B process signals
      4. Level C style score (baseline comparison)
    """
    windows = sorted(profile.behavior_timeline, key=lambda w: w.period_start)
    if not windows:
        return go.Figure()

    dates = [w.period_start for w in windows]

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        subplot_titles=(
            f"Process Signals (Level A) — {profile.display_name}",
            "Process Signals (Level B)",
            "Style Score (Level C — baseline only, not primary evidence)",
        ),
        vertical_spacing=0.08,
        row_heights=[0.45, 0.25, 0.30],
    )

    # ── Row 1: Level A signals ────────────────────────────────────────────────
    level_a_signals = [
        ("median_files_per_commit", "Files/commit (median)", "#4da6ff"),
        ("large_commit_ratio",      "Large commit ratio",    "#ff7b72"),
        ("cross_module_ratio",      "Cross-module dispersion", "#7dc67e"),
        ("refactor_ratio",          "Refactor ratio",        "#c77dff"),
    ]

    for signal, label, color in level_a_signals:
        values = [getattr(w, signal) for w in windows]
        # Normalize files/commit to [0,1] for overlay (divide by reasonable max)
        if signal == "median_files_per_commit":
            max_val = max(values) if max(values) > 0 else 1.0
            norm = [v / max_val for v in values]
            hover = [f"{v:.1f} files" for v in values]
        else:
            norm = values
            hover = [f"{v:.3f}" for v in values]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=norm,
                mode="lines+markers",
                name=label,
                line=dict(color=color, width=2),
                marker=dict(size=5),
                customdata=list(zip(values, hover)),
                hovertemplate=f"<b>{label}</b><br>%{{customdata[1]}}<br>%{{x|%Y-%m}}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # Level A change points
    for cp in profile.level_a_change_points:
        fig.add_vline(
            x=cp.date,
            line_dash="dash",
            line_color="rgba(255,100,100,0.8)",
            annotation_text=f"Δ{cp.signal[:4]}",
            annotation_font_color="#ff4444",
            row=1,
            col=1,
        )

    # ── Row 2: Level B signals ────────────────────────────────────────────────
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[w.test_touch_ratio for w in windows],
            mode="lines+markers",
            name="Test-touching ratio (B)",
            line=dict(color="#e3b341", width=2),
            marker=dict(size=5),
            hovertemplate="<b>Test-touching ratio</b><br>%{y:.1%}<br>%{x|%Y-%m}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=[max(w.median_net_lines / max(abs(w.median_net_lines) + 1, 1), -1) for w in windows],
            mode="lines",
            name="Net lines (normalized, B)",
            line=dict(color="#8b949e", width=1.5, dash="dot"),
            hovertemplate="<b>Median net lines</b><br>%{customdata:.0f}<br>%{x|%Y-%m}<extra></extra>",
            customdata=[w.median_net_lines for w in windows],
        ),
        row=2,
        col=1,
    )

    # ── Row 3: Level C style score (demoted to bottom) ────────────────────────
    style_scores = [w.style_score for w in windows]
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=style_scores,
            mode="lines+markers",
            name="Style score (C)",
            line=dict(color="#484f58", width=1.5),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor="rgba(72,79,88,0.12)",
            hovertemplate="<b>Style score</b><br>%{y:.1f}/100<br>%{x|%Y-%m}<extra></extra>",
        ),
        row=3,
        col=1,
    )

    _add_milestones(fig, row=3, col=1)

    # Drift result annotation
    dr = profile.drift_result
    if dr and dr.combined_p_value is not None:
        color = "#f85149" if dr.combined_p_value < 0.05 else "#8b949e"
        fig.add_annotation(
            text=f"Fisher p={dr.combined_p_value:.4f}",
            xref="paper", yref="paper",
            x=0.01, y=0.99,
            showarrow=False,
            font=dict(color=color, size=11),
            bgcolor="rgba(22,27,34,0.8)",
        )

    fig.update_layout(
        height=750,
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=30, t=80, b=40),
    )
    fig.update_yaxes(title_text="Normalized (0–1)", row=1, col=1, range=[0, 1.1])
    fig.update_yaxes(title_text="Ratio", row=2, col=1)
    fig.update_yaxes(title_text="Style score", row=3, col=1, range=[0, 100])

    return fig


def build_comparison_chart(profiles: list[DevProfile]) -> go.Figure:
    """Radar chart comparing Level A process signals for the latest window."""
    categories = [
        "Files/commit",
        "Large commits",
        "Cross-module",
        "Refactors",
        "Tests touched",
    ]
    signal_keys = [
        "median_files_per_commit",
        "large_commit_ratio",
        "cross_module_ratio",
        "refactor_ratio",
        "test_touch_ratio",
    ]
    # Normalization max values for radar (rough expected maxima)
    norm_max = [10.0, 1.0, 1.0, 1.0, 1.0]

    fig = go.Figure()
    colors = px.colors.qualitative.Set3

    for i, profile in enumerate(profiles):
        latest = profile.latest_window
        if not latest:
            continue
        raw = [getattr(latest, k) for k in signal_keys]
        values = [min(v / m * 100, 100) for v, m in zip(raw, norm_max)]
        values.append(values[0])

        fig.add_trace(
            go.Scatterpolar(
                r=values,
                theta=categories + [categories[0]],
                fill="toself",
                name=profile.display_name,
                line_color=colors[i % len(colors)],
                fillcolor=colors[i % len(colors)].replace(")", ",0.2)").replace("rgb", "rgba"),
            )
        )

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        title="Developer Process Fingerprint Comparison (Level A/B signals)",
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        height=520,
    )
    return fig


def render_report(
    profile: DevProfile,
    output_dir: Path,
    comparison_profiles: Optional[list[DevProfile]] = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    drift = compute_drift(profile.behavior_timeline)
    dr = profile.drift_result

    timeline_fig = build_timeline_chart(profile)
    comparison_fig = (
        build_comparison_chart([profile] + (comparison_profiles or []))
        if comparison_profiles
        else None
    )

    timeline_html = timeline_fig.to_html(full_html=False, include_plotlyjs="cdn")
    comparison_html = (
        comparison_fig.to_html(full_html=False, include_plotlyjs=False)
        if comparison_fig
        else ""
    )

    latest = profile.latest_window

    # Drift result card
    if dr:
        p_class = "verdict-high" if (dr.combined_p_value or 1.0) < 0.05 else "verdict-low"
        p_display = f"p={dr.combined_p_value:.4f}" if dr.combined_p_value is not None else "N/A"
        drift_card = f"""
  <div class="stat">
    <div class="stat-label">Fisher p (Level A)</div>
    <div class="stat-value {p_class}">{p_display}</div>
  </div>"""
    else:
        drift_card = ""

    change_points_html = ""
    for cp in profile.level_a_change_points:
        icon = "▲" if cp.value_after > cp.value_before else "▼"
        label = SIGNAL_LABELS.get(cp.signal, cp.signal)
        event = cp.nearest_known_event or ""
        change_points_html += (
            f"<div class='cp-item'>"
            f"<span>📅 {cp.date.strftime('%Y-%m')}</span>"
            f"<span>{icon} {label}: {cp.value_before:.3f} → {cp.value_after:.3f} "
            f"(Δ{cp.magnitude:.3f}, {cp.detection_method})</span>"
            f"<span style='color:#8b949e'>{event}</span>"
            f"</div>"
        )

    interpretation_html = f"<p class='interpretation'>{dr.interpretation}</p>" if dr else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{profile.display_name} — dev-fingerprint</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 2rem; }}
  h1 {{ font-size: 1.8rem; color: #58a6ff; }}
  h2 {{ font-size: 1.1rem; color: #8b949e; margin: 1.5rem 0 0.5rem; font-weight: 400; }}
  .meta {{ display: flex; gap: 2rem; margin: 1rem 0; flex-wrap: wrap; }}
  .stat {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
           padding: 0.75rem 1.25rem; }}
  .stat-label {{ font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; color: #e6edf3; margin-top: 0.2rem; }}
  .verdict-high {{ color: #f85149; }}
  .verdict-low {{ color: #3fb950; }}
  .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                      padding: 1rem; margin: 1rem 0; }}
  .change-points {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                    padding: 1rem; margin: 1rem 0; }}
  .cp-item {{ display: flex; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #21262d; }}
  .cp-item:last-child {{ border-bottom: none; }}
  .interpretation {{ background: #161b22; border-left: 3px solid #58a6ff; padding: 0.75rem 1rem;
                     margin: 1rem 0; color: #8b949e; font-style: italic; font-size: 0.9rem; }}
  .level-badge {{ display: inline-block; padding: 0.1rem 0.4rem; border-radius: 4px;
                  font-size: 0.75rem; font-weight: bold; margin-right: 0.3rem; }}
  .level-a {{ background: #1a4721; color: #3fb950; }}
  .level-b {{ background: #3d2c0a; color: #d29922; }}
  .level-c {{ background: #1c1c1c; color: #6e7681; }}
  a {{ color: #58a6ff; }}
  footer {{ margin-top: 3rem; color: #8b949e; font-size: 0.8rem; border-top: 1px solid #21262d; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>{profile.display_name}</h1>
<p style="color:#8b949e">{profile.github_login} · {profile.primary_language.value} · {profile.total_commits_analyzed} commits analyzed</p>

<div class="meta">
  <div class="stat">
    <div class="stat-label">Files/commit (latest, Level A)</div>
    <div class="stat-value">{f'{latest.median_files_per_commit:.1f}' if latest else 'N/A'}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Large commit ratio (latest, Level A)</div>
    <div class="stat-value">{f'{latest.large_commit_ratio:.1%}' if latest else 'N/A'}</div>
  </div>
  {drift_card}
  <div class="stat">
    <div class="stat-label">Style score drift (Level C)</div>
    <div class="stat-value" style="color:#6e7681; font-size:1rem; padding-top:0.4rem">
      {f"{drift['drift']:+.1f} pts" if 'drift' in drift else 'N/A'}
      <span style="font-size:0.7rem; display:block; margin-top:0.2rem">not primary evidence</span>
    </div>
  </div>
</div>

{interpretation_html}

<div class="chart-container">
{timeline_html}
</div>

{"<div class='chart-container'>" + comparison_html + "</div>" if comparison_html else ""}

{"<div class='change-points'><h2>Level A Change Points Detected</h2>" + change_points_html + "</div>" if change_points_html else ""}

<footer>
  <p>Generated by <a href="https://github.com/your-handle/dev-fingerprint">dev-fingerprint</a> —
  P(behavioral drift | Git history) · {datetime.now().strftime("%Y-%m-%d")}</p>
  <p style="margin-top:0.5rem">
    <span class="level-badge level-a">A</span> Process signals (primary evidence)
    <span class="level-badge level-b">B</span> Process signals (fragile)
    <span class="level-badge level-c">C</span> Style signals (baseline only, not primary evidence)
  </p>
</footer>
</body>
</html>"""

    out_path = output_dir / f"{profile.github_login}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
