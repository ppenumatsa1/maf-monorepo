FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple

WORKDIR /app

COPY backend/requirements.txt backend/requirements.lock ./
COPY .wheels/ /wheels/
RUN pip install --no-cache-dir --no-index --find-links=/wheels \
        --require-hashes -r requirements.lock \
    && rm -rf /wheels

RUN adduser --disabled-password --gecos "" appuser

COPY --chown=appuser:appuser backend /app/backend

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
