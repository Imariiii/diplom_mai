#!/usr/bin/env bash
# Один SQL: SELECT * FROM rental WHERE rental_id = 1
# Профили: light (15/750/5), medium (30/3000/10)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SCRIPT_DIR}/sakila_single_query_validation.lua"
OUT_DIR="${SCRIPT_DIR}"
PROFILE="${1:-medium}"
QUERY="SELECT * FROM rental WHERE rental_id = 1"

case "$PROFILE" in
  light) THREADS=15; EVENTS=750; WARMUP=5; SUFFIX="single_15t_750ev" ;;
  medium) THREADS=30; EVENTS=3000; WARMUP=10; SUFFIX="single_30t_3000ev" ;;
  *) echo "Профиль: light|medium"; exit 1 ;;
esac

echo "single query / $PROFILE"
echo "SQL: $QUERY"

run_pair() {
  local label="$1"
  shift
  local log="${OUT_DIR}/results_${label}_${SUFFIX}.log"
  echo ""
  echo "========== ${label} =========="
  sysbench "$SCRIPT" "$@" --threads="$THREADS" --time="$WARMUP" run
  sysbench "$SCRIPT" "$@" \
    --threads="$THREADS" --events="$EVENTS" --report-interval=5 \
    run 2>&1 | tee "$log"
}

run_pair "mysql_sakila" \
  --db-driver=mysql \
  --mysql-host=127.0.0.1 --mysql-port=3306 \
  --mysql-user=sakila --mysql-password=sakila --mysql-db=sakila

run_pair "pgsql_pagila" \
  --db-driver=pgsql \
  --pgsql-host=127.0.0.1 --pgsql-port=5437 \
  --pgsql-user=pagila --pgsql-password=pagila --pgsql-db=pagila_new

run_pair "maria_makila" \
  --db-driver=mysql \
  --mysql-host=127.0.0.1 --mysql-port=3307 \
  --mysql-user=sakila --mysql-password=sakila --mysql-db=sakila

echo ""
grep -h -E "transactions:|ignored errors:|avg:|95th percentile:" "${OUT_DIR}"/results_*_"${SUFFIX}".log
