"""Collect real GitHub data for all configured developers and save JSON profiles.

Sampling strategy: up to COMMITS_PER_YEAR commits per calendar year (2018–2024).
This gives uniform temporal coverage even for very active repos like linux.

Run:
    GITHUB_TOKEN=... python run_analysis.py [--force]

    --force  : ignore existing profiles and re-fetch
    --logins : comma-separated list of logins to (re-)run (e.g. --logins torvalds,gaearon)

Outputs:
    reports/real/<login>.json   — computed profile (commit this to git)
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

YEARS = list(range(2018, 2025))        # 2018 – 2024 inclusive
COMMITS_PER_YEAR = 60                  # enough to fill a quarter (~15/quarter)
MIN_COMMITS_FOR_ANALYSIS = 12         # skip developers with too few commits


async def fetch_year_window(
    client,
    login: str,
    repos: list[str],
    year: int,
    per_year: int,
) -> list:
    """Fetch up to per_year commits from a single calendar year."""
    import httpx
    from datetime import datetime, timezone
    since = datetime(year, 1, 1, tzinfo=timezone.utc)
    until = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

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
                break  # success
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 451):
                    print(f"    [skip] {repo_full} — {e.response.status_code}")
                    break
                raise
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as e:
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    print(f"    [skip] {repo_full} — network error after 3 attempts: {e}")
        if len(all_commits) >= per_year:
            break

    # Keep at most per_year, spread evenly (take every Nth)
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
) -> dict:
    from devfp.collector.github import GitHubClient
    from devfp.collector.cache import GitHubCache
    from devfp.analyzer.fingerprint import build_profile, save_profile
    from devfp.models import DeveloperConfig, Language

    out_path = OUTPUT_DIR / f"{login}.json"
    if out_path.exists() and not force:
        print(f"  [cached] {login} — profile already exists, skipping (use --force to re-run)")
        from devfp.analyzer.fingerprint import load_profile
        profile = load_profile(out_path)
        return _summarize(profile)

    print(f"\n→ {display_name} ({login})")

    all_commits = []
    async with GitHubClient(token=token, cache=GitHubCache()) as client:
        for year in YEARS:
            year_commits = await fetch_year_window(
                client, login, repos, year, COMMITS_PER_YEAR
            )
            print(f"    {year}: {len(year_commits):>3} commits")
            all_commits.extend(year_commits)

    # Deduplicate by SHA
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
        print(f"  [SKIP] Too few commits for reliable trend ({total} < {MIN_COMMITS_FOR_ANALYSIS})")
        return {"login": login, "status": "skipped", "reason": "too_few_commits", "commits": total}

    cfg = DeveloperConfig(
        github_login=login,
        display_name=display_name,
        primary_language=Language.UNKNOWN,
        repos=repos,
    )
    profile = build_profile(cfg, all_commits)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_profile(profile, OUTPUT_DIR)

    result = _summarize(profile)
    drift = result.get("drift")
    baseline = result.get("baseline")
    post = result.get("post_llm")
    print(f"  baseline={baseline}  post={post}  drift={drift}")
    print(f"  change_points: {len(result.get('change_points', []))}")
    return result


def _summarize(profile) -> dict:
    from devfp.analyzer.fingerprint import compute_drift
    drift_stats = compute_drift(profile.score_timeline)

    return {
        "login": profile.github_login,
        "display_name": profile.display_name,
        "status": "ok",
        "commits": profile.total_commits_analyzed,
        "quarters": len(profile.score_timeline),
        "baseline": round(drift_stats["baseline_mean"], 1) if "baseline_mean" in drift_stats else None,
        "post_llm": round(drift_stats["post_llm_mean"], 1) if "post_llm_mean" in drift_stats else None,
        "drift": round(drift_stats["drift"], 1) if "drift" in drift_stats else None,
        "change_points": [
            {
                "date": cp.date.strftime("%Y-%m"),
                "magnitude": round(cp.magnitude, 1),
                "event": cp.nearest_llm_event,
            }
            for cp in profile.change_points
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch real GitHub data for all configured developers")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if profile exists")
    parser.add_argument("--logins", help="Comma-separated list of logins to run (default: all)")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    with CONFIGS_PATH.open() as f:
        config = yaml.safe_load(f)

    developers = config["developers"]
    if args.logins:
        wanted = set(args.logins.split(","))
        developers = [d for d in developers if d["github_login"] in wanted]

    print(f"Analyzing {len(developers)} developers …")
    print(f"Sampling: {COMMITS_PER_YEAR} commits/year × {len(YEARS)} years ({YEARS[0]}–{YEARS[-1]})")
    print(f"Output: {OUTPUT_DIR}/")
    print()

    results = []
    for dev in developers:
        result = await analyze_one(
            dev["github_login"],
            dev["display_name"],
            dev.get("repos", []),
            token,
            force=args.force,
        )
        results.append(result)

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, indent=2))
    print(f"\n\nSummary → {summary_path}")

    # Print table
    print()
    print(f"{'Developer':<25} {'Commits':>7} {'Q':>3} {'Baseline':>9} {'Post-LLM':>9} {'Drift':>7}  Change points")
    print("-" * 95)
    for r in results:
        if r["status"] == "ok":
            cps = "  ".join(
                f"{cp['date']} Δ{cp['magnitude']}" for cp in r.get("change_points", [])
            ) or "—"
            print(f"{r['display_name'][:24]:<25} {r['commits']:>7} {r['quarters']:>3} "
                  f"{str(r['baseline']):>9} {str(r['post_llm']):>9} {str(r['drift']):>7}  {cps}")
        else:
            print(f"{r['login']:<25}  [{r['status']}]  {r.get('reason', '')}")


if __name__ == "__main__":
    asyncio.run(main())
