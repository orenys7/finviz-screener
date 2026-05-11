from unittest.mock import MagicMock, patch

import pytest

from finviz_screener.charts import download_chart


def _make_response(content: bytes, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.content = content
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@patch("finviz_screener.charts.httpx.Client")
def test_download_chart_returns_bytes(mock_client_cls):
    fake_png = b"\x89PNG\r\nfake"
    ctx = mock_client_cls.return_value.__enter__.return_value
    ctx.get.return_value = _make_response(fake_png)

    result = download_chart("AAPL")

    assert result == fake_png
    ctx.get.assert_called_once()
    call_url = ctx.get.call_args[0][0]
    assert "AAPL" in call_url


@patch("finviz_screener.charts.httpx.Client")
def test_download_chart_uppercases_ticker(mock_client_cls):
    ctx = mock_client_cls.return_value.__enter__.return_value
    ctx.get.return_value = _make_response(b"\x89PNG\r\nfake")

    download_chart("aapl")

    call_url = ctx.get.call_args[0][0]
    assert "AAPL" in call_url
    assert "aapl" not in call_url


@patch("finviz_screener.charts.httpx.Client")
def test_download_chart_raises_on_empty_response(mock_client_cls):
    ctx = mock_client_cls.return_value.__enter__.return_value
    ctx.get.return_value = _make_response(b"")

    with pytest.raises(ValueError, match="empty chart"):
        download_chart("MSFT")
