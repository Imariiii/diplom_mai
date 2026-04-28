"""
Тесты для самоверификации метрик нагрузочного теста.
"""
import pytest

from backend.load_tester.self_check import cross_validate_metrics, verify_littles_law


class TestVerifyLittlesLaw:
    def test_ideal_case(self):
        result = verify_littles_law(
            virtual_users=10,
            avg_latency_sec=0.1,
            throughput_rps=100.0,
        )

        assert result["valid"] is True
        assert result["computed_concurrency"] == pytest.approx(10.0)
        assert result["ratio"] == pytest.approx(1.0)
        assert result["warning"] is None

    def test_valid_within_tolerance(self):
        result = verify_littles_law(
            virtual_users=10,
            avg_latency_sec=0.12,
            throughput_rps=100.0,
            tolerance=0.3,
        )

        assert result["valid"] is True
        assert result["ratio"] == pytest.approx(1.2)

    def test_violation(self):
        result = verify_littles_law(
            virtual_users=10,
            avg_latency_sec=0.2,
            throughput_rps=100.0,
            tolerance=0.3,
        )

        assert result["valid"] is False
        assert result["reason"] == "concurrency_mismatch"
        assert "Закон Литтла нарушен" in result["warning"]

    def test_sql_concurrency_below_virtual_users_is_not_a_violation(self):
        result = verify_littles_law(
            virtual_users=15,
            avg_latency_sec=0.02507495107327365,
            throughput_rps=368.08402309551104,
            tolerance=0.3,
        )

        assert result["valid"] is True
        assert result["reason"] is None
        assert result["warning"] is None
        assert result["computed_sql_concurrency"] == pytest.approx(9.229688869973668)
        assert result["computed_concurrency"] == pytest.approx(9.229688869973668)

    def test_zero_metrics(self):
        result = verify_littles_law(
            virtual_users=10,
            avg_latency_sec=0.1,
            throughput_rps=0.0,
        )

        assert result["valid"] is False
        assert result["reason"] == "zero_metrics"


class TestCrossValidateMetrics:
    def test_valid_metrics_have_no_warnings(self):
        warnings = cross_validate_metrics({
            "successful": 10,
            "failed": 2,
            "iterations": 4,
            "virtual_users": 3,
            "error_rate": 16.6666667,
            "avg_time_ms": 20.0,
            "min_time_ms": 10.0,
            "max_time_ms": 40.0,
            "p50_time_ms": 18.0,
            "p95_time_ms": 30.0,
            "p99_time_ms": 35.0,
            "std_dev_ms": 5.0,
            "throughput": 50.0,
            "tps": 50.0,
        })

        assert warnings == []

    def test_warns_on_percentile_order_violation(self):
        warnings = cross_validate_metrics({
            "successful": 10,
            "failed": 0,
            "iterations": 10,
            "virtual_users": 1,
            "avg_time_ms": 20.0,
            "min_time_ms": 10.0,
            "max_time_ms": 40.0,
            "p50_time_ms": 35.0,
            "p95_time_ms": 30.0,
            "p99_time_ms": 38.0,
        })

        assert any("монотонного порядка" in warning for warning in warnings)

    def test_warns_on_total_mismatch(self):
        warnings = cross_validate_metrics({
            "successful": 9,
            "failed": 1,
            "iterations": 4,
            "virtual_users": 3,
            "error_rate": 10.0,
        })

        assert any("Количество результатов не совпадает" in warning for warning in warnings)

    def test_warns_on_negative_std(self):
        warnings = cross_validate_metrics({
            "successful": 5,
            "failed": 0,
            "iterations": 5,
            "virtual_users": 1,
            "std_dev_ms": -1.0,
            "throughput": 10.0,
            "tps": 10.0,
        })

        assert "std_dev_ms не может быть отрицательным" in warnings
