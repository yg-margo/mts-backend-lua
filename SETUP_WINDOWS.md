# Запуск на Windows — пошаговая инструкция

Документ для проверяющих и для разработчиков, поднимающих стенд с нуля. Всё делается в обычном `cmd` от имени пользователя (админ не нужен, кроме инсталляторов).

---

## 0. Системные требования

- **GPU**: NVIDIA с ≥ 8 GB VRAM, свежий драйвер (CUDA-совместимый). Проверка: `nvidia-smi` должна показать карту.
- **Диск**: ~10 GB свободно (модели + зависимости).
- **ОС**: Windows 10/11 x64.

Без дискретной NVIDIA-карты Ollama пойдёт на CPU и запрос `/generate` будет отвечать минутами — это проверочный стенд не пройдёт.

---

## 1. Поставить пререкизиты

Все ссылки — официальные инсталляторы. После каждой установки **открывайте новый `cmd`**, чтобы подхватился обновлённый `PATH`.

| Что | Откуда | Проверка |
|---|---|---|
| Python 3.10+ | <https://www.python.org/downloads/windows/> (при установке включить "Add python.exe to PATH") | `python --version` |
| Node.js LTS | <https://nodejs.org> | `node -v` и `npm -v` |
| Git | <https://git-scm.com/download/win> | `git --version` |
| Ollama for Windows | <https://ollama.com/download/windows> | `ollama --version` |
| Lua (нужен `luac`) | <https://luabinaries.sourceforge.net/> — качнуть архив Lua 5.4 Windows x64, распаковать, положить `luac54.exe` (переименовать в `luac.exe`) в любую папку из `PATH`, или добавить папку в `PATH` | `luac -v` |
| *(опц.)* selene | <https://github.com/Kampfkarren/selene/releases> — скачать `selene-*-windows.zip`, положить `selene.exe` в `PATH` | `selene --version` |

`selene` необязателен — если его нет, бэкенд просто пропустит шаг статического анализа.

**GPU-диагностика** (выполнить один раз):

```cmd
nvidia-smi
```

Должен быть виден GPU и ≥ 8 GB total. Если нет — драйвер не поставлен / карта не поддерживается.

---

## 2. Получить репозиторий

```cmd
cd C:\
mkdir Хакатоны\MTS True Tech
cd Хакатоны\MTS True Tech
git clone -b kiva https://github.com/yg-margo/mts-backend-lua.git mts-backend-lua-kiva
cd mts-backend-lua-kiva
```

Дальше все команды **выполняются из `mts-backend-lua-kiva`** (имя папки не принципиально — главное, что это корень репо).

---

## 3. Скачать и собрать модели Ollama

Ollama при установке добавляется в автозапуск и сама слушает `http://localhost:11434`. Если её нет в трэе — запусти «Ollama» из меню Пуск.

```cmd
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
ollama create lua-coder:mts -f app\Modelfile
```

- `qwen2.5-coder:7b` (~4.7 GB) — базовая модель-кодер.
- `nomic-embed-text` (~274 MB) — эмбеддер для гибридного RAG (BM25 + dense).
- `lua-coder:mts` — кастомный тэг, собранный из `app/Modelfile`. В нём зашиты `num_ctx=4096`, `num_predict=256`, `num_batch=1`, `temperature=0.2` и few-shot-примеры. Именно этот тэг ждёт `.env` (`LLM_MODEL=lua-coder:mts`).

Параметр `num_parallel=1` задаётся на уровне сервера Ollama, а не Modelfile. На Windows выставь переменную среды один раз:

```cmd
setx OLLAMA_NUM_PARALLEL 1
```

Затем в трэе: правая кнопка по Ollama → **Quit**, и запусти заново. Проверка:

```cmd
ollama list
ollama show lua-coder:mts
```

`ollama show` должна вывести блок `Parameters` с `num_ctx 4096`, `num_predict 256`, `num_batch 1`.

---

## 4. Запустить проект

В корне репо лежит `start.bat` — он сам создаст venv, поставит Python-зависимости, скопирует `.env.example → .env`, поставит `npm install` и откроет два окна (бэкенд и фронт).

```cmd
start.bat
```

Что должно получиться:
- Окно **mts-backend** — логи Uvicorn, строка `Uvicorn running on http://0.0.0.0:8080`, плюс `=== WARMUP START ===` → `=== WARMUP DONE ===` (первый прогон модели, 5–30 сек).
- Окно **mts-frontend** — Vite, строка вида `Local: http://localhost:5173/`.

Если что-то уже стоит и нужно просто запустить — открой два `cmd` вручную:

```cmd
:: окно 1 — бэкенд
cd C:\...\mts-backend-lua-kiva
.venv\Scripts\activate.bat
python run.py

:: окно 2 — фронт (опционально, можно обойтись Swagger-ом)
cd C:\...\mts-backend-lua-kiva\front
npm run dev
```

---

## 5. Как проверять (для проверяющих)

### 5.1. Быстрая проверка через Swagger (минимальный путь, фронт не нужен)

1. Открыть <http://localhost:8080/docs>.
2. Развернуть `POST /generate` → **Try it out**.
3. Вставить тело:

   ```json
   { "prompt": "function that validates an email address" }
   ```

