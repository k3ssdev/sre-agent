# 🤖 Ollama SRE Agent

Agente autónomo de observabilidad y fiabilidad (SRE) para servidores Linux. Recopila telemetría de hardware, estado de almacenamiento (SMART), Docker y actualizaciones pendientes, integrando un LLM local en **Ollama** (`qwen2.5-coder:7b`) para diagnóstico de anomalías en tiempo real y generación de reportes diarios matutinos vía **Telegram**.

---

## ⚡ Características

- **Monitorización continua (10 min):** Chequeo pasivo de CPU, RAM, GPU (NVIDIA), almacenamiento, Docker y alertas de hardware SMART sin falsos positivos.
- **Diagnóstico Inteligente Local:** Disparo automático de inferencia con Ollama únicamente ante métricas fuera de umbral o incidentes de infraestructura.
- **Reporte Matutino Visual:** Resumen diario con métricas 24h (mínimos, máximos y medias), barras de progreso monoespaciadas y diagnóstico SRE.
- **Persistencia local:** Historial CSV en un volumen Docker y ejecución continua mediante Docker Compose.

---

## Requisitos

- Docker Compose
- Ollama ejecutándose en el host
- Token y chat ID de Telegram
- Drivers NVIDIA instalados en el host para obtener datos de GPU

El contenedor accede al socket Docker y a los dispositivos del host para
recopilar métricas, SMART, discos y GPU.

---

## 🛠️ Instalación y Configuración

## Configuración

Configura el agente en `.env` a partir de `.env.example`:

```bash
cp .env.example .env
```

El token de Telegram se gestiona como Docker Secret, no como variable de
entorno. Crea el archivo local con el token nuevo generado por `@BotFather`:

```bash
mkdir -p secrets
printf '%s' 'TOKEN_DE_TELEGRAM' > secrets/telegram_token
chmod 600 secrets/telegram_token
```

El archivo `secrets/telegram_token` está excluido de Git. Si el token anterior
quedó expuesto, revócalo primero desde `@BotFather`.

Edita `.env` con tus valores:

```dotenv
SRE_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=qwen2.5-coder:7b
OPENSRE_COMMAND=~/.local/bin/opensre
OPENSRE_TIMEOUT=120
TELEGRAM_CHAT_ID=TU_CHAT_ID
SRE_HISTORY_FILE=~/.config/server_metrics_history.csv
```

El fichero `.env` contiene configuración local y no debe versionarse. El token
se lee dentro del contenedor desde `/run/secrets/telegram_token`.

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
/info          Características del sistema y hardware
/help          Lista de comandos
```

## Ejecución

Un único contenedor mantiene el bot activo, ejecuta las alertas cada 10 minutos
y genera el reporte diario a las 09:00.

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f sre-agent
```

El historial se guarda en el volumen `sre-history`. El contenedor usa acceso
privilegiado y monta `/proc`, `/sys` y `/dev` porque recopila telemetría del
host y consulta SMART. Si Ollama escucha en otra dirección, define
`OLLAMA_URL` en `.env`; en Linux, el valor predeterminado apunta al host con
`host.docker.internal`.

Para detener los servicios:

```bash
docker compose down
```

---

## 🔍 Comprobación y Operación

Para ejecutar el paquete localmente desde el layout `src`:

```bash
cd /ruta/donde/esta/clonado/sre-agent
PYTHONPATH=src python3 -m sre_agent
```

Con `python3 -m` se usa el nombre del módulo `sre_agent` (con guion bajo), no `sre-agent`.

- **Inspeccionar logs de los contenedores:**

```bash
docker compose logs -f sre-agent
```

### Pruebas manuales

`manual-test.py` permite ejecutar funciones concretas sin iniciar el polling
infinito del bot:

```bash
python3 scripts/manual-test.py config
python3 scripts/manual-test.py collect
python3 scripts/manual-test.py alerts
python3 scripts/manual-test.py ollama
python3 scripts/manual-test.py opensre
python3 scripts/manual-test.py command --command /status
```

La prueba `opensre` fuerza ese proveedor aunque `SRE_PROVIDER=ollama`. Las
pruebas de recolección necesitan las dependencias Python y, para consultar
contenedores, un daemon Docker accesible.

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
├── scripts/
│   ├── docker-entrypoint.sh       # Ciclos del agente y reporte diario
│   └── manual-test.py              # Ejecuta funciones manualmente
├── Dockerfile
├── compose.yaml                   # Servicios y scheduling de Docker
├── .gitignore
└── README.md

```
