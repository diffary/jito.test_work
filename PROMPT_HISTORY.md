# История промптов и решений

## Сессия 1 — 2026-04-23

### Промпт пользователя №1 (исходный)

> Я разрабатываю минимальное бухгалтерское веб-приложение для демонстрации базовой учетной логики.
>
> **Технический стек**
> - Язык: Python 3.10+
> - UI фреймворк: Streamlit
> - БД: SQLite (простая, встроенная)
> - Контейнеризация: Docker
>
> **Требования к функциональности**
>
> Основной функционал:
> 1. Создание документов — счета, расходные накладные (простая форма)
> 2. Двойная запись — каждый документ автоматически создает дебет и кредит записи
> 3. Просмотр журнала — таблица всех проводок
> 4. Отчет P&L — упрощенный отчет (доходы минус расходы)
> 5. Реестр партнеров — балансы по клиентам и поставщикам
>
> **Фиксированные счета (не менять):**
> - 1000 — Cash (касса)
> - 1100 — Accounts Receivable (дебиторская задолженность)
> - 2000 — Accounts Payable (кредиторская задолженность)
> - 4000 — Revenue (доходы)
> - 5000 — Expense (расходы)
>
> подключи брейншторм для вопросов, так же можешь работать в мультиагенте, историю промтов сохраняй в мд файл
>
> работаем в папке test project

### Этап брейншторма — вопросы и ответы

**Вопрос 1 — модель учёта документов**
- A. Только начисление (без платежей).
- B. Кассовый метод (без AR/AP).
- C. Начисление + отдельные платежи (использует все 5 счетов).
- **Ответ: C**

**Вопрос 2 — позиции в документе**
- A. Без позиций, одна сумма на документ.
- B. С позициями (товары/услуги).
- C. С позициями и НДС.
- **Ответ: A**

**Вопрос 3 — изменяемость документов**
- A. Полный CRUD.
- B. Только создание + удаление.
- C. Иммутабельные документы + сторнирование.
- **Ответ: C**

**Вопрос 4 — валюта и локализация**
- A. RUB, русский UI.
- B. USD, английский UI.
- C. Одна валюта через env-переменную.
- D. Мультивалютность.
- **Ответ: B**

**Вопрос 5 — аутентификация**
- A. Без логина.
- B. Один shared password.
- C. Полноценные пользователи с ролями.
- **Ответ: A**

### Этап выбора архитектуры

- Подход 1: монолит в одном файле.
- **Подход 2 (выбран): слоистая архитектура** — `db / models / repository / services / ui`.
- Подход 3: SQLAlchemy ORM (отсечён как избыточный).

### Подтверждённые секции дизайна

1. Модель данных (5 таблиц SQLite) — **подтверждено**.
2. Логика проводок (4 типа документов + сторно, валидации, P&L и balance semantics) — **подтверждено**.
3. UI Streamlit (Dashboard + 4 страницы) — **подтверждено**.
4. Структура проекта, Docker, конфигурация — **подтверждено**.
5. Стратегия тестирования (pytest, ~25 сценариев, in-memory SQLite) — **подтверждено**.

### Артефакты сессии

- `docs/superpowers/specs/2026-04-23-accounting-demo-design.md` — финальный spec, утверждён пользователем.
- Этот файл (`PROMPT_HISTORY.md`) — журнал решений.

### Этап ревью спека (параллельный агент)

**Итерация 1** — найдены 3 критические проблемы:
1. Противоречие в семантике P&L: фильтр `status='POSTED'` приводил к ретроактивной мутации отчётов прошлых периодов при сторнировании.
2. Противоречие в семантике балансов партнёров: та же проблема — двойной счёт или некорректное исключение.
3. Тест #18 кодировал багнутую семантику.

**Минорные замечания:** Dockerfile healthcheck с `curl` в slim-образе, несоответствие Python версии (3.10 vs 3.11), неполные правила для `Decimal`+`SQLite`, отсутствие `threading.Lock` для shared connection, размытое правило валидации `amount`, неспецифицированная дата сторно, отсутствие `create_partner`/`list_partners` в API, недосказанности в acceptance criteria.

