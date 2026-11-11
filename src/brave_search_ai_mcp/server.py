"""MCP server exposing Brave Search AI results over stdio."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import __version__
from .scraper import run_brave_search

mcp = MCPServer(
    "brave_search_ai_mcp",
    title="Brave Search AI",
    instructions=(
        "Search the web with Brave Search AI and return its answer, citations, "
        "and suggested follow-up questions. Results are extracted from the "
        "Brave Search website using a local Playwright browser."
    ),
    version=__version__,
)


@mcp.tool(
    name="brave_search",
    title="Search the web with Brave Search AI",
    annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True),
)
async def brave_search(
    query: str,
    timeout: int = 20,
    retries: int = 3,
) -> dict[str, Any]:
    """Search the web and return a concise AI answer with source citations.

    Args:
        query: A question or search phrase. Must contain non-whitespace text.
        timeout: Maximum seconds to wait for each browser attempt (5–120).
        retries: Number of attempts, including the first attempt (1–5).
    """
    query = query.strip()
    if not query:
        return {"query": query, "error": "query must not be empty"}
    if not 5 <= timeout <= 120:
        return {"query": query, "error": "timeout must be between 5 and 120 seconds"}
    if not 1 <= retries <= 5:
        return {"query": query, "error": "retries must be between 1 and 5"}

    try:
        result = await asyncio.to_thread(
            run_brave_search,
            query,
            timeout_s=timeout,
            retries=retries,
        )
    except Exception as exc:
        return {"query": query, "error": f"{type(exc).__name__}: {exc}"}

    return {
        "query": result.query,
        "has_ai_response": result.has_ai_response,
        "answer": result.answer,
        "citations": [
            {"url": citation.url, "title": citation.title, "snippet": citation.snippet}
            for citation in result.citations
        ],
        "followups": result.followups,
        "conversation_id": result.conversation_id,
        "strategy": result.strategy_used,
        "error": result.error_message or None,
    }


def main() -> None:
    """Run the MCP server using the portable stdio transport."""
    mcp.run(transport="stdio")
