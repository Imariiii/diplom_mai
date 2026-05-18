"""Тесты расчёта rate-метрик системы."""
import pytest

from backend.load_tester.system_metrics import SystemMetricsSampler


class TestSystemMetricsSampler:
    def test_first_sample_returns_zero_rates(self):
        sampler = SystemMetricsSampler()
        result = sampler.sample(1.0)
        assert result["disk_ops_per_sec"] == 0.0
        assert result["network_in_mib_per_sec"] == 0.0
        assert "cpu_usage" in result

    def test_second_sample_computes_non_negative_rates(self, monkeypatch):
        sampler = SystemMetricsSampler()

        class FakeDisk:
            read_bytes = 0
            write_bytes = 0
            read_count = 100
            write_count = 50

        class FakeNet:
            bytes_recv = 1024 * 1024
            bytes_sent = 512 * 1024

        import backend.load_tester.system_metrics as sm

        monkeypatch.setattr(sm.psutil, "cpu_percent", lambda interval=None: 10.0)
        monkeypatch.setattr(
            sm.psutil,
            "virtual_memory",
            lambda: type("M", (), {"used": 2 * 1024**3, "percent": 40.0})(),
        )
        monkeypatch.setattr(sm.psutil, "disk_io_counters", lambda: FakeDisk())
        monkeypatch.setattr(sm.psutil, "net_io_counters", lambda: FakeNet())

        sampler.sample(1.0)
        FakeDisk.read_count = 200
        FakeDisk.write_count = 100
        FakeNet.bytes_recv = 3 * 1024 * 1024
        FakeNet.bytes_sent = 2 * 1024 * 1024
        result = sampler.sample(1.0)

        assert result["disk_ops_per_sec"] == 150.0
        assert result["network_in_mib_per_sec"] == pytest.approx(2.0, abs=0.01)
        assert result["network_out_mib_per_sec"] == pytest.approx(1.5, abs=0.01)

    def test_reset_clears_baseline(self, monkeypatch):
        sampler = SystemMetricsSampler()
        import backend.load_tester.system_metrics as sm

        monkeypatch.setattr(sm.psutil, "cpu_percent", lambda interval=None: 0.0)
        monkeypatch.setattr(
            sm.psutil,
            "virtual_memory",
            lambda: type("M", (), {"used": 0, "percent": 0.0})(),
        )
        monkeypatch.setattr(sm.psutil, "disk_io_counters", lambda: None)
        monkeypatch.setattr(sm.psutil, "net_io_counters", lambda: None)

        sampler.sample(1.0)
        sampler.reset()
        result = sampler.sample(1.0)
        assert result["disk_ops_per_sec"] == 0.0
