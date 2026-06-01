"""dev-fingerprint CLI — devfp."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from rich.console import Console

from devfp.models import DeveloperConfig, Language

app = typer.Typer(
    name="devfp",
    help=(
        "[bold cyan]dev-fingerprint[/bold cyan] — "
        "P(behavioral drift | Git history) estimation for OSS contributors"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)

_CONFIGS_DIR = Path(__file__).parent.parent.parent / "configs"
_REPORTS_DIR = Path.cwd() / "reports"
_SAMPLE_DIR = Path(__file__).parent.parent.parent / "reports" / "sample"


def _load_configs(configs_dir: Path = _CONFIGS_DIR) -> dict[str, DeveloperConfig]:
    path = configs_dir / "developers.yaml"
    with path.open() as f:
        data = yaml.safe_load(f)

    result: dict[str, DeveloperConfig] = {}
    for dev in data["developers"]:
        cfg = DeveloperConfig(
            github_login=dev["github_login"],
            display_name=dev["display_name"],
            primary_language=Language(dev["primary_language"]),
            repos=dev.get("repos", []),
            notes=dev.get("notes", ""),
        )
        result[cfg.github_login] = cfg
    return result


@app.command()
def analyze(
    login: Annotated[str, typer.Argument(help="GitHub login to analyze (e.g. torvalds)")],
    commits: Annotated[int, typer.Option("--commits", "-n", help="Max commits to fetch")] = 300,
    since: Annotated[Optional[str], typer.Option(help="Start date (YYYY-MM-DD)")] = None,
    output: Annotated[Path, typer.Option(help="Output dir for JSON profile")] = _REPORTS_DIR,
    token: Annotated[Optional[str], typer.Option(envvar="GITHUB_TOKEN", help="GitHub token")] = None,
    html: Annotated[bool, typer.Option("--html/--no-html", help="Also generate HTML report")] = True,
    recent_n: Annotated[int, typer.Option(help="Recent windows for self-comparison test")] = 4,
    min_historical: Annotated[int, typer.Option(help="Minimum historical windows required")] = 6,
) -> None:
    """
    Fetch commits and estimate behavioral drift for a GitHub developer.

    Output: P(behavioral drift | Git history) — NOT P(AI-generated code).
    """
    from datetime import datetime

    from devfp.analyzer.fingerprint import build_profile, save_profile
    from devfp.collector.github import fetch_commits
    from devfp.reporter.terminal import print_profile
    from devfp.reporter.html import render_report

    configs = _load_configs()
    if login not in configs:
        err_console.print(f"[yellow]'{login}' not in configs/developers.yaml, using defaults.[/yellow]")
        cfg = DeveloperConfig(
            github_login=login,
            display_name=login,
            primary_language=Language.UNKNOWN,
            repos=[],
        )
    else:
        cfg = configs[login]

    if not cfg.repos:
        err_console.print(
            f"[red]No repos configured for '{login}'. Add them to configs/developers.yaml.[/red]"
        )
        raise typer.Exit(1)

    since_dt = datetime.fromisoformat(since) if since else None

    console.print(f"[bold cyan]Analyzing[/bold cyan] {cfg.display_name} ({login})")
    commits_list = asyncio.run(
        fetch_commits(login, cfg.repos, max_commits=commits, since=since_dt, token=token)
    )
    console.print(f"  Fetched [bold]{len(commits_list)}[/bold] commits")

    profile = build_profile(cfg, commits_list, recent_n=recent_n, min_historical=min_historical)
    json_path = save_profile(profile, output)
    console.print(f"  Profile saved → [dim]{json_path}[/dim]")

    print_profile(profile)

    if html:
        html_path = render_report(profile, output)
        console.print(f"\n  HTML report → [link=file://{html_path.resolve()}]{html_path}[/link]")


@app.command()
def compare(
    logins: Annotated[list[str], typer.Argument(help="GitHub logins to compare")],
    profiles_dir: Annotated[Path, typer.Option(help="Dir with pre-computed JSON profiles")] = _REPORTS_DIR,
    html: Annotated[bool, typer.Option("--html/--no-html")] = True,
    output: Annotated[Path, typer.Option()] = _REPORTS_DIR,
) -> None:
    """Compare behavioral fingerprints of multiple developers side by side."""
    from devfp.analyzer.fingerprint import load_profile
    from devfp.reporter.terminal import print_comparison
    from devfp.reporter.html import build_comparison_chart

    profiles = []
    for login in logins:
        path = profiles_dir / f"{login}.json"
        if not path.exists():
            err_console.print(
                f"[yellow]No profile for '{login}' in {profiles_dir}. "
                f"Run 'devfp analyze {login}' first.[/yellow]"
            )
            continue
        profiles.append(load_profile(path))

    if not profiles:
        err_console.print("[red]No profiles found.[/red]")
        raise typer.Exit(1)

    print_comparison(profiles)

    if html and len(profiles) > 1:
        fig = build_comparison_chart(profiles)
        out_path = output / "comparison.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(out_path))
        console.print(f"\n  Comparison chart → [dim]{out_path}[/dim]")


@app.command()
def score(
    login: Annotated[str, typer.Argument(help="GitHub login")],
    profiles_dir: Annotated[Path, typer.Option()] = _REPORTS_DIR,
) -> None:
    """Show the behavioral drift timeline for a developer."""
    from devfp.analyzer.fingerprint import load_profile
    from devfp.reporter.terminal import print_profile

    path = profiles_dir / f"{login}.json"
    if not path.exists():
        err_console.print(f"[red]Profile not found. Run: devfp analyze {login}[/red]")
        raise typer.Exit(1)

    print_profile(load_profile(path))


@app.command()
def demo() -> None:
    """Run a demo using pre-cached sample profiles (no GitHub token needed)."""
    from devfp.analyzer.fingerprint import load_profile
    from devfp.reporter.terminal import print_comparison, print_profile

    sample_profiles = list(_SAMPLE_DIR.glob("*.json"))
    if not sample_profiles:
        err_console.print("[red]No sample profiles found in reports/sample/[/red]")
        err_console.print("[dim]Run 'devfp analyze <login>' to generate profiles first.[/dim]")
        raise typer.Exit(1)

    profiles = [load_profile(p) for p in sorted(sample_profiles)]
    console.rule("[bold cyan]dev-fingerprint DEMO[/bold cyan]")
    console.print(f"[dim]Loaded {len(profiles)} sample profiles from reports/sample/[/dim]\n")
    print_comparison(profiles)
    console.print(
        "\n[dim]Run 'devfp analyze <login>' with a GITHUB_TOKEN to analyze any developer.[/dim]"
    )


@app.command(name="list")
def list_devs() -> None:
    """List all configured developers."""
    configs = _load_configs()

    from rich.table import Table
    from rich import box

    table = Table(box=box.SIMPLE, border_style="bright_black")
    table.add_column("Login", style="cyan")
    table.add_column("Display name")
    table.add_column("Language", style="dim")
    table.add_column("Repos", justify="right", style="dim")
    table.add_column("Notes", style="dim")

    for cfg in configs.values():
        table.add_row(
            cfg.github_login,
            cfg.display_name,
            cfg.primary_language.value,
            str(len(cfg.repos)),
            cfg.notes[:60] if cfg.notes else "",
        )

    console.print(table)


if __name__ == "__main__":
    app()
