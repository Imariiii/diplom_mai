#!/bin/bash
# Скрипт для инициализации базы данных Pagila

echo "Инициализация базы данных Pagila..."

# Проверка существования базы
DB_EXISTS=$(docker exec pagila psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='pagila'")

if [ "$DB_EXISTS" != "1" ]; then
    echo "Создание базы данных pagila..."
    docker exec pagila psql -U postgres -c "CREATE DATABASE pagila;"
fi

# Проверка наличия таблиц
TABLES_COUNT=$(docker exec pagila psql -U postgres -d pagila -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

if [ "$TABLES_COUNT" = "0" ]; then
    echo "База данных пуста. Инициализация схемы и данных..."
    
    # Инициализация схемы
    if [ -f "../pagila/pagila/pagila-schema.sql" ]; then
        echo "Загрузка схемы..."
        docker exec -i pagila psql -U postgres -d pagila < ../pagila/pagila/pagila-schema.sql
    fi
    
    # Инициализация данных
    if [ -f "../pagila/pagila/pagila-data.sql" ]; then
        echo "Загрузка данных..."
        docker exec -i pagila psql -U postgres -d pagila < ../pagila/pagila/pagila-data.sql
    fi
    
    echo "Инициализация завершена!"
else
    echo "База данных уже инициализирована ($TABLES_COUNT таблиц)"
fi

