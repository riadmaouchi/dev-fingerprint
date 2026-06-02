"""
Aggregate per-commit StyleMetrics into quarterly BehaviorWindow objects.

Process signals (Level A/B) are the primary output.
Style signals (Level C) are computed alongside for baseline comparison.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import groupby

import numpy as np

from devfp.models import BehaviorWindow, StyleMetrics


def _quarter(dt: datetime) -> tuple[int, int]:
    return dt.year, (dt.month - 1) // 3 + 1


def _function_style_score(items: list[StyleMetrics]) -> float:
    """
    Level C: inverse of average function length, normalized [0, 1].

    Historically calibrated: ≤8 lines → 1.0, ≥40 lines → 0.0.
    This is fragile — developer style dominates over AI influence.
    """
    lengths = [m.avg_function_length for m in items if m.avg_function_length > 0]
    if not lengths:
        return 0.0
    mean_len = float(np.mean(lengths))
    score = 1.0 - (mean_len - 8.0) / (40.0 - 8.0)
    return float(np.clip(score, 0.0, 1.0))


def aggregate_windows(
    author: str,
    metrics_list: list[StyleMetrics],
) -> list[BehaviorWindow]:
    """
    Fold per-commit StyleMetrics into quarterly BehaviorWindow objects.

    Process signals are aggregated using median/ratio statistics (robust to outliers).
    Style signals are averaged for display purposes only.
    """
    if not metrics_list:
        return []

    sorted_metrics = sorted(metrics_list, key=lambda m: m.date)
    windows: list[BehaviorWindow] = []

    for (year, q), group in groupby(sorted_metrics, key=lambda m: _quarter(m.date)):
        items = list(group)
        period_start = datetime(year, (q - 1) * 3 + 1, 1, tzinfo=timezone.utc)
        end_month = q * 3
        end_day = 30 if end_month in {4, 6, 9, 11} else 31
        period_end = datetime(year, end_month, end_day, tzinfo=timezone.utc)

        # ── Level A: Process signals ─────────────────────────────────────────

        files_per_commit = [m.files_changed for m in items]
        median_files = float(np.median(files_per_commit)) if files_per_commit else 0.0

        net_lines_per = [m.net_lines for m in items]
        median_net = float(np.median(net_lines_per)) if net_lines_per else 0.0

        large_commit_ratio = sum(
            1 for m in items if abs(m.net_lines) > 200
        ) / max(len(items), 1)

        cross_mod_vals = [m.cross_module_ratio for m in items]
        avg_cross_module = float(np.mean(cross_mod_vals)) if cross_mod_vals else 0.0

        refactor_ratio = sum(1 for m in items if m.is_refactor) / max(len(items), 1)

        # Velocity: inter-commit delay (hours between consecutive commits)
        inter_hours = [m.inter_commit_hours for m in items if m.inter_commit_hours is not None]
        median_inter = float(np.median(inter_hours)) if inter_hours else 0.0

        # Commit frequency: commits per calendar week over the window
        duration_days = max((period_end - period_start).days, 1)
        commits_per_week = len(items) / (duration_days / 7.0)

        # ── Level B: Process signals ─────────────────────────────────────────

        test_touch_ratio = sum(
            1 for m in items if m.touches_tests
        ) / max(len(items), 1)

        merge_ratio = sum(1 for m in items if m.is_merge) / max(len(items), 1)

        # ── Level D: Content signals on new files only ───────────────────────

        new_file_commits_ratio = sum(
            1 for m in items if m.new_file_count > 0
        ) / max(len(items), 1)

        # Weighted mean: weight each commit by its function count so that
        # commits with many new functions dominate over single-function files.
        def _weighted_mean(ratio_attr: str) -> float:
            total_w = sum(m.new_file_fn_count for m in items)
            if total_w == 0:
                return 0.0
            return sum(
                getattr(m, ratio_attr) * m.new_file_fn_count for m in items
            ) / total_w

        new_file_type_annotation_density = _weighted_mean("new_file_typed_fn_ratio")
        new_file_docstring_density = _weighted_mean("new_file_docstring_fn_ratio")

        # error density is weighted by total lines in new files; approximate with fn_count
        new_file_error_density = _weighted_mean("new_file_try_per_100")

        # ── Level C: Style signals ────────────────────────────────────────────

        def avg(attr: str) -> float:
            vals = [getattr(m, attr) for m in items]
            return round(float(np.mean(vals)), 3)

        style_score = float(np.mean([m.style_score for m in items])) * 100

        windows.append(
            BehaviorWindow(
                author=author,
                period_start=period_start,
                period_end=period_end,
                n_commits=len(items),
                # Level A
                median_files_per_commit=round(median_files, 2),
                median_net_lines=round(median_net, 1),
                large_commit_ratio=round(large_commit_ratio, 3),
                cross_module_ratio=round(avg_cross_module, 3),
                refactor_ratio=round(refactor_ratio, 3),
                median_inter_commit_hours=round(median_inter, 1),
                commits_per_week=round(commits_per_week, 2),
                # Level B
                test_touch_ratio=round(test_touch_ratio, 3),
                merge_ratio=round(merge_ratio, 3),
                # Level D
                new_file_commits_ratio=round(new_file_commits_ratio, 3),
                new_file_type_annotation_density=round(new_file_type_annotation_density, 3),
                new_file_docstring_density=round(new_file_docstring_density, 3),
                new_file_error_density=round(new_file_error_density, 3),
                # Level C
                comment_score=avg("comment_density"),
                docstring_score=avg("docstring_coverage"),
                verbosity_score=min(avg("avg_identifier_length") / 20.0, 1.0),
                error_handling_score=min(avg("error_handling_density") / 15.0, 1.0),
                commit_style_score=float(np.mean([
                    1.0 if m.has_conventional_commit else 0.0 for m in items
                ])),
                function_style_score=_function_style_score(items),
                style_score=round(style_score, 1),
            )
        )

    return windows


# Backward-compatibility alias
aggregate_quarterly = aggregate_windows
