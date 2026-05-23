"""Change-point detection on LLM score timelines — delegates to stylometry.stats."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from stylometry.stats import detect_change_points as _detect_cps, compute_drift as _drift

from devfp.models import ChangePoint, LLMScore, LLM_MILESTONES


def detect_change_points(
    author: str,
    scores: list[LLMScore],
    metric: str = "llm_score",
    min_size: int = 3,
    penalty: float = 3.0,
    min_magnitude: float = 5.0,
) -> list[ChangePoint]:
    if len(scores) < min_size * 2:
        return []

    sorted_scores = sorted(scores, key=lambda s: s.period_start)
    series = [getattr(s, metric) for s in sorted_scores]

    raw = _detect_cps(series, min_size=min_size, penalty=penalty, min_magnitude=min_magnitude)

    result: list[ChangePoint] = []
    for cp in raw:
        idx = cp["index"]
        if idx >= len(sorted_scores):
            continue
        bkp_date = sorted_scores[idx].period_start
        result.append(ChangePoint(
            author=author,
            date=bkp_date,
            metric=metric,
            value_before=cp["value_before"],
            value_after=cp["value_after"],
            magnitude=cp["magnitude"],
            nearest_llm_event=_nearest_milestone(bkp_date),
        ))

    return result


def _nearest_milestone(dt: datetime, max_delta_days: int = 180) -> Optional[str]:
    best_label: Optional[str] = None
    best_delta = float("inf")
    dt_naive = dt.replace(tzinfo=None) if dt.tzinfo else dt

    for label, milestone_dt in LLM_MILESTONES.items():
        delta = abs((dt_naive - milestone_dt).days)
        if delta < best_delta and delta <= max_delta_days:
            best_delta = delta
            best_label = f"{label} ({milestone_dt.strftime('%Y-%m')})"

    return best_label


def compute_drift(scores: list[LLMScore]) -> dict[str, float]:
    """Pre/post Copilot GA (2022-06) drift summary."""
    split = next(
        (i for i, s in enumerate(scores)
         if s.period_start.year > 2022
         or (s.period_start.year == 2022 and s.period_start.month >= 6)),
        len(scores),
    )
    series = [s.llm_score for s in scores]
    raw = _drift(series, split_index=split)
    # Rename keys to match existing callers
    result: dict[str, float] = {}
    if "baseline_mean" in raw:
        result["baseline_mean"] = raw["baseline_mean"]
    if "post_mean" in raw:
        result["post_llm_mean"] = raw["post_mean"]
    if "drift" in raw:
        result["drift"] = raw["drift"]
    return result
