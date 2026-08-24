"""External service clients."""

from __future__ import annotations

from typing import Any

import requests

from .config import Settings


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def ask(self, prompt: str, fallback: str) -> str:
        concise_prompt = (
            "Responde de forma directa y suficientemente detallada. Contesta solo lo que se pregunta, "
            "sin saludos, introducciones, contexto repetido, conclusiones genéricas "
            "ni texto de relleno. Prioriza datos, causa, impacto y acción.\n\n"
            + prompt
        )
        payload = {
            "model": self.settings.model_name,
            "prompt": concise_prompt,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 500},
        }
        try:
            response = requests.post(self.settings.ollama_url, json=payload, timeout=60)
            return response.json().get("response", fallback)
        except (requests.RequestException, ValueError, KeyError):
            return fallback


class InvestigationClient:
    def __init__(self, settings: Settings) -> None:
        self.ollama = OllamaClient(settings)

    def investigate(
        self,
        alert_reasons: list[str],
        telemetry: dict[str, Any],
        prompt: str,
        fallback: str,
    ) -> str:
        del alert_reasons, telemetry
        return self.ollama.ask(prompt, fallback)

    def ask(self, prompt: str, fallback: str) -> str:
        return self.ollama.ask(prompt, fallback)

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
