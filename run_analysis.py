"""Collect real GitHub data for all configured developers and save JSON profiles.

Sampling strategy: up to COMMITS_PER_YEAR commits per calendar year (2018–2025).
This gives uniform temporal coverage even for very active repos like linux.

Each commit is enriched with file-level metadata (filenames, additions, deletions,
diff patch) via a separate API call.  With a GitHub token this costs ~5000 req/hour;
the SQLite cache (TTL 7 days) avoids re-fetching on subsequent runs.

What is actually computed (honestly):
  Level A  — process signals from commit metadata (files changed, net lines,
             cross-module ratio, inter-commit hours, …).  These are real numbers.
  Level B  — test-touch ratio, merge ratio.  Real numbers.
  Level C  — style signals from AST analysis of diff patches.  Real numbers but
             scientifically weak (see CRITIQUE.md).
  Drift    — Mann-Whitney U per signal, Fisher combined p-value (Level A only).
             Returns None when history < recent_n + min_historical windows.

Run:
    GITHUB_TOKEN=<token> python run_analysis.py [--force] [--logins torvalds,dhh]

    --force  : ignore existing profiles and re-fetch from GitHub
    --logins : comma-separated list of logins to run (default: all)

Outputs:
    reports/real/<login>.json   — full DevProfile (commit to git)
    reports/real/summary.json   — cross-developer summary table

Cache: ~/.cache/dev-fingerprint/ (SQLite, TTL 7 days — do NOT commit this)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

OUTPUT_DIR = Path("reports/real")
CONFIGS_PATH = Path("configs/developers.yaml")

YEARS = list(range(2018, 2026))   # 2018 – 2025 inclusive
# 120 commits/year → ~30/quarter.  Enough for reliable medians and Mann-Whitney U.
# (The old pipeline used 60, which gave ~15/quarter — borderline for Level A.)
COMMITS_PER_YEAR = 120
MIN_COMMITS_FOR_ANALYSIS = 12


async def fetch_year_window(
    client,
    login: str,
    repos: list[str],
    year: int,
    per_year: int,
    name_filter: str | None = None,
) -> list:
    """Fetch up to per_year commits from a single calendar year across repos.

    Falls back to client-side name filtering when the ?author=login server filter
    misses commits (e.g. DHH whose old email isn't linked to his GitHub account).
    """
    import httpx
    since = datetime(year, 1, 1, tzinfo=timezone.utc)
    until = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    NAME_FILTER_THRESHOLD = 3

    all_commits = []
    for repo_full in repos:
        owner, _, repo_name = repo_full.partition("/")
        for attempt in range(3):
            try:
                async for commit in client.iter_commits(
                    owner, repo_name, login,
                    max_commits=per_year,
                    since=since,
                    until=until,
                ):
                    all_commits.append(commit)
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 451):
                    print(f"    [skip] {repo_full} — HTTP {e.response.status_code}")
                    break
                raise
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    print(f"    [skip] {repo_full} — network error after 3 attempts: {e}")

        if name_filter and len(all_commits) < NAME_FILTER_THRESHOLD:
            for attempt in range(3):
                try:
                    async for commit in client.iter_commits_by_name(
                        owner, repo_name, name_filter,
                        max_commits=per_year,
                        since=since,
                        until=until,
                    ):
                        all_commits.append(commit)
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (404, 451):
                        break
                    raise
                except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
                    if attempt < 2:
                        await asyncio.sleep(5 * (attempt + 1))
                    else:
                        print(f"    [skip name-filter] {repo_full} — {e}")

        if len(all_commits) >= per_year:
            break

    # Uniform temporal subsampling if over limit
    if len(all_commits) > per_year:
        step = len(all_commits) // per_year
        all_commits = all_commits[::step][:per_year]

    return all_commits


async def analyze_one(
    login: str,
    display_name: str,
    repos: list[str],
    token: str,
    force: bool = False,
    name_filter: str | None = None,
) -> dict:
    from devfp.collector.github import GitHubClient
    from devfp.collector.cache import GitHubCache
    from devfp.analyzer.fingerprint import build_profile, save_profile, profile_summary
    from devfp.models import DeveloperConfig, Language

    out_path = OUTPUT_DIR / f"{login}.json"
    if out_path.exists() and not force:
        print(f"  [cached] {login} — use --force to re-fetch")
        from devfp.analyzer.fingerprint import load_profile
        return profile_summary(load_profile(out_path))

    print(f"\n→ {display_name} ({login})")
    if name_filter:
        print(f"  [name-filter] client-side filtering on '{name_filter}'")

    all_commits = []
    async with GitHubClient(token=token, cache=GitHubCache()) as client:
        for year in YEARS:
            year_commits = await fetch_year_window(
                client, login, repos, year, COMMITS_PER_YEAR,
                name_filter=name_filter,
            )
            print(f"    {year}: {len(year_commits):>3} commits fetched")
            all_commits.extend(year_commits)

    # Deduplicate by SHA and sort chronologically
    seen: set[str] = set()
    deduped = []
    for c in all_commits:
        if c.sha not in seen:
            seen.add(c.sha)
            deduped.append(c)
    all_commits = sorted(deduped, key=lambda c: c.date)

    total = len(all_commits)
    print(f"  Total unique commits: {total}")

    if total < MIN_COMMITS_FOR_ANALYSIS:
        print(f"  [SKIP] Too few commits ({total} < {MIN_COMMITS_FOR_ANALYSIS})")
        return {
            "login": login,
            "display_name": display_name,
            "status": "skipped",
            "reason": "too_few_commits",
            "commits_analyzed": total,
        }

    cfg = DeveloperConfig(
        github_login=login,
        display_name=display_name,
        primary_language=Language.UNKNOWN,
        repos=repos,
    )
    profile = build_profile(cfg, all_commits)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_profile(profile, OUTPUT_DIR)

    summary = profile_summary(profile)

    dr = profile.drift_result
    if dr:
        print(f"  Fisher p={dr.combined_p_value}  → {dr.interpretation[:80]}…")
    else:
        print("  Drift result: None (insufficient history for statistical test)")

    n_level_a_cps = len(profile.level_a_change_points)
    print(f"  Level A change points: {n_level_a_cps}")

    return summary


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch real GitHub data and compute behavioral fingerprints."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-fetch from GitHub even if a profile already exists",
    )
    parser.add_argument(
        "--logins",
        help="Comma-separated list of logins to run (default: all configured developers)",
    )
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print(
            "ERROR: GITHUB_TOKEN not set.\n"
            "  export GITHUB_TOKEN=ghp_... && python run_analysis.py --force",
            file=sys.stderr,
        )
        sys.exit(1)

    with CONFIGS_PATH.open() as f:
        config = yaml.safe_load(f)

    developers = config["developers"]
    if args.logins:
        wanted = set(args.logins.split(","))
        developers = [d for d in developers if d["github_login"] in wanted]
        if not developers:
            print(f"ERROR: no developers matched --logins={args.logins}", file=sys.stderr)
            sys.exit(1)

    print(f"Analyzing {len(developers)} developers")
    print(f"Sampling:  {COMMITS_PER_YEAR} commits/year × {len(YEARS)} years "
          f"({YEARS[0]}–{YEARS[-1]}) ≈ {COMMITS_PER_YEAR // 4}/quarter")
    print(f"Output:    {OUTPUT_DIR}/")
    print()
    print("Signals computed:")
    print("  Level A (process) — files/commit, net lines, cross-module ratio,")
    print("                      refactor ratio, inter-commit hours, commits/week")
    print("  Level B (process) — test-touch ratio, merge ratio")
    print("  Level C (style)   — style score, comment density, docstring coverage, …")
    print("  Drift test        — Mann-Whitney U + Fisher (Level A only)")
    print()

    summaries = []
    for dev in developers:
        try:
            summary = await analyze_one(
                dev["github_login"],
                dev["display_name"],
                dev.get("repos", []),
                token,
                force=args.force,
                name_filter=dev.get("author_name"),
            )
            summaries.append(summary)
        except Exception as exc:
            print(f"  [ERROR] {dev['github_login']}: {exc}")
            summaries.append({
                "login": dev["github_login"],
                "display_name": dev["display_name"],
                "status": "error",
                "error": str(exc),
            })

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2, default=str))
    print(f"\nSummary → {summary_path}")

    # Display results table
    print()
    print(f"{'Developer':<28} {'Commits':>7} {'Win':>4} {'Fisher p':>9}  Level-A CPs")
    print("─" * 90)
    for s in summaries:
        if s.get("status") in ("skipped", "error"):
            reason = s.get("reason", s.get("error", ""))
            print(f"{s.get('display_name', s['login'])[:27]:<28}  [{s['status']}] {reason}")
            continue
        n_commits = s.get("commits_analyzed", "?")
        n_windows = s.get("windows_analyzed", "?")
        fisher_p = s.get("drift_combined_p")
        p_str = f"{fisher_p:.4f}" if fisher_p is not None else "n/a"
        cps = s.get("level_a_change_points", [])
        cp_str = ", ".join(
            f"{cp['date']} {cp['signal'][:14]}" for cp in cps
        ) or "—"
        print(f"{s.get('display_name', '?')[:27]:<28} {str(n_commits):>7} "
              f"{str(n_windows):>4} {p_str:>9}  {cp_str}")


if __name__ == "__main__":
    asyncio.run(main())
