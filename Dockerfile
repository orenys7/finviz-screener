# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install deps in a cached layer before copying source.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy source and install the project (editable).
COPY src/ ./src/
COPY config.yaml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Install Chromium + all required system libs.
RUN uv run playwright install --with-deps chromium \
    && chmod -R o+rX /ms-playwright

RUN useradd --create-home --uid 1001 app && chown -R app:app /app
USER app

# state.db lives on a mounted volume so history survives restarts.
ENV FINVIZ_DB_PATH=/data/state.db
VOLUME ["/data"]

ENTRYPOINT ["uv", "run", "python", "-m", "finviz_screener"]
CMD ["scan"]
