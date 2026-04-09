"""
Миграция 002: Заполнение built-in сценариев тестирования

Создаёт 6 встроенных сценариев: read_only, write_only, mixed_light,
mixed_heavy, oltp, olap — с SQL-запросами и параметрами.
"""
import uuid

from sqlalchemy import text


BUILTIN_SCENARIOS = [
    {
        "name": "read_only",
        "description": "Только чтение - 100% SELECT запросов разной сложности",
        "scenario_type": "read_only",
        "queries": [
            {
                "sql_template": "SELECT * FROM actor WHERE actor_id = {actor_id}",
                "query_type": "select",
                "weight": 30,
                "description": "Простой SELECT по primary key",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "SELECT * FROM film WHERE film_id = {film_id}",
                "query_type": "select",
                "weight": 30,
                "description": "SELECT фильма по ID",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": (
                    "SELECT f.*, c.name as category FROM film f "
                    "JOIN film_category fc ON f.film_id = fc.film_id "
                    "JOIN category c ON fc.category_id = c.category_id "
                    "WHERE f.film_id = {film_id}"
                ),
                "query_type": "select",
                "weight": 20,
                "description": "SELECT с JOIN",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": (
                    "SELECT COUNT(*) as rental_count, SUM(p.amount) as total_amount "
                    "FROM rental r JOIN payment p ON r.rental_id = p.rental_id "
                    "WHERE r.customer_id = {customer_id}"
                ),
                "query_type": "select",
                "weight": 20,
                "description": "Аналитический SELECT с агрегацией",
                "params": [
                    {"param_name": "customer_id", "param_type": "random_from_table", "table_ref": "customer", "column_ref": "customer_id"},
                ],
            },
        ],
    },
    {
        "name": "write_only",
        "description": "Только запись - INSERT, UPDATE, DELETE",
        "scenario_type": "write_only",
        "queries": [
            {
                "sql_template": "UPDATE actor SET last_update = NOW() WHERE actor_id = {actor_id}",
                "query_type": "update",
                "weight": 40,
                "description": "Обновление записи актёра",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "UPDATE film SET rental_rate = rental_rate + 0.01 WHERE film_id = {film_id}",
                "query_type": "update",
                "weight": 30,
                "description": "Обновление цены фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": "UPDATE customer SET last_update = NOW() WHERE customer_id = {customer_id}",
                "query_type": "update",
                "weight": 30,
                "description": "Обновление записи клиента",
                "params": [
                    {"param_name": "customer_id", "param_type": "random_from_table", "table_ref": "customer", "column_ref": "customer_id"},
                ],
            },
        ],
    },
    {
        "name": "mixed_light",
        "description": "Лёгкая смесь - 80% SELECT, 20% UPDATE",
        "scenario_type": "mixed_light",
        "queries": [
            {
                "sql_template": "SELECT * FROM actor WHERE actor_id = {actor_id}",
                "query_type": "select",
                "weight": 25,
                "description": "SELECT актёра",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "SELECT * FROM film WHERE film_id = {film_id}",
                "query_type": "select",
                "weight": 25,
                "description": "SELECT фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": "SELECT * FROM customer WHERE customer_id = {customer_id}",
                "query_type": "select",
                "weight": 20,
                "description": "SELECT клиента",
                "params": [
                    {"param_name": "customer_id", "param_type": "random_from_table", "table_ref": "customer", "column_ref": "customer_id"},
                ],
            },
            {
                "sql_template": "UPDATE actor SET last_update = NOW() WHERE actor_id = {actor_id}",
                "query_type": "update",
                "weight": 15,
                "description": "UPDATE актёра",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "UPDATE film SET rental_rate = rental_rate + 0.01 WHERE film_id = {film_id}",
                "query_type": "update",
                "weight": 15,
                "description": "UPDATE фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
        ],
    },
    {
        "name": "mixed_heavy",
        "description": "Тяжёлая смесь - 50% SELECT, 50% UPDATE",
        "scenario_type": "mixed_heavy",
        "queries": [
            {
                "sql_template": "SELECT * FROM actor WHERE actor_id = {actor_id}",
                "query_type": "select",
                "weight": 20,
                "description": "SELECT актёра",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "SELECT * FROM film WHERE film_id = {film_id}",
                "query_type": "select",
                "weight": 20,
                "description": "SELECT фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": "SELECT * FROM rental WHERE rental_id = {rental_id}",
                "query_type": "select",
                "weight": 10,
                "description": "SELECT аренды",
                "params": [
                    {"param_name": "rental_id", "param_type": "random_from_table", "table_ref": "rental", "column_ref": "rental_id"},
                ],
            },
            {
                "sql_template": "UPDATE actor SET last_update = NOW() WHERE actor_id = {actor_id}",
                "query_type": "update",
                "weight": 20,
                "description": "UPDATE актёра",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "UPDATE film SET rental_rate = rental_rate + 0.01 WHERE film_id = {film_id}",
                "query_type": "update",
                "weight": 20,
                "description": "UPDATE фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": "UPDATE customer SET last_update = NOW() WHERE customer_id = {customer_id}",
                "query_type": "update",
                "weight": 10,
                "description": "UPDATE клиента",
                "params": [
                    {"param_name": "customer_id", "param_type": "random_from_table", "table_ref": "customer", "column_ref": "customer_id"},
                ],
            },
        ],
    },
    {
        "name": "oltp",
        "description": "OLTP - транзакционная нагрузка, короткие запросы",
        "scenario_type": "oltp",
        "queries": [
            {
                "sql_template": "SELECT actor_id, first_name, last_name FROM actor WHERE actor_id = {actor_id}",
                "query_type": "select",
                "weight": 35,
                "description": "Быстрый SELECT по PK",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
            {
                "sql_template": "SELECT film_id, title, rental_rate FROM film WHERE film_id = {film_id}",
                "query_type": "select",
                "weight": 35,
                "description": "Быстрый SELECT фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
            {
                "sql_template": "SELECT inventory_id, film_id, store_id FROM inventory WHERE inventory_id = {inventory_id}",
                "query_type": "select",
                "weight": 20,
                "description": "Проверка наличия",
                "params": [
                    {"param_name": "inventory_id", "param_type": "random_from_table", "table_ref": "inventory", "column_ref": "inventory_id"},
                ],
            },
            {
                "sql_template": "UPDATE actor SET last_update = NOW() WHERE actor_id = {actor_id}",
                "query_type": "update",
                "weight": 10,
                "description": "Быстрое обновление",
                "params": [
                    {"param_name": "actor_id", "param_type": "random_from_table", "table_ref": "actor", "column_ref": "actor_id"},
                ],
            },
        ],
    },
    {
        "name": "olap",
        "description": "OLAP - аналитические запросы с JOIN и агрегацией",
        "scenario_type": "olap",
        "queries": [
            {
                "sql_template": (
                    "SELECT c.name as category, COUNT(*) as film_count, AVG(f.rental_rate) as avg_rate "
                    "FROM category c "
                    "JOIN film_category fc ON c.category_id = fc.category_id "
                    "JOIN film f ON fc.film_id = f.film_id "
                    "GROUP BY c.category_id, c.name "
                    "ORDER BY film_count DESC"
                ),
                "query_type": "select",
                "weight": 25,
                "description": "Агрегация по категориям",
                "params": [],
            },
            {
                "sql_template": (
                    "SELECT DATE(r.rental_date) as rental_day, COUNT(*) as rentals, SUM(p.amount) as revenue "
                    "FROM rental r "
                    "JOIN payment p ON r.rental_id = p.rental_id "
                    "WHERE r.rental_date >= CURRENT_DATE - INTERVAL '30 days' "
                    "GROUP BY DATE(r.rental_date) "
                    "ORDER BY rental_day DESC"
                ),
                "query_type": "select",
                "weight": 25,
                "description": "Ежедневная статистика за 30 дней",
                "params": [],
            },
            {
                "sql_template": (
                    "SELECT cu.first_name, cu.last_name, COUNT(r.rental_id) as rental_count, SUM(p.amount) as total_spent "
                    "FROM customer cu "
                    "JOIN rental r ON cu.customer_id = r.customer_id "
                    "JOIN payment p ON r.rental_id = p.rental_id "
                    "WHERE cu.customer_id = {customer_id} "
                    "GROUP BY cu.customer_id, cu.first_name, cu.last_name"
                ),
                "query_type": "select",
                "weight": 25,
                "description": "Статистика по клиенту",
                "params": [
                    {"param_name": "customer_id", "param_type": "random_from_table", "table_ref": "customer", "column_ref": "customer_id"},
                ],
            },
            {
                "sql_template": (
                    "SELECT f.title, f.rental_rate, f.replacement_cost, "
                    "COUNT(r.rental_id) as times_rented, "
                    "SUM(p.amount) as total_revenue "
                    "FROM film f "
                    "LEFT JOIN inventory i ON f.film_id = i.film_id "
                    "LEFT JOIN rental r ON i.inventory_id = r.inventory_id "
                    "LEFT JOIN payment p ON r.rental_id = p.rental_id "
                    "WHERE f.film_id = {film_id} "
                    "GROUP BY f.film_id, f.title, f.rental_rate, f.replacement_cost"
                ),
                "query_type": "select",
                "weight": 25,
                "description": "ROI анализ фильма",
                "params": [
                    {"param_name": "film_id", "param_type": "random_from_table", "table_ref": "film", "column_ref": "film_id"},
                ],
            },
        ],
    },
]


def _insert_scenario(conn, scenario_data: dict) -> None:
    """Вставить один сценарий с его запросами и параметрами."""
    scenario_id = str(uuid.uuid4())

    conn.execute(
        text(
            "INSERT INTO test_scenarios (id, name, description, scenario_type, is_builtin, is_active) "
            "VALUES (:id, :name, :desc, :stype, 't', 't') "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {
            "id": scenario_id,
            "name": scenario_data["name"],
            "desc": scenario_data["description"],
            "stype": scenario_data["scenario_type"],
        },
    )

    for idx, query_data in enumerate(scenario_data["queries"]):
        query_id = str(uuid.uuid4())
        conn.execute(
            text(
                "INSERT INTO scenario_queries "
                "(id, scenario_id, sql_template, query_type, weight, order_index, description) "
                "VALUES (:id, :sid, :sql, :qtype, :weight, :idx, :desc)"
            ),
            {
                "id": query_id,
                "sid": scenario_id,
                "sql": query_data["sql_template"].strip(),
                "qtype": query_data["query_type"],
                "weight": query_data["weight"],
                "idx": idx,
                "desc": query_data.get("description", ""),
            },
        )

        for param_data in query_data.get("params", []):
            param_id = str(uuid.uuid4())
            conn.execute(
                text(
                    "INSERT INTO scenario_params "
                    "(id, query_id, param_name, param_type, min_value, max_value, "
                    "string_pattern, string_length, table_ref, column_ref, current_value, step) "
                    "VALUES (:id, :qid, :pname, :ptype, :minv, :maxv, "
                    ":spattern, :slength, :tref, :cref, :curval, :step)"
                ),
                {
                    "id": param_id,
                    "qid": query_id,
                    "pname": param_data["param_name"],
                    "ptype": param_data["param_type"],
                    "minv": param_data.get("min_value"),
                    "maxv": param_data.get("max_value"),
                    "spattern": param_data.get("string_pattern"),
                    "slength": param_data.get("string_length"),
                    "tref": param_data.get("table_ref"),
                    "cref": param_data.get("column_ref"),
                    "curval": param_data.get("current_value", 0),
                    "step": param_data.get("step", 1),
                },
            )


def upgrade(conn) -> None:
    existing = conn.execute(
        text("SELECT COUNT(*) FROM test_scenarios WHERE is_builtin = 't'")
    ).scalar()

    if existing and existing > 0:
        print("  Built-in сценарии уже существуют, пропуск")
        return

    for scenario_data in BUILTIN_SCENARIOS:
        _insert_scenario(conn, scenario_data)
        print(f"  ✓ Сценарий '{scenario_data['name']}'")
