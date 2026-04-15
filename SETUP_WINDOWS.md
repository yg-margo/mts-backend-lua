# Запуск на Windows — Docker

Документ для проверяющих и для разработчиков, поднимающих стенд с нуля. Весь прод-контур крутится в Docker: отдельно поднимать Python, Node.js, Lua или `luac` **не нужно** — всё уже внутри образа.

---

## 0. Системные требования

- **ОС**: Windows 10 22H2 / Windows 11 x64.
- **GPU**: NVIDIA с ≥ 8 GB VRAM, свежий драйвер (CUDA-совместимый, Game Ready / Studio 552+). Проверка: в PowerShell `nvidia-smi` должна показать карту.
- **Docker Desktop** с включённым бэкендом WSL 2 и GPU-пробросом (`Settings → Resources → WSL Integration`, `Settings → Docker Engine` — в секции `features.gpu` должно быть `true`).
- **Диск**: ~15 GB свободно (~5 GB базовый образ + ~5 GB модели Ollama + запас).

Без дискретной NVIDIA-карты можно запустить CPU-профиль, но генерация будет занимать минуты — проверочный стенд по ТЗ не пройдёт.

---

## 1. Поставить пререкизиты

| Что | Откуда | Проверка |
|---|---|---|
| **Docker Desktop for Windows** | <https://www.docker.com/products/docker-desktop/> — при установке выбрать бэкенд **WSL 2** | `docker --version`, `docker compose version` |
| **NVIDIA Driver** (если используется GPU) | <https://www.nvidia.com/Download/index.aspx> — Game Ready или Studio, ≥ 552 | `nvidia-smi` в PowerShell |
| **Git** | <https://git-scm.com/download/win> | `git --version` |

После установки Docker Desktop **перезагрузить Windows** и убедиться, что Docker Desktop стартовал (иконка в трэе «Docker Desktop is running»).

Для GPU-прохода в Docker на Windows ничего отдельно ставить **не нужно**: Docker Desktop сам подхватывает NVIDIA GPU через WSL 2, если стоит свежий драйвер. Проверить можно так:

```powershell
docker run --rm --gpus=all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

Команда должна вывести таблицу со списком GPU — значит проброс работает.

---

## 2. Получить репозиторий

```powershell
cd C:\
mkdir "Хакатоны\MTS True Tech"
cd "Хакатоны\MTS True Tech"
git clone -b kiva https://github.com/yg-margo/mts-backend-lua.git mts-backend-lua-kiva
cd mts-backend-lua-kiva
```

Дальше все команды выполняются **из корня репозитория** (`mts-backend-lua-kiva` или как вы его назвали).

---

## 3. Запустить стек

### 3.1. С GPU (рекомендуется — соответствует ТЗ)

```powershell
docker compose --profile gpu up --build
```

Первый запуск:
1. Соберёт образ `mts-lua-app:local` (~3–5 минут, качает Node/Python-зависимости и собирает фронтенд).
2. Поднимет два контейнера: `ollama` (с NVIDIA-пробросом) и `app`.
3. `docker-entrypoint.sh` в контейнере `app` автоматически:
   - дождётся Ollama на `http://ollama:11434`;
   - выполнит `ollama pull qwen2.5-coder:7b` (~4.7 GB, несколько минут);
   - соберёт кастомный тэг `lua-coder:mts` из `app/Modelfile` (прошиты `num_ctx=4096`, `num_predict=256`, `num_batch=1`, `temperature=0.2` и few-shot-примеры).
4. Запустит FastAPI на `:8080`. Ждите строки `=== WARMUP DONE ===` в логах.

`num_parallel=1` прошит в `docker-compose.yml` через `OLLAMA_NUM_PARALLEL=1` на сервисе `ollama-gpu`.

### 3.2. Без GPU (CPU-only, для разработки)

```powershell
docker compose --profile cpu up --build
```

Ожидаемо в ~10–30 раз медленнее. Подходит чтобы проверить код и UI, но **не проходит** требования по VRAM / времени отклика.

### 3.3. Остановка

В окне с логами — `Ctrl+C`, затем:

```powershell
docker compose down          # остановить контейнеры, сохранить скачанные модели
docker compose down -v       # + удалить volume ollama_models (сотрёт скачанные модели)
```

---

## 4. Как проверять (для проверяющих)

### 4.1. UI

Открыть <http://localhost:8080/> — собранный Vite-фронт отдаётся из того же контейнера. Ввести промпт, увидеть сгенерированный Lua в Monaco-редакторе и скелет инпутов в InputNode.

### 4.2. Swagger / `curl`

Минимальный путь без фронта — <http://localhost:8080/docs>, `POST /generate` → **Try it out**:

```json
{ "prompt": "function that validates an email address" }
```

Или из PowerShell:

```powershell
curl.exe -X POST http://localhost:8080/generate `
  -H "Content-Type: application/json" `
  -d '{\"prompt\":\"function that validates an email address\"}'
```

Ожидаемый ответ `200 OK` с полем `code` (валидный Lua, проходит `luac -p`) и `inputs` (скелет полей для InputNode).

### 4.3. Проверка VRAM и параметров инференса (обязательный шаг из ТЗ)

Во время генерации в отдельном окне PowerShell:

```powershell
nvidia-smi -l 1
```

Должно быть:
- процесс `ollama` (внутри контейнера) держит < 8000 MiB;
- `GPU-Util` скачет на 80–100 %;
- нет CPU-offload (если VRAM не хватает, Ollama выгрузит слои в RAM, и GPU-Util будет 0–20 %).

Параметры модели:

```powershell
docker exec ollama ollama show lua-coder:mts
```

Должны совпадать с ТЗ: `num_ctx=4096`, `num_predict=256`, `num_batch=1`. `num_parallel=1` — через env:

```powershell
docker exec ollama env | Select-String OLLAMA_NUM_PARALLEL
```

### 4.4. Эталонные промпты

Три промпта зашиты в `app/Modelfile` как few-shot — на них модель должна отвечать стабильно:

1. `function that validates an email address`
2. `сумма двух чисел`
3. `перевести строку YYYYMMDD в ISO-дату`

Полезно дёрнуть свой промпт вне few-shot — например `factorial of n` или `разбить строку на слова` — чтобы увидеть работу пайплайна планнер → кодер → валидатор → фиксер.

### 4.5. Чек-лист соответствия ТЗ

- [ ] Локальная open-source модель через Ollama (`lua-coder:mts`, базируется на `qwen2.5-coder:7b`).
- [ ] Никаких внешних AI-API — проверяется по `app/services/llm_client.py` (`base_url` смотрит на Ollama в Docker-сети).
- [ ] Параметры: `num_ctx=4096`, `num_predict=256`, `num_batch=1`, `num_parallel=1` (`docker exec ollama ollama show …` + `OLLAMA_NUM_PARALLEL`).
- [ ] Пиковый VRAM ≤ 8 GB (`nvidia-smi` во время генерации).
- [ ] Есть валидация: `luac -p` в `app/services/validator.py` + форбид-гард (`_check_forbidden_identifiers`) + опциональный `selene`.
- [ ] Есть хотя бы одна итерация доработки: `MAX_FIX_CYCLES=1`, фикс-цикл в `pipeline.py`.
- [ ] Демо воспроизводится одной командой `docker compose --profile gpu up --build`.

---

## 5. Траблшутинг

| Симптом | Причина | Что делать |
|---|---|---|
| `docker: command not found` | Docker Desktop не установлен / не запущен | Установить Docker Desktop и дождаться, пока иконка в трэе скажет `running` |
| `could not select device driver "nvidia"` | Нет NVIDIA-проброса в Docker Desktop | Обновить драйвер NVIDIA (≥ 552); убедиться что в Docker Desktop включён WSL 2 backend |
| `port 8080 is already allocated` | Порт занят другим процессом | `netstat -ano | findstr :8080` → `taskkill /PID <pid> /F`, либо сменить маппинг в `docker-compose.yml` (`ports: ["8081:8080"]`) |
| `Ollama unreachable after 60s` в логах `app` | Контейнер `ollama` не стартовал / профиль не указан | Проверить `docker compose ps`; всегда запускать с `--profile gpu` или `--profile cpu` |
| `CUDA out of memory` / очень медленно | Другие приложения занимают VRAM, либо карта < 8 GB | Закрыть браузеры/игры/Stable Diffusion; если карта мелкая — решение не пройдёт ТЗ |
| `pull … failed` в логах entrypoint | Нет интернета внутри контейнера / блокировка | Проверить прокси в Docker Desktop (`Settings → Resources → Proxies`); можно пулить заранее: `docker exec ollama ollama pull qwen2.5-coder:7b` |
| Warmup падает с таймаутом | Модель качается первый раз | Подождать, дать `ollama pull` дозакончиться. Следующий старт будет быстрым — модели лежат в volume `ollama_models` |
| Фронт не открывается на `:8080` | Билд фронта упал в Dockerfile | Пересобрать с `--no-cache`: `docker compose build --no-cache app` |
| `warning: no space left on device` | Docker Desktop упёрся в лимит WSL-диска | Docker Desktop → Settings → Resources → Disk image size — поднять; либо `docker system prune -a` |

---

## 6. Полезные ссылки

- UI (Vite SPA): <http://localhost:8080/>
- Swagger UI: <http://localhost:8080/docs>
- ReDoc: <http://localhost:8080/redoc>
- OpenAPI JSON: <http://localhost:8080/openapi.json>
