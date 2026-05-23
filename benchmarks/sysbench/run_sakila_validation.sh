#!/usr/bin/env bash
# Прогоны sysbench для сравнения с OLTP bundle (Sakila/Pagila/Makila)
# Использование:
#   ./run_sakila_validation.sh          # средняя нагрузка (по умолчанию)
#   ./run_sakila_validation.sh light    # 15 threads, 750 tx, warmup 5s
#   ./run_sakila_validation.sh medium   # 30 threads, 3000 tx, warmup 10s
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/sakila_oltp_validation.lua"
OUT_DIR="${SCRIPT_DIR}"
PROFILE="${1:-medium}"

if ! command -v sysbench >/dev/null 2>&1; then
  echo "sysbench не найден. Установите: sudo apt install sysbench"
  exit 1
fi

case "$PROFILE" in
  light)
    THREADS=15
    EVENTS=750
    WARMUP=5
    SUFFIX="15t_750ev"
    ;;
  medium)
    THREADS=30
    EVENTS=3000
    WARMUP=10
    SUFFIX="30t_3000ev"
    ;;
  *)
    echo "Неизвестный профиль: $PROFILE (light|medium)"
    exit 1
    ;;
esac

echo "Профиль: $PROFILE (threads=$THREADS events=$EVENTS warmup=${WARMUP}s)"

run_pair() {
  local label="$1"
  shift
  local log="${OUT_DIR}/results_${label}_${SUFFIX}.log"
  echo ""
  echo "========== ${label}: warmup (${WARMUP}s) =========="
  sysbench "$SCRIPT" "$@" --threads="$THREADS" --time="$WARMUP" run
  echo ""
  echo "========== ${label}: measure (${EVENTS} events) =========="
  sysbench "$SCRIPT" "$@" --threads="$THREADS" --events="$EVENTS" --report-interval=5 run 2>&1 | tee "$log"
  echo "Сохранено: $log"
}

run_pair "mysql_sakila" \
  --db-driver=mysql \
  --mysql-host=127.0.0.1 --mysql-port=3306 \
  --mysql-user=sakila --mysql-password=sakila \
  --mysql-db=sakila

run_pair "pgsql_pagila" \
  --db-driver=pgsql \
  --pgsql-host=127.0.0.1 --pgsql-port=5437 \
  --pgsql-user=pagila --pgsql-password=pagila \
  --pgsql-db=pagila_new

run_pair "maria_makila" \
  --db-driver=mysql \
  --mysql-host=127.0.0.1 --mysql-port=3307 \
  --mysql-user=sakila --mysql-password=sakila \
  --mysql-db=sakila

echo ""
echo "========== Сводка (${SUFFIX}) =========="
grep -h -E "transactions:|ignored errors:|avg:|95th percentile:" \
  "${OUT_DIR}"/results_*_"${SUFFIX}".log 2>/dev/null || true
