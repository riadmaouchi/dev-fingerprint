"""Extract code metrics and process signals from commits."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from stylometry import CodeAnalyzer

from devfp.models import Commit, CommitFile, Language, StyleMetrics

# ── Merge commit detection ─────────────────────────────────────────────────────
_MERGE_MSG = re.compile(r"^merge\b", re.IGNORECASE)

# ── Conventional commit prefix regex ──────────────────────────────────────────
_CONVENTIONAL_COMMIT = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:\s",
    re.IGNORECASE,
)

# ── Test file patterns (language-agnostic) ────────────────────────────────────
_TEST_PATH = re.compile(
    r"(^|/)tests?/|"
    r"(^|/)specs?/|"
    r"(^|/)__tests__/|"
    r"(^|/)test_[^/]+\.(py|go|rs|rb|c|h|js|ts|jsx|tsx)$|"
    r"[^/]+_test\.(py|go|rs|rb|c|h)$|"
    r"[^/]+\.(spec|test)\.(js|ts|jsx|tsx|mjs)$",
    re.IGNORECASE,
)

_LANG_MAP: dict[Language, str] = {
    Language.PYTHON:     "python",
    Language.JAVASCRIPT: "javascript",
    Language.TYPESCRIPT: "typescript",
    Language.C:          "c",
    Language.RUBY:       "ruby",
    Language.GO:         "go",
    Language.RUST:       "rust",
}


def _extract_added_lines(patch: str) -> list[str]:
    return [
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _dominant_language(commit: Commit) -> str:
    counts: dict[Language, int] = {}
    for f in commit.files:
        if f.language in _LANG_MAP:
            counts[f.language] = counts.get(f.language, 0) + f.additions
    if not counts:
        return "python"
    return _LANG_MAP[max(counts, key=counts.__getitem__)]


def _is_test_file(filename: str) -> bool:
    return bool(_TEST_PATH.search(filename))


def _cross_module_ratio(files: list[CommitFile]) -> float:
    """
    Normalized cross-module dispersion.

    Returns 0.0 when all changed files live in the same top-level directory
    (or when fewer than 2 files are changed).  Returns 1.0 when each changed
    file is in a distinct top-level directory.

    Formula: (n_distinct_top_dirs - 1) / (n_files - 1)
    """
    if len(files) <= 1:
        return 0.0
    top_dirs = {f.filename.split("/")[0] if "/" in f.filename else "root" for f in files}
    return (len(top_dirs) - 1) / (len(files) - 1)


def extract_metrics(
    commit: Commit,
    prev_date: Optional[datetime] = None,
) -> StyleMetrics:
    # ── Process signals — extracted from commit metadata, no AST needed ───────
    files = commit.files
    additions = sum(f.additions for f in files)
    deletions = sum(f.deletions for f in files)
    net_lines = additions - deletions
    total_churn = additions + deletions

    is_refactor = total_churn > 50 and abs(net_lines) < 0.20 * total_churn

    test_files = [f for f in files if _is_test_file(f.filename)]
    touches_tests = len(test_files) > 0
    test_file_ratio = len(test_files) / max(len(files), 1)
    cross_mod = _cross_module_ratio(files)

    msg_first_line = commit.message.split("\n")[0]
    is_merge = bool(_MERGE_MSG.match(msg_first_line))

    inter_commit_hours: Optional[float] = None
    if prev_date is not None:
        delta_s = (commit.date - prev_date).total_seconds()
        inter_commit_hours = max(delta_s / 3600.0, 0.0)

    # ── Style signals — require diff text and AST analysis ───────────────────
    lang_str = _dominant_language(commit)
    ca = CodeAnalyzer(language=lang_str, min_lines=2)

    code_parts: list[str] = []
    for f in files:
        if _LANG_MAP.get(f.language) == lang_str and f.patch:
            added = _extract_added_lines(f.patch)
            if added:
                code_parts.extend(added)

    if not code_parts:
        return StyleMetrics(
            commit_sha=commit.sha,
            date=commit.date,
            author=commit.author,
            files_changed=len(files),
            net_lines=net_lines,
            total_churn=total_churn,
            total_lines_changed=total_churn,
            cross_module_ratio=cross_mod,
            is_refactor=is_refactor,
            touches_tests=touches_tests,
            test_file_ratio=test_file_ratio,
            is_merge=is_merge,
            inter_commit_hours=inter_commit_hours,
            commit_message_length=len(msg_first_line),
            has_conventional_commit=bool(_CONVENTIONAL_COMMIT.match(msg_first_line)),
        )

    code_text = "\n".join(code_parts)

    try:
        features = ca.extract_features(code_text)
        style_score = ca.copilot_score(code_text)
    except ValueError:
        features = {}
        style_score = 0.0

    todo_count = sum(
        1 for line in code_parts
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE)
    )

    return StyleMetrics(
        commit_sha=commit.sha,
        date=commit.date,
        author=commit.author,
        # process signals
        files_changed=len(files),
        net_lines=net_lines,
        total_churn=total_churn,
        total_lines_changed=total_churn,
        cross_module_ratio=cross_mod,
        is_refactor=is_refactor,
        touches_tests=touches_tests,
        test_file_ratio=test_file_ratio,
        is_merge=is_merge,
        inter_commit_hours=inter_commit_hours,
        # style signals
        comment_density=features.get("comment_density", 0.0),
        docstring_coverage=features.get("docstring_completeness", 0.0),
        avg_identifier_length=features.get("identifier_verbosity", 0.0) * 20,
        error_handling_density=features.get("error_handling_density", 0.0) * 15,
        commit_message_length=len(msg_first_line),
        has_conventional_commit=bool(_CONVENTIONAL_COMMIT.match(msg_first_line)),
        todo_count=todo_count,
        n_code_lines=len([line for line in code_parts if line.strip()]),
        n_comment_lines=int(features.get("comment_density", 0.0) * max(len(code_parts), 1)),
        style_score=style_score,
    )


def batch_extract(commits: list[Commit]) -> list[StyleMetrics]:
    """
    Extract metrics for all commits, in chronological order.

    Commits are sorted before processing so that inter_commit_hours
    is computed correctly regardless of input order.
    """
    sorted_commits = sorted(commits, key=lambda c: c.date)
    result: list[StyleMetrics] = []
    prev_date: Optional[datetime] = None

    for commit in sorted_commits:
        if not commit.files:
            # Still update prev_date so the next real commit gets the right delta.
            prev_date = commit.date
            continue
        result.append(extract_metrics(commit, prev_date=prev_date))
        prev_date = commit.date

    return result
