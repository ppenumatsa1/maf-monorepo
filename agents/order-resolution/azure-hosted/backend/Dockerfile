ARG BACKEND_PLATFORM=linux/amd64
FROM --platform=${BACKEND_PLATFORM} python:3.13-slim AS wheelhouse

WORKDIR /build

ENV PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple

COPY requirements.lock ./
COPY .wheels/ /prebuilt-wheels/
RUN set -eux; \
    mkdir -p /wheels; \
    if find /prebuilt-wheels -maxdepth 1 -type f -name '*.whl' -print -quit | grep -q .; then \
        cp /prebuilt-wheels/*.whl /wheels/; \
    else \
        pip download \
            --disable-pip-version-check \
            --index-url "$PIP_INDEX_URL" \
            --extra-index-url https://pypi.org/simple \
            --only-binary=:all: \
            --platform manylinux2014_x86_64 \
            --python-version 3.13 \
            --implementation cp \
            --abi cp313 \
            --require-hashes \
            --dest /wheels \
            -r requirements.lock; \
    fi; \
    pip install --dry-run --no-index --find-links=/wheels \
        --require-hashes -r requirements.lock

FROM --platform=${BACKEND_PLATFORM} python:3.13-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple

COPY requirements.txt requirements.lock ./
COPY --from=wheelhouse /wheels/ /wheels/
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
