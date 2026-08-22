"""CSV persistence for resource samples."""

from __future__ import annotations

import csv
import time
from pathlib import Path
from statistics import mean
from typing import Any

HISTORY_HEADERS = ["timestamp", "cpu_percent", "cpu_temp", "ram_percent", "gpu_temp"]


class HistoryRepository:
    def __init__(self, history_file: Path) -> None:
        self.history_file = history_file

    def record(self, resources: dict[str, Any]) -> None:
        gpu_temp = resources.get("gpu", {}).get("temp_c", 0.0)
        if not isinstance(gpu_temp, (int, float)):
            gpu_temp = 0.0
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a", newline="") as file:
            writer = csv.writer(file)
            if self.history_file.stat().st_size == 0:
                writer.writerow(HISTORY_HEADERS)
            writer.writerow([int(time.time()), resources.get("cpu_load_percent", 0.0), resources.get("cpu_temp_c", 0.0), resources.get("ram_used_percent", 0.0), gpu_temp])

    def get_last_24_hours(self) -> dict[str, Any] | None:
        if not self.history_file.exists():
            return None
        cutoff = int(time.time()) - 24 * 3600
        rows: list[dict[str, float]] = []
        with self.history_file.open(newline="") as file:
            for row in csv.DictReader(file):
                try:
                    timestamp = int(row["timestamp"])
                    if timestamp >= cutoff:
                        rows.append({"timestamp": timestamp, "cpu_load": float(row["cpu_percent"]), "cpu_temp": float(row["cpu_temp"]), "ram_load": float(row["ram_percent"]), "gpu_temp": float(row["gpu_temp"])})
                except (KeyError, TypeError, ValueError):
                    continue
        self._rewrite(rows)
        if not rows:
            return None
        return {"samples": len(rows), **{key: self._stats(rows, key) for key in ("cpu_load", "cpu_temp", "ram_load", "gpu_temp")}}

    def _rewrite(self, rows: list[dict[str, float]]) -> None:
        with self.history_file.open("w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(HISTORY_HEADERS)
            for row in rows:
                writer.writerow([row["timestamp"], row["cpu_load"], row["cpu_temp"], row["ram_load"], row["gpu_temp"]])

    @staticmethod
    def _stats(rows: list[dict[str, float]], key: str) -> tuple[float, float, float]:
        values = [row[key] for row in rows]
        return min(values), max(values), mean(values)
