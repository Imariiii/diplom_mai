#!/usr/bin/env bash
#
# Запуск backend-тестов с покрытием
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

if [ -f venv/bin/activate ]; then
    source venv/bin/activate
fi

echo "=== Backend Tests ==="
python -m pytest backend/tests/ \
    -v \
    --tb=short \
    --cov=backend \
    --cov-report=term-missing \
    --cov-report=html:backend/tests/htmlcov \
    "$@"

echo ""
echo "HTML coverage report: backend/tests/htmlcov/index.html"