4. **Execute**. Ожидаемый ответ `200 OK` с полем `code`, в котором лежит валидный Lua (проходит `luac -p`).

Альтернативно — через `curl` в новом `cmd`:

```cmd
curl -X POST http://localhost:8080/generate ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"function that validates an email address\"}"
```

### 5.2. Проверка через UI

Открой URL, который показал Vite (обычно <http://localhost:5173/>). Введи тот же промпт — ответ появится в Monaco-редакторе.

### 5.3. Проверка VRAM и параметров инференса (обязательный шаг из ТЗ)

Параллельно с запросом запусти в отдельном окне:

```cmd
nvidia-smi -l 1
```

Во время генерации:
- процесс `ollama.exe` должен держать < 8000 MiB;
- `GPU-Util` скачет на 80–100 %;
- `CPU offload` отсутствует (Ollama по умолчанию кладёт всё на GPU; если VRAM мало — она выгружает слои в RAM, и GPU-Util будет колебаться в районе 0–20 %).

Параметры модели:

```cmd
ollama show lua-coder:mts
```

Должны совпадать с ТЗ: `num_ctx=4096`, `num_predict=256`, `num_batch=1`, `num_parallel=1` (последний — env на сервере).

### 5.4. Эталонные промпты для проверки

Три примера зашиты в `app/Modelfile` как few-shot — на них модель должна отвечать стабильно:

1. `function that validates an email address`
2. `сумма двух чисел`
3. `перевести строку YYYYMMDD в ISO-дату`

Полезно дёрнуть свой промпт вне few-shot — например `factorial of n` или `разбить строку на слова` — чтобы увидеть работу пайплайна планер → RAG → кодер → валидатор → фиксер.

### 5.5. Чек-лист соответствия ТЗ

- [ ] Локальная open-source модель через Ollama (`lua-coder:mts`, базируется на `qwen2.5-coder:7b`).
- [ ] Никаких внешних AI-API — проверяется по `app/services/llm_client.py` (`base_url` смотрит на `http://localhost:11434/v1`).
- [ ] Параметры: `num_ctx=4096`, `num_predict=256`, `num_batch=1`, `num_parallel=1` (`ollama show` + `OLLAMA_NUM_PARALLEL`).
- [ ] Пиковый VRAM ≤ 8 GB (`nvidia-smi` во время генерации).
- [ ] Есть валидация: `luac -p` в `app/services/validator.py` + опциональный `selene`.
- [ ] Есть хотя бы одна итерация доработки: `MAX_FIX_CYCLES=1` в `.env`, фикс-цикл в `pipeline.py`.
- [ ] Есть RAG: hybrid BM25 + `nomic-embed-text`, корпус `docs/lua_examples.txt`, код в `app/services/rag.py`.
- [ ] Демо воспроизводится локально — эта инструкция и `start.bat`.

---

## 6. Траблшутинг

| Симптом | Причина | Что делать |
|---|---|---|
| `ERROR: npm not on PATH` | Node.js не поставлен или старое окно `cmd` | Поставить Node LTS, открыть **новое** окно `cmd` |
| `ERROR: python not on PATH` | Python не в PATH | Переустановить Python с галкой «Add to PATH», либо добавить вручную |
| `luac: command not found` в логах бэкенда | `luac` не в PATH | Поставить Lua (см. п.1), перезапустить `start.bat` |
| `connection refused` на `:11434` | Ollama не запущена | Запустить Ollama из меню Пуск; проверить иконку в трэе |
| `model 'lua-coder:mts' not found` | Пропущен `ollama create` | Выполнить `ollama create lua-coder:mts -f app\Modelfile` |
| `CUDA out of memory` / очень медленно | Другие приложения занимают VRAM, либо карта < 8 GB | Закрыть браузеры/игры/Stable Diffusion; если карта мелкая — решение не пройдёт ТЗ |
| Порт 8080 занят | Другой сервис на порту | `netstat -ano | findstr :8080` → убить процесс через `taskkill /PID <pid> /F`, либо поменять порт в `run.py` |
| Фронт не видит бэкенд | CORS / порт фронта не 5173-5175/3000/4173 | Смотри `app/main.py:88` (`allow_origin_regex`) — добавить свой порт |
| `Failed to load model` в Ollama | Мало VRAM / слишком большая квантизация | По умолчанию `qwen2.5-coder:7b` = Q4_K_M, это ~4.7 GB. Если не помещается — освободи VRAM; ставить более тяжёлую квантизацию нельзя (нарушит 8 GB лимит) |
| Warmup падает с таймаутом | Модель качается первый раз | Подождать, дать `ollama pull` дозакончиться. Следующий старт будет быстрым |

---

## 7. Остановка

- В окнах бэкенда и фронта нажми `Ctrl+C`, потом `Y` / закрой окно.
- Ollama оставляй запущенной — её завершение: правая кнопка по иконке в трэе → **Quit**.

---

## 8. Полезные ссылки

- Swagger UI: <http://localhost:8080/docs>
- ReDoc: <http://localhost:8080/redoc>
- OpenAPI JSON: <http://localhost:8080/openapi.json>
- Фронт (Vite): <http://localhost:5173/>