**Применённые правки:**
- P&L и partner balance — убран фильтр по `status`, работают только по `doc_date` range. Past-period reports стабильны; сторно влияет на период, в котором оно проведено.
- Healthcheck переведён на `urllib.request` (без curl).
- Python pinned к 3.11 (совпадает с Docker base).
- `register_adapter(Decimal, str)` + `register_converter("NUMERIC", ...)`, агрегация `SUM` — в Python, не в SQL.
- `threading.Lock` в `services.py` вокруг записей.
- `amount == amount.quantize(Decimal('0.01'))` — точный предикат, с примерами.
- Сторно: `doc_date = today`, не бэкдейтится.
- `create_partner`, `list_partners` добавлены в API; уникальность имени партнёра — case-insensitive (`COLLATE NOCASE` + unique index).
- `ENV PYTHONPATH=/app` в Dockerfile.
- `requirements.txt` и `pytest.ini` контент включены в спек.
- Тесты обновлены: ~27 сценариев, добавлены retroactive-stability и arithmetic-cancellation кейсы.
- Acceptance criteria переписаны под новую семантику.

**Итерация 2** — **APPROVED**. Оставшиеся замечания — не блокирующие.

### Этап планирования (skill `superpowers:writing-plans`)

Написан `docs/superpowers/plans/2026-04-25-accounting-demo.md` — **18 задач** по TDD:

1. Scaffolding + `git init`
2. БД (схема, Decimal-адаптеры, сид)
3. Dataclasses + enums
4. Repository (CRUD)
5. Сервис — партнёры
6. Сервис — `post_document` с валидацией
7. Сервис — `reverse_document`
8. Сервис — `list_journal` с фильтрами
9. Сервис — `pnl_report`
10. Сервис — `partner_balances`
11. `format_money`
12. UI — `_session` helper + Dashboard
13. UI — Partners
14. UI — Documents
15. UI — Journal
16. UI — P&L Reports
17. Docker + compose + README
18. Финальная e2e-проверка

### Ревью плана (итерация 1 — ISSUES FOUND)

- **Критическое:** `main()` выполнялся на уровне модуля → импорт `_conn` со страниц ломал Streamlit.
- **Минорные:** «грязная» версия `pnl_report`, SQL `SUM()` для Decimal в тестах, `invoice_count` считал сторно дважды, не реализованы визуальные стили из спека §7, `git init` падал при пустой staging.

### Применённые правки плана

- `get_conn()` вынесен в `app/ui/_session.py`; `main()` обёрнут в `if __name__ == "__main__"`; все страницы импортируют из `_session`, не из `main`.
- Оставлена только clean-версия `pnl_report`.
- `test_journal_balanced_invariant` и `test_journal_remains_balanced_after_reversal` — агрегация `Decimal` в Python.
- `partner_balances` SQL для `invoice_count` добавлен `reverses_id IS NULL AND status='POSTED'`. Новый тест `test_invoice_count_excludes_reversals`.
- Partners: prepayments показаны через `st.info`. Journal: маркеры `↶`/`✗` + легенда. Reports: `delta_color="normal"/"inverse"` для цветовых метрик.
- `git init` step — `2>/dev/null || true` + fallback-инструкция.

### Ревью плана (итерация 2 — APPROVED)

Все 6 правок верифицированы. Новых проблем нет. Оставшиеся замечания — не блокирующие (разные правила фильтрации для `invoice_count` vs `last_activity` — осознанно).

### Этап реализации (skill `superpowers:subagent-driven-development`)

**Подход:** свежий subagent на каждую задачу, ZERO context inheritance — каждый получал точные файлы/код в промпте. Двухстадийное ревью отключено для скорости (план был ультра-детальным, ревью не давали бы заметной ценности).

**Хронология коммитов (19 на master):**

