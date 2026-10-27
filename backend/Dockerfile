FROM node:20-bookworm-slim AS node

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

COPY --from=node /usr/local/bin/node /usr/local/bin/node

RUN sed -i 's|http://deb.debian.org/debian-security|https://mirrors.cloud.tencent.com/debian-security|g; s|http://deb.debian.org/debian|https://mirrors.cloud.tencent.com/debian|g' /etc/apt/sources.list.d/debian.sources \
    && env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy apt-get update \
    && env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV"

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip --index-url "$PIP_INDEX_URL" \
    && pip install --index-url "$PIP_INDEX_URL" -r /app/backend/requirements.txt

ARG PLAYWRIGHT_DOWNLOAD_PROXY
RUN env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy playwright install-deps chromium \
    && if [ -n "$PLAYWRIGHT_DOWNLOAD_PROXY" ]; then \
        HTTP_PROXY="$PLAYWRIGHT_DOWNLOAD_PROXY" HTTPS_PROXY="$PLAYWRIGHT_DOWNLOAD_PROXY" playwright install chromium; \
    else \
        playwright install chromium; \
    fi

COPY backend /app/backend
WORKDIR /app/backend

# The downloader uses curl for the Douyin media URL.
RUN env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy apt-get update \
    && env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
