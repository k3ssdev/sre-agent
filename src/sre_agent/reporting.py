"""Pure formatting helpers for Telegram reports."""

import os
import platform
import re
from pathlib import Path
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


def get_hostname() -> str:
    hostname_file = Path(os.getenv("SRE_HOSTNAME_FILE", "/host/etc/hostname"))
    try:
        hostname = hostname_file.read_text(encoding="utf-8").strip()
        if hostname:
            return hostname
    except OSError:
        pass
    return platform.node() or "hostname-desconocido"


def format_alert_report(alerts: list[str], diagnosis: str, hostname: str | None = None) -> str:
    """Build an alert message without Markdown formatting."""
    alert_lines = "\n".join(f"🔴 *Alerta:* `{alert}`" for alert in alerts)
    return (
        f"🚨 *ALERTA SERVIDOR: {hostname or get_hostname()}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*ESTADO*\n"
        f"{alert_lines}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "*DIAGNÓSTICO SRE*\n"
        f"{strip_markdown(diagnosis)}"
    )


def strip_markdown(text: str) -> str:
    """Remove common Markdown markers from model output."""
    return re.sub(r"[`*_#]", "", text).replace("•", "-").strip()
