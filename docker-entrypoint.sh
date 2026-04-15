#!/usr/bin/env bash
set -e

LLM_BASE_URL="${LLM_BASE_URL:-http://ollama:11434/v1}"
OLLAMA_NATIVE="${OLLAMA_NATIVE_URL:-${LLM_BASE_URL%/v1}}"
LLM_MODEL="${LLM_MODEL:-lua-coder:mts}"
BASE_MODEL="${BASE_MODEL:-qwen2.5-coder:7b}"
EMBED_MODEL="${EMBED_MODEL:-nomic-embed-text}"
AUTO_BUILD_MODEL="${AUTO_BUILD_MODEL:-1}"
MODELFILE_PATH="${MODELFILE_PATH:-/app/app/Modelfile}"

log() { echo "[entrypoint] $*"; }

log "Probing Ollama at ${LLM_BASE_URL}/models ..."
OLLAMA_OK=""
for i in $(seq 1 60); do
    if curl -fsS -o /dev/null --max-time 2 "${LLM_BASE_URL}/models"; then
        log "Ollama reachable after ${i}s"
        OLLAMA_OK=1
        break
    fi
    sleep 1
done
[ -z "$OLLAMA_OK" ] && log "WARN: Ollama unreachable after 60s — continuing (lifespan warmup will log the failure)."

if [ "$AUTO_BUILD_MODEL" = "1" ] && [ -n "$OLLAMA_OK" ]; then
    if TAGS_JSON="$(curl -fsS --max-time 3 "${OLLAMA_NATIVE}/api/tags" 2>/dev/null)"; then
        need_base=1; need_embed=1; need_create=1
        echo "$TAGS_JSON" | grep -q "\"${BASE_MODEL}\""  && need_base=0
        echo "$TAGS_JSON" | grep -q "\"${EMBED_MODEL}\"" && need_embed=0
        echo "$TAGS_JSON" | grep -q "\"${LLM_MODEL}\""   && need_create=0

        if [ "$need_base" = "1" ]; then
            log "Pulling ${BASE_MODEL} (blocking, may take several minutes) ..."
            curl -fsS -X POST "${OLLAMA_NATIVE}/api/pull" \
                 -H 'Content-Type: application/json' \
                 -d "{\"name\":\"${BASE_MODEL}\",\"stream\":false}" >/dev/null \
              || log "WARN: pull ${BASE_MODEL} failed"
        fi
        if [ "$need_embed" = "1" ]; then
            log "Pulling ${EMBED_MODEL} ..."
            curl -fsS -X POST "${OLLAMA_NATIVE}/api/pull" \
                 -H 'Content-Type: application/json' \
                 -d "{\"name\":\"${EMBED_MODEL}\",\"stream\":false}" >/dev/null \
              || log "WARN: pull ${EMBED_MODEL} failed"
        fi
        if [ "$need_create" = "1" ] && [ -f "$MODELFILE_PATH" ]; then
            log "Creating ${LLM_MODEL} from ${MODELFILE_PATH} ..."
            MF_JSON="$(python3 -c 'import json,sys; print(json.dumps(open(sys.argv[1]).read()))' "$MODELFILE_PATH")"
            curl -fsS -X POST "${OLLAMA_NATIVE}/api/create" \
                 -H 'Content-Type: application/json' \
                 -d "{\"name\":\"${LLM_MODEL}\",\"modelfile\":${MF_JSON}}" >/dev/null \
              || log "WARN: create ${LLM_MODEL} failed"
        fi
    else
        log "WARN: ${OLLAMA_NATIVE}/api/tags unreachable — skipping auto-build."
    fi
fi

exec "$@"
