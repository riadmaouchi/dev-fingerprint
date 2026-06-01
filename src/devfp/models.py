"""Core data models for dev-fingerprint."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    C = "c"
    RUBY = "ruby"
    GO = "go"
    RUST = "rust"
    UNKNOWN = "unknown"


class CommitFile(BaseModel):
    filename: str
    language: Language = Language.UNKNOWN
    additions: int = 0
    deletions: int = 0
    patch: Optional[str] = None


class Commit(BaseModel):
    sha: str
    author: str
    date: datetime
    message: str
    files: list[CommitFile] = Field(default_factory=list)

    @property
    def total_additions(self) -> int:
        return sum(f.additions for f in self.files)

    @property
    def total_deletions(self) -> int:
        return sum(f.deletions for f in self.files)


class StyleMetrics(BaseModel):
    """Per-commit signals extracted from a commit's diffs and metadata."""

    commit_sha: str
    date: datetime
    author: str

    # === Process signals (Level A — primary, process-level evidence) ===
    # These measure HOW code is written, not what it looks like.

    # Raw counts (commit-level, derived from GitHub API metadata)
    files_changed: int = 0          # total files modified in this commit
    net_lines: int = 0              # additions - deletions (net code added)
    total_churn: int = 0            # additions + deletions (total work)

    # Derived process signals
    cross_module_ratio: float = 0.0       # (distinct top-level dirs - 1) / (files - 1), 0 if ≤1 file
    is_refactor: bool = False             # churn > 50 lines and |net| < 20% of churn
    touches_tests: bool = False           # any test/spec file modified
    test_file_ratio: float = 0.0          # test files / total files
    is_merge: bool = False                # merge commit (message starts with "Merge")

    # Velocity signals — require knowing the previous commit's timestamp.
    # Populated by batch_extract(), which processes commits in chronological order.
    # None when no predecessor is available (first commit, or first in batch).
    inter_commit_hours: Optional[float] = None  # hours since the previous commit

    # === Style signals (Level C — weak, confounded with developer style) ===
    # Kept for baseline comparison — these are the "naive" approach.

    comment_density: float = 0.0       # comment lines / total lines
    docstring_coverage: float = 0.0    # functions with docstrings / total functions
    avg_identifier_length: float = 0.0 # avg length of variable/function names
    error_handling_density: float = 0.0
    avg_function_length: float = 0.0
    commit_message_length: int = 0
    has_conventional_commit: bool = False
    todo_count: int = 0
    total_lines_changed: int = 0       # alias for total_churn (backward compat)

    # Raw counts for aggregation
    n_functions: int = 0
    n_documented_functions: int = 0
    n_identifiers: int = 0
    n_comment_lines: int = 0
    n_code_lines: int = 0

    # Composite style score from CodeAnalyzer.copilot_score() — [0, 1]
    # Renamed from llm_score to be honest about what it measures.
    style_score: float = 0.0


# Maps each BehaviorWindow field to its scientific evidence level.
# A = strongly defensible process signals
# B = useful but fragile process signals
# C = style signals (weak evidence, high confound risk)
SIGNAL_LEVELS: dict[str, str] = {
    # Level A — process signals, primary evidence
    "median_files_per_commit": "A",
    "large_commit_ratio": "A",
    "cross_module_ratio": "A",
    "refactor_ratio": "A",
    "median_inter_commit_hours": "A",
    "commits_per_week": "A",
    # Level B — process signals, useful but fragile
    "test_touch_ratio": "B",
    "median_net_lines": "B",
    "merge_ratio": "B",
    # Level C — style signals, weak evidence
    "style_score": "C",
    "comment_score": "C",
    "docstring_score": "C",
    "verbosity_score": "C",
    "error_handling_score": "C",
    "commit_style_score": "C",
    "function_style_score": "C",
}

# Human-readable labels for display
SIGNAL_LABELS: dict[str, str] = {
    "median_files_per_commit": "Files/commit (median)",
    "large_commit_ratio": "Large commit ratio",
    "cross_module_ratio": "Cross-module dispersion",
    "refactor_ratio": "Refactor commit ratio",
    "median_inter_commit_hours": "Inter-commit delay (median h)",
    "commits_per_week": "Commits per week",
    "test_touch_ratio": "Test-touching ratio",
    "median_net_lines": "Net lines/commit (median)",
    "merge_ratio": "Merge commit ratio",
    "style_score": "Style score (Level C)",
    "comment_score": "Comment density",
    "docstring_score": "Docstring coverage",
    "verbosity_score": "Identifier verbosity",
    "error_handling_score": "Error handling",
    "commit_style_score": "Conventional commits",
    "function_style_score": "Function brevity",
}


