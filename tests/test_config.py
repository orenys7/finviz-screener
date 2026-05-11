from pathlib import Path

import pytest

from finviz_screener.config import AppConfig, ScreenerConfig, load_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_returns_appconfig():
    config = load_config(FIXTURES / "config_test.yaml")
    assert isinstance(config, AppConfig)


def test_load_config_values():
    config = load_config(FIXTURES / "config_test.yaml")
    assert config.model == "claude-sonnet-4-6"
    assert config.score_threshold == 7
    assert config.lookback_runs == 4


def test_load_config_screeners():
    config = load_config(FIXTURES / "config_test.yaml")
    assert len(config.screeners) == 2
    assert all(isinstance(s, ScreenerConfig) for s in config.screeners)
    assert config.screeners[0].name == "test-screener"
    assert config.screeners[0].url.startswith("https://")


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config(FIXTURES / "nonexistent.yaml")


def test_appconfig_defaults():
    config = AppConfig(screeners=[])
    assert config.model == "claude-sonnet-4-6"
    assert config.score_threshold == 8
    assert config.lookback_runs == 6
