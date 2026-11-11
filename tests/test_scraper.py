from brave_search_ai_mcp.scraper import (
    BraveAIResult,
    _parse_sse_body,
    extract_conv_id,
    parse_sse_line,
)


def test_parse_sse_line_ignores_comments_and_invalid_json():
    assert parse_sse_line(": keep-alive") is None
    assert parse_sse_line("data: not-json") is None
    assert parse_sse_line('data: {"type":"text_stop","text":"hello"}') == {
        "type": "text_stop",
        "text": "hello",
    }


def test_extract_conversation_id_from_url():
    assert (
        extract_conv_id("https://example.com/search?conversation=abc-123&source=web")
        == "abc-123"
    )
    assert extract_conv_id("https://example.com/search") == ""


def test_parse_sse_answer_citations_and_followups():
    body = b"\n".join(
        [
            b'data: {"type":"text_stop","text":"Answer text."}',
            b'data: {"type":"augment_with_inline_citation","url":"https://example.com",'
            b'"title":"Example","snippet":"Source text"}',
            b'data: {"type":"followups","followups":["Why?"]}',
        ]
    )

    result = _parse_sse_body(body, BraveAIResult(query="question"))

    assert result.answer == "Answer text."
    assert [(citation.url, citation.title) for citation in result.citations] == [
        ("https://example.com", "Example")
    ]
    assert result.followups == ["Why?"]
