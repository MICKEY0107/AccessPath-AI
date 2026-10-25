FROM python:3.13-slim AS development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright"

WORKDIR /app

RUN pip install --no-cache-dir "uv==0.8.22"

COPY pyproject.toml README.md ./
RUN uv sync --no-dev --no-install-project

COPY . .
RUN uv sync --no-dev --no-install-project \
    && .venv/bin/python -m playwright install --with-deps chromium \
    && mkdir -p /app/output/runs \
    && groupadd --system app \
    && useradd --system --gid app --create-home app \
    && chown -R app:app /app /ms-playwright

USER app

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
