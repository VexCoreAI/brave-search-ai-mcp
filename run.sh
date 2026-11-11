#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER="$DIR/.venv/bin/brave-search-ai-mcp"

if [[ ! -x "$SERVER" ]]; then
	echo "MCP server is not installed. Run $DIR/scripts/setup.sh first." >&2
	exit 1
fi

exec "$SERVER"
