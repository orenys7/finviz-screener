import pytest

from finviz_screener.scraper import (
    _build_rows,
    _column_indices,
    _parse_change,
    _parse_price,
    _parse_volume,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("$12.34", 12.34),
        ("12.34", 12.34),
        ("$1,234.56", 1234.56),
        ("0.01", 0.01),
        ("", None),
        (None, None),
        ("N/A", None),
        ("--", None),
    ],
)
def test_parse_price(text, expected):
    assert _parse_price(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.23%", 1.23),
        ("-1.23%", -1.23),
        ("0.00%", 0.0),
        ("12%", 12.0),
        ("", None),
        (None, None),
        ("--", None),
    ],
)
def test_parse_change(text, expected):
    assert _parse_change(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1.23M", 1_230_000),
        ("456K", 456_000),
        ("2.5B", 2_500_000_000),
        ("789", 789),
        ("1,234", 1234),
        ("", None),
        (None, None),
        ("--", None),
    ],
)
def test_parse_volume(text, expected):
    assert _parse_volume(text) == expected


def test_column_indices_resolves_by_header_text():
    headers = [
        "No.",
        "Ticker",
        "Company",
        "Sector",
        "Industry",
        "Country",
        "Market Cap",
        "P/E",
        "Price",
        "Change",
        "Volume",
    ]
    idx = _column_indices(headers)
    assert idx["ticker"] == 1
    assert idx["price"] == 8
    assert idx["change_pct"] == 9
    assert idx["volume"] == 10


def test_column_indices_falls_back_when_header_missing():
    # No "Price" or "Change" header → those should be None
    headers = ["No.", "Ticker", "Volume"]
    idx = _column_indices(headers)
    assert idx["ticker"] == 1
    assert idx["price"] is None
    assert idx["change_pct"] is None
    assert idx["volume"] == 2


def test_build_rows_parses_cells_in_resolved_order():
    headers = ["No.", "Ticker", "Price", "Change", "Volume"]
    raw_rows = [
        ["1", "NVDA", "$123.45", "2.50%", "12.3M"],
        ["2", "AAPL", "$200.10", "-0.75%", "45.6M"],
    ]
    idx = _column_indices(headers)
    rows = _build_rows(raw_rows, idx)
    assert len(rows) == 2
    assert rows[0].ticker == "NVDA"
    assert rows[0].price == 123.45
    assert rows[0].change_pct == 2.5
    assert rows[0].volume == 12_300_000
    assert rows[1].ticker == "AAPL"
    assert rows[1].change_pct == -0.75


def test_build_rows_tolerates_missing_market_data():
    headers = ["No.", "Ticker", "Price", "Change", "Volume"]
    raw_rows = [["1", "NEW", "--", "--", "--"]]
    idx = _column_indices(headers)
    rows = _build_rows(raw_rows, idx)
    assert len(rows) == 1
    assert rows[0].ticker == "NEW"
    assert rows[0].price is None
    assert rows[0].change_pct is None
    assert rows[0].volume is None
