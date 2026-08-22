"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        os.environ.setdefault(key.removeprefix("export ").strip(), value.strip().strip("\"'"))


load_env_file(Path(__file__).resolve().parents[2] / ".env")


@dataclass(frozen=True)
class Settings:
    sre_provider: str = field(default_factory=lambda: os.getenv("SRE_PROVIDER", "ollama").strip().lower())
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"))
    model_name: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"))
    opensre_command: str = field(default_factory=lambda: os.path.expanduser(os.path.expandvars(os.getenv("OPENSRE_COMMAND", "$HOME/.local/bin/opensre"))))
    opensre_timeout: int = field(default_factory=lambda: int(os.getenv("OPENSRE_TIMEOUT", "120")))
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))
    history_file: Path = field(default_factory=lambda: Path(os.path.expanduser(os.path.expandvars(os.getenv("SRE_HISTORY_FILE", "$HOME/.config/server_metrics_history.csv")))))
    thresholds: dict[str, float] = field(default_factory=lambda: {"cpu_temp": 80.0, "gpu_temp": 82.0, "disk_percent": 90.0})
