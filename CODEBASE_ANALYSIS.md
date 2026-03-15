# Анализ кодовой базы: Database Load Testing System

Дата анализа: Март 2026 | Язык: Python/TypeScript | Статус: Production-ready (с модулем восстановления БД)

---

## 1. BUILD/TEST КОМАНДЫ

### Backend (Python)

| Команда | Назначение | Файл |
|---------|-----------|------|
| `./start_backend.sh` | Полный запуск backend (venv + dependencies + сервер) | [start_backend.sh](start_backend.sh) |
| `python3 main.py` | Прямой запуск FastAPI-сервера | [backend/main.py](backend/main.py) |
| `pip install -r requirements.txt` | Установка Python-зависимостей | [requirements.txt](requirements.txt) |
| `python3 -m pytest` | Unit-тесты (если есть файлы test_*.py) | scripts/test_*.py |
| `python3 scripts/test_backup_restore.py` | Тестирование backup/restore функций | [scripts/test_backup_restore.py](backend/scripts/test_backup_restore.py) |
| `python3 scripts/init_history_db.py` | Инициализация БД истории тестов | [scripts/init_history_db.py](backend/scripts/init_history_db.py) |
| `python3 scripts/init_scenarios.py` | Загрузка сценариев в БД | [scripts/init_scenarios.py](backend/scripts/init_scenarios.py) |

### Frontend (Next.js)

