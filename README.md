# Ollama SRE Agent

Agente autónomo de observabilidad y fiabilidad (SRE) para servidores Linux. Recoge telemetría de hardware, estado de almacenamiento (SMART), contenedores Docker y actualizaciones pendientes. Integra un modelo de lenguaje local mediante **Ollama** (`qwen2.5-coder:latest`) para diagnosticar anomalías en tiempo real y enviar un reporte diario vía **Telegram**.

---

## Características

| Capacidad | Descripción |
|---|---|
| Monitorización continua | Ciclo de 10 minutos: CPU, RAM, GPU NVIDIA, discos, Docker y SMART |
| Diagnóstico inteligente | Inferencia local con Ollama activada únicamente ante umbrales superados |
| Reporte matutino | Resumen diario con estadísticas de 24 h (mín/máx/media) enviado a Telegram |
| Bot de Telegram | Consultas bajo demanda mediante comandos de chat |
| Persistencia local | Historial de métricas en CSV dentro de un volumen Docker |

---

## Arquitectura

```mermaid
flowchart LR
    subgraph Host["Entorno Host"]
        Proc["/proc · /sys · /dev"]
        DockerRuntime["Docker socket"]
        Nvidia["nvidia-smi"]
    end

    subgraph Container["Contenedor Docker: sre-agent"]
        Entrypoint["Entrypoint"]
        Agent["SREAgent"]
        Collector["InfrastructureCollector"]
        Alerts["AlertEvaluator"]
        History["HistoryRepository"]
        Reporter["Reporting"]
        Bot["Telegram Bot"]
    end

    subgraph External["Servicios externos"]
        Ollama["Ollama"]
        Telegram["API Telegram"]
    end

    Proc --> Collector
    DockerRuntime --> Collector
    Nvidia --> Collector

    Entrypoint --> Agent
    Entrypoint --> Bot
    Agent -->|control| Collector
    Agent -->|control| Alerts
    Collector -->|métricas| Alerts
    Alerts --> History
    History --> Reporter

    Alerts -- "anomalía detectada" --> Ollama
    Agent --> Ollama
    Ollama --> Reporter
    Reporter --> Telegram
    Bot --> Agent
    Bot --> Telegram
    Agent --> Telegram

    classDef infra fill:#f3f4f6,stroke:#9ca3af,color:#111827,stroke-width:1px;
    classDef internal fill:#ffffff,stroke:#6b7280,color:#111827,stroke-width:1px;
    classDef external fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a,stroke-width:1px;
    classDef anomaly fill:#fef2f2,stroke:#ef4444,color:#7f1d1d,stroke-width:2px;

    class Proc,DockerRuntime,Nvidia infra;
    class Entrypoint,Agent,Collector,History,Reporter,Bot internal;
    class Ollama,Telegram external;
    class Alerts anomaly;
```

---

## Flujo de ejecución

```mermaid
flowchart TD
    Start([Inicio: docker-entrypoint.sh])
    Start --> P1[Proceso: ciclo de SREAgent\ncada 10 min]
    Start --> P2[Proceso: reporte diario\nHH:MM configurado]
    Start --> P3[Proceso: Telegram Bot\npolling continuo]

    P1 --> Collect[InfrastructureCollector\nrecopila telemetría]
    Collect --> Eval{¿Algún umbral\nsuperado?}
    Eval -- No --> Sleep[Esperar siguiente ciclo]
    Sleep --> Collect
    Eval -- Sí --> SaveAlert[AlertEvaluator\nregistra alerta]
    SaveAlert --> Store[HistoryRepository\nguarda en CSV]
    Store --> AskOllama[Enviar contexto\na Ollama]
    AskOllama --> Notify[Reporting\nenvía alerta a Telegram]
    Notify --> Sleep

    P2 --> Wait[Esperar hora\nconfigurada]
    Wait --> ReadCSV[HistoryRepository\nlee 24 h]
    ReadCSV --> BuildReport[Reporting\ngenera estadísticas]
    BuildReport --> SendReport[Enviar reporte\na Telegram]
    SendReport --> Wait

    P3 --> BotPoll[Recibir comando\n/status /cpu /gpu …]
    BotPoll --> RunCmd[SREAgent\nprocesa comando]
    RunCmd --> Reply[Enviar respuesta\na Telegram]
    Reply --> BotPoll
```

---

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/status` | Estado general del servidor |
| `/report` | Reporte diario bajo demanda |
| `/cpu` | Carga de CPU, temperatura y RAM |
| `/gpu` | Temperatura, VRAM y uso de GPU |
| `/disks` | Uso de discos |
| `/docker` | Estado de contenedores |
| `/info` | Características del sistema y hardware |
| `/sre <pregunta>` | Diagnóstico SRE con contexto enriquecido |
| `/help` | Lista de comandos disponibles |

---

## Inicio rápido

Consulta la guía completa en [`docs/installation.md`](docs/installation.md).

```bash
# 1. Clonar y entrar al repositorio
git clone https://github.com/k3ssdev/sre-agent.git
cd sre-agent

# 2. Crear el secret de Telegram
mkdir -p secrets
printf '%s' 'TOKEN_DE_TELEGRAM' > secrets/telegram_token
chmod 600 secrets/telegram_token

# 3. Configurar variables de entorno
cp .env.example .env
# Editar .env con TELEGRAM_CHAT_ID y, si es necesario, OLLAMA_URL

# 4. Arrancar
docker compose up -d --build
docker compose logs -f sre-agent
```

---

## Estructura del repositorio

```text
.
├── docs/
│   ├── installation.md           # Guía de instalación y puesta en marcha
│   └── testing.md                # Guía de pruebas automatizadas y manuales
├── src/
│   └── sre_agent/
│       ├── __main__.py           # Entrada: python -m sre_agent
│       ├── cli.py                # Interfaz de línea de comandos
│       ├── agent.py              # Orquestación y casos de uso
│       ├── config.py             # Carga de configuración y .env
│       ├── collectors.py         # Recolección de telemetría del host
│       ├── history.py            # Persistencia de muestras en CSV
│       ├── alerts.py             # Evaluación de umbrales
│       ├── integrations.py       # Clientes Ollama y Telegram
│       └── reporting.py          # Formateo de reportes
├── scripts/
│   ├── docker-entrypoint.sh      # Ciclos del agente y reporte diario
│   └── manual-test.py            # Ejecución manual de funciones
├── tests/
│   └── test_agent_commands.py    # Suite de pruebas unitarias
├── pyproject.toml                # Metadatos y dependencias del paquete
├── Dockerfile
├── compose.yaml                  # Definición de servicios Docker
├── .env.example                  # Plantilla de variables de entorno
└── .gitignore
```

---

## Requisitos del sistema

- Docker Engine ≥ 24 con Docker Compose
- Ollama en ejecución en el host (puerto 11434)
- Bot de Telegram y su token (`@BotFather`) y chat ID
- Drivers NVIDIA instalados en el host (opcional, para métricas de GPU)

---

## Documentación adicional

- [Instalación y puesta en marcha](docs/installation.md)
- [Pruebas](docs/testing.md)
