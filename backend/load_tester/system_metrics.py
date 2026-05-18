"""
Вспомогательный модуль: снимки psutil и расчёт rate-метрик за интервал.
"""
from typing import Any, Dict, Optional

import psutil


class SystemMetricsSampler:
    """Хранит предыдущий снимок счётчиков и считает rate за интервал."""

    def __init__(self) -> None:
        self._prev: Optional[Dict[str, float]] = None
        psutil.cpu_percent(interval=None)

    def sample(self, interval_sec: float) -> Dict[str, Any]:
        """
        Вернуть instant-метрики и rate за interval_sec.

        Поля cumulative (legacy): disk_iops, network_in_mbps, network_out_mbps,
        disk_read_mbps, disk_write_mbps.
        Поля rate (additive): disk_ops_per_sec, disk_read_mib_per_sec,
        disk_write_mib_per_sec, network_in_mib_per_sec, network_out_mib_per_sec.
        """
        cpu_usage = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        network_io = psutil.net_io_counters()

        disk_read_bytes = float(disk_io.read_bytes) if disk_io else 0.0
        disk_write_bytes = float(disk_io.write_bytes) if disk_io else 0.0
        disk_read_count = float(disk_io.read_count) if disk_io else 0.0
        disk_write_count = float(disk_io.write_count) if disk_io else 0.0
        net_in_bytes = float(network_io.bytes_recv) if network_io else 0.0
        net_out_bytes = float(network_io.bytes_sent) if network_io else 0.0

        current = {
            "disk_read_bytes": disk_read_bytes,
            "disk_write_bytes": disk_write_bytes,
            "disk_ops": disk_read_count + disk_write_count,
            "net_in_bytes": net_in_bytes,
            "net_out_bytes": net_out_bytes,
        }

        rates = self._compute_rates(current, interval_sec)
        self._prev = current

        mib = 1024 * 1024
        return {
            "cpu_usage": cpu_usage,
            "memory_usage_mb": memory.used / mib,
            "memory_usage_percent": memory.percent,
            "disk_iops": current["disk_ops"],
            "disk_read_mbps": disk_read_bytes / mib,
            "disk_write_mbps": disk_write_bytes / mib,
            "network_in_mbps": net_in_bytes / mib,
            "network_out_mbps": net_out_bytes / mib,
            "disk_ops_per_sec": rates["disk_ops_per_sec"],
            "disk_read_mib_per_sec": rates["disk_read_mib_per_sec"],
            "disk_write_mib_per_sec": rates["disk_write_mib_per_sec"],
            "network_in_mib_per_sec": rates["network_in_mib_per_sec"],
            "network_out_mib_per_sec": rates["network_out_mib_per_sec"],
        }

    def _compute_rates(self, current: Dict[str, float], interval_sec: float) -> Dict[str, float]:
        mib = 1024 * 1024
        zero = {
            "disk_ops_per_sec": 0.0,
            "disk_read_mib_per_sec": 0.0,
            "disk_write_mib_per_sec": 0.0,
            "network_in_mib_per_sec": 0.0,
            "network_out_mib_per_sec": 0.0,
        }
        if interval_sec <= 0 or self._prev is None:
            return zero

        prev = self._prev
        return {
            "disk_ops_per_sec": max(0.0, (current["disk_ops"] - prev["disk_ops"]) / interval_sec),
            "disk_read_mib_per_sec": max(
                0.0, (current["disk_read_bytes"] - prev["disk_read_bytes"]) / mib / interval_sec
            ),
            "disk_write_mib_per_sec": max(
                0.0, (current["disk_write_bytes"] - prev["disk_write_bytes"]) / mib / interval_sec
            ),
            "network_in_mib_per_sec": max(
                0.0, (current["net_in_bytes"] - prev["net_in_bytes"]) / mib / interval_sec
            ),
            "network_out_mib_per_sec": max(
                0.0, (current["net_out_bytes"] - prev["net_out_bytes"]) / mib / interval_sec
            ),
        }

    def reset(self) -> None:
        """Сброс baseline (начало измеряемой фазы)."""
        self._prev = None
        psutil.cpu_percent(interval=None)
