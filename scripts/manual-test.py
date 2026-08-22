#!/usr/bin/env python3
"""Run SRE agent functions manually without starting the Telegram polling loop."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))


def test_config() -> None:
    from sre_agent.config import Settings

    settings = Settings()
    print(f"SRE_PROVIDER: {settings.sre_provider}")
    print(f"OLLAMA_MODEL: {settings.model_name}")
    print(f"OLLAMA_URL: {settings.ollama_url}")
    print(f"OPENSRE_COMMAND: {settings.opensre_command}")
    print(f"Telegram configurado: {'sí' if settings.telegram_token and settings.telegram_chat_id else 'no'}")


def collect_telemetry() -> dict:
    from sre_agent.collectors import InfrastructureCollector

    collector = InfrastructureCollector()
    telemetry = {
        "resources": collector.collect_resources(),
        "disks": collector.collect_disks(),
        "smart_health": collector.collect_smart(),
        "containers": collector.collect_containers(),
        "updates": collector.collect_updates(),
    }
    print(json.dumps(telemetry, indent=2, ensure_ascii=False))
    return telemetry


def test_alerts() -> None:
    from sre_agent.alerts import AlertEvaluator

    telemetry = collect_telemetry()
    alerts = AlertEvaluator({"cpu_temp": 80, "gpu_temp": 82, "disk_percent": 90}).evaluate(telemetry)
    print("Alertas:")
    print("\n".join(f"- {alert}" for alert in alerts) or "Sin alertas")


def test_ollama() -> None:
    from sre_agent.config import Settings
    from sre_agent.integrations import OllamaClient

    response = OllamaClient(Settings()).ask(
        "Responde exactamente: Ollama operativo",
        "Ollama no respondió",
    )
    print(response)


def test_opensre() -> None:
    from sre_agent.config import Settings
    from sre_agent.integrations import InvestigationClient

    settings = replace(Settings(), sre_provider="opensre")
    telemetry = {"manual_test": True}
    response = InvestigationClient(settings).investigate(
        ["Prueba manual de OpenSRE"],
        telemetry,
        "",
        "OpenSRE no respondió",
    )
    print(response)


def test_command(command: str) -> None:
    from sre_agent.agent import SREAgent
    from sre_agent.config import Settings

    print(SREAgent(Settings()).command(command))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pruebas manuales del agente SRE")
    parser.add_argument(
        "function",
        choices=("config", "collect", "alerts", "ollama", "opensre", "command"),
        help="Función que se quiere ejecutar",
    )
    parser.add_argument("--command", default="/status", help="Comando para la prueba command")
    args = parser.parse_args()

    tests = {
        "config": test_config,
        "collect": collect_telemetry,
        "alerts": test_alerts,
        "ollama": test_ollama,
        "opensre": test_opensre,
    }
    if args.function == "command":
        test_command(args.command)
    else:
        tests[args.function]()


if __name__ == "__main__":
    main()