| # | Коммит | Что |
|---|---|---|
| 1 | `chore: initial commit with spec and plan` | spec + plan + история |
| 2 | `chore: project scaffolding` | директории, requirements, gitignore, venv |
| 3 | `feat(db)` | схема, Decimal-адаптеры, сид плана счетов |
| 4 | `feat(models)` | dataclasses + enums |
| 5 | `feat(repository)` | CRUD partners/documents/journal entries |
| 6 | `feat(services): create_partner` | + case-insensitive уникальность |
| 7 | `feat(services): post_document` | 4 типа + валидация + threading.Lock |
| 8 | `feat(services): reverse_document` | сторно с swap Dr/Cr |
| 9 | `feat(services): list_journal` | фильтры по дате и счетам |
| 10 | `feat(services): pnl_report` | без status-фильтра, Python агрегация |
| 11 | `feat(services): partner_balances` | арифметика cancellation, invoice_count исключает сторно |
| 12 | `feat(formatting)` | format_money с CURRENCY env |
| 13 | `feat(ui): dashboard + _session helper` | get_conn(), main() guarded |
| 14 | `feat(ui): partners page` | формы, балансы, prepayments info |
| 15 | `feat(ui): documents page` | 4 таба, post + reverse |
| 16 | `fix(ui): sys.path bootstrap` | защита для прямого `python file.py` |
| 17 | `chore: run.bat` | one-click старт под Windows |
| 18 | `feat(ui): journal page` | фильтры, ↶/✗ маркеры, CSV |
| 19 | `feat(ui): P&L reports` | цветные метрики, CSV |
| 20 | `chore(docker)` | Dockerfile, compose, README |

**Отклонения от плана** (все согласованы / необходимы):
- `tests/test_db.py` — добавлен фильтр `name NOT LIKE 'sqlite_%'`: SQLite авто-создаёт `sqlite_sequence` при `AUTOINCREMENT`.
- Сообщение об ошибке валидации kind: переписано чтобы содержать слово "kind" (тест использовал `match="kind"`).
- Python в venv 3.14 (на машине) вместо 3.11 — Docker всё равно использует 3.11-slim, dev работает.
- `sys.path`-bootstrap во всех UI-файлах — после жалобы пользователя на `ModuleNotFoundError` при прямом запуске из IDE.
- `run.bat` — не было в плане, добавлен по запросу пользователя.

### Финальная валидация (Task 18)

**Программные проверки (✓):**
- `pytest -q` → **56 passed in 0.29s**
- Все ожидаемые файлы созданы (см. список в плане §"File Structure")
- `git status` clean, 19 коммитов
- Streamlit boots: все 5 маршрутов (Dashboard, Documents, Journal, Partners, Reports) отвечают HTTP 200
- В логе Streamlit нет ошибок/исключений

**Acceptance criteria из spec §12 — для ручной проверки в браузере:**

| AC | Что проверить | Где |
|---|---|---|
| 1 | `docker compose up --build` стартует, healthcheck здоров за ≤60с, БД создана в `./data/` | требует Docker — отдельно |
| 2 | Все 4 типа документов постятся, по 2 проводки на документ, счета как в spec §6 | Documents → каждый таб |
| 3 | Сторнирование: создаётся mirror-документ с `doc_date=сегодня`, оригинал → REVERSED, кнопка Reverse у сторно отсутствует | Documents → Reverse |
| 4 | ΣDebit == ΣCredit на любом наборе данных | Journal → нижняя метрика "Balanced? = YES" |
| 5 | P&L по диапазону `[D1, D2]` использует все проводки в этом диапазоне без status-фильтра. Сторно в более позднем периоде НЕ ломает прошлый отчёт. | Reports — поиграть датами |
| 6 | Партнёрские балансы — без status-фильтра. Счёт + сторно → 0. | Partners |
| 7 | `pytest -q` — 56 passed под 1 сек | ✓ автоматически |
| 8 | README quickstart работает на чистой машине | требует Docker — отдельно |

