"""Extract code style metrics from commit diffs using stylometry.CodeAnalyzer."""

from __future__ import annotations

import re
from pathlib import Path

from stylometry import CodeAnalyzer

from devfp.models import Commit, Language, StyleMetrics

_CONVENTIONAL_COMMIT = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?:\s",
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
    """Return the most-used language in this commit (by lines added)."""
    counts: dict[Language, int] = {}
    for f in commit.files:
        if f.language in _LANG_MAP:
            counts[f.language] = counts.get(f.language, 0) + f.additions
    if not counts:
        return "python"
    dominant = max(counts, key=counts.__getitem__)
    return _LANG_MAP[dominant]


def extract_metrics(commit: Commit) -> StyleMetrics:
    lang_str = _dominant_language(commit)
    ca = CodeAnalyzer(language=lang_str, min_lines=2)

    # Aggregate added code from all relevant files
    code_parts: list[str] = []
    for f in commit.files:
        if _LANG_MAP.get(f.language) == lang_str and f.patch:
            added = _extract_added_lines(f.patch)
            if added:
                code_parts.extend(added)

    msg_first_line = commit.message.split("\n")[0]

    if not code_parts:
        return StyleMetrics(
            commit_sha=commit.sha,
            date=commit.date,
            author=commit.author,
            commit_message_length=len(msg_first_line),
            has_conventional_commit=bool(_CONVENTIONAL_COMMIT.match(msg_first_line)),
        )

    code_text = "\n".join(code_parts)

    try:
        features = ca.extract_features(code_text)
        llm_score = ca.copilot_score(code_text)
    except ValueError:
        features = {}
        llm_score = 0.0

    todo_count = sum(
        1 for line in code_parts
        if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE)
    )

    return StyleMetrics(
        commit_sha=commit.sha,
        date=commit.date,
        author=commit.author,
        comment_density=features.get("comment_density", 0.0),
        docstring_coverage=features.get("docstring_completeness", 0.0),
        avg_identifier_length=features.get("identifier_verbosity", 0.0) * 20,
        error_handling_density=features.get("error_handling_density", 0.0) * 15,
        commit_message_length=len(msg_first_line),
        has_conventional_commit=bool(_CONVENTIONAL_COMMIT.match(msg_first_line)),
        todo_count=todo_count,
        total_lines_changed=sum(f.additions for f in commit.files),
        n_code_lines=len([l for l in code_parts if l.strip()]),
        n_comment_lines=int(features.get("comment_density", 0.0) * max(len(code_parts), 1)),
        llm_score=llm_score,
    )


def batch_extract(commits: list[Commit]) -> list[StyleMetrics]:
    return [extract_metrics(c) for c in commits if c.files]
