"""Rich terminal reporter for dev-fingerprint."""

from __future__ import annotations

from datetime import datetime

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from devfp.analyzer.fingerprint import profile_summary
from devfp.analyzer.temporal import compute_drift
from devfp.models import DevProfile, LLMScore

console = Console()


def _score_color(score: float) -> str:
    if score >= 70:
        return "red"
    elif score >= 40:
        return "yellow"
    return "green"


def _score_bar(score: float, width: int = 20) -> str:
    filled = int(score / 100 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{_score_color(score)}]{bar}[/] {score:.0f}/100"


def print_profile(profile: DevProfile) -> None:
    summary = profile_summary(profile)
    drift = compute_drift(profile.score_timeline)

    title = f"[bold cyan]{profile.display_name}[/bold cyan] ([dim]{profile.github_login}[/dim])"
    console.print(Panel(title, box=box.DOUBLE_EDGE, border_style="cyan"))

    # Stats grid
    meta_table = Table(box=None, show_header=False, padding=(0, 2))
    meta_table.add_column(style="dim")
    meta_table.add_column()
    meta_table.add_row("Primary language", f"[bold]{profile.primary_language.value}[/bold]")
    meta_table.add_row("Commits analyzed", str(profile.total_commits_analyzed))
    meta_table.add_row("Quarters analyzed", str(len(profile.score_timeline)))
    if profile.first_commit_date:
        meta_table.add_row("Date range", f"{profile.first_commit_date.strftime('%Y-%m')} → {profile.last_commit_date.strftime('%Y-%m') if profile.last_commit_date else '?'}")
    console.print(meta_table)
    console.print()

    # Score timeline table
    if profile.score_timeline:
        table = Table(
            title="[bold]Quarterly LLM Influence Score[/bold]",
            box=box.SIMPLE_HEAVY,
            border_style="bright_black",
        )
        table.add_column("Quarter", style="dim", width=10)
        table.add_column("LLM Score", width=28)
        table.add_column("Comments", justify="right")
        table.add_column("Docstrings", justify="right")
        table.add_column("Verbosity", justify="right")
        table.add_column("Commits", justify="right", style="dim")

        for score in sorted(profile.score_timeline, key=lambda s: s.period_start):
            q_label = f"{score.period_start.year} Q{(score.period_start.month - 1) // 3 + 1}"
            table.add_row(
                q_label,
                _score_bar(score.llm_score),
                f"{score.comment_score:.2f}",
                f"{score.docstring_score:.2f}",
                f"{score.verbosity_score:.2f}",
                str(score.n_commits),
            )
        console.print(table)

    # Drift summary
    if "drift" in drift:
        console.print()
        drift_val = drift["drift"]
        drift_color = "red" if drift_val > 10 else "yellow" if drift_val > 3 else "green"
        drift_sign = "+" if drift_val > 0 else ""
        console.print(
            f"[bold]Style Drift (pre-2022 → post-Copilot):[/bold] "
            f"[{drift_color}]{drift_sign}{drift_val:.1f} pts[/]"
            f"  (baseline {drift.get('baseline_mean', 0):.1f} → post {drift.get('post_llm_mean', 0):.1f})"
        )

    # Change points
    if profile.change_points:
        console.print()
        console.print("[bold]Detected Style Change Points:[/bold]")
        for cp in profile.change_points:
            icon = "▲" if cp.value_after > cp.value_before else "▼"
            color = "red" if cp.value_after > cp.value_before else "green"
            event = f"  [dim]≈ {cp.nearest_llm_event}[/dim]" if cp.nearest_llm_event else ""
            console.print(
                f"  [{color}]{icon}[/] {cp.date.strftime('%Y-%m')}  "
                f"{cp.value_before:.1f} → {cp.value_after:.1f}  "
                f"(Δ {cp.magnitude:.1f}){event}"
            )


def print_comparison(profiles: list[DevProfile]) -> None:
    table = Table(
        title="[bold]Developer LLM Influence Comparison[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
    )
    table.add_column("Developer", style="bold")
    table.add_column("Language", style="dim")
    table.add_column("LLM Score (latest)")
    table.add_column("Verdict")
    table.add_column("Drift", justify="right")
    table.add_column("Change Points", justify="right")

    for profile in sorted(
        profiles, key=lambda p: p.latest_score.llm_score if p.latest_score else 0, reverse=True
    ):
        latest = profile.latest_score
        drift = compute_drift(profile.score_timeline)
        drift_val = drift.get("drift")

        score_str = _score_bar(latest.llm_score, width=12) if latest else "[dim]N/A[/dim]"
        verdict_str = latest.verdict if latest else "N/A"
        drift_str = (
            f"[{'red' if drift_val > 5 else 'green'}]{drift_val:+.1f}[/]"
            if drift_val is not None
            else "[dim]N/A[/dim]"
        )

        table.add_row(
            profile.display_name,
            profile.primary_language.value,
            score_str,
            verdict_str,
            drift_str,
            str(len(profile.change_points)),
        )

    console.print(table)