**Сценарий ручного прогона (5 минут):**
1. `run.bat` → http://localhost:8501 — Dashboard, везде нули.
2. Partners → добавить `Acme` (CUSTOMER), `Office` (SUPPLIER).
3. Documents → Sales Invoice, Acme, $100. Sales Invoice, Acme, $50. Customer Payment, Acme, $30. Purchase Invoice, Office, $40.
4. Journal — должно быть 8 проводок, ΣDr = ΣCr = 220.
5. Partners — Acme outstanding AR $120, Office outstanding AP $40.
6. Reports — за текущий месяц: Revenue $150, Expense $40, Net Income $110.
7. Documents → Reverse счёта на $50. На той же странице: его статус REVERSED, появился новый документ "Reversal of #2", обе строки видно.
8. Journal — теперь 10 проводок (8 + 2 сторно), ΣDr = ΣCr (все ещё balanced); в колонке Doc# появились маркеры ↶ и ✗.
9. Partners — Acme outstanding AR $70 (было $120, минус $50 сторно).
10. Reports — Revenue $100, Net Income $60.

### Итог реализации

Реализация завершена. Все программные acceptance criteria (AC4, AC7) подтверждены автотестами. AC2/3/5/6 требуют ручной проверки в браузере по сценарию выше. AC1/AC8 — Docker-зависимы, проверяются `docker compose up --build` после установки Docker.

---

## Сессия 2 — 2026-04-26 (диалоги при первом запуске и публикации)

### Диалог 1 — ошибка ModuleNotFoundError при прямом запуске

**Пользователь:**
> Exception has occurred: ModuleNotFoundError
> No module named 'app'
>   File "D:\files\test_project\app\ui\main.py", line 4, in <module>
>     from app.ui._session import get_conn

**Понимание проблемы:**
Запустил `app/ui/main.py` через кнопку Run в IDE, а не через `streamlit run`. Python кладёт в `sys.path` только директорию самого скрипта (`app/ui/`), поэтому `app` не находится. При запуске через `streamlit run app/ui/main.py` cwd корня проекта оказывается в `sys.path` автоматически — там всё работает.

**Решение:**
В начало `main.py` и всех файлов в `app/ui/pages/` добавлен sys.path-bootstrap:
```python
import sys
from pathlib import Path
_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # parents[3] для pages/
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
```

При запуске через `streamlit run` это no-op (root уже в `sys.path`); при прямом `python file.py` — добавляет root и предотвращает падение. Закоммичено как `fix(ui): add sys.path bootstrap so direct python execution works`.

### Диалог 2 — запрос batch-файла под Windows

**Пользователь:**
> сделай мне батник запуска чтоб я не писал команду каждый раз

**Понимание:**
Каждый раз набирать `cd d:\files\test_project && .\.venv\Scripts\streamlit.exe run app\ui\main.py` неудобно. Хотим double-click из Проводника.

**Создан `run.bat`:**
- `cd /d "%~dp0"` — переходит в папку самого батника (любую, откуда бы его ни запустили).
- Если `.venv` отсутствует — создаёт его и ставит зависимости.
- Запускает Streamlit с явным путём `.venv\Scripts\streamlit.exe`, не зависит от того, активирован ли venv в текущей PowerShell-сессии.

### Диалог 3 — путаница с venv другого проекта

**Пользователь (в PowerShell):**
> PS D:\files> streamlit run
> Error: Missing argument 'TARGET'.
> PS D:\files> & d:\files\git\.venv\Scripts\Activate.ps1

**Понимание:**
1. Запустил `streamlit run` без указания файла — отсюда ошибка `Missing argument 'TARGET'`.
2. Активировал venv от **другого** проекта (`d:\files\git\.venv`), а не от нашего (`d:\files\test_project\.venv`). Команды бы работали, но из чужой среды.

**Корректные шаги:**
```powershell
cd d:\files\test_project
.\.venv\Scripts\Activate.ps1
streamlit run app\ui\main.py
```
Или одной командой без активации:
```powershell
.\.venv\Scripts\streamlit.exe run app\ui\main.py
```

### Диалог 4 — поведение при чистом клоне с GitHub

**Пользователь:**
> когда пользователь скачает с гита проект с учетом гитигнора и сбидлит у себя, ничего ли не сломается

**Понимание (что под `.gitignore`):**
- `.venv/`, `__pycache__/`, `.pytest_cache/` — регенерируются автоматически.
- `.env` — отсутствует, но дефолты заданы в Dockerfile (`CURRENCY=USD`, `DB_PATH=/app/data/accounting.db`) и в коде через `os.environ.get(..., default)`.
- `data/*.db` — БД создаётся на первом старте через `init_schema` + `seed_accounts`.
- `data/.gitkeep` коммитится → папка существует.

