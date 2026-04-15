# syntax=docker/dockerfile:1.7

# ---------- Stage 1: build the Vite frontend ----------
FROM node:20-alpine AS frontend-builder
WORKDIR /front
COPY front/package.json front/package-lock.json ./
RUN npm ci
COPY front/ ./
RUN npm run build

# ---------- Stage 2: Python runtime ----------
FROM python:3.11-slim AS runtime
ARG TARGETARCH
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        lua5.4 curl ca-certificates unzip \
    && ln -sf /usr/bin/luac5.4 /usr/local/bin/luac \
    && rm -rf /var/lib/apt/lists/*

ARG SELENE_VERSION=0.27.1
RUN set -eux; \
    if [ "${TARGETARCH:-amd64}" = "amd64" ]; then \
        (curl -fsSL -o /tmp/selene.zip \
             "https://github.com/Kampfkarren/selene/releases/download/${SELENE_VERSION}/selene-${SELENE_VERSION}-linux.zip" \
             && unzip /tmp/selene.zip -d /usr/local/bin/ \
             && chmod +x /usr/local/bin/selene \
             && rm /tmp/selene.zip) \
        || echo "WARN: selene download failed; validator will skip it at runtime"; \
    else \
        echo "selene: no upstream prebuilt for ${TARGETARCH}; skipping"; \
    fi

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py ./

COPY lua_examples.txt ./docs/lua_examples.txt

COPY --from=frontend-builder /front/dist ./app/static

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python", "run.py"]
