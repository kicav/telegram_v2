from __future__ import annotations

from collections import defaultdict, deque
from threading import RLock


class PerformanceMonitor:
    """Small in-memory diagnostics collector; never participates in the hot-path DB work."""

    def __init__(self, sample_limit: int = 500) -> None:
        self._samples: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=sample_limit)
        )
        self._gauges: dict[str, float] = {}
        self._lock = RLock()

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._samples[name].append(float(value))

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            result = dict(self._gauges)
            for name, values in self._samples.items():
                if values:
                    result[f"{name}_avg"] = sum(values) / len(values)
                    result[f"{name}_max"] = max(values)
            return result
