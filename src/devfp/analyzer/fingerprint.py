"""Build developer style fingerprints from metrics + scores."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
import json

from devfp.analyzer.llm_signals import aggregate_quarterly
from devfp.analyzer.style import batch_extract
from devfp.analyzer.temporal import detect_change_points, compute_drift
from devfp.models import Commit, DeveloperConfig, DevProfile, Language, LLM_MILESTONES


def build_profile(
    config: DeveloperConfig,
    commits: list[Commit],
) -> DevProfile:
    """Full pipeline: commits → metrics → scores → change points → profile."""
    metrics = batch_extract(commits)
    scores = aggregate_quarterly(config.github_login, metrics)
    change_points = detect_change_points(config.github_login, scores)

    profile = DevProfile(
        github_login=config.github_login,
        display_name=config.display_name,
        primary_language=config.primary_language,
        analyzed_repos=config.repos,
        total_commits_analyzed=len(commits),
        score_timeline=scores,
        change_points=change_points,
    )

    if commits:
        sorted_commits = sorted(commits, key=lambda c: c.date)
        profile.first_commit_date = sorted_commits[0].date
        profile.last_commit_date = sorted_commits[-1].date

    return profile


def profile_summary(profile: DevProfile) -> dict[str, object]:
    """Return a concise dict summary for terminal display."""
    drift_stats = compute_drift(profile.score_timeline)
    latest = profile.latest_score

    return {
        "login": profile.github_login,
        "display_name": profile.display_name,
        "commits_analyzed": profile.total_commits_analyzed,
        "quarters_analyzed": len(profile.score_timeline),
        "latest_llm_score": latest.llm_score if latest else None,
        "latest_verdict": latest.verdict if latest else "N/A",
        "baseline_score": drift_stats.get("baseline_mean"),
        "post_llm_score": drift_stats.get("post_llm_mean"),
        "drift": drift_stats.get("drift"),
        "change_points": [
            {
                "date": cp.date.strftime("%Y-%m"),
                "magnitude": cp.magnitude,
                "nearest_event": cp.nearest_llm_event,
            }
            for cp in profile.change_points
        ],
    }


def save_profile(profile: DevProfile, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{profile.github_login}.json"
    path.write_text(profile.model_dump_json(indent=2))
    return path


def load_profile(path: Path) -> DevProfile:
    return DevProfile.model_validate_json(path.read_text())
