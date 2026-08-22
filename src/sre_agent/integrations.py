"""External service clients."""

from __future__ import annotations

import json
import subprocess
import tempfile

import requests

from .config import Settings


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ask(self, prompt: str, fallback: str) -> str:
        payload = {"model": self.settings.model_name, "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}
        try:
            response = requests.post(self.settings.ollama_url, json=payload, timeout=60)
            return response.json().get("response", fallback)
        except (requests.RequestException, ValueError, KeyError):
            return fallback


class InvestigationClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.ollama = OllamaClient(settings)

    def investigate(self, alert_reasons: list[str], telemetry: dict, prompt: str, fallback: str) -> str:
        if self.settings.sre_provider == "opensre":
            return self._investigate_with_opensre(alert_reasons, telemetry, fallback)
        return self.ollama.ask(prompt, fallback)

    def ask(self, prompt: str, fallback: str) -> str:
        return self.ollama.ask(prompt, fallback)

    def _investigate_with_opensre(self, alert_reasons: list[str], telemetry: dict, fallback: str) -> str:
        alert_payload = {
            "status": "firing",
            "labels": {
                "alertname": "AnomaliaServidor",
                "host": "servidor-b150m",
                "severity": "critical",
            },
            "annotations": {
                "description": " | ".join(alert_reasons),
                "telemetry": json.dumps(telemetry, ensure_ascii=False),
            },
        }
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8") as alert_file:
                json.dump(alert_payload, alert_file, ensure_ascii=False)
                alert_file.flush()
                result = subprocess.run(
                    [self.settings.opensre_command, "investigate", "-i", alert_file.name],
                    capture_output=True,
                    text=True,
                    timeout=self.settings.opensre_timeout,
                    check=False,
                )
            if result.returncode != 0:
                return f"Error al ejecutar OpenSRE: {result.stderr.strip() or result.returncode}"
            return result.stdout.strip() or fallback
        except (OSError, subprocess.TimeoutExpired) as error:
            return f"Error al ejecutar OpenSRE: {error}"


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, text: str, parse_mode: str | None = "Markdown") -> None:
        self.send_to_chat(self.settings.telegram_chat_id, text, parse_mode)

    def send_to_chat(self, chat_id: str, text: str, parse_mode: str | None = None) -> None:
        if not self.settings.telegram_token or not self.settings.telegram_chat_id:
            print("Telegram no configurado. Mensaje:\n", text)
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_token}/sendMessage"
        try:
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            requests.post(url, json=payload, timeout=30).raise_for_status()
        except requests.RequestException as error:
            print(f"Error enviando mensaje a Telegram: {error}")
