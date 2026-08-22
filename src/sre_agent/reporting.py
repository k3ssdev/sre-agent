"""Pure formatting helpers for Telegram reports."""

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
