# Contributing

## Local checks

Use Python 3.12 or newer and `uv`:

```sh
uv sync --locked --all-groups
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests must not require a live Brave Search request or a browser download.
Changes to the scraper should preserve upstream attribution in `NOTICE.md` and
the source module.

## Pull requests

Describe the user-visible behavior, include focused tests, and mention any
known changes in Brave website compatibility. Do not include API keys, browser
profiles, cookies, or personal search data.
