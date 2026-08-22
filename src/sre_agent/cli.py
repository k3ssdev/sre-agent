"""Command-line interface."""

import argparse

from .agent import SREAgent
from .bot import TelegramBot
from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitorización SRE con Ollama")
    parser.add_argument("--daily-report", action="store_true", help="Envía el reporte diario")
    parser.add_argument("--telegram-bot", action="store_true", help="Inicia el bot de comandos Telegram")
    args = parser.parse_args()
    agent = SREAgent(Settings())
    if args.daily_report:
        agent.daily_report()
    elif args.telegram_bot:
        TelegramBot(Settings(), agent).run_forever()
    else:
        agent.run()
