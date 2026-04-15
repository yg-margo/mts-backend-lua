workspace "LocalScript API" "Lua code generator для MWS Octapi/LowCode, работает целиком on-prem через Ollama." {

    model {

        developer = person "Разработчик Octapi/LowCode" "Пишет задачу на естественном языке, получает Lua-скрипт и исполняет его локально."

        ollama = softwareSystem "Ollama" "Локальный LLM-хост на :11434. Модель: lua-coder:mts (chat, num_ctx=4096, num_predict=256). OpenAI-compat API." {
            tags "External"
        }

        luaTools = softwareSystem "Lua Toolchain" "Shell-бинари: luac -p (обязательный, синтаксис) и selene (опциональный линтинг)." {
            tags "External"
        }

        localscript = softwareSystem "LocalScript API" "Сервис генерации Lua через локальный LLM с clarifier/planner/validator/fixer пайплайном." {

            frontend = container "Frontend SPA" "3-панельное SPA: Chat + Monaco-редактор Lua + xyflow node-graph. Lua исполняется локально в браузере через wasmoon." "Vite + React 18 + TS + Zustand 5 + xyflow 12 + Monaco + Tailwind + wasmoon" {
                tags "Browser"

                chatPanel = component "ChatPanel" "WS-чат с Backend, рендерит историю и pipeline-визуализацию (ThinkingPanel). Кнопка apply-code пишет код в активную lua-ноду." "React + native WebSocket"
                editorPanel = component "EditorPanel" "Monaco-редактор Lua + локальный wasmoon-runner с перехватом print." "React + @monaco-editor/react + wasmoon"
                flowPanel = component "FlowPanel" "ReactFlow-граф из 8 типов нод (prompt/example/hint/coder/result + input/lua/output). CoderNode зовёт /generate-from-context." "React + @xyflow/react"

                flowStore = component "flowStore" "Состояние графа: nodes, edges, мутации, gatherContextForCoder (BFS по prompt/example/hint)." "Zustand 5"
                chatStore = component "chatStore" "История сообщений, isGenerating, chat_session_id." "Zustand 5"
                thinkingStore = component "thinkingStore" "Pipeline-события из WS: стадии, токены, план." "Zustand 5"

                apiLib = component "lib/api.ts" "fetch-клиент для POST /generate и POST /generate-from-context." "TypeScript + fetch"
                wsLib = component "lib/ws.ts" "Нативный WebSocket-клиент для /generate/ws. Типизирует события stage/token/plan/validator/clarification/done/error." "TypeScript + WebSocket"
            }

            backend = container "Backend API" "FastAPI-сервис: REST + WebSocket. Оркестрирует clarifier/planner/coder/validator/fixer. Порт 8080." "Python 3 + FastAPI + Uvicorn + Pydantic v2 + AsyncOpenAI + rank_bm25 + tree-sitter + tiktoken" {

                apiRoutes = component "api/routes.py" "Роутер: POST /generate (clarification-aware, 200/410/422/500), POST /generate-from-context (node-graph), WS /generate/ws (streaming + 15s heartbeat)." "FastAPI router"

                pipeline = component "services/pipeline.py" "Оркестратор. generate_code / generate_code_from_clarified / generate_code_from_context. Single-task shortcut минует planner; multi-step склеивается в один lua_node-вызов через _format_multistep_task. Clarifier fast-path для коротких чётких промптов." "Python asyncio"

                llmClient = component "services/llm_client.py" "AsyncOpenAI-клиент к Ollama: chat / chat_json (JSON-mode) / chat_stream. keep_alive=30m." "Python + openai SDK"

                validator = component "services/validator.py" "Валидация Lua через subprocess: luac -p + опциональный selene. _line_to_block даёт контекст ±5 строк вокруг ошибки." "Python subprocess"

                chunker = component "services/chunker.py" "tree-sitter Lua AST → chunks + tiktoken packer с BM25-скорингом под context_budget_tokens=2800. Только для /generate-from-context." "Python + tree-sitter + tiktoken + rank_bm25"

                inputExtractor = component "services/input_extractor.py" "AST-walk по сгенерированному Lua: input.<field>-contract и entry_point{name, params}. Для автозаполнения InputNode на фронте." "Python AST"

                sessionsStore = component "services/sessions.py + chat_sessions.py" "Две in-memory TTL-таблицы: clarification (TTL 1800s, prompt+questions) и chat (TTL 3600s, last_code для edit-режима). is_edit_intent + truncate_code_for_context." "Python dict + time"

                models = component "models/models.py" "Pydantic-схемы request/response/internal: GenerateRequest/Response, ClarificationPayload, Plan, ErrorDetail, ValidationResult, ContextBlock, EntryPoint." "Pydantic v2"

                prompts = component "services/prompts.py" "Шаблоны: CLARIFIER/PLANNER/LUA_NODE/LUA_NODE_EDIT/FIXER SYSTEM + user-функции. Расходуют input-токены из num_ctx=4096." "Python templates"

                config = component "core/config.py" "pydantic-settings. llm_* endpoint, все *_max_tokens ≤256, max_fix_cycles=1, context_budget_tokens=2800, TTL. env-file ../../.env." "Pydantic Settings"

                mainApp = component "main.py" "FastAPI-приложение. CORS для localhost:5173-5175/3000/4173. Lifespan warmup: ping LLM (fail-open)." "FastAPI lifespan"
            }

            sessions = container "Sessions Store" "In-memory TTL-таблицы внутри процесса Backend: clarification (1800s) и chat-edit (3600s)." "Python dict" {
                tags "Database"
            }
        }

        # --- System Context ---
        developer -> localscript "Пишет задачу, получает Lua-код" "HTTP/WS"
        localscript -> ollama "Chat completions" "HTTP (OpenAI-compat)"
        localscript -> luaTools "Валидирует Lua" "subprocess"

        # --- Container level ---
        developer -> frontend "Открывает браузер" "HTTP"
        frontend -> backend "POST /generate, POST /generate-from-context" "HTTP+JSON"
        frontend -> backend "WS /generate/ws — стриминг pipeline" "WebSocket+JSON"
        backend -> ollama "Chat (stream / JSON-mode)" "POST /v1/chat/completions"
        backend -> luaTools "luac -p, опц. selene" "subprocess"
        backend -> sessions "peek/create/pop clarification; ensure/update chat" "in-process"

        # --- Frontend components ---
        chatPanel -> chatStore "История, isGenerating"
        chatPanel -> thinkingStore "Pipeline-события"
        chatPanel -> flowStore "Apply-code → активная lua-нода"
        chatPanel -> wsLib "Открывает WS"
        editorPanel -> flowStore "Синхронизирует код активной ноды"
        flowPanel -> flowStore "Реактивный рендер графа"
        flowPanel -> apiLib "CoderNode → /generate-from-context"
        apiLib -> backend "HTTP JSON"
        wsLib -> backend "WebSocket JSON"

        # --- Backend components ---
        apiRoutes -> pipeline "generate_code / _from_clarified / _from_context"
        apiRoutes -> sessionsStore "peek/create/pop + ensure/update"
        apiRoutes -> models "Валидирует request/response"
        pipeline -> llmClient "chat / chat_json / chat_stream"
        pipeline -> validator "validate() → ValidationResult"
        pipeline -> chunker "chunk_lua + pack_chunks (context-mode)"
        pipeline -> inputExtractor "extract_entry_point + extract_inputs"
        pipeline -> sessionsStore "is_edit_intent + truncate_code_for_context"
        pipeline -> prompts "все SYSTEM + user-шаблоны"
        pipeline -> config "все knobs (max_tokens, max_fix_cycles, …)"
        validator -> luaTools "luac + selene"
        llmClient -> ollama "Chat (OpenAI-compat)"
        mainApp -> llmClient "Warmup ping"
        mainApp -> apiRoutes "include_router"
    }

    views {
        systemContext localscript "SystemContext" {
            include *
            autoLayout lr
            description "LocalScript API в окружении: разработчик, локальный Ollama, Lua-toolchain, корпус примеров."
        }

        container localscript "Containers" {
            include *
            autoLayout tb
            description "Frontend SPA + Backend API + in-memory Sessions Store. Всё локально."
        }

        component backend "BackendComponents" {
            include *
            autoLayout tb
            description "Внутренности Backend API: роутер, оркестратор, стадии пайплайна, LLM-клиент, validator, chunker, input extractor, config, main."
        }

        component frontend "FrontendComponents" {
            include *
            autoLayout tb
            description "Три UI-панели, три Zustand-стора, api/ws-библиотеки."
        }

        styles {
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "External" {
                background #777777
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Browser" {
                shape WebBrowser
            }
            element "Database" {
                shape Cylinder
                background #8cbfea
                color #000000
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
        }
    }
}
