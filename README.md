# 🤖 Ollama SRE Agent

Agente autónomo de observabilidad y fiabilidad (SRE) para servidores Linux. Recopila telemetría de hardware, estado de almacenamiento (SMART), Docker y actualizaciones pendientes, integrando un LLM local en **Ollama** (`qwen2.5-coder:7b`) para diagnóstico de anomalías en tiempo real y generación de reportes diarios matutinos vía **Telegram**.

---

## ⚡ Características

- **Monitorización continua (10 min):** Chequeo pasivo de CPU, RAM, GPU (NVIDIA), almacenamiento, Docker y alertas de hardware SMART sin falsos positivos.
- **Diagnóstico Inteligente Local:** Disparo automático de inferencia con Ollama únicamente ante métricas fuera de umbral o incidentes de infraestructura.
- **Reporte Matutino Visual:** Resumen diario con métricas 24h (mínimos, máximos y medias), barras de progreso monoespaciadas y diagnóstico SRE.
- **Persistencia local:** Historial CSV en el directorio del usuario y despliegue mediante `systemd user timers` con soporte para ejecuciones continuas en segundo plano (`loginctl enable-linger`).

---

## 📦 Requisitos y Dependencias

- **OS:** Pop!\_OS / Ubuntu / Debian-based
- **Hardware:** GPU NVIDIA con drivers operativos (`nvidia-smi`)
- **Servicios:** Docker y Ollama en ejecución

### 1. Paquetes del Sistema

```bash
sudo apt update
sudo apt install -y python3 python3-docker python3-psutil python3-requests smartmontools
```

### 2. Dependencias Python

Las dependencias se instalan desde los paquetes del sistema para evitar modificar
el entorno Python gestionado por Debian/Ubuntu. Los paquetes necesarios están
incluidos en el comando de la sección anterior.

Además, deben estar instalados y activos Docker y Ollama. `smartmontools` aporta
`smartctl`; `lsblk` pertenece normalmente a `util-linux`, y `nvidia-smi` requiere
los controladores NVIDIA correspondientes. El agente necesita acceso al socket
de Docker y permisos `sudoers` para ejecutar `smartctl` sin contraseña.

---

## 🛠️ Instalación y Configuración

### 1. Configuración de permisos SMART

Para permitir que el script lea el estado de salud físico de los discos NVMe/SATA sin interactividad de contraseña:

```bash
echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/smartctl" | sudo tee /etc/sudoers.d/smartctl
sudo chmod 0440 /etc/sudoers.d/smartctl

```

### 2. Variables de Configuración

Configura el agente en `.env` a partir de `.env.example`:

```bash
cp .env.example .env
```

Edita `.env` con tus valores:

```dotenv
SRE_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5-coder:7b
OPENSRE_COMMAND=~/.local/bin/opensre
OPENSRE_TIMEOUT=120
TELEGRAM_TOKEN=TU_BOT_TOKEN
TELEGRAM_CHAT_ID=TU_CHAT_ID
SRE_HISTORY_FILE=~/.config/server_metrics_history.csv
```

El fichero `.env` contiene credenciales y no debe versionarse.

`SRE_PROVIDER` controla el análisis de alertas y acepta `ollama` u `opensre`. Con
`opensre`, el agente crea un JSON temporal con la alerta y ejecuta
`OPENSRE_COMMAND investigate -i <archivo>`. Los reportes diarios y los comandos
de Telegram siguen usando Ollama. `OPENSRE_TIMEOUT` está expresado en segundos.

El script está organizado por responsabilidades: `InfrastructureCollector` recopila telemetría, `HistoryRepository` persiste muestras, `AlertEvaluator` aplica umbrales, y `OllamaClient`/`TelegramNotifier` integran servicios externos. `SREAgent` coordina los casos de uso y `main()` solo procesa la CLI.

Las alertas se envían a Telegram como texto plano con formato visual y sin Markdown. El reporte diario conserva su formato Markdown.

El bot de Telegram permite consultar el servidor con estos comandos:

```text
/status        Estado general
/report        Reporte diario
/cpu           CPU, temperatura y RAM
/gpu           Temperatura y uso de GPU
/disks         Uso de discos
/docker        Estado de contenedores
/help          Lista de comandos
```

### 3. Despliegue de Servicios y Timers (`systemd`)

```bash
# Crear directorio de servicios de usuario si no existe
mkdir -p ~/.config/systemd/user

# Copiar archivos systemd
cp systemd/* ~/.config/systemd/user/

# Indicar dónde está clonado el proyecto (puede ser cualquier ruta)
mkdir -p ~/.config/sre-agent
printf 'SRE_AGENT_DIR=%s\n' "$PWD" > ~/.config/sre-agent/environment

# Recargar daemons y habilitar temporizadores
systemctl --user daemon-reload
systemctl --user enable --now ollama-agent.timer
systemctl --user enable --now ollama-daily-report.timer
systemctl --user enable --now ollama-telegram-bot.service

# Habilitar persistencia de procesos tras cerrar sesión
loginctl enable-linger $USER

```

Los servicios leen la ruta del proyecto desde `~/.config/sre-agent/environment`,
por lo que el repositorio puede clonarse en cualquier directorio. El fichero debe
contener, por ejemplo:

```dotenv
SRE_AGENT_DIR=/ruta/donde/esta/clonado/sre-agent
```

Después ejecutan el paquete con `/usr/bin/python3` y `PYTHONPATH` apunta a
`$SRE_AGENT_DIR/src`.

---

## 🔍 Comprobación y Operación

Para ejecutar el paquete localmente desde el layout `src`:

```bash
cd /ruta/donde/esta/clonado/sre-agent
PYTHONPATH=src python3 -m sre_agent
```

Con `python3 -m` se usa el nombre del módulo `sre_agent` (con guion bajo), no `sre-agent`.

- **Verificar próximos disparos programados:**

```bash
systemctl --user list-timers --all | grep ollama

```

- **Forzar ejecución manual del agente de alerta:**

```bash
systemctl --user start ollama-agent.service

```

- **Forzar envío del reporte diario visual:**

```bash
systemctl --user start ollama-daily-report.service

```

- **Inspeccionar logs del sistema:**

```bash
journalctl --user -u ollama-agent.service -n 50 --no-pager
journalctl --user -u ollama-daily-report.service -n 50 --no-pager
journalctl --user -u ollama-telegram-bot.service -n 50 --no-pager

```

---

## 📂 Estructura del Repositorio

```text
.
├── src/
│   └── sre_agent/
│       ├── __main__.py           # Entrada para python -m sre_agent
│       ├── cli.py                # Interfaz de línea de comandos
│       ├── agent.py              # Casos de uso y orquestación
│       ├── config.py             # Configuración y carga de .env
│       ├── collectors.py         # Recolección de telemetría
│       ├── history.py            # Persistencia de muestras CSV
│       ├── alerts.py             # Evaluación de umbrales
│       ├── integrations.py       # Clientes Ollama y Telegram
│       └── reporting.py          # Formateo de reportes
├── pyproject.toml                # Metadatos y dependencias del paquete
├── .env.example                  # Plantilla de configuración
├── systemd/
│   ├── ollama-agent.service     # Servicio de comprobación periódica
│   ├── ollama-agent.timer       # Temporizador cada 10 minutos
│   ├── ollama-daily-report.service # Servicio de reporte ejecutivo matutino
│   ├── ollama-daily-report.timer   # Temporizador de reporte diario (09:00)
│   └── ollama-telegram-bot.service # Bot de comandos Telegram
├── .gitignore
└── README.md

```
