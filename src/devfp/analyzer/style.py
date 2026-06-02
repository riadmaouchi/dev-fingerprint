"""Extract code metrics and process signals from commits."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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

# ── Level-D: new-file content signal patterns ─────────────────────────────────

# Python
_PY_FUNC_DEF  = re.compile(r"^\s*(?:async\s+)?def\s+\w+\s*\(")
_PY_RETURN_T  = re.compile(r"\)\s*->\s*\S")           # has return type annotation
_PY_DOCSTRING = re.compile(r'^\s*(?:"""|\'\'\')')
_PY_TRY       = re.compile(r"^\s*try\s*:")
_PY_DECORATOR = re.compile(r"^\s*@")

# TypeScript / JavaScript
_TS_FUNC_DEF  = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+\w+"            # function keyword
    r"|^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\("  # arrow
    r"|^\s*(?:public|private|protected|static|async|override).*\w+\s*\("  # method
)
_TS_RETURN_T  = re.compile(r"\)\s*:\s*\w")             # ): ReturnType
_TS_JSDOC     = re.compile(r"^\s*/\*\*")
_TS_TRY       = re.compile(r"^\s*try\s*\{")

_SUPPORTED_LANGUAGES = {Language.PYTHON, Language.TYPESCRIPT, Language.JAVASCRIPT}

# Comment-line patterns for patch-level signal extraction (all modified files).
# Used by _extract_patch_signals() — validated in companion study copilot-signal.
_COMMENT_RE: dict[Language, re.Pattern] = {
    Language.PYTHON:     re.compile(r"^\s*#"),
    Language.JAVASCRIPT: re.compile(r"^\s*(//|/\*|\*)"),
    Language.TYPESCRIPT: re.compile(r"^\s*(//|/\*|\*)"),
    Language.GO:         re.compile(r"^\s*//"),
    Language.RUST:       re.compile(r"^\s*//"),
    Language.C:          re.compile(r"^\s*(//|/\*|\*)"),
}


@dataclass
class _NewFileStats:
    fn_count: int = 0
    typed_fn_count: int = 0
    docstring_fn_count: int = 0
    try_count: int = 0
    total_lines: int = 0


def _analyze_new_file(lines: list[str], language: Language) -> _NewFileStats:
    """
    Count annotation quality signals in lines extracted from a newly created file.

    Operates on added lines from the patch (which for a new file is the full content).
    Uses conservative heuristics: only counts return-type annotations (not param-only),
    so the signal is systematic rather than noisy.
    """
    stats = _NewFileStats(total_lines=sum(1 for l in lines if l.strip()))
    pending_fn = False           # True after a function def line, waiting for docstring
    pending_fn_py = False        # Python-specific: need to skip decorators
    prev_jsdoc = False           # TS/JS: previous non-continuation line was /**

    if language == Language.PYTHON:
        for line in lines:
            stripped = line.rstrip()
            bare = stripped.lstrip()

            if _PY_TRY.match(bare):
                stats.try_count += 1

            if _PY_FUNC_DEF.match(bare):
                stats.fn_count += 1
                if _PY_RETURN_T.search(bare):
                    stats.typed_fn_count += 1
                pending_fn = True
                continue

            if pending_fn and bare:
                if _PY_DOCSTRING.match(bare):
                    stats.docstring_fn_count += 1
                # decorator after def is unusual but reset regardless
                pending_fn = False

    elif language in (Language.TYPESCRIPT, Language.JAVASCRIPT):
        for line in lines:
            bare = line.strip()

            if _TS_TRY.match(bare):
                stats.try_count += 1

            is_jsdoc = bool(_TS_JSDOC.match(bare))
            is_fn = bool(_TS_FUNC_DEF.match(bare))

            if is_fn:
                stats.fn_count += 1
                if _TS_RETURN_T.search(bare):
                    stats.typed_fn_count += 1
                if prev_jsdoc:
                    stats.docstring_fn_count += 1
                prev_jsdoc = False
            elif is_jsdoc:
                prev_jsdoc = True
            elif bare and not bare.startswith("*") and not bare.startswith("*/"):
                prev_jsdoc = False

    return stats


def _extract_level_d(commit: Commit) -> dict[str, float | int]:
    """
    Extract Level-D content signals from newly created files in this commit.

    Returns a dict of per-commit Level-D values, all 0 if no new source files exist.
    """
    new_files = [
        f for f in commit.files
        if f.status == "added" and f.language in _SUPPORTED_LANGUAGES and f.patch
    ]
    if not new_files:
        return {"new_file_count": 0, "new_file_fn_count": 0,
                "new_file_typed_fn_ratio": 0.0, "new_file_docstring_fn_ratio": 0.0,
                "new_file_try_per_100": 0.0}

    totals = _NewFileStats()
    for f in new_files:
        added = _extract_added_lines(f.patch)
        s = _analyze_new_file(added, f.language)
        totals.fn_count         += s.fn_count
        totals.typed_fn_count   += s.typed_fn_count
        totals.docstring_fn_count += s.docstring_fn_count
        totals.try_count        += s.try_count
        totals.total_lines      += s.total_lines

    fn = max(totals.fn_count, 1)
    lines = max(totals.total_lines, 1)
    return {
        "new_file_count": len(new_files),
        "new_file_fn_count": totals.fn_count,
        "new_file_typed_fn_ratio": totals.typed_fn_count / fn,
        "new_file_docstring_fn_ratio": totals.docstring_fn_count / fn,
        "new_file_try_per_100": totals.try_count * 100.0 / lines,
    }


def _extract_patch_signals(commit: Commit) -> dict[str, float]:
    """
    Compute comment density and blank-line ratio from added lines across ALL
    modified files (not just new files).

    These patch-level signals are more targeted than the full-file CodeAnalyzer
    metrics because they only measure what the developer actually wrote in this
    commit, not the surrounding existing code.

    Validated as the most consistent Level B signals in copilot-signal
    (github.com/riadmaouchi/copilot-signal): higher in Copilot-tagged commits
    in 2/3 testable repos (comment_density p=0.004–0.024; blank_line_ratio
    p=0.008 across two independent repos).
    """
    total_added = 0
    blank_added = 0
    comment_lines = 0

    for f in commit.files:
        if not f.patch or f.language not in _COMMENT_RE:
            continue
        pattern = _COMMENT_RE[f.language]
        for line in f.patch.splitlines():
            if not (line.startswith("+") and not line.startswith("+++")):
                continue
            raw = line[1:]
            total_added += 1
            if not raw.strip():
                blank_added += 1
            elif pattern.match(raw):
                comment_lines += 1

    code_lines = total_added - blank_added
    return {
        "patch_comment_density": comment_lines / max(code_lines, 1),
        "patch_blank_line_ratio": blank_added / max(total_added, 1),
    }


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

    level_d = _extract_level_d(commit)
    patch_sigs = _extract_patch_signals(commit)

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
            **level_d,
            **patch_sigs,
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
        # Level D — content signals on new files
        **level_d,
        # Level B — patch-level content signals (all files)
        **patch_sigs,
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
