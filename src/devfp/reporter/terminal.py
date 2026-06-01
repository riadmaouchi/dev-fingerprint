"""Rich terminal reporter for dev-fingerprint."""

from __future__ import annotations

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from devfp.analyzer.fingerprint import profile_summary
from devfp.analyzer.temporal import compute_drift
from devfp.models import BehaviorWindow, DevProfile, SIGNAL_LABELS, SIGNAL_LEVELS

console = Console()


def _p_color(p: float | None) -> str:
    if p is None:
        return "bright_black"
    if p < 0.01:
        return "red"
    if p < 0.05:
        return "yellow"
    return "green"


def _p_label(p: float | None) -> str:
    if p is None:
        return "[dim]N/A[/dim]"
    color = _p_color(p)
    stars = "**" if p < 0.01 else "*" if p < 0.05 else ""
    return f"[{color}]p={p:.3f}{stars}[/]"


def _bar(value: float, max_val: float = 1.0, width: int = 14) -> str:
    ratio = min(value / max(max_val, 1e-9), 1.0)
    filled = int(ratio * width)
    return "█" * filled + "░" * (width - filled)


def _direction_icon(direction: str) -> str:
    return {"increase": "▲", "decrease": "▼", "stable": "─"}.get(direction, "?")


def print_profile(profile: DevProfile) -> None:
    summary = profile_summary(profile)

    title = (
        f"[bold cyan]{profile.display_name}[/bold cyan] "
        f"([dim]{profile.github_login}[/dim])"
    )
    console.print(Panel(title, box=box.DOUBLE_EDGE, border_style="cyan"))

    # Meta
    meta = Table(box=None, show_header=False, padding=(0, 2))
    meta.add_column(style="dim")
    meta.add_column()
    meta.add_row("Primary language", f"[bold]{profile.primary_language.value}[/bold]")
    meta.add_row("Commits analyzed", str(profile.total_commits_analyzed))
    meta.add_row("Quarterly windows", str(len(profile.behavior_timeline)))
    if profile.first_commit_date:
        date_range = (
            f"{profile.first_commit_date.strftime('%Y-%m')} → "
            f"{profile.last_commit_date.strftime('%Y-%m') if profile.last_commit_date else '?'}"
        )
        meta.add_row("Date range", date_range)
    console.print(meta)
    console.print()

    # ── Behavioral timeline (Level A/B signals) ───────────────────────────────
    if profile.behavior_timeline:
        table = Table(
            title="[bold]Behavioral Timeline — Process Signals (Level A/B)[/bold]",
            box=box.SIMPLE_HEAVY,
            border_style="bright_black",
        )
        table.add_column("Quarter", style="dim", width=10)
        table.add_column("Files/commit", width=16)
        table.add_column("Large commits", width=14, justify="right")
        table.add_column("Cross-module", width=14, justify="right")
        table.add_column("Refactors", width=12, justify="right")
        table.add_column("Tests touched", width=13, justify="right")
        table.add_column("N commits", width=9, justify="right", style="dim")

        for w in sorted(profile.behavior_timeline, key=lambda w: w.period_start):
            q_label = f"{w.period_start.year} Q{(w.period_start.month - 1) // 3 + 1}"
            table.add_row(
                q_label,
                f"{_bar(w.median_files_per_commit, max_val=10)} {w.median_files_per_commit:.1f}",
                f"{w.large_commit_ratio:.1%}",
                f"{w.cross_module_ratio:.2f}",
                f"{w.refactor_ratio:.1%}",
                f"{w.test_touch_ratio:.1%}",
                str(w.n_commits),
            )
        console.print(table)
        console.print()

    # ── Style signals (Level C — baseline only) ───────────────────────────────
    drift = compute_drift(profile.behavior_timeline)
    if drift.get("drift") is not None:
        d = drift["drift"]
        sign = "+" if d > 0 else ""
        color = "bright_black"
        console.print(
            f"[dim]Style score drift (Level C baseline, pre-2022 → post-Copilot):[/dim] "
            f"[{color}]{sign}{d:.1f} pts[/]  "
            f"[dim]({drift.get('baseline_mean', 0):.1f} → {drift.get('post_llm_mean', 0):.1f})[/dim]"
        )
        console.print()

    # ── Drift result (statistical self-comparison) ────────────────────────────
    dr = profile.drift_result
    if dr is not None:
        console.print(
            Panel(
                f"[bold]Statistical Self-Comparison[/bold]  "
                f"[dim]({dr.n_windows_baseline} baseline vs {dr.n_windows_recent} recent windows)[/dim]",
                box=box.SIMPLE,
                border_style="bright_black",
            )
        )

        sig_table = Table(box=None, show_header=True, padding=(0, 1))
        sig_table.add_column("Signal", style="dim", width=28)
        sig_table.add_column("Level", width=5, justify="center")
        sig_table.add_column("Baseline", width=9, justify="right")
        sig_table.add_column("Recent", width=9, justify="right")
        sig_table.add_column("Δ%", width=9, justify="right")
        sig_table.add_column("p-value", width=14)
        sig_table.add_column("CP", width=4, justify="center")

        for sd in sorted(dr.signals, key=lambda s: s.signal_level):
            label = SIGNAL_LABELS.get(sd.signal, sd.signal)
            level_color = {"A": "green", "B": "yellow", "C": "bright_black"}.get(
                sd.signal_level, "white"
            )
            icon = _direction_icon(sd.direction)
            dir_color = "red" if sd.direction == "increase" else "green" if sd.direction == "decrease" else "bright_black"
            cp_marker = "[yellow]●[/]" if sd.change_point_detected else "[dim]○[/]"
            sig_table.add_row(
                f"[{level_color}]{label}[/]",
                f"[{level_color}]{sd.signal_level}[/]",
                f"{sd.baseline_mean:.3f}",
                f"[{dir_color}]{icon} {sd.recent_mean:.3f}[/]",
                f"[{dir_color}]{sd.delta_pct:+.0f}%[/]",
                _p_label(sd.p_value),
                cp_marker,
            )

        console.print(sig_table)

        combined = dr.combined_p_value
        if combined is not None:
            c = _p_color(combined)
            console.print(
                f"\n  [bold]Fisher combined p (Level A):[/bold] [{c}]p={combined:.4f}[/]"
            )

        console.print(f"\n  [italic dim]{dr.interpretation}[/italic dim]")
        console.print()

    # ── Change points (Level A only shown prominently) ────────────────────────
    level_a_cps = profile.level_a_change_points
    if level_a_cps:
        console.print("[bold]Level A Change Points Detected:[/bold]")
        for cp in level_a_cps:
            icon = "▲" if cp.value_after > cp.value_before else "▼"
            color = "red" if cp.value_after > cp.value_before else "green"
            event = f"  [dim]≈ {cp.nearest_known_event}[/dim]" if cp.nearest_known_event else ""
            label = SIGNAL_LABELS.get(cp.signal, cp.signal)
            console.print(
                f"  [{color}]{icon}[/] {cp.date.strftime('%Y-%m')}  "
                f"[dim]{label}:[/dim] "
                f"{cp.value_before:.3f} → {cp.value_after:.3f}  "
                f"(Δ {cp.magnitude:.3f}, {cp.detection_method}){event}"
            )
        console.print()