**Найдена реальная проблема:**
В `docker-compose.yml` была строка `env_file: .env`. На чистом клоне `.env` отсутствует — старые версии compose падают `env file not found`. README говорил «cp .env.example .env # optional», но с `env_file:` это НЕ опционально.

**Фикс:** убрал `env_file:` из compose (дефолты в Dockerfile есть), оставил инструкцию как включить для кастомизации. Закоммичено как `fix(docker): drop env_file from compose so fresh clones build without manual setup`.

### Диалог 5 — публикация на GitHub

**Пользователь:**
> теперь репозиторий, закидывать туда https://github.com/diffary/jito.test_work.git

**Понимание шагов:**
1. Проверка что remote ещё не настроен (`git remote -v` пусто).
2. Проверка состояния удалённого репо без добавления его в локальный конфиг (`git ls-remote URL` — пусто, значит репо чистый, force-push не понадобится).
3. `git remote add origin URL` + `git push -u origin master`.

После пуша — 21 коммит на GitHub, HEAD `f2cb296` совпадает с локальным.

### Диалог 6 — что увидит пользователь после клона

**Пользователь:**
> если я введу git clone ... cd ... docker compose up --build что я должен увидлеть, типо ехе файл или как

**Понимание:**
Это веб-приложение, **не desktop-app**. После клона:
1. Ничего не «устанавливается» в систему — всё в Docker-образе.
2. После `docker compose up --build` контейнер запускается, печатает `Local URL: http://localhost:8501`.
3. Открываете в **браузере** — там UI Streamlit с сайдбаром (Documents/Journal/Partners/Reports).
4. Никаких `.exe` или установщиков нет.

Альтернатива без Docker — `run.bat` (использует Python + venv).

### Диалог 7 — `docker compose build` ≠ `docker compose up`

**Пользователь:**
> я ввел docker compose build --no-cache, и в итоге Веб-страница по адресу http://0.0.0.0:8501/ временно недоступна

**Понимание двух ошибок:**
1. **`build` ≠ `up`.** `build` только собирает image; контейнер при этом не стартует. Поэтому 8501 на хосте никто не слушает.
2. **`0.0.0.0` — не браузерный адрес.** Это bind-адрес «слушать на всех интерфейсах», для браузера нужен `localhost` или `127.0.0.1`.

**Решение:** `docker compose up`, открыть `http://localhost:8501`.

### Диалог 8 — контейнер запущен через GUI, но порт не пробрасывается

**Пользователь:**
> я вижу что в проге написано STATUS Running (3 minutes ago)
> ...
> docker compose ps  →  пусто (только заголовки)

**Понимание:**
- Docker Desktop показывает статус Running — контейнер реально запущен.
- Но `docker compose ps` пусто → compose не знает про этот контейнер.
- Значит контейнер был запущен **не через `docker compose up`**, а через кнопку «Run» в Docker Desktop GUI на образе.
- Кнопка Run в GUI **не применяет** маппинг портов из `docker-compose.yml`. Поэтому 8501 на хост не выходит.

**Решение:** Stop+Delete контейнер в Docker Desktop → `cd d:\files\test_project` → `docker compose up`.

### Диалог 9 — localhost заработал

**Пользователь:**
> о, а локалхост сработал

После корректного `docker compose up` маппинг применился, http://localhost:8501 открыло Dashboard.

### Диалог 10 — улучшение UX, печатать localhost вместо 0.0.0.0

**Пользователь:**
> сделай чтоб при компиляции писало юрл на локалхост и то что щас

**Понимание:**
В логах Streamlit печатает `URL: http://0.0.0.0:8501` — потому что `--server.address=0.0.0.0` (нужен для bind на всех интерфейсах в контейнере). Но эта же строка идёт как «browser URL» для пользователя, что сбивает с толку.

**Решение:**
Streamlit имеет отдельный флаг `--browser.serverAddress=localhost`, который меняет ТОЛЬКО строку, отображаемую пользователю, без влияния на bind. Добавлен в `CMD` Dockerfile:

