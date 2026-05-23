# Contributing to dev-fingerprint

## Ways to contribute

- **Add a developer** — edit `configs/developers.yaml` with a new GitHub login
- **Add a language** — extend `src/devfp/analyzer/style.py` (delegates to `stylometry-python`)
- **Add a signal** — add a feature to `stylometry-python` first, then wire it in `llm_signals.py`
- **Improve change-point detection** — `src/devfp/analyzer/temporal.py`
- **Fix a bug** — open an issue first, then a PR

## Setup

```bash
git clone https://github.com/riadmaouchi/dev-fingerprint
cd dev-fingerprint
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/
```

## Before submitting a PR

```bash
ruff check src/ tests/
mypy src/devfp/
pytest tests/ -v
```

All checks must pass. No new `Co-Authored-By` lines in commit messages.

## Adding a developer

```yaml
# configs/developers.yaml
- github_login: your-target
  display_name: "Developer Name"
  primary_language: python   # python | javascript | typescript | c | ruby | go | rust
  repos:
    - owner/repo
  notes: "Why this dev is interesting"
```

Then verify: `devfp analyze your-target --commits 50`

## Commit style

`feat:`, `fix:`, `docs:`, `chore:` prefixes. Keep messages under 72 chars.
