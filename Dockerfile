FROM python:3.13.14-slim-bookworm AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv==0.11.19

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13.14-slim-bookworm AS runtime

RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 src /app/src
COPY --chown=10001:10001 config /app/config

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "resume_matcher.main:app", "--host", "0.0.0.0", "--port", "8000"]