| Команда | Назначение | Файл |
|---------|-----------|------|
| `pnpm install` или `npm install` | Установка Node-зависимостей | [package.json](frontend/package.json) |
| `pnpm dev` или `npm run dev` | Dev-сервер (http://localhost:3000) | [package.json](frontend/package.json) |
| `pnpm build` или `npm run build` | Продакшн-сборка | [package.json](frontend/package.json) |
| `pnpm start` или `npm start` | Запуск продакшн-сборки | [package.json](frontend/package.json) |
| `pnpm lint` или `npm run lint` | ESLint проверка | [package.json](frontend/package.json) |

### Базы данных (Docker)

```bash
# PostgreSQL (Pagila)
cd ../pagila/pagila && docker-compose up -d
./init_pagila.sh  # если не инициализировалась автоматически

# MySQL (Sakila)
cd ../sakila && docker-compose up -d

# История тестов (PostgreSQL на 5433)
docker-compose up -d history-db  # из корневого docker-compose.yml
```

### Полный запуск системы (QUICKSTART)

```bash
# 1. Запуск БД
cd ../pagila/pagila && docker-compose up -d
cd ../../sakila && docker-compose up -d
cd ../code

# 2. Backend
./start_backend.sh  # http://localhost:8000

# 3. Frontend
cd frontend && pnpm install && pnpm dev  # http://localhost:3000
```

---

## 2. АРХИТЕКТУРА И КЛЮЧЕВЫЕ РЕШЕНИЯ

### 2.1 Backend Architecture

**Фреймворк:** FastAPI 0.104.1 + Uvicorn  
**Async/await:** ✅ Полная поддержка асинхронности  
**СУБД система:** Dual-support (PostgreSQL + MySQL)

```
┌─────────────────────────────────────────────────────┐
│              FastAPI Application                    │
│            (main.py - точка входа)                  │
└────────┬────────────────────────────────────────────┘
         │
    ┌────┴────────────────────────────────────┐
    │                                         │
┌───▼──────────────────────┐    ┌────────────▼───────┐
│ LoadTester               │    │ WebSocket Manager   │
│ - Нагрузочное тестир.    │    │ - Real-time metrics │
│ - Выполнение запросов    │    │ - Streaming results │
│ - Сбор метрик            │    │ - Client management │
└───┬──────────────────────┘    └────────────────────┘
    │
    ├─────────────┬──────────────┬──────────────┐
    │             │              │              │
┌───▼──┐  ┌──────▼─────┐  ┌─────▼────┐  ┌─────▼───────────────┐
│ Conn │  │ QueryMgr   │  │ StateMan │  │ BackupStrategy      │
│      │  │            │  │ (Restore)│  │ - SqlBackupStrategy │
│ YAML │  │ - Queries  │  │ - Verify │  │ - NativeDumpStrat.  │
│      │  │ - Scenarios│  │ - Analyze│  │ - Cleanup           │
└──────┘  └────────────┘  └──────────┘  └─────────────────────┘
```

**Ключевые компоненты:**

| Класс | Файл | Назначение |
|-------|------|-----------|
| `DatabaseConnection` | [connection.py](backend/database/connection.py) | YAML-конфиг для MySQL/PostgreSQL |
| `LoadTester` | [load_tester/tester.py](backend/load_tester/tester.py) | Выполнение нагрузочных тестов |
| `QueryManager` | [queries.py](backend/database/queries.py) | Управление сценариями запросов |
| `DatabaseStateManager` | [state_manager.py](backend/database/state_manager.py) | Оркестратор backup/restore |
| `StateVerifier` | [state_verifier.py](backend/database/state_verifier.py) | Верификация состояния БД |
| `QueryAnalyzer` | [query_analyzer.py](backend/database/query_analyzer.py) | Парсинг и классификация запросов |
| `SqlBackupStrategy` | [backup_strategies/sql_strategy.py](backend/database/backup_strategies/sql_strategy.py) | Selective SQL backup |
| `NativeDumpStrategy` | [backup_strategies/native_strategy.py](backend/database/backup_strategies/native_strategy.py) | pg_dump/mysqldump |

### 2.2 Frontend Architecture

**Фреймворк:** Next.js 16.0.10 + React 19.2.0  
**Язык:** TypeScript 5.0  
**UI-компоненты:** Radix UI (40+ компонентов)  
**Стилизация:** Tailwind CSS 4.1.9  
**Графики:** Recharts 2.15.4  
**State management:** Zustand 5.0.9  
**Формы:** React Hook Form 7.60.0 + Zod 3.25.76

```
┌──────────────────────────────────────────────────┐
│     Next.js Application (layout.tsx)             │
│              http://localhost:3000               │
└──────────────────────┬───────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼─────┐  ┌────▼───────┐  ┌──▼──────────┐
│ Header      │  │ Sidebar    │  │ Pages       │
│ (навигация) │  │ (меню)     │  │             │
└─────────────┘  └────────────┘  ├─ home-page  │
                                 ├─ config-    │
                                 │  page       │
                                 ├─ scenarios- │
                                 │  page       │
                                 ├─ dashboards │
                                 │  -page      │
                                 ├─ reports-   │
                                 │  page       │
                                 ├─ history-   │
                                 │  page       │
                                 └─ database-  │
                                    state-     │
                                    panel      │
```

**Key Pages:**
- **home-page**: Главная (статус подключений)
- **config-page**: Конфигурация тестов (выбор БД, запросов, параметров)
- **scenarios-page**: Управление сценариями
- **dashboards-page**: Real-time графики (RPS, latency, CPU)
- **reports-page**: Сохраненные отчеты результатов
- **history-page**: История тестирований
- **database-state-panel**: Статус состояния БД

### 2.3 Двойная поддержка СУБД

**PostgreSQL:**
- Водитель: `psycopg2`
- Порт: 5432 (Pagila БД)
- Особенности: Sequences, CASCADE constraints, JSON support

**MySQL:**
- Водитель: `pymysql`
- Порт: 3306 (Sakila БД)
- Особенности: AUTO_INCREMENT, InnoDB Foreign Keys

**История тестов:**
- Отдельная PostgreSQL инстанция на порту 5433
- Таблицы: test_runs, test_metrics, test_results
- URL: `postgresql://postgres:history123@localhost:5433/test_history`

### 2.4 Backup/Restore Архитектура (Unique Feature)

**Проблема:** Write-операции (UPDATE, DELETE) в тестах изменяют БД. Нужно восстановление.

**Решение: Двухуровневая стратегия**

**Level 1: SQL-based Selective Backup** (по умолчанию, универсален)
```python
PRE-TEST:
  CREATE TABLE _backup_film AS SELECT * FROM film;
  CREATE TABLE _backup_customer AS SELECT * FROM customer;
  -- Сохраняем sequences

POST-TEST:
  TRUNCATE film CASCADE;
  INSERT INTO film SELECT * FROM _backup_film;
  -- Восстанавливаем sequences
  DROP TABLE _backup_film;
```
✅ Работает с любым SQLAlchemy-соединением  
✅ Не требует утилит (pg_dump/mysqldump)  
✅ Выбирает только затронутые таблицы  
✅ Мгновенно даже для больших БД (бэкапит только измененные строки)

**Level 2: Native Dump Strategy** (опционально, если доступны утилиты)
```bash
pg_dump -t affected_tables -Fd -f dump/  # PostgreSQL
mysqldump --tables film customer > dump.sql  # MySQL
# ... восстановление из дампа
```
✅ Полнофункциональный native-backup  
✅ Fallback если SQL-копии недоступны

**Верификация:**
- Сравнение row counts до/после
- Опциональные чексуммы (для критичных данных)
- Логирование всех операций

---

## 3. ПРОЕКТНЫЕ КОНВЕНЦИИ И СТАНДАРТЫ

### 3.1 Python Код

**Стиль:** PEP 8 + Google docstring format

```python
# Соглас с projeto: асинхронность везде где возможно
async def run_test(self, ...):
    """Docstring с описанием функции"""
    pass

# Type hints обязательны
def get_engine(self, db_type: str) -> Engine:
    pass
```

**Структура модулей:**
```
backend/
├── main.py                          # FastAPI app + endpoints
├── config.py                        # Конфигурация (YAML, env)
├── websocket_manager.py            # WebSocket для real-time
├── load_tester/
│   ├── __init__.py
│   └── tester.py                   # LoadTester класс
├── database/
│   ├── connection.py               # DatabaseConnection
│   ├── models.py                   # SQLAlchemy models
│   ├── queries.py                  # QueryManager
│   ├── query_analyzer.py           # QueryAnalyzer
│   ├── repository.py               # TestRepository (история)
│   ├── state_manager.py            # DatabaseStateManager (orchestrator)
│   ├── state_verifier.py           # StateVerifier
│   └── backup_strategies/
│       ├── sql_strategy.py         # SqlBackupStrategy
│       ├── native_strategy.py      # NativeDumpStrategy
│       └── __init__.py
├── visualizer/
│   ├── charts.py                   # Matplotlib/Seaborn графики
│   ├── result_saver.py             # Сохранение результатов
│   └── __init__.py
└── scripts/
    ├── init_history_db.py
    ├── init_scenarios.py
    └── test_backup_restore.py      # Тестирование restore
```

### 3.2 TypeScript/React Код

**Стиль:** Functional components + Hooks

```typescript
// Файл: frontend/components/home-page.tsx
export default function HomePage() {
  const [status, setStatus] = useState(...);
  const [data, setData] = useStore(...);
  
  return (
    <div>
      {/* Radix UI компоненты */}
    </div>
  );
}
```

**Структура compонентов:**
```
frontend/
├── app/                         # Next.js app directory (App Router)
│   ├── page.tsx                # Root page (/home-page)
│   ├── layout.tsx              # Root layout
│   └── globals.css
├── components/
│   ├── pages/
│   │   ├── home-page.tsx       # Главная
│   │   ├── config-page.tsx     # Конфигурация тестов
│   │   ├── scenarios-page.tsx  # Управление сценариями
│   │   ├── dashboards-page.tsx # Real-time метрики
│   │   ├── reports-page.tsx    # Отчеты
│   │   └── history-page.tsx    # История
│   ├── ui/                     # Radix UI + Tailwind компоненты
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   └── ... (40+ компонентов)
│   ├── header.tsx              # Top navigation
│   ├── sidebar.tsx             # Left sidebar menu
│   ├── database-state-panel.tsx
│   └── theme-provider.tsx      # Dark/Light mode
├── hooks/
│   ├── use-test-websocket.ts   # WebSocket для metrics
│   ├── use-mobile.ts           # Responsive detection
│   └── use-toast.ts            # Toast notifications
├── lib/
│   ├── api.ts                  # Fetch wrappers для backend
│   ├── types.ts                # TypeScript interfaces
│   ├── store.ts                # Zustand store
│   ├── chart-colors.ts         # Цветовая схема
│   └── utils.ts                # Утилиты
└── styles/
    └── globals.css             # Tailwind directives
```

### 3.3 Переменные окружения

**Backend (.env):**
```
# БД MySQL (Sakila)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=sakila
MYSQL_PASSWORD=sakila
MYSQL_DATABASE=sakila

# БД PostgreSQL (Pagila)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=123456
POSTGRES_DATABASE=pagila

# История тестов (отдельная PostgreSQL)
HISTORY_DATABASE_URL=postgresql://postgres:history123@localhost:5433/test_history

# API
API_HOST=0.0.0.0
API_PORT=8000
```

**Frontend (.env.local в frontend/):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### 3.4 Конфигурационные файлы

| Файл | Назначение | Формат |
|------|-----------|--------|
| [backend/config/database_config.yaml](backend/config/database_config.yaml) | Параметры подключения СУБД | YAML |
| [frontend/tsconfig.json](frontend/tsconfig.json) | TypeScript конфиг | JSON |
| [frontend/next.config.mjs](frontend/next.config.mjs) | Next.js конфиг | ESM |
| [frontend/postcss.config.mjs](frontend/postcss.config.mjs) | Tailwind конфиг | ESM |
| [frontend/components.json](frontend/components.json) | shadcn/ui конфиг | JSON |
| [docker-compose.yml](docker-compose.yml) | Docker сервисы (history-db) | YAML |

---

## 4. ПОТЕНЦИАЛЬНЫЕ ПОДВОДНЫЕ КАМНИ И РЕШЕНИЯ

### 4.1 Database Connection Issues

**Проблема:** Backend не подключается к БД

**Решение:**
```bash
# 1. Проверить, запущены ли контейнеры
docker ps | grep postgres
docker ps | grep mysql

# 2. Проверить конфиг в database_config.yaml
cat backend/config/database_config.yaml

# 3. Проверить логи backend
tail -f /tmp/backend.log  # если запускается фоном

# 4. Проверить conextion вручную
python3 -c "from backend.database.connection import DatabaseConnection; c = DatabaseConnection(); c.test_connection('postgresql')"
```

### 4.2 Frontend WebSocket Connection

**Проблема:** Real-time метрики не обновляются

**Решение:**
```typescript
// Проверить в DevTools Console
const ws = new WebSocket('ws://localhost:8000/ws/test-run/...');
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error:', e);

// Проверить на backend
# Смотреть логи WebSocket в main.py
```

**Key websocket paths:**
```
ws://localhost:8000/ws/test-run/{run_id}   # Metrics streaming
ws://localhost:8000/ws/status              # Status updates
```

### 4.3 History Database не инициализирована

**Проблема:** Таблицы test_runs не существуют

**Решение:**
```bash
# 1. Запустить history-db контейнер
docker-compose up -d history-db

# 2. Инициализировать БД
python3 backend/scripts/init_history_db.py

# 3. Проверить таблицы
psql -h localhost -p 5433 -U postgres -d test_history -c "\dt"
```

### 4.4 Virtual Environment Issues

**Проблема:** `ImportError` при запуске backend

**Решение:**
```bash
# 1. Пересоздать venv
rm -rf venv
python3 -m venv venv
source venv/bin/activate

# 2. Переустановить зависимости
pip install --upgrade pip
pip install -r requirements.txt

# 3. Проверить версию Python (должна быть 3.8+)
python3 --version
```

### 4.5 npm/pnpm Dependencies Issues

**Проблема:** `npm ERR!` при установке frontend

**Решение:**
```bash
# Проверить версию Node.js (14+)
node --version
npm --version

# Очистить кэш npm
npm cache clean --force

# Переустановить
rm -rf node_modules pnpm-lock.yaml
pnpm install  # или npm install
```

### 4.6 Write-операции сломали БД структуру

**Проблема:** После теста данные Sakila/Pagila испорчены

**Контекст:** Это нормальное состояние! Система как раз для этого:
- Тесты выполняют UPDATE/DELETE
- После теста состояние восстанавливается через StateManager
- Если restore не произошел → можно пересоздать БД из дампа

**Восстановление вручную:**
```bash
# PostgreSQL
cd ../pagila/pagila
./restore-pagila-data-jsonb.sh

# MySQL
cd ../../sakila
mysql -u root -p sakila < sakila-schema.sql
mysql -u root -p sakila < sakila-data.sql
```

### 4.7 Long-running Tests и Timeout

**Проблема:** Тест прерывается по timeout

**Решение:**
- Увеличить `operation_timeout` в [config.py](backend/config.py)
- Уменьшить количество итераций в конфигурации тестов
- Проверить, не заблокирована ли БД: `SELECT * FROM pg_locks;` (PostgreSQL)

### 4.8 Memory Leaks при долгих тестах

**Проблема:** Backend потребляет все больше памяти

**Решение:**
- Включить connection pooling (по умолчанию включен в [connection.py](backend/database/connection.py))
- Закрывать connections явно: `engine.dispose()`
- Проверить размеры `results[]` списка в LoadTester — не должны быть бесконечны

---

## 5. EXEMPLARY FILES (Образцовые файлы проекта)

### 5.1 Backend Patterns

**1. DatabaseConnection с YAML-конфигом**
```python
# backend/database/connection.py - строчки 1-70
# ✅ Pattern: YAML-config loading, engine pooling, type hints
```

**2. Async LoadTester с streaming metrics**
```python
# backend/load_tester/tester.py - строчки 1-80
# ✅ Pattern: async def, callbacks, type hints, metrics collection
```

**3. DatabaseStateManager (orchestrator pattern)**
```python
# backend/database/state_manager.py
# ✅ Pattern: Orchestrating multiple strategies, error handling
```

**4. FastAPI Endpoints с WebSocket + async**
```python
# backend/main.py - строчки 200-300 (примеры endpoints)
# ✅ Pattern: FastAPI routes, CORS middleware, WebSocket, background tasks
```

### 5.2 Frontend Patterns

**1. TypeScript hook для WebSocket**
```typescript
// frontend/hooks/use-test-websocket.ts
// ✅ Pattern: Custom hook, useEffect cleanup, error handling
```

**2. Zustand store для глобального state**
```typescript
// frontend/lib/store.ts
// ✅ Pattern: Reactive state, computed values, async actions
```

**3. Form с React Hook Form + Zod**
```typescript
// frontend/components/pages/config-page.tsx
// ✅ Pattern: Type-safe forms, validation, error messages
```

**4. Recharts dashboard**
```typescript
// frontend/components/pages/dashboards-page.tsx
// ✅ Pattern: Real-time charting, responsive layout, theme support
```

### 5.3 Configuration Files

**1. Dual-DBMS конфиг**
```yaml
# backend/config/database_config.yaml
# ✅ Pattern: Multi-database support, structured config
```

**2. Next.js App Router setup**
```typescript
// frontend/app/layout.tsx
// ✅ Pattern: App Router root layout, providers, metadata
```

**3. Tailwind + Radix UI integration**
```
# frontend/components/ui/*.tsx
# ✅ Pattern: Compound components, CSS-in-JS, accessibility
```

---

## 6. KEY ENTRY POINTS И WORKFLOW

### 6.1 Полный workflow тестирования

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. USER OPENS DASHBOARD                                         │
│    http://localhost:3000                                        │
│    (frontend/components/pages/home-page.tsx)                    │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. USER CONFIGURES TEST                                         │
│    - Selects: MySQL or PostgreSQL                              │
│    - Chooses scenario (SELECT, UPDATE, etc.)                   │
│    - Sets: num_users, spawn_rate, duration                     │
│    POST /api/tests/configure                                   │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. BACKEND ANALYZES SCENARIO                                    │
│    QueryAnalyzer.analyze_scenario(queries)                     │
│    ├─ extract_affected_tables() → {table1, table2, ...}        │
│    ├─ classify_queries() → [READ, WRITE, ...]                 │
│    └─ has_write_operations() → True/False                      │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. CREATE BACKUP (if WRITE operations detected)                │
│    StateManager.prepare_backup()                               │
│    ├─ SqlBackupStrategy.create_backup(engine, tables)          │
│    │  └─ CREATE TABLE _backup_film AS SELECT * FROM film       │
│    └─ Save sequence values (PostgreSQL) / AUTO_INCREMENT (MySQL)
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. RUN TEST UNDER LOAD                                         │
│    LoadTester.run_test(...)                                    │
│    ├─ Spawn N concurrent users (asyncio)                      │
│    ├─ Execute queries repeatedly                              │
│    ├─ Collect metrics (RPS, latency, CPU, memory)             │
│    └─ Stream metrics via WebSocket in real-time               │
│       ws://localhost:8000/ws/test-run/{run_id}                │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. FRONTEND DISPLAYS REAL-TIME DASHBOARD                       │
│    use-test-websocket.ts hook subscribes to metrics            │
│    ├─ Response Time graph (Recharts)                          │
│    ├─ TPS (transactions/sec)                                  │
│    ├─ CPU Usage %                                             │
│    ├─ Memory Usage                                            │
│    └─ Error Rate                                              │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. TEST COMPLETES                                              │
│    SaveResults + StoreInHistory DB                             │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. RESTORE DATABASE STATE (if WRITE operations were done)      │
│    StateManager.restore_backup()                               │
│    ├─ TRUNCATE tables                                          │
│    ├─ INSERT INTO film SELECT * FROM _backup_film             │
│    ├─ Restore sequences (PostgreSQL)                          │
│    ├─ DROP backup tables                                      │
│    └─ StateVerifier.verify() - confirm row counts match        │
└────────┬──────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. VIEW RESULTS                                                 │
│    Reports Page: Можно сравнить MySQL vs PostgreSQL            │
│    History Page: Все прошлые тесты                             │
│    Download: CSV/JSON export                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 Key Files для Modifications

| Задача | Файл | Раздел |
|--------|------|--------|
| Добавить новый endpoint API | [backend/main.py](backend/main.py) | После других endpoints |
| Добавить новую метрику | [backend/load_tester/tester.py](backend/load_tester/tester.py) | `_emit_metrics()` |
| Новая стратегия backup | [backend/database/state_manager.py](backend/database/state_manager.py) | Наследовать `BackupStrategy` |
| Новая страница UI | [frontend/components/pages/](frontend/components/pages/) | Создать `*.tsx` |
| Изменить дизайн | [frontend/styles/globals.css](frontend/styles/globals.css) | Tailwind directives |
| Новая сценарий БД | [backend/scripts/init_scenarios.py](backend/scripts/init_scenarios.py) | Добавить INSERT |

---

## 7. DEPENDENCIES OVERVIEW

### Backend (Python)

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| fastapi | 0.104.1 | Web framework |
| uvicorn | 0.24.0 | ASGI сервер |
| sqlalchemy | 2.0.23 | ORM + database abstraction |
| psycopg2-binary | 2.9.9 | PostgreSQL водитель |
| pymysql | 1.1.0 | MySQL водитель |
| asyncpg | 0.29.0 | Async PostgreSQL (опционально) |
| pydantic | 2.5.0 | Data validation |
| pandas | 2.1.3 | Data analysis |
| matplotlib/seaborn | 3.8.2 / 0.13.0 | Графики |
| locust | 2.17.0 | Load testing framework |
| websockets | 12.0 | WebSocket поддержка |
| pyyaml | 6.0.1 | YAML parsing |

### Frontend (Node.js)

| Пакет | Версия | Назначение |
|-------|--------|-----------|
| next | 16.0.10 | React framework |
| react | 19.2.0 | UI library |
| typescript | 5 | Language |
| tailwindcss | 4.1.9 | Styling |
| @radix-ui/* | 1.x | Headless UI components |
| recharts | 2.15.4 | Charting |
| zustand | 5.0.9 | State management |
| react-hook-form | 7.60.0 | Form handling |
| zod | 3.25.76 | Schema validation |

---

## 8. PRODUCTIVITY TIPS FOR AGENTS

### 8.1 Quick Commands

```bash
# Полный restart
docker-compose down && docker-compose up -d
./start_backend.sh
cd frontend && pnpm dev

# Проверить все компоненты
python3 -m py_compile backend/database/*.py backend/load_tester/*.py

# Просмотреть логи backend (в отдельном терминале)
tail -f $HOME/.pm2/logs/backend-error.log  # если PM2
journalctl -u backend -f  # если systemd
```

### 8.2 Debugging Tips

```python
# В backend для отладки metrics
print(f"[DEBUG] Metrics: RPS={tps}, Latency={response_time}ms")

# Для WebSocket в frontend
localStorage.setItem('debug', 'true');  // DevTools Console
```

### 8.3 Performance Profiling

```bash
# CPU profiling (Python)
python3 -m cProfile -s cumtime backend/main.py

# Memory profiling
pip install tracemalloc
python3 -c "import tracemalloc; tracemalloc.start(); ..."

# Network monitoring (Frontend)
# DevTools → Network → Filter XHR
```

### 8.4 Database Query Optimization

```sql
-- PostgreSQL
EXPLAIN ANALYZE SELECT * FROM film WHERE rental_rate > 4.99;
CREATE INDEX idx_rental_rate ON film(rental_rate);

-- MySQL
EXPLAIN SELECT * FROM film WHERE rental_rate > 4.99\G
CREATE INDEX idx_rental_rate ON film(rental_rate);
```

---

## 9. SUMMARY TABLE

| Аспект | Значение | Файл |
|--------|----------|------|
| **Backend язык** | Python 3.8+ | [requirements.txt](requirements.txt) |
| **Frontend язык** | TypeScript 5 + React 19 | [package.json](frontend/package.json) |
| **API Framework** | FastAPI 0.104.1 | [main.py](backend/main.py#L1) |
| **СУБД** | PostgreSQL + MySQL | [database_config.yaml](backend/config/database_config.yaml) |
| **UI Components** | Radix UI 40+ | [frontend/components/ui/](frontend/components/ui/) |
| **Scaling** | Concurrent users | [tester.py](backend/load_tester/tester.py#L50-L100) |
| **Backup Strategy** | SQL-selective + Native | [state_manager.py](backend/database/state_manager.py) |
| **Real-time Updates** | WebSocket + Zustand | [use-test-websocket.ts](frontend/hooks/use-test-websocket.ts) |
| **Data Persistence** | Test History DB | [repository.py](backend/database/repository.py) |
| **Deployment** | Docker + Docker-compose | [docker-compose.yml](docker-compose.yml) |

---

**Создано при анализе:** 2026-03-16  
**Версия проекта:** 2.0.0 (с модулем восстановления БД)  
**Статус:** Production-ready + Testing features
