"""Safe, read-only system tools used by the SRE investigation command."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psutil


def obtener_telemetria_sistema() -> dict[str, Any]:
    """Return a compact snapshot of host resources."""
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.getenv("SRE_HOST_ROOT", "/"))
    temperature = "No disponible"
    try:
        for entries in psutil.sensors_temperatures().values():
            for entry in entries:
                if entry.current is not None:
                    temperature = f"{entry.current:.1f}°C"
                    break
            if temperature != "No disponible":
                break
    except (AttributeError, OSError):
        pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "cpu_temperature": temperature,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / 1024**3, 2),
        "memory_total_gb": round(memory.total / 1024**3, 2),
        "disk_root_percent": disk.percent,
        "disk_root_free_gb": round(disk.free / 1024**3, 2),
    }


def auditar_red_sockets() -> list[dict[str, Any]]:
    """Return listening TCP/UDP sockets without invoking a shell command."""
    sockets: list[dict[str, Any]] = []
    try:
        connections = psutil.net_connections(kind="inet")
    except (OSError, psutil.AccessDenied):
        return sockets
    for connection in connections:
        if connection.status not in {psutil.CONN_LISTEN, "NONE"}:
            continue
        sockets.append(
            {
                "type": "tcp" if connection.type == 1 else "udp",
                "local_address": f"{connection.laddr.ip}:{connection.laddr.port}" if connection.laddr else "unknown",
                "pid": connection.pid,
            }
        )
    return sorted(sockets, key=lambda item: (item["type"], item["local_address"]))


def buscar_archivo(nombre: str, directorio: str = "/home", max_results: int = 20) -> list[str]:
    """Find an exact filename below approved, bounded directories."""
    root = Path(directorio).expanduser().resolve()
    allowed_roots = (Path("/home"), Path("/tmp"), Path("/var/log"))
    if not any(root == allowed or allowed in root.parents for allowed in allowed_roots):
        return []
    matches: list[str] = []
    for current_root, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = [directory for directory in directories if not (Path(current_root) / directory).is_symlink()]
        if nombre in filenames:
            matches.append(str(Path(current_root) / nombre))
            if len(matches) >= max_results:
                break
    return matches
