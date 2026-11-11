#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/." >&2
	exit 1
fi

uv sync --project "$DIR" --locked
uv run --project "$DIR" playwright install chromium
