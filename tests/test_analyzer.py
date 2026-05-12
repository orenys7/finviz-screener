import json
from unittest.mock import MagicMock

import anthropic
import pytest
from google.genai import errors as genai_errors

from finviz_screener.analyzer import _parse_response, _provider_for, analyze
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
    result = _parse_response(payload)
    assert isinstance(result, AnalysisResponse)
    assert result.score == 8
    assert "breakout" in result.analysis


def test_parse_response_strips_markdown_fences():
    payload = (
        "```json\n" + json.dumps({"score": 5, "analysis": "Mixed signals."}) + "\n```"
    )
    result = _parse_response(payload)
    assert result.score == 5


def test_parse_response_invalid_score_raises():
    payload = json.dumps({"score": 15, "analysis": "Out of range."})
    with pytest.raises(Exception):
        _parse_response(payload)


@pytest.mark.parametrize(
    "model,expected",
    [
        ("claude-sonnet-4-6", "anthropic"),
        ("claude-opus-4-7", "anthropic"),
        ("gemini-2.5-pro", "google"),
        ("gemini-2.5-flash", "google"),
    ],
)
def test_provider_for_dispatch(model: str, expected: str):
    assert _provider_for(model) == expected


def test_provider_for_unknown_prefix_raises():
    with pytest.raises(ValueError, match="unknown model prefix"):
        _provider_for("gpt-4")


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


def _make_genai_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _genai_api_error(code: int) -> genai_errors.APIError:
    err = genai_errors.APIError.__new__(genai_errors.APIError)
    err.code = code
    err.message = "overloaded"
    err.status = "RESOURCE_EXHAUSTED"
    err.details = None
    err.response = None
    return err


def test_analyze_gemini_returns_analysis_response():
    mock_client = MagicMock()
    good_json = json.dumps({"score": 8, "analysis": "Clean Gemini breakout call."})
    mock_client.models.generate_content.return_value = _make_genai_response(good_json)

    result = analyze(
        "NVDA", b"\x89PNG\r\nfake", "gemini-2.5-pro", client=mock_client
    )

    assert result.score == 8
    assert isinstance(result, AnalysisResponse)
    mock_client.models.generate_content.assert_called_once()


def test_analyze_gemini_retries_on_429():
    mock_client = MagicMock()
    good_json = json.dumps({"score": 7, "analysis": "Recovered after retry."})
    mock_client.models.generate_content.side_effect = [
        _genai_api_error(429),
        _make_genai_response(good_json),
    ]

    result = analyze(
        "TSLA", b"\x89PNG\r\nfake", "gemini-2.5-pro", client=mock_client
    )

    assert result.score == 7
    assert mock_client.models.generate_content.call_count == 2


def test_analyze_gemini_raises_after_two_429_errors():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = _genai_api_error(429)

    with pytest.raises(RuntimeError, match="overloaded"):
        analyze(
            "AMD", b"\x89PNG\r\nfake", "gemini-2.5-pro", client=mock_client
        )
