from unittest.mock import Mock

import pytest

from sre_agent.agent import SREAgent
from sre_agent.history import HISTORY_HEADERS, HistoryRepository


@pytest.fixture
def agent() -> SREAgent:
    instance = SREAgent.__new__(SREAgent)
    instance.hostname = "test-host"
    instance.collector = Mock()
    instance.collector.collect_resources.return_value = {
        "cpu_load_percent": 12.5,
        "cpu_temp_c": 48.0,
        "ram_used_percent": 63.25,
        "gpu": {
            "temp_c": 55.0,
            "vram_used_mb": 1024.0,
            "vram_total_mb": 8192.0,
            "util_percent": 20.0,
        },
    }
    return instance


def test_cpu_command_formats_ram_percentage(agent: SREAgent) -> None:
    response = agent.command("/cpu")

    assert "Carga:* `12.5%`" in response
    assert "RAM:* `63.2%`" in response
    assert "]" not in response


def test_gpu_command_reports_gpu_metrics(agent: SREAgent) -> None:
    response = agent.command("/gpu")

    assert "Temperatura:* `55.0°C`" in response
    assert "VRAM:* `1024.0 / 8192.0 MB`" in response
    assert "Uso:* `20.0%`" in response


def test_gpu_command_handles_unavailable_gpu(agent: SREAgent) -> None:
    agent.collector.collect_resources.return_value["gpu"] = {
        "error": "nvidia-smi not found"
    }

    response = agent.command("/gpu")

    assert "Temperatura:* `N/A°C`" in response
    assert "VRAM:* `0 / 0 MB`" in response
    assert "Uso:* `N/A%`" in response


def test_docker_command_lists_running_and_stopped_containers(agent: SREAgent) -> None:
    agent.collector.collect_containers.return_value = {
        "web": {"running": True, "status": "running"},
        "worker": {"running": False, "status": "exited"},
    }

    response = agent.command("/docker")

    assert "*web:* `running`" in response
    assert "*worker:* `exited`" in response
    assert "🟢" in response
    assert "🔴" in response


def test_docker_command_reports_empty_host(agent: SREAgent) -> None:
    agent.collector.collect_containers.return_value = {}

    response = agent.command("/docker")

    assert "Sin contenedores" in response


def test_history_returns_only_samples_from_last_24_hours(tmp_path, monkeypatch) -> None:
    now = 1_000_000
    history_file = tmp_path / "history.csv"
    history_file.write_text(
        ",".join(HISTORY_HEADERS)
        + f"\n{now - 24 * 3600},10,40,50,45"
        + f"\n{now - 24 * 3600 - 1},20,50,60,55"
        + f"\n{now - 60},30,60,70,65\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("sre_agent.history.time.time", lambda: now)

    stats = HistoryRepository(history_file).get_last_24_hours()

    assert stats is not None
    assert stats["samples"] == 2
