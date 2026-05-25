# Сравнительное нагрузочное тестирование СУБД

Веб-система для запуска сценариев нагрузки на **PostgreSQL**, **MySQL** и **MariaDB**, сбора метрик в реальном времени, хранения истории прогонов и сравнения результатов.

**Стек:** Python 3 / FastAPI, Next.js 16, служебная БД PostgreSQL (`project-db`) для истории и справочников.

## Быстрый старт (Docker)

```bash
cp env.example .env

docker compose up -d --build
```

- UI: http://localhost:3000  
- API: http://localhost:8000 (Swagger: `/docs`)  
- История тестов: PostgreSQL на порту **5433** (`project_data`)

Проверка: `curl http://localhost:8000/health`

## Локальная разработка

**БД проекта** (остальное на хосте):

```bash
docker compose up -d project-db
cp env.example .env
```

**Backend** (из корня, нужен `venv`):

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./start_backend.sh
```

Миграции Alembic применяются при старте API.

**Frontend** (Node ≥ 20.19, см. `.nvmrc`):

```bash
cd frontend && npm ci && npm run dev
```

Hot reload в контейнере: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`.

## Тесты

```bash
# backend
source venv/bin/activate && python -m pytest backend/tests/ -m "not integration" -v

# frontend
cd frontend && npm test
```

Интеграционные тесты backup/restore — `backend/tests/integration/README.md`.