FROM python:3.13-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt requirements.lock ./
COPY .wheels/ /wheels/
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
        --require-hashes -r requirements.lock \
    && rm -rf /wheels

RUN adduser --disabled-password --gecos "" appuser

COPY --chown=appuser:appuser . .
RUN mkdir -p /app/.foundry/checkpoints /app/.foundry/memory /app/.foundry/results \
    && chown -R appuser:appuser /app/.foundry

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
