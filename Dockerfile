FROM python:3.13-slim AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright"

WORKDIR /app

# git clones the active codebase (read-only, shallow; never run).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==0.8.22"

COPY pyproject.toml uv.lock README.md ./
# The development image includes the test and lint tools (pytest, ruff), so
# `docker compose exec web python -m pytest` works without installing anything.
RUN uv sync --locked --no-install-project

COPY . .
RUN uv sync --locked --no-install-project \
    && .venv/bin/python -m playwright install --with-deps chromium \
    && mkdir -p /app/output/runs /app/.runtime/repos \
    && groupadd --system app \
    && useradd --system --gid app --create-home app \
    && chown -R app:app /app /ms-playwright

USER app

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
