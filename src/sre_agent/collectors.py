"""Infrastructure telemetry collectors."""

from __future__ import annotations

import json
import os
import platform
import subprocess
from typing import Any

import docker
import psutil


class InfrastructureCollector:
    def collect_resources(self) -> dict[str, Any]:
        ram = psutil.virtual_memory()
        return {"cpu_load_percent": psutil.cpu_percent(interval=1), "cpu_temp_c": self._cpu_temperature(), "ram_used_percent": ram.percent, "ram_used_gb": round(ram.used / 1024**3, 2), "gpu": self._gpu_info()}

    @staticmethod
    def _cpu_temperature() -> float:
        temperatures = psutil.sensors_temperatures()
        for sensor in ("coretemp", "k10temp"):
            if sensor in temperatures:
                return max(entry.current for entry in temperatures[sensor])
        return 0.0

    @staticmethod
    def _gpu_info() -> dict[str, Any]:
        try:
            result = subprocess.check_output(["nvidia-smi", "--query-gpu=temperature.gpu,memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"], text=True)
            temp, memory_used, memory_total, utilization = (float(value.strip()) for value in result.strip().split(","))
            return {"temp_c": temp, "vram_used_mb": memory_used, "vram_total_mb": memory_total, "util_percent": utilization}
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            return {"error": str(error)}

    @staticmethod
    def collect_disks() -> dict[str, float]:
        disks = {"root": psutil.disk_usage("/").percent}
        for name, path in (("hdd8tb", "/mnt/hdd8tb"), ("hdd1tb", "/mnt/hdd1tb")):
            if os.path.exists(path):
                disks[name] = psutil.disk_usage(path).percent
        return disks

    @staticmethod
    def collect_containers() -> dict[str, dict[str, Any]]:
        try:
            client = docker.from_env()
            return {container.name: {"status": container.status, "image": container.image.tags[0] if container.image.tags else "unknown", "running": container.status == "running"} for container in client.containers.list(all=True)}
        except docker.errors.DockerException as error:
            print(f"Docker no disponible; se omite la comprobación de contenedores: {error}")
            return {}

    def collect_system_info(self) -> dict[str, Any]:
        memory = psutil.virtual_memory()
        cpu_frequency = psutil.cpu_freq()
        return {
            "system": {
                "os": platform.platform(),
                "kernel": platform.release(),
                "architecture": platform.machine(),
                "processor": platform.processor() or "unknown",
            },
            "cpu": {
                "physical_cores": psutil.cpu_count(logical=False) or 0,
                "logical_cores": psutil.cpu_count(logical=True) or 0,
                "frequency_mhz": round(cpu_frequency.max if cpu_frequency else 0),
            },
            "memory": {"total_gb": round(memory.total / 1024**3, 2)},
            "gpu": self._gpu_hardware_info(),
            "disks": self.collect_disks(),
            "docker_containers": len(self.collect_containers()),
        }

    @staticmethod
    def _gpu_hardware_info() -> dict[str, Any]:
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            name, driver, memory_total = (value.strip() for value in output.split(",", 2))
            return {"name": name, "driver": driver, "memory_total_mb": float(memory_total)}
        except (OSError, subprocess.CalledProcessError, ValueError) as error:
            return {"status": "unavailable", "error": str(error)}

    @staticmethod
    def collect_updates() -> dict[str, int]:
        try:
            output = subprocess.check_output(["apt-get", "-s", "upgrade"], stderr=subprocess.DEVNULL, text=True)
            return {"pending_updates": output.count("Inst ")}
        except (OSError, subprocess.CalledProcessError):
            return {"pending_updates": 0}

    @staticmethod
    def collect_smart() -> dict[str, dict[str, Any]]:
        try:
            output = subprocess.check_output(["lsblk", "-d", "-n", "-o", "NAME,TYPE"], stderr=subprocess.DEVNULL, text=True)
        except (OSError, subprocess.CalledProcessError) as error:
            return {"error": {"error": f"No se pudieron listar los discos: {error}"}}
        disks = [fields[0] for line in output.splitlines() if len(fields := line.split()) >= 2 and fields[1] == "disk" and not fields[0].startswith(("zram", "loop", "ram"))]
        report: dict[str, dict[str, Any]] = {}
        for disk in disks:
            device = f"/dev/{disk}"
            try:
                smart_output = subprocess.check_output(["sudo", "smartctl", "-H", "-A", "-j", device], stderr=subprocess.DEVNULL, text=True)
                data = json.loads(smart_output)
                reallocated = next((attribute.get("raw", {}).get("value", 0) for attribute in data.get("ata_smart_attributes", {}).get("table", []) if attribute.get("name") == "Reallocated_Sector_Ct"), 0)
                report[disk] = {"device": device, "health_passed": data.get("smart_status", {}).get("passed", True), "temperature_c": data.get("temperature", {}).get("current"), "reallocated_sectors": reallocated}
            except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
                report[disk] = {"device": device, "error": f"Error leyendo SMART: {error}"}
        return report

    def collect_telemetry(self, stats: dict[str, Any] | None = None) -> dict[str, Any]:
        telemetry = {"resources": self.collect_resources(), "disks": self.collect_disks(), "smart_health": self.collect_smart(), "containers": self.collect_containers(), "updates": self.collect_updates()}
        if stats is not None:
            telemetry["stats_24h"] = stats
        return telemetry
