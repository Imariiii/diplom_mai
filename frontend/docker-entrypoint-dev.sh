#!/bin/sh
set -e
# При bind-mount ./frontend том node_modules может быть пустым при первом запуске
if [ ! -x "node_modules/.bin/next" ]; then
  echo "[docker-entrypoint-dev] Устанавливаю зависимости (npm ci)..."
  npm ci
fi
exec npm run dev -- --hostname 0.0.0.0 --port 3000
