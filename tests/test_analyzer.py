"""Tests for the analyzer pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pytest

from devfp.analyzer.style import batch_extract, extract_metrics, _extract_added_lines, _is_test_file, _cross_module_ratio
from devfp.analyzer.llm_signals import aggregate_windows
from devfp.analyzer.temporal import (
    detect_change_points,
    compare_recent_vs_historical,
    _cusum_detect,
    _ewma_detect,
    _nearest_known_event,
)
from devfp.models import (
    BehaviorWindow,
    Commit,
    CommitFile,
    Language,
    StyleMetrics,
)
from tests.fixtures.sample_diff_python import HUMAN_STYLE_PATCH, LLM_STYLE_PATCH


def _make_commit(
    patch: str,
    lang: Language = Language.PYTHON,
    sha: str = "abc123",
    n_files: int = 1,
    filename: str = "src/module/test.py",
) -> Commit:
    files = [
        CommitFile(
            filename=f"src/module_{i}/file.py" if n_files > 1 else filename,
            language=lang,
            additions=20,
            deletions=5,
            patch=patch if i == 0 else None,
        )
        for i in range(n_files)
    ]
    return Commit(
        sha=sha,
        author="test-dev",
        date=datetime(2023, 6, 1, tzinfo=timezone.utc),
        message="feat: add new features",
        files=files,
    )


def _make_window(
    author: str = "dev",
    year: int = 2023,
    quarter: int = 1,
    **kwargs: object,
) -> BehaviorWindow:
    start_month = (quarter - 1) * 3 + 1
    return BehaviorWindow(
        author=author,
        period_start=datetime(year, start_month, 1, tzinfo=timezone.utc),
        period_end=datetime(year, start_month + 2, 28, tzinfo=timezone.utc),
        n_commits=10,
        **kwargs,
    )


# ── Process signal extraction ──────────────────────────────────────────────────

class TestProcessSignals:
    def test_files_changed_counted(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH, n_files=3)
        metrics = extract_metrics(commit)
        assert metrics.files_changed == 3

    def test_net_lines_computed(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH, n_files=1)
        metrics = extract_metrics(commit)
        assert metrics.net_lines == 20 - 5  # additions - deletions

    def test_total_churn_computed(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH, n_files=1)
        metrics = extract_metrics(commit)
        assert metrics.total_churn == 20 + 5  # additions + deletions

    def test_refactor_flag_when_balanced_churn(self) -> None:
        commit = Commit(
            sha="ref",
            author="dev",
            date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            message="refactor: rename functions",
            files=[CommitFile(
                filename="src/main.py", language=Language.PYTHON,
                additions=100, deletions=99, patch=None,
            )],
        )
        metrics = extract_metrics(commit)
        assert metrics.is_refactor is True
        assert metrics.net_lines == 1

    def test_refactor_flag_false_for_pure_addition(self) -> None:
        commit = Commit(
            sha="add",
            author="dev",
            date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            message="feat: new module",
            files=[CommitFile(
                filename="src/new.py", language=Language.PYTHON,
                additions=200, deletions=0, patch=None,
            )],
        )
        metrics = extract_metrics(commit)
        assert metrics.is_refactor is False

    def test_test_file_detection(self) -> None:
        commit = Commit(
            sha="tst",
            author="dev",
            date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            message="test: add tests",
            files=[
                CommitFile(filename="tests/test_auth.py", language=Language.PYTHON,
                           additions=30, deletions=0),
                CommitFile(filename="src/auth.py", language=Language.PYTHON,
                           additions=20, deletions=0),
            ],
        )
        metrics = extract_metrics(commit)
        assert metrics.touches_tests is True
        assert abs(metrics.test_file_ratio - 0.5) < 0.01

    def test_cross_module_ratio_single_file(self) -> None:
        files = [CommitFile(filename="src/main.py", language=Language.PYTHON)]
        assert _cross_module_ratio(files) == 0.0

    def test_cross_module_ratio_same_dir(self) -> None:
        files = [
            CommitFile(filename="src/a.py", language=Language.PYTHON),
            CommitFile(filename="src/b.py", language=Language.PYTHON),
        ]
        # 1 distinct dir, 2 files → (1-1)/(2-1) = 0
        assert _cross_module_ratio(files) == 0.0

    def test_cross_module_ratio_max_dispersion(self) -> None:
        files = [
            CommitFile(filename="src/a.py", language=Language.PYTHON),
            CommitFile(filename="tests/b.py", language=Language.PYTHON),
            CommitFile(filename="docs/c.md", language=Language.UNKNOWN),
        ]
        # 3 dirs, 3 files → (3-1)/(3-1) = 1.0
        assert _cross_module_ratio(files) == pytest.approx(1.0)

    def test_is_test_file_patterns(self) -> None:
        assert _is_test_file("tests/test_auth.py")
        assert _is_test_file("src/auth_test.go")
        assert _is_test_file("auth.spec.ts")
        assert _is_test_file("auth.test.js")
        assert _is_test_file("__tests__/auth.js")
        assert not _is_test_file("src/auth.py")
        assert not _is_test_file("src/test_config.yaml")

    def test_empty_commit_returns_zero_process_signals(self) -> None:
        commit = Commit(
            sha="empty",
            author="dev",
            date=datetime(2023, 1, 1, tzinfo=timezone.utc),
            message="empty",
            files=[],
        )
        metrics = extract_metrics(commit)
        assert metrics.files_changed == 0
        assert metrics.net_lines == 0
        assert metrics.is_refactor is False

    def test_merge_commit_detected(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit = commit.model_copy(update={"message": "Merge pull request #123 from feature/x"})
        metrics = extract_metrics(commit)
        assert metrics.is_merge is True

    def test_non_merge_commit(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit = commit.model_copy(update={"message": "feat: add login"})
        metrics = extract_metrics(commit)
        assert metrics.is_merge is False

    def test_inter_commit_hours_with_prev_date(self) -> None:
        from datetime import timedelta
        commit = _make_commit(HUMAN_STYLE_PATCH)
        prev = commit.date - timedelta(hours=6)
        metrics = extract_metrics(commit, prev_date=prev)
        assert metrics.inter_commit_hours == pytest.approx(6.0)

    def test_inter_commit_hours_none_without_prev(self) -> None:
        metrics = extract_metrics(_make_commit(HUMAN_STYLE_PATCH))
        assert metrics.inter_commit_hours is None

    def test_batch_extract_computes_inter_commit_hours(self) -> None:
        from datetime import timedelta
        base = datetime(2023, 1, 1, tzinfo=timezone.utc)
        commits = [
            Commit(sha=f"c{i}", author="dev", date=base + timedelta(hours=i * 10),
                   message="feat: x",
                   files=[CommitFile(filename="src/f.py", language=Language.PYTHON,
                                     additions=10, deletions=0, patch=HUMAN_STYLE_PATCH)])
            for i in range(3)
        ]
        metrics = batch_extract(commits)
        assert len(metrics) == 3
        assert metrics[0].inter_commit_hours is None       # first commit, no predecessor
        assert metrics[1].inter_commit_hours == pytest.approx(10.0)
        assert metrics[2].inter_commit_hours == pytest.approx(10.0)


# ── Style signal extraction (Level C — kept for baseline) ─────────────────────

class TestStyleSignals:
    def test_llm_patch_has_higher_style_score(self) -> None:
        human = extract_metrics(_make_commit(HUMAN_STYLE_PATCH, sha="human"))
        llm = extract_metrics(_make_commit(LLM_STYLE_PATCH, sha="llm"))
        assert llm.style_score > human.style_score

    def test_style_score_in_range(self) -> None:
        metrics = extract_metrics(_make_commit(LLM_STYLE_PATCH))
        assert 0.0 <= metrics.style_score <= 1.0

    def test_conventional_commit_detected(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit = commit.model_copy(update={"message": "feat(auth): add OAuth2 support"})
        metrics = extract_metrics(commit)
        assert metrics.has_conventional_commit is True

    def test_non_conventional_commit(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit = commit.model_copy(update={"message": "fix the thing"})
        metrics = extract_metrics(commit)
        assert metrics.has_conventional_commit is False

    def test_extract_added_lines_filters_header(self) -> None:
        patch = "+++ b/file.py\n+actual code\n-removed\n context"
        lines = _extract_added_lines(patch)
        assert "actual code" in lines
        assert "+++ b/file.py" not in "\n".join(lines)


# ── BehaviorWindow aggregation ────────────────────────────────────────────────

class TestBehaviorWindow:
    def _make_metrics(
        self,
        date: datetime,
        files: int = 2,
        net: int = 50,
        churn: int = 80,
        is_refactor: bool = False,
        touches_tests: bool = False,
        cross: float = 0.3,
        style_score: float = 0.5,
        inter_hours: Optional[float] = None,
        is_merge: bool = False,
    ) -> StyleMetrics:
        return StyleMetrics(
            commit_sha="x",
            date=date,
            author="dev",
            files_changed=files,
            net_lines=net,
            total_churn=churn,
            total_lines_changed=churn,
            cross_module_ratio=cross,
            is_refactor=is_refactor,
            touches_tests=touches_tests,
            test_file_ratio=0.5 if touches_tests else 0.0,
            is_merge=is_merge,
            inter_commit_hours=inter_hours,
            style_score=style_score,
        )

    def test_quarterly_grouping(self) -> None:
        metrics = [
            self._make_metrics(datetime(2023, 1, 15, tzinfo=timezone.utc)),
            self._make_metrics(datetime(2023, 2, 20, tzinfo=timezone.utc)),
            self._make_metrics(datetime(2023, 4, 10, tzinfo=timezone.utc)),
        ]
        windows = aggregate_windows("dev", metrics)
        assert len(windows) == 2  # Q1 and Q2

    def test_process_signals_aggregated(self) -> None:
        metrics = [
            self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), files=4, is_refactor=True),
            self._make_metrics(datetime(2023, 2, 1, tzinfo=timezone.utc), files=2, is_refactor=False),
        ]
        windows = aggregate_windows("dev", metrics)
        assert len(windows) == 1
        w = windows[0]
        assert w.median_files_per_commit == pytest.approx(3.0)
        assert w.refactor_ratio == pytest.approx(0.5)

    def test_large_commit_ratio(self) -> None:
        metrics = [
            self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), net=300),  # large
            self._make_metrics(datetime(2023, 1, 5, tzinfo=timezone.utc), net=50),   # normal
            self._make_metrics(datetime(2023, 1, 10, tzinfo=timezone.utc), net=250), # large
        ]
        windows = aggregate_windows("dev", metrics)
        assert windows[0].large_commit_ratio == pytest.approx(2 / 3, abs=1e-3)

    def test_test_touch_ratio(self) -> None:
        metrics = [
            self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), touches_tests=True),
            self._make_metrics(datetime(2023, 1, 5, tzinfo=timezone.utc), touches_tests=False),
        ]
        windows = aggregate_windows("dev", metrics)
        assert windows[0].test_touch_ratio == pytest.approx(0.5)

    def test_style_score_scaled_to_100(self) -> None:
        metrics = [self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), style_score=0.7)]
        windows = aggregate_windows("dev", metrics)
        assert windows[0].style_score == pytest.approx(70.0)

    def test_median_inter_commit_hours_aggregated(self) -> None:
        items = [
            self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), inter_hours=4.0),
            self._make_metrics(datetime(2023, 1, 3, tzinfo=timezone.utc), inter_hours=8.0),
            self._make_metrics(datetime(2023, 1, 5, tzinfo=timezone.utc), inter_hours=12.0),
        ]
        windows = aggregate_windows("dev", items)
        assert windows[0].median_inter_commit_hours == pytest.approx(8.0)

    def test_inter_commit_hours_zero_when_no_data(self) -> None:
        items = [self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), inter_hours=None)]
        windows = aggregate_windows("dev", items)
        assert windows[0].median_inter_commit_hours == 0.0

    def test_commits_per_week_computed(self) -> None:
        # A quarter (Q1) has 90 days = ~13 weeks; 26 commits → ~2 per week
        items = [
            self._make_metrics(datetime(2023, 1, i + 1, tzinfo=timezone.utc))
            for i in range(26)
        ]
        windows = aggregate_windows("dev", items)
        assert windows[0].commits_per_week == pytest.approx(26 / (90 / 7), abs=0.5)

    def test_merge_ratio_aggregated(self) -> None:
        items = [
            self._make_metrics(datetime(2023, 1, 1, tzinfo=timezone.utc), is_merge=True),
            self._make_metrics(datetime(2023, 1, 2, tzinfo=timezone.utc), is_merge=False),
            self._make_metrics(datetime(2023, 1, 3, tzinfo=timezone.utc), is_merge=False),
            self._make_metrics(datetime(2023, 1, 4, tzinfo=timezone.utc), is_merge=False),
        ]
        windows = aggregate_windows("dev", items)
        assert windows[0].merge_ratio == pytest.approx(0.25)


# ── Change-point detection ────────────────────────────────────────────────────

class TestChangePointDetection:
    def _make_windows(
        self,
        signal_values: list[float],
        signal: str = "median_files_per_commit",
        start_year: int = 2020,
    ) -> list[BehaviorWindow]:
        windows = []
        year, q = start_year, 1
        for v in signal_values:
            windows.append(_make_window(year=year, quarter=q, **{signal: v}))
            q += 1
            if q > 4:
                q = 1
                year += 1
        return windows

    def test_cusum_detects_upward_shift(self) -> None:
        series = [1.0, 1.1, 0.9, 1.0, 1.1, 5.0, 5.2, 4.9, 5.1, 5.3]
        alarms = _cusum_detect(series)
        assert len(alarms) > 0
        assert alarms[0] > 3  # not in the stable period

    def test_cusum_no_alarm_stable(self) -> None:
        series = [1.0, 1.1, 0.9, 1.05, 1.02, 0.98, 1.01, 1.03]
        alarms = _cusum_detect(series)
        assert len(alarms) == 0

    def test_ewma_detects_shift(self) -> None:
        series = [1.0, 1.1, 0.9, 1.0, 5.0, 5.2, 4.9, 5.1]
        alarms = _ewma_detect(series)
        assert len(alarms) > 0

    def test_pelt_detects_large_shift(self) -> None:
        values = [1.0] * 6 + [5.0] * 6
        windows = self._make_windows(values)
        cps = detect_change_points("dev", windows, signals=["median_files_per_commit"], min_size=2)
        assert len(cps) > 0
        assert cps[0].signal == "median_files_per_commit"
        assert cps[0].signal_level == "A"

    def test_no_change_on_stable_series(self) -> None:
        values = [2.0, 2.1, 1.9, 2.05, 1.95, 2.1, 2.0, 1.98]
        windows = self._make_windows(values)
        cps = detect_change_points("dev", windows, signals=["median_files_per_commit"])
        assert len(cps) == 0

    def test_change_point_carries_signal_level(self) -> None:
        values = [0.1] * 5 + [0.8] * 5
        windows = self._make_windows(values, signal="style_score")
        cps = detect_change_points("dev", windows, signals=["style_score"], min_size=2)
        if cps:
            assert cps[0].signal_level == "C"

    def test_nearest_known_event_within_range(self) -> None:
        dt = datetime(2022, 7, 1)
        label = _nearest_known_event(dt, max_delta_days=60)
        assert label is not None
        assert "Copilot" in label

    def test_nearest_known_event_out_of_range(self) -> None:
        dt = datetime(2019, 1, 1)
        label = _nearest_known_event(dt, max_delta_days=60)
        assert label is None


# ── Self-comparison (drift result) ────────────────────────────────────────────

class TestSelfComparison:
    def _make_windows_series(
        self,
        baseline_vals: list[float],
        recent_vals: list[float],
        signal: str = "median_files_per_commit",
    ) -> list[BehaviorWindow]:
        windows = []
        year, q = 2019, 1
        for v in baseline_vals + recent_vals:
            windows.append(_make_window(year=year, quarter=q, **{signal: v}))
            q += 1
            if q > 4:
                q = 1
                year += 1
        return windows

    def test_returns_none_when_insufficient_data(self) -> None:
        # Only 3 windows total — less than min_historical=6 + recent_n=4
        windows = self._make_windows_series([1.0, 1.1, 1.2], [])
        result = compare_recent_vs_historical("dev", windows, recent_n=4, min_historical=6)
        assert result is None

    def test_returns_result_with_enough_data(self) -> None:
        baseline = [1.0, 1.1, 0.9, 1.05, 1.02, 0.98]   # 6 stable windows
        recent = [4.0, 4.5, 3.8, 4.2]                    # 4 shifted windows
        windows = self._make_windows_series(baseline, recent)
        result = compare_recent_vs_historical("dev", windows, recent_n=4, min_historical=6)
        assert result is not None
        assert result.n_windows_baseline == 6
        assert result.n_windows_recent == 4

    def test_significant_shift_detected(self) -> None:
        baseline = [1.0, 1.1, 0.9, 1.05, 1.02, 0.98]
        recent = [8.0, 9.0, 7.5, 8.5]
        windows = self._make_windows_series(baseline, recent)
        result = compare_recent_vs_historical(
            "dev", windows, signals=["median_files_per_commit"],
            recent_n=4, min_historical=6
        )
        assert result is not None
        sd = next(s for s in result.signals if s.signal == "median_files_per_commit")
        assert sd.delta > 0
        assert sd.direction == "increase"

    def test_stable_series_not_significant(self) -> None:
        stable = [2.0, 2.1, 1.9, 2.05, 1.95, 2.1, 2.0, 1.98, 2.03, 1.97]
        windows = self._make_windows_series(stable[:6], stable[6:])
        result = compare_recent_vs_historical(
            "dev", windows, signals=["median_files_per_commit"],
            recent_n=4, min_historical=6
        )
        assert result is not None
        sd = next(s for s in result.signals if s.signal == "median_files_per_commit")
        # p should NOT be significant for a stable series
        if sd.p_value is not None:
            assert sd.p_value > 0.05

    def test_interpretation_is_probabilistic(self) -> None:
        """Interpretation must never assert AI causation."""
        baseline = [1.0, 1.1, 0.9, 1.05, 1.02, 0.98]
        recent = [8.0, 9.0, 7.5, 8.5]
        windows = self._make_windows_series(baseline, recent)
        result = compare_recent_vs_historical("dev", windows, recent_n=4, min_historical=6)
        assert result is not None
        interp = result.interpretation.lower()
        # Must NOT claim AI generated the code
        assert "generated by ai" not in interp
        assert "proof" not in interp
        assert "definitely" not in interp
        # Must reference uncertainty or alternative explanations
        assert any(word in interp for word in [
            "compatible", "hypothesis", "consistent", "cannot", "alternative"
        ])

    def test_drift_result_signals_have_levels(self) -> None:
        baseline = [1.0] * 6
        recent = [5.0] * 4
        windows = self._make_windows_series(baseline, recent)
        result = compare_recent_vs_historical("dev", windows, recent_n=4, min_historical=6)
        assert result is not None
        for sd in result.signals:
            assert sd.signal_level in ("A", "B", "C")
