"""Tests for the analyzer pipeline."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from devfp.analyzer.style import extract_metrics, _extract_added_lines
from devfp.analyzer.llm_signals import aggregate_quarterly
from devfp.analyzer.temporal import detect_change_points, compute_drift, _nearest_milestone
from devfp.models import Commit, CommitFile, Language, StyleMetrics, LLMScore
from tests.fixtures.sample_diff_python import HUMAN_STYLE_PATCH, LLM_STYLE_PATCH


def _make_commit(patch: str, lang: Language = Language.PYTHON, sha: str = "abc123") -> Commit:
    return Commit(
        sha=sha,
        author="test-dev",
        date=datetime(2023, 6, 1, tzinfo=timezone.utc),
        message="feat: add new features",
        files=[CommitFile(filename="test.py", language=lang, additions=20, deletions=0, patch=patch)],
    )


class TestStyleExtraction:
    def test_human_style_has_low_comment_density(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        metrics = extract_metrics(commit)
        assert metrics.comment_density < 0.15

    def test_llm_style_has_high_docstring_coverage(self) -> None:
        commit = _make_commit(LLM_STYLE_PATCH)
        metrics = extract_metrics(commit)
        assert metrics.docstring_coverage > 0.5

    def test_llm_style_has_longer_identifiers(self) -> None:
        human_commit = _make_commit(HUMAN_STYLE_PATCH, sha="human")
        llm_commit = _make_commit(LLM_STYLE_PATCH, sha="llm")
        human_metrics = extract_metrics(human_commit)
        llm_metrics = extract_metrics(llm_commit)
        assert llm_metrics.avg_identifier_length > human_metrics.avg_identifier_length

    def test_llm_style_has_error_handling(self) -> None:
        llm_metrics = extract_metrics(_make_commit(LLM_STYLE_PATCH, sha="llm"))
        assert llm_metrics.error_handling_density > 0.0

    def test_llm_style_has_higher_llm_score(self) -> None:
        human_metrics = extract_metrics(_make_commit(HUMAN_STYLE_PATCH, sha="human"))
        llm_metrics = extract_metrics(_make_commit(LLM_STYLE_PATCH, sha="llm"))
        assert llm_metrics.llm_score > human_metrics.llm_score

    def test_llm_score_in_range(self) -> None:
        metrics = extract_metrics(_make_commit(LLM_STYLE_PATCH))
        assert 0.0 <= metrics.llm_score <= 1.0

    def test_conventional_commit_detected(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit.message = "feat(auth): add OAuth2 support"
        metrics = extract_metrics(commit)
        assert metrics.has_conventional_commit is True

    def test_non_conventional_commit(self) -> None:
        commit = _make_commit(HUMAN_STYLE_PATCH)
        commit.message = "fix the thing"
        metrics = extract_metrics(commit)
        assert metrics.has_conventional_commit is False

    def test_empty_patch_returns_zero_metrics(self) -> None:
        commit = _make_commit("")
        metrics = extract_metrics(commit)
        assert metrics.comment_density == 0.0
        assert metrics.n_code_lines == 0

    def test_extract_added_lines_filters_header(self) -> None:
        patch = "+++ b/file.py\n+actual code\n-removed\n context"
        lines = _extract_added_lines(patch)
        assert "actual code" in lines
        assert "+++ b/file.py" not in "\n".join(lines)


class TestLLMScoring:
    def _make_style_metrics(
        self,
        llm_score: float = 0.7,
        date: datetime | None = None,
    ) -> StyleMetrics:
        return StyleMetrics(
            commit_sha="test",
            date=date or datetime(2023, 1, 1, tzinfo=timezone.utc),
            author="test",
            comment_density=0.2,
            docstring_coverage=0.6,
            avg_identifier_length=10.5,
            error_handling_density=3.5,
            commit_message_length=60,
            has_conventional_commit=True,
            llm_score=llm_score,
        )

    def test_quarterly_aggregation_groups_correctly(self) -> None:
        metrics = [
            self._make_style_metrics(date=datetime(2023, 1, 15, tzinfo=timezone.utc)),
            self._make_style_metrics(date=datetime(2023, 2, 20, tzinfo=timezone.utc)),
            self._make_style_metrics(date=datetime(2023, 4, 10, tzinfo=timezone.utc)),
        ]
        quarters = aggregate_quarterly("test-dev", metrics)
        assert len(quarters) == 2  # Q1 and Q2

    def test_quarterly_score_is_in_range(self) -> None:
        metrics = [self._make_style_metrics(date=datetime(2023, 3, 1, tzinfo=timezone.utc))]
        quarters = aggregate_quarterly("dev", metrics)
        assert len(quarters) == 1
        assert 0.0 <= quarters[0].llm_score <= 100.0

    def test_quarterly_score_reflects_input_llm_score(self) -> None:
        high = [self._make_style_metrics(llm_score=0.9, date=datetime(2023, 1, 1, tzinfo=timezone.utc))]
        low = [self._make_style_metrics(llm_score=0.1, date=datetime(2023, 1, 1, tzinfo=timezone.utc))]
        high_quarters = aggregate_quarterly("dev", high)
        low_quarters = aggregate_quarterly("dev", low)
        assert high_quarters[0].llm_score > low_quarters[0].llm_score

    def test_high_llm_score_patch_produces_high_quarterly_score(self) -> None:
        commit = _make_commit(LLM_STYLE_PATCH)
        style = extract_metrics(commit)
        quarters = aggregate_quarterly("dev", [style])
        assert len(quarters) == 1
        assert quarters[0].llm_score > 30.0

    def test_verdict_high(self) -> None:
        score = LLMScore(
            author="dev", period_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2023, 3, 31, tzinfo=timezone.utc), llm_score=75.0
        )
        assert "High" in score.verdict

    def test_verdict_low(self) -> None:
        score = LLMScore(
            author="dev", period_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2023, 3, 31, tzinfo=timezone.utc), llm_score=20.0
        )
        assert "Organic" in score.verdict


class TestTemporalAnalysis:
    def _make_scores(self, values: list[float], start_year: int = 2020) -> list[LLMScore]:
        scores = []
        year, month = start_year, 1
        for v in values:
            scores.append(LLMScore(
                author="dev",
                period_start=datetime(year, month, 1, tzinfo=timezone.utc),
                period_end=datetime(year, month + 2 if month < 11 else 12, 28, tzinfo=timezone.utc),
                llm_score=v,
                n_commits=10,
            ))
            month += 3
            if month > 12:
                month = 1
                year += 1
        return scores

    def test_detects_large_shift(self) -> None:
        values = [15.0, 18.0, 12.0, 16.0, 14.0, 65.0, 68.0, 72.0, 70.0]
        scores = self._make_scores(values)
        change_points = detect_change_points("dev", scores, min_size=2)
        assert len(change_points) > 0
        assert change_points[0].magnitude > 30

    def test_no_change_on_stable_series(self) -> None:
        values = [20.0, 22.0, 19.0, 21.0, 18.0, 23.0]
        scores = self._make_scores(values)
        change_points = detect_change_points("dev", scores, min_size=2)
        assert len(change_points) == 0

    def test_nearest_milestone_copilot(self) -> None:
        dt = datetime(2022, 7, 1)
        label = _nearest_milestone(dt, max_delta_days=60)
        assert label is not None
        assert "Copilot" in label

    def test_nearest_milestone_out_of_range(self) -> None:
        dt = datetime(2019, 1, 1)
        label = _nearest_milestone(dt, max_delta_days=60)
        assert label is None

    def test_compute_drift(self) -> None:
        pre_scores = self._make_scores([15.0, 18.0, 20.0], start_year=2020)
        post_scores = self._make_scores([50.0, 55.0, 60.0], start_year=2023)
        all_scores = pre_scores + post_scores
        drift = compute_drift(all_scores)
        assert "drift" in drift
        assert drift["drift"] > 0
