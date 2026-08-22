"""Alert rules."""

from typing import Any


class AlertEvaluator:
    def __init__(self, thresholds: dict[str, float]) -> None:
        self.thresholds = thresholds

    def evaluate(self, telemetry: dict[str, Any]) -> list[str]:
        resources = telemetry["resources"]
        alerts = []
        if resources["cpu_temp_c"] > self.thresholds["cpu_temp"]:
            alerts.append(f"Temperatura CPU alta: {resources['cpu_temp_c']}°C")
        gpu_temp = resources.get("gpu", {}).get("temp_c")
        if isinstance(gpu_temp, (int, float)) and gpu_temp > self.thresholds["gpu_temp"]:
            alerts.append(f"Temperatura GPU alta: {gpu_temp}°C")
        for name, percent in telemetry["disks"].items():
            if percent > self.thresholds["disk_percent"]:
                alerts.append(f"Disco {name} superó el 90%: {percent}%")
        for name, container in telemetry["containers"].items():
            if not container["running"]:
                alerts.append(f"Contenedor detenido: {name}")
        for name, info in telemetry["smart_health"].items():
            if not isinstance(info, dict):
                continue
            if not info.get("health_passed", True):
                alerts.append(f"¡FALLO DE HARDWARE SMART en {info.get('device', name)}!")
            if info.get("reallocated_sectors", 0) > 0:
                alerts.append(f"Sectores reasignados detectados en {name}: {info['reallocated_sectors']}")
        return alerts
