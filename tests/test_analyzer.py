import json
from unittest.mock import MagicMock, patch

import anthropic
import pytest

from finviz_screener.analyzer import analyze, _parse_response
from finviz_screener.models import AnalysisResponse


def _overloaded_error() -> anthropic.InternalServerError:
    import httpx

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(529, text="overloaded", request=req)
    return anthropic.InternalServerError(message="overloaded", response=resp, body=None)


def _make_message(text: str, cache_read: int = 0, cache_created: int = 0) -> MagicMock:
    msg = MagicMock(spec=anthropic.types.Message)
    content_block = MagicMock()
    content_block.text = text
    msg.content = [content_block]
    usage = MagicMock()
    usage.input_tokens = 100
    usage.cache_read_input_tokens = cache_read
    usage.cache_creation_input_tokens = cache_created
    msg.usage = usage
    return msg


def test_parse_response_clean_json():
    payload = json.dumps({"score": 8, "analysis": "Strong breakout with volume."})
    msg = _make_message(payload)
    result = _parse_response(msg)
    assert isinstance(result, AnalysisResponse)
    assert result.score == 8
    assert "breakout" in result.analysis


def test_parse_response_strips_markdown_fences():
    payload = (
        "```json\n" + json.dumps({"score": 5, "analysis": "Mixed signals."}) + "\n```"
    )
    msg = _make_message(payload)
    result = _parse_response(msg)
    assert result.score == 5


def test_parse_response_invalid_score_raises():
    payload = json.dumps({"score": 15, "analysis": "Out of range."})
    msg = _make_message(payload)
    with pytest.raises(Exception):
        _parse_response(msg)


def test_analyze_returns_analysis_response():
    mock_client = MagicMock(spec=anthropic.Anthropic)
    timed = MagicMock()
    mock_client.with_options.return_value = timed

    good_json = json.dumps({"score": 9, "analysis": "Ideal setup."})
    timed.messages.create.return_value = _make_message(good_json, cache_read=2048)

    result = analyze(
        "NVDA", b"\x89PNG\r\nfake", "claude-sonnet-4-6", client=mock_client
    )

    assert result.score == 9
    assert isinstance(result, AnalysisResponse)
    timed.messages.create.assert_called_once()


def test_analyze_retries_on_overload():
    mock_client = MagicMock(spec=anthropic.Anthropic)
    timed = MagicMock()
    mock_client.with_options.return_value = timed

    good_json = json.dumps({"score": 7, "analysis": "Good setup after retry."})
    timed.messages.create.side_effect = [
        _overloaded_error(),
        _make_message(good_json),
    ]

    result = analyze(
        "TSLA", b"\x89PNG\r\nfake", "claude-sonnet-4-6", client=mock_client
    )

    assert result.score == 7
    assert timed.messages.create.call_count == 2


def test_analyze_raises_after_two_overload_errors():
    mock_client = MagicMock(spec=anthropic.Anthropic)
    timed = MagicMock()
    mock_client.with_options.return_value = timed

    timed.messages.create.side_effect = _overloaded_error()

    with pytest.raises(RuntimeError, match="overloaded"):
        analyze("AMD", b"\x89PNG\r\nfake", "claude-sonnet-4-6", client=mock_client)
