"""
Тесты классификации SQL-нагрузки для cache meaningfulness.
"""
from backend.load_tester.sql_workload_classifier import (
    ACTIVITY_SCALAR_ONLY,
    ACTIVITY_METADATA_ONLY,
    ACTIVITY_USER_TABLE_READ,
    ACTIVITY_WRITE_WORKLOAD,
    classify_workload_sql,
)


def test_classify_select1_scalar_only():
    assert classify_workload_sql("SELECT 1") == ACTIVITY_SCALAR_ONLY


def test_classify_information_schema_metadata():
    sql = "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    assert classify_workload_sql(sql) == ACTIVITY_METADATA_ONLY


def test_classify_user_table_read():
    assert classify_workload_sql("SELECT * FROM customer WHERE customer_id = 1") == ACTIVITY_USER_TABLE_READ


def test_classify_write_workload():
    assert classify_workload_sql("UPDATE customer SET active = 1 WHERE id = 5") == ACTIVITY_WRITE_WORKLOAD
