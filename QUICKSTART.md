# Быстрый старт

## Полный запуск системы

### 1. Запуск баз данных

```bash
# PostgreSQL (Pagila)
cd ../pagila/pagila
docker-compose up -d

# MySQL (Sakila)
cd ../../sakila
docker-compose up -d

# Инициализация Pagila (если нужно)
cd ../code
./init_pagila.sh
```

### 2. Запуск Backend

```bash
cd code
source venv/bin/activate
pip install -r requirements.txt
./start_backend.sh
```

Backend будет доступен на http://localhost:8000

### 3. Запуск Frontend

```bash
cd code/frontend_prototype

# Установка зависимостей (первый раз)
pnpm install
# или
npm install

# Создание .env.local
cp env.example .env.local

# Запуск dev сервера
pnpm dev
# или
npm run dev
```

Frontend будет доступен на http://localhost:3000

## Проверка работы

1. Откройте http://localhost:3000
2. На главной странице проверьте статус подключений к БД
3. Перейдите в "Конфигурация и запуск"
4. Выберите базы данных и запрос
5. Запустите тестирование
6. Просмотрите результаты в "Дашборды" и "Отчёты"

## Структура проекта

- `backend/` - FastAPI сервер
- `frontend_prototype/` - Next.js приложение (основной frontend)
- `frontend_legacy/` - Простой HTML frontend (legacy)
- `database/` - Модули подключения к БД
- `load_tester/` - Модуль нагрузочного тестирования
- `visualizer/` - Визуализация результатов

