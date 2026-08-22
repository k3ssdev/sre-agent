"""Application use cases and orchestration."""

from __future__ import annotations

import json
import re
from typing import Any

from .alerts import AlertEvaluator
from .collectors import InfrastructureCollector
from .config import Settings
from .history import HistoryRepository
from .integrations import OllamaClient, TelegramNotifier
from .reporting import get_status_icon, make_bar


class SREAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.collector = InfrastructureCollector()
        self.history = HistoryRepository(settings.history_file)
        self.evaluator = AlertEvaluator(settings.thresholds)
        self.ollama = OllamaClient(settings)
        self.telegram = TelegramNotifier(settings)

    def run(self) -> None:
        resources = self.collector.collect_resources()
        self.history.record(resources)
        telemetry = {"resources": resources, "disks": self.collector.collect_disks(), "smart_health": self.collector.collect_smart(), "containers": self.collector.collect_containers(), "updates": self.collector.collect_updates()}
        alerts = self.evaluator.evaluate(telemetry)
        print("Telemetría:", json.dumps(telemetry, indent=2))
        if not alerts:
            print("\nSistema nominal: sin alertas que enviar.")
            return
        print(f"\nDisparando análisis con Ollama ({self.settings.model_name})...")
        prompt = ("Eres un agente SRE de Linux. Analiza la siguiente telemetría donde se han detectado anomalías. " "Genera un reporte conciso de 3-4 líneas en Markdown: causa raíz, severidad y comando sugerido.\n\n" f"Anomalías detectadas: {alerts}\nTelemetría del equipo:\n{json.dumps(telemetry, indent=2)}")
        diagnosis = self.ollama.ask(prompt, "Sin respuesta de Ollama")
        message = "🚨 *ALERTA SERVIDOR*\n\n" + "\n".join(f"• {alert}" for alert in alerts)
        self.telegram.send(f"{message}\n\n*Diagnóstico Ollama:*\n{diagnosis}")

    def daily_report(self) -> None:
        stats = self.history.get_last_24_hours()
        telemetry = self.collector.collect_telemetry(stats)
        prompt = ("Eres un agente SRE de Linux. Escribe un veredicto de estado general de 1 o 2 líneas resumiendo " f"las últimas 24h sin listas ni código.\n\nTelemetría actual y estadísticas 24h:\n{json.dumps(telemetry, indent=2)}")
        verdict = self.ollama.ask(prompt, "Servicios operando dentro de los parámetros esperados en las últimas 24 horas.")
        verdict = re.sub(r"```[a-zA-Z]*", "", verdict).replace("```", "").strip()
        self.telegram.send(self._format_report(telemetry, verdict))
        print("Reporte diario visual enviado con éxito a Telegram.")

    @staticmethod
    def _format_report(telemetry: dict[str, Any], verdict: str) -> str:
        resources, disks = telemetry["resources"], telemetry["disks"]
        gpu, stats = resources.get("gpu", {}), telemetry.get("stats_24h")
        smart_failed = any(isinstance(info, dict) and not info.get("health_passed", True) for info in telemetry["smart_health"].values())
        history = "\n📈 *MÉTRICAS 24H*\n• Recopilando primeras muestras..."
        if stats:
            history = (f"\n📈 *MÉTRICAS 24H ({stats['samples']} muestras)*\n" f"• `CPU Carga` Min {stats['cpu_load'][0]:.1f}% | Avg {stats['cpu_load'][2]:.1f}% | Max *{stats['cpu_load'][1]:.1f}%*\n" f"• `CPU Temp` Min {stats['cpu_temp'][0]:.1f}°C | Avg {stats['cpu_temp'][2]:.1f}°C | Max *{stats['cpu_temp'][1]:.1f}°C*\n" f"• `RAM Carga` Min {stats['ram_load'][0]:.1f}% | Avg {stats['ram_load'][2]:.1f}% | Max *{stats['ram_load'][1]:.1f}%*\n" f"• `GPU Temp` Min {stats['gpu_temp'][0]:.1f}°C | Avg {stats['gpu_temp'][2]:.1f}°C | Max *{stats['gpu_temp'][1]:.1f}°C*")
        docker_status = "\n".join(f"  {'🟢' if info.get('running') else '🔴'} `{name}`" for name, info in telemetry["containers"].items()) or "  ⚪ Sin contenedores"
        return f"""📊 *REPORTE DIARIO DEL SERVIDOR*
━━━━━━━━━━━━━━━━━━━━

🧠 *ESTADO ACTUAL*
• `CPU` `{make_bar(resources.get('cpu_load_percent', 0))}` {resources.get('cpu_load_percent', 0)}% ({resources.get('cpu_temp_c', 0)}°C)
• `RAM` `{make_bar(resources.get('ram_used_percent', 0))}` {resources.get('ram_used_percent', 0)}% ({resources.get('ram_used_gb', 0)} GB)

🎮 *GPU*
• `Núcleo` {gpu.get('temp_c', 'N/A')}°C | `VRAM` {int(gpu.get('vram_used_mb', 0))} MB
{history}

💾 *ALMACENAMIENTO*
• `240GB SSD` `{make_bar(disks.get('root', 0))}` {disks.get('root', 0)}% {get_status_icon(disks.get('root', 0))}
• `8TB HDD` `{make_bar(disks.get('hdd8tb', 0))}` {disks.get('hdd8tb', 0)}% {get_status_icon(disks.get('hdd8tb', 0))}
• `1TB HDD` `{make_bar(disks.get('hdd1tb', 0))}` {disks.get('hdd1tb', 0)}% {get_status_icon(disks.get('hdd1tb', 0))}
• `SMART` {'🔴 Fallo detectado' if smart_failed else '🟢 Todos saludables'}

🐳 *DOCKER*
{docker_status}

📦 *SISTEMA*
• `Actualizaciones` {telemetry['updates'].get('pending_updates', 0)} pendientes

━━━━━━━━━━━━━━━━━━━━
💡 *Diagnóstico SRE:*
_{verdict}_"""
