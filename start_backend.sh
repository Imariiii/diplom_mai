#!/bin/bash
cd "$(dirname "$0")"

VENV_DIR="venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "Виртуальное окружение не найдено. Создайте его: python3 -m venv $VENV_DIR"
    exit 1
fi

PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip3"

# Проверка наличия pip (на всякий случай)
if [ ! -f "$PIP" ]; then
    echo "pip не найден в виртуальном окружении. Возможно, окружение повреждено."
    exit 1
fi

# Установка зависимостей, если fastapi не импортируется
if ! $PYTHON -c "import fastapi" 2>/dev/null; then
    echo "Установка зависимостей..."
    $PIP install -q -r requirements.txt
fi

echo "Запуск backend сервера на http://localhost:8000"
echo "Документация API: http://localhost:8000/docs"
echo ""
$PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port 8000