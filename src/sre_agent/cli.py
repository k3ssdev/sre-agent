"""Command-line interface."""

import argparse

from .agent import SREAgent
from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitorización SRE con Ollama")
    parser.add_argument("--daily-report", action="store_true", help="Envía el reporte diario")
    args = parser.parse_args()
    agent = SREAgent(Settings())
    if args.daily_report:
        agent.daily_report()
    else:
        agent.run()
