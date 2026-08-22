#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SRE_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/sre-agent"
ENVIRONMENT_FILE="$SRE_CONFIG_DIR/environment"

usage() {
    printf 'Uso: %s [--test-bot]\n' "$(basename "$0")"
}

test_bot() {
    systemctl --user is-active --quiet ollama-telegram-bot.service || {
        printf 'El servicio del bot no está activo.\n' >&2
        systemctl --user --no-pager --full status ollama-telegram-bot.service || true
        return 1
    }

    PYTHONPATH="$PROJECT_DIR/src" /usr/bin/python3 - <<'PY'
from sre_agent.config import Settings
import requests

settings = Settings()
if not settings.telegram_token or not settings.telegram_chat_id:
    raise SystemExit("TELEGRAM_TOKEN y TELEGRAM_CHAT_ID no están configurados")

response = requests.get(
    f"https://api.telegram.org/bot{settings.telegram_token}/getMe",
    timeout=15,
)
response.raise_for_status()
data = response.json()
if not data.get("ok"):
    raise SystemExit("Telegram rechazó el token configurado")
print(f"Telegram OK: @{data['result'].get('username', 'sin_username')}")
print(f"Servicio OK: ollama-telegram-bot.service activo; envía /status al bot para probar comandos")
PY
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    exit 0
fi
if [[ "${1:-}" != "" && "${1:-}" != "--test-bot" ]]; then
    usage >&2
    exit 2
fi

command -v systemctl >/dev/null || { printf 'systemctl no está disponible.\n' >&2; exit 1; }
if ! PYTHONPATH="$PROJECT_DIR/src" /usr/bin/python3 -c 'import docker, psutil, requests' 2>/dev/null; then
    printf 'Faltan dependencias para /usr/bin/python3. Instala: sudo apt install -y python3-docker python3-psutil python3-requests\n' >&2
    exit 1
fi
mkdir -p "$SYSTEMD_DIR" "$SRE_CONFIG_DIR"
install -m 0644 "$PROJECT_DIR"/systemd/*.service "$PROJECT_DIR"/systemd/*.timer "$SYSTEMD_DIR"/
printf 'SRE_AGENT_DIR=%s\n' "$PROJECT_DIR" > "$ENVIRONMENT_FILE"

systemctl --user daemon-reload
systemctl --user enable --now ollama-telegram-bot.service
systemctl --user enable --now ollama-agent.timer
systemctl --user enable --now ollama-daily-report.timer
printf 'Servicios instalados en %s\n' "$SYSTEMD_DIR"

if [[ "${1:-}" == "--test-bot" ]]; then
    test_bot
else
    printf 'Instalación OK. Ejecuta %s --test-bot y envía /status al bot.\n' "$(basename "$0")"
fi