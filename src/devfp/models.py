"""Core data models for dev-fingerprint."""

from __future__ import annotations

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
    """Code style metrics extracted from a commit's diffs."""

    commit_sha: str
    date: datetime
    author: str

    # Primary LLM signals
    comment_density: float = 0.0        # comment lines / total lines
    docstring_coverage: float = 0.0     # functions with docstrings / total functions
    avg_identifier_length: float = 0.0  # avg length of variable/function names
    error_handling_density: float = 0.0 # try/except or guard clauses per 100 lines

    # Secondary signals
    avg_function_length: float = 0.0    # average lines per function
    commit_message_length: int = 0
    has_conventional_commit: bool = False  # feat:/fix:/chore: prefix
    todo_count: int = 0
    total_lines_changed: int = 0

    # Raw counts for aggregation
    n_functions: int = 0
    n_documented_functions: int = 0
    n_identifiers: int = 0
    n_comment_lines: int = 0
    n_code_lines: int = 0

    # Pre-computed by CodeAnalyzer.copilot_score() — [0, 1]
    llm_score: float = 0.0


class LLMScore(BaseModel):
    """Aggregated LLM likelihood score for a time window."""

    author: str
    period_start: datetime
    period_end: datetime

    # Component scores (0-1 each)
    comment_score: float = 0.0
    docstring_score: float = 0.0
    verbosity_score: float = 0.0
    error_handling_score: float = 0.0
    commit_style_score: float = 0.0
    function_style_score: float = 0.0

    # Final weighted score (0-100)
    llm_score: float = 0.0
    n_commits: int = 0

    @property
    def verdict(self) -> str:
        if self.llm_score >= 70:
            return "High LLM influence"
        elif self.llm_score >= 40:
            return "Possible LLM influence"
        else:
            return "Organic style"


class ChangePoint(BaseModel):
    """A detected style change point in the timeline."""

    author: str
    date: datetime
    metric: str
    value_before: float
    value_after: float
    magnitude: float  # absolute change
    nearest_llm_event: Optional[str] = None  # e.g. "GitHub Copilot GA (2022-06)"


class DevProfile(BaseModel):
    """Full style profile for a developer."""

    github_login: str
    display_name: str
    primary_language: Language
    analyzed_repos: list[str] = Field(default_factory=list)
    first_commit_date: Optional[datetime] = None
    last_commit_date: Optional[datetime] = None
    total_commits_analyzed: int = 0

    # Time series of scores (quarterly buckets)
    score_timeline: list[LLMScore] = Field(default_factory=list)
    change_points: list[ChangePoint] = Field(default_factory=list)

    @property
    def latest_score(self) -> Optional[LLMScore]:
        if not self.score_timeline:
            return None
        return max(self.score_timeline, key=lambda s: s.period_start)

    @property
    def baseline_score(self) -> Optional[float]:
        """Score in the pre-LLM era (before 2022)."""
        pre_era = [s for s in self.score_timeline if s.period_end.year < 2022]
        if not pre_era:
            return None
        return sum(s.llm_score for s in pre_era) / len(pre_era)

    @property
    def post_llm_score(self) -> Optional[float]:
        """Score after Copilot GA (Jun 2022)."""
        post_era = [
            s for s in self.score_timeline
            if s.period_start.year > 2022
            or (s.period_start.year == 2022 and s.period_start.month >= 6)
        ]
        if not post_era:
            return None
        return sum(s.llm_score for s in post_era) / len(post_era)

    @property
    def drift(self) -> Optional[float]:
        """Style drift: post_llm_score - baseline_score."""
        b = self.baseline_score
        p = self.post_llm_score
        if b is None or p is None:
            return None
        return p - b


# Key LLM milestones for annotation
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
