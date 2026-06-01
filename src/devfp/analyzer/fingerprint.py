"""Build developer behavioral fingerprints from commits."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import json

from devfp.analyzer.llm_signals import aggregate_windows
from devfp.analyzer.style import batch_extract
from devfp.analyzer.temporal import (
    compare_recent_vs_historical,
    compute_drift,
    detect_change_points,
)
from devfp.models import Commit, DeveloperConfig, DevProfile, Language


def build_profile(
    config: DeveloperConfig,
    commits: list[Commit],
    recent_n: int = 4,
    min_historical: int = 6,
) -> DevProfile:
    """
    Full pipeline: commits → per-commit metrics → behavioral windows →
                   change points → drift result → profile.

    recent_n / min_historical control the self-comparison window.
    The drift_result is None when there is insufficient history.
    """
    metrics = batch_extract(commits)
    windows = aggregate_windows(config.github_login, metrics)
    change_points = detect_change_points(config.github_login, windows)
    drift_result = compare_recent_vs_historical(
        author=config.github_login,
        windows=windows,
        recent_n=recent_n,
        min_historical=min_historical,
        change_points=change_points,
    )

    profile = DevProfile(
        github_login=config.github_login,
        display_name=config.display_name,
        primary_language=config.primary_language,
        analyzed_repos=config.repos,
        total_commits_analyzed=len(commits),
        behavior_timeline=windows,
        change_points=change_points,
        drift_result=drift_result,
    )

    if commits:
        sorted_commits = sorted(commits, key=lambda c: c.date)
        profile.first_commit_date = sorted_commits[0].date
        profile.last_commit_date = sorted_commits[-1].date

    return profile


def profile_summary(profile: DevProfile) -> dict[str, object]:
    """Return a concise dict summary for terminal display."""
    drift = compute_drift(profile.behavior_timeline)
    latest = profile.latest_window
    dr = profile.drift_result

    return {
        "login": profile.github_login,
        "display_name": profile.display_name,
        "commits_analyzed": profile.total_commits_analyzed,
        "windows_analyzed": len(profile.behavior_timeline),
        # Level C legacy score
        "latest_style_score": latest.style_score if latest else None,
        "style_drift_pre_post": drift.get("drift"),
        # Level A process signals (recent window)
        "latest_median_files": latest.median_files_per_commit if latest else None,
        "latest_large_commit_ratio": latest.large_commit_ratio if latest else None,
        "latest_refactor_ratio": latest.refactor_ratio if latest else None,
        # Statistical result
        "drift_combined_p": dr.combined_p_value if dr else None,
        "interpretation": dr.interpretation if dr else "Insufficient data.",
        "level_a_change_points": [
            {
                "date": cp.date.strftime("%Y-%m"),
                "signal": cp.signal,
                "magnitude": cp.magnitude,
                "method": cp.detection_method,
                "nearest_event": cp.nearest_known_event,
            }
            for cp in profile.level_a_change_points
        ],
    }


def save_profile(profile: DevProfile, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{profile.github_login}.json"
    path.write_text(profile.model_dump_json(indent=2))
    return path


def load_profile(path: Path) -> DevProfile:
    return DevProfile.model_validate_json(path.read_text())
