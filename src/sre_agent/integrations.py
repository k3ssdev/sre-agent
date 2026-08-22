"""External service clients."""

from __future__ import annotations

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


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send(self, text: str) -> None:
        if not self.settings.telegram_token or not self.settings.telegram_chat_id:
            print("Telegram no configurado. Mensaje:\n", text)
            return
        url = f"https://api.telegram.org/bot{self.settings.telegram_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": self.settings.telegram_chat_id, "text": text, "parse_mode": "Markdown"}, timeout=30).raise_for_status()
        except requests.RequestException as error:
            print(f"Error enviando mensaje a Telegram: {error}")