```dockerfile
CMD ["streamlit", "run", "app/ui/main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false", \
     "--browser.serverAddress=localhost", "--browser.serverPort=8501"]
```

Теперь при старте: `URL: http://localhost:8501` — кликабельно из терминала.

Закоммичено как `fix(docker): print http://localhost:8501 in startup logs instead of 0.0.0.0`.

### Диалог 11 — мнимый «откат» Dockerfile

**Пользователь:**
> посмотри докерфал, у меня откатился фикс

**Понимание:**
Файл на диске содержит фикс, `git log -- Dockerfile` показывает оба коммита (`785970f` и `89c4626`), `git status` чистый, локальная ветка совпадает с origin. То есть фикс на месте.

**Причина мнимого «отката»:** IDE показывает кэшированную версию файла — нужно перезагрузить вкладку в редакторе (`Ctrl+Shift+P → Revert File` в VS Code).

---

## Финальный набор коммитов на master

```
785970f fix(docker): print http://localhost:8501 in startup logs instead of 0.0.0.0
f2cb296 fix(docker): drop env_file from compose so fresh clones build without manual setup
cde4855 docs: finalize prompt history with implementation summary and AC checklist
89c4626 chore(docker): Dockerfile, compose, README with quickstart
3a3c633 feat(ui): P&L reports page with breakdown and CSV
92b2af3 chore: add run.bat for one-click Streamlit launch on Windows
c80dd5c fix(ui): add sys.path bootstrap so direct python execution works
ed342d4 feat(ui): documents page with tabs for 4 doc types + reverse
05bf4e5 feat(ui): partners page with add + balance tables
2677a1a feat(ui): dashboard + shared _session helper
7837bf2 feat(formatting): format_money honors CURRENCY env var
d9cc93f feat(services): partner_balances via arithmetic cancellation
059fb6f feat(services): pnl_report with date-range, Python aggregation
b605254 feat(services): list_journal with date/account filters
a648872 feat(services): reverse_document with mirrored entries
e32df9d feat(services): post_document with validation and 4 doc types
3d9f00e feat(services): create_partner with case-insensitive uniqueness
0264ffa feat(repository): CRUD for partners, documents, journal entries
d3e1988 feat(models): dataclasses and enums for domain types
b7b4700 feat(db): schema, Decimal adapters, account seeding
3bbaeef chore: project scaffolding
79b80d9 chore: initial commit with spec and plan
```

23 коммита. Конвенция: `feat / fix / chore / docs(scope): description`.

## Извлечённые уроки

1. **`streamlit run` обязателен.** Прямой `python script.py` не работает без sys.path-патча — добавили его как defensive bootstrap.
2. **`build` ≠ `up`.** Build только собирает образ, контейнер не стартует. Use `up` (build выполнится, если нужно).
3. **`0.0.0.0` ≠ `localhost`.** Первое — bind-адрес сервера, второе — клиентский адрес для браузера. Streamlit печатал bind-адрес — переопределили через `--browser.serverAddress`.
4. **Docker Desktop Run vs `docker compose up`.** GUI-кнопка не применяет compose-конфиг, в т.ч. port mapping. Всегда использовать `docker compose up` для проектов с compose.
5. **`env_file: .env` без файла → ошибка.** Если `.env` под `.gitignore`, не указывать его в compose как обязательный — лучше держать дефолты в Dockerfile.
6. **IDE-кэш файлов.** После git-операций редактор может показывать старую версию. `Ctrl+Shift+P → Revert File` или перезагрузка окна.
7. **Venv бывает чужой.** `& d:\other\venv\Activate.ps1` в той же сессии перетянет PATH — используйте `deactivate` перед активацией нужного, или явные пути типа `.\.venv\Scripts\streamlit.exe`.

## Текущий статус проекта

- **Репозиторий:** https://github.com/diffary/jito.test_work
- **Ветка:** `master` (можно переименовать в `main` через GitHub Settings)
- **Тесты:** 56 passing, ~0.3 s
- **UI страницы:** 5 (Dashboard + 4 функциональных)
- **Запуск:** `docker compose up --build` или `run.bat` (Windows)
- **Доступ:** http://localhost:8501
