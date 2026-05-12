from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScreenerConfig(BaseModel):
    name: str
    url: str


class AppConfig(BaseModel):
    model: str = "claude-sonnet-4-6"
    score_threshold: int = 8
    min_score_to_store: int = 7
    lookback_runs: int = 6
    export_dir: str | None = None
    screeners: list[ScreenerConfig]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    discord_webhook_url: str = ""

    def require_key_for(self, model: str) -> None:
        if model.startswith("claude-") and not self.anthropic_api_key:
            raise ValueError(f"ANTHROPIC_API_KEY is required for model {model!r}")
        if model.startswith("gemini-") and not self.gemini_api_key:
            raise ValueError(f"GEMINI_API_KEY is required for model {model!r}")


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig.model_validate(data)
