"""Aggregate per-commit LLM scores into quarterly LLMScore windows."""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import groupby

import numpy as np

from devfp.models import LLMScore, StyleMetrics


def _quarter(dt: datetime) -> tuple[int, int]:
    return dt.year, (dt.month - 1) // 3 + 1


def _function_style_score(items: list[StyleMetrics]) -> float:
    """Signal 6: inverse of average function length, normalized to [0, 1].

    LLMs tend to emit short, single-purpose functions (mean ~8–15 lines).
    Long organic functions (20–60 lines) are less common in LLM output.
    Score = 1.0 when avg_function_length ≤ 8 lines, 0.0 when ≥ 40 lines.
    Commits with no function data (avg_function_length == 0) are excluded.
    """
    lengths = [m.avg_function_length for m in items if m.avg_function_length > 0]
    if not lengths:
        return 0.0
    mean_len = float(np.mean(lengths))
    # Linear interpolation: 8 → 1.0, 40 → 0.0; clamped
    score = 1.0 - (mean_len - 8.0) / (40.0 - 8.0)
    return float(np.clip(score, 0.0, 1.0))


def aggregate_quarterly(
    author: str,
    metrics_list: list[StyleMetrics],
) -> list[LLMScore]:
    """Average the per-commit copilot scores into quarterly LLMScore objects."""
    if not metrics_list:
        return []

    sorted_metrics = sorted(metrics_list, key=lambda m: m.date)
    quarters: list[LLMScore] = []

    for (year, q), group in groupby(sorted_metrics, key=lambda m: _quarter(m.date)):
        items = list(group)
        period_start = datetime(year, (q - 1) * 3 + 1, 1, tzinfo=timezone.utc)
        end_month = q * 3
        end_day = 30 if end_month in {4, 6, 9, 11} else 31
        period_end = datetime(year, end_month, end_day, tzinfo=timezone.utc)

        # Primary score: average of CodeAnalyzer.copilot_score() per commit
        llm_score = float(np.mean([m.llm_score for m in items])) * 100

        # Per-signal averages (for display / radar chart)
        def avg(attr: str) -> float:
            vals = [getattr(m, attr) for m in items]
            return round(float(np.mean(vals)), 3)

        quarters.append(
            LLMScore(
                author=author,
                period_start=period_start,
                period_end=period_end,
                comment_score=avg("comment_density"),
                docstring_score=avg("docstring_coverage"),
                verbosity_score=min(avg("avg_identifier_length") / 20.0, 1.0),
                error_handling_score=min(avg("error_handling_density") / 15.0, 1.0),
                commit_style_score=float(np.mean([
                    1.0 if m.has_conventional_commit else 0.0 for m in items
                ])),
                function_style_score=_function_style_score(items),
                llm_score=round(llm_score, 1),
                n_commits=len(items),
            )
        )

    return quarters
