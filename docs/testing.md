# Pruebas

Guía para ejecutar la suite de pruebas automatizadas y las pruebas manuales del agente SRE.

---

## Pruebas automatizadas

### Requisitos

Instala el paquete con las dependencias de desarrollo:

```bash
pip install -e ".[dev]"
```

Esto instala `pytest` y el paquete `sre_agent` en modo editable, por lo que las pruebas encuentran el módulo sin necesidad de ajustar `PYTHONPATH`.

### Ejecutar la suite

```bash
python -m pytest -q
```

### Cobertura actual

La suite se encuentra en `tests/test_agent_commands.py` e incluye siete pruebas unitarias:

| Prueba | Qué verifica |
|---|---|
| `test_cpu_command_formats_ram_percentage` | Formato de carga de CPU y porcentaje de RAM en `/cpu` |
| `test_gpu_command_reports_gpu_metrics` | Temperatura, VRAM y uso de GPU en `/gpu` |
| `test_gpu_command_handles_unavailable_gpu` | Respuesta cuando `nvidia-smi` no está disponible |
| `test_docker_command_lists_running_and_stopped_containers` | Estado de contenedores en `/docker` |
| `test_docker_command_reports_empty_host` | Respuesta cuando no hay contenedores |
| `test_status_command_uses_collected_telemetry` | Estado general del servidor en `/status` |
| `test_sre_command_uses_local_tools_and_ollama` | Enriquecimiento del prompt con telemetría y sockets en `/sre` |
| `test_history_returns_only_samples_from_last_24_hours` | Filtrado correcto de muestras del historial CSV |

Las pruebas usan mocks y archivos temporales. No envían mensajes a Telegram ni consultan Ollama.

---

## Pruebas manuales

El script `scripts/manual-test.py` permite invocar funciones del agente de forma aislada, sin iniciar el polling infinito del bot.

### Configuración

Carga

```bash
python3 scripts/manual-test.py config
```

Muestra la configuración efectiva cargada desde `.env`.

### Recolección de telemetría

```bash
python3 scripts/manual-test.py collect
```

Ejecuta `InfrastructureCollector` y muestra las métricas recopiladas: CPU, RAM, GPU, discos, Docker y SMART. Requiere las dependencias Python instaladas y, para los datos de Docker, un daemon accesible.

### Evaluación de alertas

```bash
python3 scripts/manual-test.py alerts
```

Recopila telemetría y ejecuta `AlertEvaluator` para mostrar qué alertas se dispararían con los valores actuales.

### Consulta a Ollama

```bash
python3 scripts/manual-test.py ollama
```

Envía una consulta de prueba al modelo configurado. Si el contenedor usa `host.docker.internal` para llegar a Ollama pero se ejecuta desde el host, pasa la URL directamente:

```bash
python3 scripts/manual-test.py ollama --ollama-url http://localhost:11434/api/generate
```

### Comando del bot

```bash
python3 scripts/manual-test.py command --command /status
python3 scripts/manual-test.py command --command /cpu
python3 scripts/manual-test.py command --command /gpu
python3 scripts/manual-test.py command --command /docker
```

Ejecuta el comando indicado en `SREAgent` y muestra la respuesta formateada, sin enviarla a Telegram.

---

## Consideraciones

- Las pruebas de recolección de telemetría y SMART necesitan acceso a los dispositivos del host y pueden requerir privilegios elevados.
- Si ejecutas las pruebas dentro del contenedor Docker, el entorno ya está correctamente configurado.
- Para añadir nuevas pruebas, crea o amplía archivos en el directorio `tests/`. La configuración de `pytest` en `pyproject.toml` apunta a ese directorio automáticamente.
