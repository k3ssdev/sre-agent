"""Pure formatting helpers for Telegram reports."""

import re
from typing import Any


def make_bar(percent: Any, length: int = 8) -> str:
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return "N/A"
    filled = min(max(int(round(value / 100 * length)), 0), length)
    return "■" * filled + "□" * (length - filled)


def get_status_icon(value: Any, warn: float = 75, crit: float = 90) -> str:
    try:
        numeric_value = float(value)
        if numeric_value >= crit:
            return "🔴"
        if numeric_value >= warn:
            return "🟡"
        return "🟢"
    except (TypeError, ValueError):
        return "⚪"


def format_alert_report(alerts: list[str], diagnosis: str) -> str:
    """Build an alert message without Markdown formatting."""
    alert_lines = "\n".join(f"🔴 {alert}" for alert in alerts)
    return (
        "🚨 ALERTA SERVIDOR\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ESTADO\n"
        f"{alert_lines}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "DIAGNÓSTICO OLLAMA\n"
        f"{strip_markdown(diagnosis)}"
    )


def strip_markdown(text: str) -> str:
    """Remove common Markdown markers from model output."""
    return re.sub(r"[`*_#]", "", text).replace("•", "-").strip()
