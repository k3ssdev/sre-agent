# Instalación y puesta en marcha

Guía paso a paso para desplegar el agente SRE en un servidor Linux mediante Docker Compose.

---

## Requisitos previos

| Componente | Versión mínima | Notas |
|---|---|---|
| Docker Engine | 24.0 | Incluye Docker Compose v2 |
| Ollama | cualquiera | Debe escuchar en el host en el puerto 11434 |
| Bot de Telegram | — | Token generado con `@BotFather` |
| Drivers NVIDIA | cualquiera | Solo necesario para métricas de GPU |

El contenedor corre en modo privilegiado y monta `/proc`, `/sys` y `/dev` del host para acceder a métricas de hardware y datos SMART. Asegúrate de ejecutarlo en un entorno de confianza.

---

## 1. Clonar el repositorio

```bash
git clone https://github.com/k3ssdev/sre-agent.git
cd sre-agent
```

---

## 2. Crear el secret de Telegram

El token de Telegram se gestiona como Docker Secret, no como variable de entorno, para evitar exponerlo en el historial del shell o en los logs del contenedor.

```bash
mkdir -p secrets
printf '%s' 'TOKEN_DE_TELEGRAM' > secrets/telegram_token
chmod 600 secrets/telegram_token
```

> **Importante:** Si el token anterior quedó expuesto, revócalo desde `@BotFather` antes de continuar.

El archivo `secrets/telegram_token` está incluido en `.gitignore` y no se versiona.

---

## 3. Configurar variables de entorno

Copia la plantilla y edita el archivo resultante:

```bash
cp .env.example .env
```

Valores configurables en `.env`:

| Variable | Valor por defecto | Descripción |
|---|---|---|
| `SRE_PROVIDER` | `ollama` | Proveedor de análisis (actualmente solo `ollama`) |
| `OLLAMA_URL` | `http://host.docker.internal:11434/api/generate` | Endpoint de la API de Ollama |
| `OLLAMA_MODEL` | `qwen2.5-coder:latest` | Modelo a usar en Ollama |
| `TELEGRAM_CHAT_ID` | — | ID del chat al que se enviarán los mensajes |
| `SRE_HISTORY_FILE` | `/var/lib/sre-agent/server_metrics_history.csv` | Ruta interna del historial CSV |
| `REPORT_TIME` | `08:00` | Hora del reporte diario (formato HH:MM) |

En Linux, `host.docker.internal` se resuelve automáticamente mediante el alias configurado en `compose.yaml`. Si Ollama escucha en una dirección distinta, actualiza `OLLAMA_URL`.

El fichero `.env` contiene configuración local y no debe versionarse.

---

## 4. Arrancar el agente

```bash
docker compose up -d --build
```

Esto construye la imagen, crea el volumen `sre-history` y arranca el contenedor con tres procesos concurrentes:

- **Ciclo del agente** — recopila telemetría y evalúa alertas cada 10 minutos.
- **Reporte diario** — espera la hora configurada en `REPORT_TIME` y envía el resumen a Telegram.
- **Bot de Telegram** — polling continuo para responder comandos en el chat.

---

## 5. Verificar el estado

Consulta los logs en tiempo real:

```bash
docker compose logs -f sre-agent
```

Comprueba que el bot responde enviando `/status` en el chat de Telegram.

---

## 6. Detener el agente

```bash
docker compose down
```

El volumen `sre-history` se conserva. Para eliminarlo también:

```bash
docker compose down -v
```

---

## Ejecución local (sin Docker)

Para ejecutar el paquete directamente en el host, instálalo en modo editable:

```bash
pip install -e ".[dev]"
```

A continuación, lanza el agente indicando la ruta del módulo:

```bash
python -m sre_agent
```

Las variables de entorno pueden definirse en el shell o cargarse desde `.env`. El token de Telegram debe estar disponible en la ruta indicada por `TELEGRAM_TOKEN_FILE` o como variable `TELEGRAM_TOKEN`.

---

## Actualización

```bash
git pull
docker compose up -d --build
```

La imagen se reconstruye con los últimos cambios. El volumen de historial se mantiene entre actualizaciones.
