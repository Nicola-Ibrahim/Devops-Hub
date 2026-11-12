FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
RUN useradd --system --uid 10001 app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.8.6 && uv sync --frozen --no-dev --no-install-project
COPY app ./app
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)"
CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
