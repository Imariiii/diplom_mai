# Native Backup/Restore Integration Tests

Интеграционные тесты проверяют полный цикл именно для `NativeDumpStrategy`:

1. создание тестовой схемы;
2. `DatabaseStateManager.prepare_for_test`;
3. реальные `UPDATE` / `INSERT` / `DELETE`;
4. `restore_after_test`;
5. сравнение значений, количества строк и sequence / auto-increment.

Обычный pytest не запускает эти тесты без явного маркера.

## Быстрые unit-тесты

```bash
source venv/bin/activate
python -m pytest backend/tests/test_native_dump_strategy.py -v
```

## Интеграция с уже запущенными БД

Используйте только отдельные disposable-базы. По умолчанию тесты пропускают
непустые базы, чтобы случайно не трогать рабочие Sakila/Pagila/Makila. На
машине должны быть установлены рабочие CLI-клиенты `pg_dump` / `pg_restore`,
`mysqldump` / `mysql` или `mariadb-dump` / `mariadb`.

```bash
source venv/bin/activate
BACKUP_RESTORE_POSTGRES_URL="postgresql+asyncpg://user:pass@localhost:5432/restore_test" \
BACKUP_RESTORE_MYSQL_URL="mysql+aiomysql://user:pass@localhost:3306/restore_test" \
BACKUP_RESTORE_MARIADB_URL="mysql+aiomysql://user:pass@localhost:3307/restore_test" \
python -m pytest backend/tests/integration -m integration
```

Если вы осознанно запускаете тесты против непустой тестовой базы, добавьте:

```bash
BACKUP_RESTORE_ALLOW_NONEMPTY=1
```

## Самодостаточный Docker-режим

Рекомендуемый режим. Compose поднимает PostgreSQL, MySQL, MariaDB и отдельный
`native-test-runner` с Python-зависимостями и native CLI-клиентами внутри
контейнера. Это исключает skip из-за отсутствующих клиентов на host-машине.

```bash
docker compose -f backend/tests/integration/docker-compose.backup-restore.yml \
  run --rm native-test-runner
```

После проверки можно удалить тестовые БД и volumes:

```bash
docker compose -f backend/tests/integration/docker-compose.backup-restore.yml \
  down -v
```

## Что Покрыто

- PostgreSQL: `pg_dump --format=custom`, `pg_restore --data-only`, partitioned
  table, trigger, sequence.
- MySQL: `mysqldump` / `mariadb-dump`, restore через native client, FK,
  trigger, AUTO_INCREMENT.
- MariaDB: dump с `DEFINER`, restore пользователем без `SET USER`, проверка
  удаления `DEFINER` перед импортом.
