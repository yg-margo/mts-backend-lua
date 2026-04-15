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
        lua5.4 curl ca-certificates \
    && ln -sf /usr/bin/luac5.4 /usr/local/bin/luac \
    && rm -rf /var/lib/apt/lists/*

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
