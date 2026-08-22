"""Telegram command polling service."""

from __future__ import annotations

import time
from typing import Any

import requests

from .agent import SREAgent
from .config import Settings
from .integrations import TelegramNotifier
from .reporting import get_hostname


COMMANDS = {
    "/status": "Estado general del servidor",
    "/report": "Reporte diario",
    "/cpu": "CPU, temperatura y RAM",
    "/gpu": "Temperatura y uso de GPU",
    "/disks": "Uso de discos",
    "/docker": "Estado de contenedores",
    "/info": "Características del sistema y hardware",
    "/help": "Lista de comandos",
}


class TelegramBot:
    def __init__(self, settings: Settings, agent: SREAgent) -> None:
        self.settings = settings
        self.agent = agent
        self.notifier = TelegramNotifier(settings)
        self.offset = 0

    def run_forever(self) -> None:
        if not self.settings.telegram_token or not self.settings.telegram_chat_id:
            raise RuntimeError("TELEGRAM_TOKEN y TELEGRAM_CHAT_ID son obligatorios para el bot")
        print("Bot de Telegram iniciado")
        while True:
            try:
                updates = self._get_updates()
                for update in updates:
                    self._handle_update(update)
            except requests.RequestException as error:
                print(f"Error consultando Telegram: {error}")
                time.sleep(5)

    def _get_updates(self) -> list[dict[str, Any]]:
        url = f"https://api.telegram.org/bot{self.settings.telegram_token}/getUpdates"
        response = requests.get(url, params={"offset": self.offset, "timeout": 25}, timeout=35)
        response.raise_for_status()
        return response.json().get("result", [])

    def _handle_update(self, update: dict[str, Any]) -> None:
        self.offset = update["update_id"] + 1
        message = update.get("message", {})
        chat_id = str(message.get("chat", {}).get("id", ""))
        if chat_id != self.settings.telegram_chat_id:
            return
        text = message.get("text", "").split()[0].lower() if message.get("text") else ""
        if not text:
            return
        if text == "/help":
            response = f"🤖 COMANDOS SRE - {get_hostname()}\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"{command} - {description}" for command, description in COMMANDS.items())
        else:
            response = self.agent.command(text)
        self.notifier.send_to_chat(chat_id, response, parse_mode="Markdown" if text == "/info" else None)
