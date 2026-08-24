"""Telegram command polling service."""

from __future__ import annotations

import re
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
    "/wake": "Despertar el servidor (Wake-on-LAN)",
    "/sre": "Investigar incidente profundo con IA",
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

    @staticmethod
    def format_markdown_v2(text: str) -> str:
        escape_chars = r"\\_*\[\]()~`>#+\-=|{}.!"

        def escape(value: str) -> str:
            return re.sub(f"([{escape_chars}])", r"\\\1", value)

        def format_inline(value: str) -> str:
            replacements: dict[str, str] = {}

            def keep(value_to_keep: str) -> str:
                token = f"TGFORMAT{len(replacements)}TOKEN"
                replacements[token] = value_to_keep
                return token

            value = re.sub(
                r"`([^`\n]+)`",
                lambda match: keep("`" + match.group(1).replace("\\", "\\\\").replace("`", "\\`") + "`"),
                value,
            )
            value = re.sub(
                r"\[([^\]\n]+)\]\(([^)\n]+)\)",
                lambda match: keep(f"[{escape(match.group(1))}]({match.group(2).replace('\\', '\\\\').replace(')', '\\)')})"),
                value,
            )
            value = re.sub(r"\*\*([^*\n]+)\*\*", lambda match: keep(f"*{escape(match.group(1))}*"), value)
            value = re.sub(r"__([^_\n]+)__", lambda match: keep(f"_{escape(match.group(1))}_"), value)
            formatted = escape(value)
            for token, replacement in replacements.items():
                formatted = formatted.replace(token, replacement)
            return formatted

        lines: list[str] = []
        for line in text.splitlines():
            heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
            bullet = re.match(r"^\s*[-+*]\s+(.+)$", line)
            numbered = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
            if heading:
                lines.append(f"*{format_inline(heading.group(1))}*")
            elif bullet:
                lines.append(f"• {format_inline(bullet.group(1))}")
            elif numbered:
                lines.append(f"{numbered.group(1)}\\. {format_inline(numbered.group(2))}")
            else:
                lines.append(format_inline(line))
        return "\n".join(lines).strip()

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

        full_text = message.get("text", "").strip()
        if not full_text:
            return

        response, parse_mode = self._build_command_response(full_text)
        self.notifier.send_to_chat(chat_id, response, parse_mode=parse_mode)

    def _build_command_response(self, full_text: str) -> tuple[str, str]:
        command_word = full_text.split()[0].lower()
        if command_word == "/help":
            return self._help_response(), "Markdown"

        response = self.agent.command(full_text)
        if command_word == "/sre":
            return self.format_markdown_v2(response), "MarkdownV2"
        return response, "Markdown"

    @staticmethod
    def _help_response() -> str:
        return (
            f"🤖 *COMANDOS SRE - {get_hostname()}*\n━━━━━━━━━━━━━━━━━━━━\n"
            + "\n".join(f"`{command}` - {description}" for command, description in COMMANDS.items())
        )
