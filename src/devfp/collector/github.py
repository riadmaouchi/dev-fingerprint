"""GitHub API client with rate limiting and disk caching."""

from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from devfp.collector.cache import GitHubCache
from devfp.models import Commit, CommitFile, Language

_console = Console(stderr=True)

_EXT_TO_LANG: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".c": Language.C,
    ".h": Language.C,
    ".rb": Language.RUBY,
    ".go": Language.GO,
    ".rs": Language.RUST,
}


def _detect_language(filename: str) -> Language:
    suffix = Path(filename).suffix.lower()
    return _EXT_TO_LANG.get(suffix, Language.UNKNOWN)


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(
        self,
        token: Optional[str] = None,
        cache: Optional[GitHubCache] = None,
    ) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._cache = cache or GitHubCache()
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client = httpx.AsyncClient(
            base_url=self.BASE,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )
        self._last_request_at: float = 0.0

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        cache_key = f"{path}?{params}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        # Respect GitHub rate limit: min 72ms between requests (~14 req/s)
        gap = time.monotonic() - self._last_request_at
        if gap < 0.072:
            await asyncio.sleep(0.072 - gap)

        resp = await self._client.get(path, params=params)
        self._last_request_at = time.monotonic()

        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            _console.print(f"[yellow]Rate limited. Waiting {wait}s...[/yellow]")
            await asyncio.sleep(wait)
            resp = await self._client.get(path, params=params)

        resp.raise_for_status()
        data = resp.json()
        self._cache.set(cache_key, data)
        return data

    async def get_user_repos(self, login: str) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = await self._get(
                f"/users/{login}/repos",
                {"per_page": 100, "page": page, "sort": "pushed", "type": "owner"},
            )
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return repos

    async def iter_commits(
        self,
        owner: str,
        repo: str,
        author: str,
        max_commits: int = 500,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AsyncIterator[Commit]:
        fetched = 0
        page = 1
        params: dict[str, Any] = {"per_page": 100, "author": author}
        if since:
            params["since"] = since.isoformat()
        if until:
            params["until"] = until.isoformat()

        while fetched < max_commits:
            params["page"] = page
            batch = await self._get(f"/repos/{owner}/{repo}/commits", params)
            if not batch:
                break

            for raw in batch:
                if fetched >= max_commits:
                    return
                commit = await self._enrich_commit(owner, repo, raw)
                if commit:
                    yield commit
                    fetched += 1

            if len(batch) < 100:
                break
            page += 1

    async def _enrich_commit(
        self, owner: str, repo: str, raw: dict[str, Any]
    ) -> Optional[Commit]:
        sha = raw["sha"]
        detail = await self._get(f"/repos/{owner}/{repo}/commits/{sha}")

        author_info = detail.get("commit", {}).get("author", {})
        date_str = author_info.get("date")
        if not date_str:
            return None

        files: list[CommitFile] = []
        for f in detail.get("files", []):
            files.append(
                CommitFile(
                    filename=f["filename"],
                    language=_detect_language(f["filename"]),
                    additions=f.get("additions", 0),
                    deletions=f.get("deletions", 0),
                    patch=f.get("patch"),
                )
            )

        return Commit(
            sha=sha,
            author=detail.get("commit", {}).get("author", {}).get("name", "unknown"),
            date=datetime.fromisoformat(date_str.replace("Z", "+00:00")),
            message=detail.get("commit", {}).get("message", ""),
            files=files,
        )

    async def close(self) -> None:
        await self._client.aclose()
        self._cache.close()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


async def fetch_commits(
    login: str,
    repos: list[str],
    max_commits: int = 500,
    since: Optional[datetime] = None,
    token: Optional[str] = None,
    cache_dir: Optional[Path] = None,
) -> list[Commit]:
    """Fetch commits for a developer across given repos."""
    all_commits: list[Commit] = []

    async with GitHubClient(token=token, cache=GitHubCache(cache_dir)) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=_console,
        ) as progress:
            task = progress.add_task(f"Fetching {login}", total=len(repos))
            for repo_full in repos:
                owner, _, repo_name = repo_full.partition("/")
                progress.update(task, description=f"[cyan]{login}[/] / {repo_name}")
                async for commit in client.iter_commits(
                    owner, repo_name, login, max_commits=max_commits, since=since
                ):
                    all_commits.append(commit)
                progress.advance(task)

    all_commits.sort(key=lambda c: c.date)
    return all_commits
