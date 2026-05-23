"""HTML report generator using Plotly."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from devfp.analyzer.temporal import compute_drift
from devfp.models import DevProfile, LLM_MILESTONES


_MILESTONE_COLORS = {
    "GitHub Copilot Technical Preview": "rgba(100,180,255,0.3)",
    "GitHub Copilot GA": "rgba(50,150,255,0.5)",
    "ChatGPT Launch": "rgba(255,160,50,0.5)",
    "GPT-4 Release": "rgba(255,80,80,0.5)",
    "GitHub Copilot Chat GA": "rgba(180,50,255,0.4)",
    "Claude 3 Opus": "rgba(80,200,120,0.4)",
}


def _add_milestones(fig: go.Figure, row: int = 1, col: int = 1) -> None:
    for label, dt in LLM_MILESTONES.items():
        fig.add_vline(
            x=dt.timestamp() * 1000,  # plotly uses ms
            line_dash="dot",
            line_color="rgba(150,150,150,0.6)",
            annotation_text=label.split(" ")[0],
            annotation_textangle=-90,
            annotation_font_size=9,
            row=row,
            col=col,
        )


def build_timeline_chart(profile: DevProfile) -> go.Figure:
    scores = sorted(profile.score_timeline, key=lambda s: s.period_start)
    if not scores:
        return go.Figure()

    dates = [s.period_start for s in scores]
    llm_scores = [s.llm_score for s in scores]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=(
            f"LLM Influence Score — {profile.display_name}",
            "Signal Breakdown",
        ),
        vertical_spacing=0.1,
    )

    # Main score line
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=llm_scores,
            mode="lines+markers",
            name="LLM Score",
            line=dict(color="#4da6ff", width=2.5),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(77,166,255,0.12)",
        ),
        row=1,
        col=1,
    )

    # Change points
    for cp in profile.change_points:
        fig.add_vline(
            x=cp.date,
            line_dash="dash",
            line_color="rgba(255,100,100,0.7)",
            annotation_text=f"Δ{cp.magnitude:.0f}",
            annotation_font_color="red",
            row=1,
            col=1,
        )

    # Threshold band
    fig.add_hrect(y0=40, y1=70, fillcolor="rgba(255,200,50,0.07)", line_width=0, row=1, col=1)
    fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,80,80,0.07)", line_width=0, row=1, col=1)

    # Signal breakdown (stacked area)
    signal_colors = {
        "comment_score": "#4da6ff",
        "docstring_score": "#ff9f40",
        "verbosity_score": "#7dc67e",
        "error_handling_score": "#ff6b6b",
        "commit_style_score": "#c77dff",
    }
    signal_labels = {
        "comment_score": "Comments",
        "docstring_score": "Docstrings",
        "verbosity_score": "Verbosity",
        "error_handling_score": "Error handling",
        "commit_style_score": "Commit style",
    }

    for key, color in signal_colors.items():
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=[getattr(s, key) * 20 for s in scores],  # scale to 0-20 each
                mode="lines",
                name=signal_labels[key],
                stackgroup="signals",
                line=dict(color=color, width=0.5),
                fillcolor=color.replace(")", ",0.6)").replace("rgb", "rgba") if "rgb" in color else color,
            ),
            row=2,
            col=1,
        )

    _add_milestones(fig, row=1, col=1)

    fig.update_layout(
        height=700,
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        font=dict(color="#c9d1d9"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=60, r=30, t=80, b=40),
    )
    fig.update_yaxes(title_text="LLM Score (0-100)", row=1, col=1, range=[0, 100])
    fig.update_yaxes(title_text="Signal intensity", row=2, col=1)

    return fig


def build_comparison_chart(profiles: list[DevProfile]) -> go.Figure:
    """Radar chart comparing the latest signal scores for multiple devs."""
    categories = ["Comments", "Docstrings", "Verbosity", "Error handling", "Commit style"]
    signal_keys = ["comment_score", "docstring_score", "verbosity_score", "error_handling_score", "commit_style_score"]

    fig = go.Figure()
    colors = px.colors.qualitative.Set3

    for i, profile in enumerate(profiles):
        latest = profile.latest_score
        if not latest:
            continue
        values = [getattr(latest, k) * 100 for k in signal_keys]
        values.append(values[0])  # close the polygon

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
        title="Developer Style Fingerprint Comparison",
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        font=dict(color="#c9d1d9"),
        height=500,
    )
    return fig


def render_report(
    profile: DevProfile,
    output_dir: Path,
    comparison_profiles: Optional[list[DevProfile]] = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    drift = compute_drift(profile.score_timeline)

    timeline_fig = build_timeline_chart(profile)
    comparison_fig = build_comparison_chart(
        [profile] + (comparison_profiles or [])
    ) if comparison_profiles else None

    timeline_html = timeline_fig.to_html(full_html=False, include_plotlyjs="cdn")
    comparison_html = comparison_fig.to_html(full_html=False, include_plotlyjs=False) if comparison_fig else ""

    verdict = profile.latest_score.verdict if profile.latest_score else "N/A"
    score_val = profile.latest_score.llm_score if profile.latest_score else 0

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
  .verdict-mid {{ color: #d29922; }}
  .verdict-low {{ color: #3fb950; }}
  .chart-container {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                      padding: 1rem; margin: 1rem 0; }}
  .change-points {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                    padding: 1rem; margin: 1rem 0; }}
  .cp-item {{ display: flex; gap: 1rem; padding: 0.5rem 0; border-bottom: 1px solid #21262d; }}
  .cp-item:last-child {{ border-bottom: none; }}
  a {{ color: #58a6ff; }}
  footer {{ margin-top: 3rem; color: #8b949e; font-size: 0.8rem; border-top: 1px solid #21262d; padding-top: 1rem; }}
</style>
</head>
<body>
<h1>{profile.display_name}</h1>
<p style="color:#8b949e">{profile.github_login} · {profile.primary_language.value} · {profile.total_commits_analyzed} commits analyzed</p>

<div class="meta">
  <div class="stat">
    <div class="stat-label">Latest LLM Score</div>
    <div class="stat-value {'verdict-high' if score_val >= 70 else 'verdict-mid' if score_val >= 40 else 'verdict-low'}">{score_val:.0f} / 100</div>
  </div>
  <div class="stat">
    <div class="stat-label">Verdict</div>
    <div class="stat-value" style="font-size:1rem; padding-top:0.4rem">{verdict}</div>
  </div>
  <div class="stat">
    <div class="stat-label">Style Drift</div>
    <div class="stat-value {'verdict-high' if (drift.get('drift') or 0) > 10 else 'verdict-mid' if (drift.get('drift') or 0) > 3 else 'verdict-low'}">
      {f"{drift['drift']:+.1f} pts" if 'drift' in drift else 'N/A'}
    </div>
  </div>
  <div class="stat">
    <div class="stat-label">Baseline → Post-LLM</div>
    <div class="stat-value" style="font-size:1rem; padding-top:0.4rem">
      {drift.get('baseline_mean', 'N/A'):.1f if isinstance(drift.get('baseline_mean'), float) else 'N/A'}
      →
      {drift.get('post_llm_mean', 'N/A'):.1f if isinstance(drift.get('post_llm_mean'), float) else 'N/A'}
    </div>
  </div>
</div>

<div class="chart-container">
{timeline_html}
</div>

{"<div class='chart-container'>" + comparison_html + "</div>" if comparison_html else ""}

{"<div class='change-points'><h2>Style Change Points Detected</h2>" + "".join(f"<div class='cp-item'><span>📅 {cp.date.strftime('%Y-%m')}</span><span>{'▲' if cp.value_after > cp.value_before else '▼'} {cp.value_before:.1f} → {cp.value_after:.1f} (Δ{cp.magnitude:.1f})</span><span style='color:#8b949e'>{cp.nearest_llm_event or ''}</span></div>" for cp in profile.change_points) + "</div>" if profile.change_points else ""}

<footer>
  Generated by <a href="https://github.com/your-handle/dev-fingerprint">dev-fingerprint</a> —
  Detecting the AI Drift in Famous OSS Contributors ·
  {datetime.now().strftime("%Y-%m-%d")}
</footer>
</body>
</html>"""

    out_path = output_dir / f"{profile.github_login}.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
