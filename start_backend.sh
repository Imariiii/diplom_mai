#!/bin/bash
# Скрипт для запуска backend сервера

cd "$(dirname "$0")"

# Активация виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Виртуальное окружение не найдено. Создайте его: python3 -m venv venv"
    exit 1
fi

# Проверка установки зависимостей
if ! python3 -c "import fastapi" 2>/dev/null; then
    echo "Установка зависимостей..."
    pip install -q -r requirements.txt
fi

# Запуск backend
echo "Запуск backend сервера на http://localhost:8000"
echo "Документация API: http://localhost:8000/docs"
echo ""
cd backend
python3 main.py