class BehaviorWindow(BaseModel):
    """
    Aggregated behavioral profile for one time window (default: one quarter).

    Process signals (Level A/B) are the primary evidence — they measure
    HOW the developer works, not what the code looks like.

    Style signals (Level C) are kept for baseline comparison but should not
    be used as primary evidence for AI-assistance inference.
    """

    author: str
    period_start: datetime
    period_end: datetime
    n_commits: int = 0

    # === Level A — Process signals (primary evidence) ===

    # Files changed per commit (median — robust to outliers)
    median_files_per_commit: float = 0.0

    # Net lines changed per commit (median)
    median_net_lines: float = 0.0

    # Fraction of commits with |net_lines| > 200 (large generation events)
    large_commit_ratio: float = 0.0

    # Average cross-module dispersion (0 = all changes in one module, 1 = max spread)
    cross_module_ratio: float = 0.0

    # Fraction of commits that are refactors (high churn, low net change)
    refactor_ratio: float = 0.0

    # Median hours between consecutive commits in this window.
    # Low value = high velocity (many commits per day).
    # 0.0 means no inter-commit data was available for this window.
    median_inter_commit_hours: float = 0.0

    # Commits per calendar week over the window duration.
    commits_per_week: float = 0.0

    # === Level B — Process signals (useful but fragile) ===

    # Fraction of commits that touch test files
    test_touch_ratio: float = 0.0

    # Fraction of merge commits (low code authorship signal, high integration signal)
    merge_ratio: float = 0.0

    # === Level C — Style signals (kept for baseline, NOT primary evidence) ===

    comment_score: float = 0.0
    docstring_score: float = 0.0
    verbosity_score: float = 0.0
    error_handling_score: float = 0.0
    commit_style_score: float = 0.0
    function_style_score: float = 0.0

    # Composite style score (0-100), formerly "llm_score" — renamed for honesty
    style_score: float = 0.0


class SignalDrift(BaseModel):
    """Statistical drift result for one signal across recent vs. historical windows."""

    signal: str
    signal_level: str              # "A", "B", or "C"
    baseline_mean: float           # mean over historical windows
    recent_mean: float             # mean over recent windows
    delta: float                   # recent_mean - baseline_mean
    delta_pct: float               # delta / baseline_mean * 100 (inf if baseline=0)
    p_value: Optional[float]       # Mann-Whitney U p-value (None if insufficient data)
    significant_at_05: bool        # p_value < 0.05
    change_point_detected: bool    # PELT/CUSUM/EWMA detected a breakpoint
    direction: str                 # "increase", "decrease", "stable"


class DriftResult(BaseModel):
    """
    Full probabilistic drift result for a developer.

    The interpretation field is the only valid output for public communication —
    it is deliberately probabilistic and does not assert AI usage.
    """

    author: str
    n_windows_baseline: int
    n_windows_recent: int
    signals: list[SignalDrift] = Field(default_factory=list)
    combined_p_value: Optional[float] = None  # Fisher's method on Level A signals
    interpretation: str = ""


class ChangePoint(BaseModel):
    """A detected behavioral change point in the timeline."""

    author: str
    date: datetime
    signal: str              # which signal changed
    signal_level: str        # "A", "B", or "C"
    value_before: float
    value_after: float
    magnitude: float         # absolute |value_after - value_before|
    detection_method: str    # "pelt", "cusum", "ewma"
    # Post-hoc informational annotation only — NOT used to detect the breakpoint.
    nearest_known_event: Optional[str] = None


class DevProfile(BaseModel):
    """Full behavioral profile for a developer."""

    github_login: str
    display_name: str
    primary_language: Language
    analyzed_repos: list[str] = Field(default_factory=list)
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None
    total_commits_analyzed: int = 0

    # Time series of behavioral windows (quarterly by default)
    behavior_timeline: list[BehaviorWindow] = Field(default_factory=list)

    # Detected change points (across all signals)
    change_points: list[ChangePoint] = Field(default_factory=list)

    # Statistical drift result (computed from behavior_timeline)
    drift_result: Optional[DriftResult] = None

    @property
    def latest_window(self) -> Optional[BehaviorWindow]:
        if not self.behavior_timeline:
            return None
        return max(self.behavior_timeline, key=lambda w: w.period_start)

    @property
    def level_a_change_points(self) -> list[ChangePoint]:
        """Change points on Level A (process) signals only."""
        return [cp for cp in self.change_points if cp.signal_level == "A"]

    def style_drift(self) -> Optional[float]:
        """
        Style score drift pre/post June 2022.

        This is the Level C (weak) signal kept for baseline comparison.
        Use drift_result for scientifically defensible inference.
        """
        pre = [w for w in self.behavior_timeline if w.period_end.year < 2022]
        post = [
            w for w in self.behavior_timeline
            if w.period_start.year > 2022
            or (w.period_start.year == 2022 and w.period_start.month >= 6)
        ]
        if not pre or not post:
            return None
        return (
            sum(w.style_score for w in post) / len(post)
            - sum(w.style_score for w in pre) / len(pre)
        )


# Key LLM milestones — used for informational annotation of change points only.
# These are NEVER used to locate change points (that would be circular reasoning).
LLM_MILESTONES: dict[str, datetime] = {
    "GitHub Copilot Technical Preview": datetime(2021, 6, 29),
    "GitHub Copilot GA": datetime(2022, 6, 21),
    "ChatGPT Launch": datetime(2022, 11, 30),
    "GPT-4 Release": datetime(2023, 3, 14),
    "GitHub Copilot Chat GA": datetime(2023, 12, 19),
    "Claude 3 Opus": datetime(2024, 3, 4),
}


@dataclass
class DeveloperConfig:
    """Configuration for a developer to analyze."""

    github_login: str
    display_name: str
    primary_language: Language
    repos: list[str] = field(default_factory=list)
    notes: str = ""
