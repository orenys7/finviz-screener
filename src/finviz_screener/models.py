from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    score: int = Field(ge=1, le=10)
    analysis: str


class Signal(BaseModel):
    ticker: str
    screener: str
    score: int
    analysis: str
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class ScreenerRow(BaseModel):
    ticker: str
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class RunRow(BaseModel):
    id: int
    started_at: str
    finished_at: str | None = None
    status: str  # 'ok' | 'partial' | 'failed'


class NewHit(BaseModel):
    ticker: str
    screener: str
    score: int
    analysis: str


# ── Dashboard / API response models ──────────────────────────────────────────


class SignalRow(BaseModel):
    ticker: str
    screener: str
    score: int
    analysis: str
    is_new_hit: bool = False
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class RunSummary(BaseModel):
    id: int
    started_at: str
    finished_at: str | None = None
    status: str
    n_signals: int
    n_new_hits: int


class RunDetailResponse(BaseModel):
    run: RunSummary
    signals: list[SignalRow]


# Same shape as RunDetailResponse; named separately for API clarity.
LatestRunResponse = RunDetailResponse


class Manifest(BaseModel):
    generated_at: str
    latest_run_id: int | None = None
    score_threshold: int = 8
