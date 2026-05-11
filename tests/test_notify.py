from unittest.mock import MagicMock, call, patch

import pytest

from finviz_screener.models import NewHit
from finviz_screener.notify import post_discord, _color, _embed

WEBHOOK = "https://discord.com/api/webhooks/123/abc"


def hit(ticker: str = "AAPL", score: int = 9, screener: str = "s1") -> NewHit:
    return NewHit(
        ticker=ticker, screener=screener, score=score, analysis="Strong breakout."
    )


def _mock_resp(status_code: int = 204) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = ""
    resp.is_client_error = 400 <= status_code < 500
    resp.is_server_error = status_code >= 500
    return resp


# ── color helper ──────────────────────────────────────────────────────────────


def test_color_score_10_is_green():
    assert _color(10) == 0x2ECC71


def test_color_score_9_is_green():
    assert _color(9) == 0x2ECC71


def test_color_score_8_is_gold():
    assert _color(8) == 0xF1C40F


def test_color_score_5_is_orange():
    assert _color(5) == 0xE67E22


def test_color_score_3_is_red():
    assert _color(3) == 0xE74C3C


# ── embed builder ─────────────────────────────────────────────────────────────


def test_embed_contains_ticker_and_score():
    e = _embed(hit("NVDA", 9))
    assert "NVDA" in e["title"]
    assert "9" in e["title"]


def test_embed_url_points_to_finviz_quote():
    e = _embed(hit("MSFT", 8))
    assert "MSFT" in e["url"]
    assert "finviz.com/quote" in e["url"]


def test_embed_chart_field_contains_chart_link():
    e = _embed(hit("TSLA", 9))
    chart_field = next(f for f in e["fields"] if f["name"] == "Chart")
    assert "TSLA" in chart_field["value"]
    assert "chart.ashx" in chart_field["value"]


def test_embed_screener_field_value():
    e = _embed(hit("AMD", 9, screener="breakouts"))
    screener_field = next(f for f in e["fields"] if f["name"] == "Screener")
    assert screener_field["value"] == "breakouts"


# ── post_discord — no-op cases ────────────────────────────────────────────────


@patch("finviz_screener.notify.httpx.Client")
def test_empty_hits_sends_nothing(mock_client):
    post_discord([], WEBHOOK)
    mock_client.assert_not_called()


@patch("finviz_screener.notify.httpx.Client")
def test_no_webhook_url_sends_nothing(mock_client):
    post_discord([hit()], "")
    mock_client.assert_not_called()


# ── post_discord — happy path ─────────────────────────────────────────────────


@patch("finviz_screener.notify.httpx.Client")
def test_single_hit_sends_one_request(mock_client):
    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.return_value = _mock_resp(204)

    post_discord([hit()], WEBHOOK)

    ctx.post.assert_called_once()
    url = ctx.post.call_args[0][0]
    assert url == WEBHOOK


@patch("finviz_screener.notify.httpx.Client")
def test_payload_has_content_on_first_batch(mock_client):
    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.return_value = _mock_resp(204)

    post_discord([hit("AAPL", 9), hit("MSFT", 8)], WEBHOOK)

    payload = ctx.post.call_args[1]["json"]
    assert "content" in payload
    assert "2" in payload["content"]


@patch("finviz_screener.notify.httpx.Client")
def test_more_than_10_hits_sends_multiple_requests(mock_client):
    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.return_value = _mock_resp(204)

    hits = [hit(f"T{i}", 9) for i in range(13)]
    post_discord(hits, WEBHOOK)

    assert ctx.post.call_count == 2
    first_payload = ctx.post.call_args_list[0][1]["json"]
    second_payload = ctx.post.call_args_list[1][1]["json"]
    assert len(first_payload["embeds"]) == 10
    assert len(second_payload["embeds"]) == 3
    # content header only on first batch
    assert "content" in first_payload
    assert "content" not in second_payload


# ── post_discord — error handling (no raise) ─────────────────────────────────


@patch("finviz_screener.notify.httpx.Client")
def test_4xx_response_logs_error_does_not_raise(mock_client):
    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.return_value = _mock_resp(400)

    post_discord([hit()], WEBHOOK)  # must not raise


@patch("finviz_screener.notify.httpx.Client")
def test_5xx_response_logs_error_does_not_raise(mock_client):
    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.return_value = _mock_resp(500)

    post_discord([hit()], WEBHOOK)  # must not raise


@patch("finviz_screener.notify.httpx.Client")
def test_timeout_does_not_raise(mock_client):
    import httpx

    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.side_effect = httpx.TimeoutException("timed out")

    post_discord([hit()], WEBHOOK)  # must not raise


@patch("finviz_screener.notify.httpx.Client")
def test_network_error_does_not_raise(mock_client):
    import httpx

    ctx = mock_client.return_value.__enter__.return_value
    ctx.post.side_effect = httpx.NetworkError("connection refused")

    post_discord([hit()], WEBHOOK)  # must not raise
