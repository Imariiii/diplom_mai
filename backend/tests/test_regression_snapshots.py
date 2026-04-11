"""
Regression-тесты: фиксированный вход -> проверка структуры ComparisonResult.
Проверяют, что ключевые поля результата не меняются при рефакторинге.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import numpy as np
import pytest

from backend.comparison.service import ComparisonService


def _make_test_data(test_id, name, db_keys, virtual_users=4, iterations=100, created_at=None):
    results = []
    for dk in db_keys:
        results.append({
            "db_type": "postgresql",
            "query_id": "q1",
            "metrics": {
                "connection_key": dk,
                "avg_response_time_ms": 45.0,
                "throughput": 120.0,
                "total_queries": iterations * virtual_users,
                "error_count": 0,
                "total_time_seconds": 60.0,
            },
        })
    return {
        "id": test_id,
        "name": name,
        "status": "completed",
        "config": {
            "virtual_users": virtual_users,
            "iterations": iterations,
            "scenario": "mixed_light",
            "scenario_template_id": None,
            "db_types": [],
            "warmup_time": 0,
        },
        "results": results,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "logical_database_id": None,
    }


def _make_samples(db_key, seed=42):
    rng = np.random.RandomState(seed)
    samples = []
    for _ in range(100):
        samples.append({
            "sample_type": "request_latency",
            "connection_key": db_key,
            "latency_ms": float(rng.normal(45.0, 8.0)),
        })
    for _ in range(20):
        samples.append({
            "sample_type": "throughput_window",
            "connection_key": db_key,
            "throughput": float(rng.normal(120.0, 15.0)),
        })
    return samples


class TestRegressionStructure:
    """Проверяют стабильность структуры ComparisonResult."""

    @pytest.mark.asyncio
    async def test_result_has_all_required_fields(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "MySQL", ["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", ["conn_pg"]),
        }
        sm = {
            str(id1): _make_samples("conn_mysql", seed=42),
            str(id2): _make_samples("conn_pg", seed=99),
        }
        repo = AsyncMock()
        repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: td.get(tid))
        repo.get_metric_samples = AsyncMock(side_effect=lambda tid: sm.get(tid, []))
        repo.get_time_series = AsyncMock(return_value=[])

        svc = ComparisonService(repository=repo)
        result = await svc.analyze([id1, id2])

        # Сериализуем в JSON и проверяем ключевые поля
        data = json.loads(result.model_dump_json())

        assert "tests" in data
        assert "baseline_id" in data
        assert "comparison_type" in data
        assert "warnings" in data
        assert "descriptive_stats" in data
        assert "pairwise_comparisons" in data
        assert "charts_data" in data
        assert "analysis_report" in data
        assert "db_key_labels" in data
        assert "parameter_impacts" in data
        assert "normalized_metrics" in data

    @pytest.mark.asyncio
    async def test_descriptive_stats_structure(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", ["conn_pg"], created_at="2025-01-01T00:00:00Z"),
            str(id2): _make_test_data(id2, "B", ["conn_pg"], created_at="2025-02-01T00:00:00Z"),
        }
        sm = {
            str(id1): _make_samples("conn_pg", seed=10),
            str(id2): _make_samples("conn_pg", seed=20),
        }
        repo = AsyncMock()
        repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: td.get(tid))
        repo.get_metric_samples = AsyncMock(side_effect=lambda tid: sm.get(tid, []))
        repo.get_time_series = AsyncMock(return_value=[])

        svc = ComparisonService(repository=repo)
        result = await svc.analyze([id1, id2])

        data = json.loads(result.model_dump_json())
        for test_id_str, db_map in data["descriptive_stats"].items():
            for db_key, bundle in db_map.items():
                if bundle.get("latency_ms"):
                    lat = bundle["latency_ms"]
                    for field in ["count", "mean", "median", "std", "min", "max", "p50", "p95", "p99"]:
                        assert field in lat, f"Missing {field} in latency_ms"

    @pytest.mark.asyncio
    async def test_pairwise_comparison_structure(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "A", ["conn_mysql"]),
            str(id2): _make_test_data(id2, "B", ["conn_pg"]),
        }
        sm = {
            str(id1): _make_samples("conn_mysql"),
            str(id2): _make_samples("conn_pg", seed=99),
        }
        repo = AsyncMock()
        repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: td.get(tid))
        repo.get_metric_samples = AsyncMock(side_effect=lambda tid: sm.get(tid, []))
        repo.get_time_series = AsyncMock(return_value=[])

        svc = ComparisonService(repository=repo)
        result = await svc.analyze([id1, id2])

        data = json.loads(result.model_dump_json())
        for pc in data["pairwise_comparisons"]:
            assert "baseline_test_id" in pc
            assert "compared_test_id" in pc
            assert "db_key" in pc
            assert "metric" in pc
            assert "interpretation" in pc

    @pytest.mark.asyncio
    async def test_analysis_report_sections(self):
        id1, id2 = uuid.uuid4(), uuid.uuid4()
        td = {
            str(id1): _make_test_data(id1, "MySQL", ["conn_mysql"]),
            str(id2): _make_test_data(id2, "PG", ["conn_pg"]),
        }
        sm = {
            str(id1): _make_samples("conn_mysql"),
            str(id2): _make_samples("conn_pg", seed=99),
        }
        repo = AsyncMock()
        repo.get_test_run_with_results = AsyncMock(side_effect=lambda tid: td.get(tid))
        repo.get_metric_samples = AsyncMock(side_effect=lambda tid: sm.get(tid, []))
        repo.get_time_series = AsyncMock(return_value=[])

        svc = ComparisonService(repository=repo)
        result = await svc.analyze([id1, id2])

        data = json.loads(result.model_dump_json())
        report = data["analysis_report"]
        assert "verdict" in report
        assert "sections" in report
        assert len(report["sections"]) > 0
        for section in report["sections"]:
            assert "title" in section
            assert "items" in section