def print_comparison(profiles: list[DevProfile]) -> None:
    table = Table(
        title="[bold]Developer Behavioral Comparison[/bold]",
        box=box.ROUNDED,
        border_style="cyan",
    )
    table.add_column("Developer", style="bold")
    table.add_column("Language", style="dim")
    table.add_column("Files/commit", justify="right")
    table.add_column("Large commits", justify="right")
    table.add_column("Refactor ratio", justify="right")
    table.add_column("Fisher p (A)", justify="right")
    table.add_column("Δ CPs (A)", justify="right", style="dim")

    for profile in sorted(
        profiles,
        key=lambda p: p.drift_result.combined_p_value
        if p.drift_result and p.drift_result.combined_p_value is not None
        else 1.0,
    ):
        latest = profile.latest_window
        dr = profile.drift_result

        files_str = f"{latest.median_files_per_commit:.1f}" if latest else "[dim]N/A[/dim]"
        large_str = f"{latest.large_commit_ratio:.1%}" if latest else "[dim]N/A[/dim]"
        refactor_str = f"{latest.refactor_ratio:.1%}" if latest else "[dim]N/A[/dim]"

        p_str: str
        if dr and dr.combined_p_value is not None:
            c = _p_color(dr.combined_p_value)
            stars = "**" if dr.combined_p_value < 0.01 else "*" if dr.combined_p_value < 0.05 else ""
            p_str = f"[{c}]p={dr.combined_p_value:.3f}{stars}[/]"
        else:
            p_str = "[dim]N/A[/dim]"

        cp_count = str(len(profile.level_a_change_points))

        table.add_row(
            profile.display_name,
            profile.primary_language.value,
            files_str,
            large_str,
            refactor_str,
            p_str,
            cp_count,
        )

    console.print(table)
    console.print(
        "\n[dim]Sorted by Fisher combined p (Level A signals only). "
        "Low p = process drift detected. "
        "Does NOT imply AI assistance.[/dim]"
    )
