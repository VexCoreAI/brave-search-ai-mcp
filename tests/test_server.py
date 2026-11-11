import asyncio
from types import SimpleNamespace

import pytest

from brave_search_ai_mcp import server


def test_rejects_empty_query_without_search(monkeypatch):
    def fail_if_called(*args, **kwargs):
        pytest.fail("scraper must not run for an empty query")

    monkeypatch.setattr(server, "run_brave_search", fail_if_called)

    result = asyncio.run(server.brave_search("  "))

    assert result == {"query": "", "error": "query must not be empty"}


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeout": 4}, "timeout must be between 5 and 120 seconds"),
        ({"timeout": 121}, "timeout must be between 5 and 120 seconds"),
        ({"retries": 0}, "retries must be between 1 and 5"),
        ({"retries": 6}, "retries must be between 1 and 5"),
    ],
)
def test_rejects_out_of_range_options(monkeypatch, kwargs, message):
    def fail_if_called(*args, **kwargs):
        pytest.fail("scraper must not run for invalid options")

    monkeypatch.setattr(server, "run_brave_search", fail_if_called)

    result = asyncio.run(server.brave_search("query", **kwargs))

    assert result == {"query": "query", "error": message}


def test_returns_search_answer_and_citations(monkeypatch):
    expected = SimpleNamespace(
        query="query",
        has_ai_response=True,
        answer="An answer.",
        citations=[
            SimpleNamespace(
                url="https://example.com", title="Example", snippet="Source"
            )
        ],
        followups=["A follow-up?"],
        conversation_id="conversation-1",
        strategy_used="SSE Network Interception",
        error_message="",
    )
    calls = []

    def search(query, **kwargs):
        calls.append((query, kwargs))
        return expected

    monkeypatch.setattr(server, "run_brave_search", search)

    result = asyncio.run(server.brave_search("  query  ", timeout=30, retries=2))

    assert calls == [("query", {"timeout_s": 30, "retries": 2})]
    assert result == {
        "query": "query",
        "has_ai_response": True,
        "answer": "An answer.",
        "citations": [
            {"url": "https://example.com", "title": "Example", "snippet": "Source"}
        ],
        "followups": ["A follow-up?"],
        "conversation_id": "conversation-1",
        "strategy": "SSE Network Interception",
        "error": None,
    }


def test_returns_scraper_exception_as_error(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("browser failed")

    monkeypatch.setattr(server, "run_brave_search", fail)

    result = asyncio.run(server.brave_search("query"))

    assert result == {"query": "query", "error": "RuntimeError: browser failed"}
