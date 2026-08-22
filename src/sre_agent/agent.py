"""Application use cases and orchestration."""

from __future__ import annotations

import json
from typing import Any

from .alerts import AlertEvaluator
from .collectors import InfrastructureCollector
from .config import Settings
from .history import HistoryRepository
from .integrations import InvestigationClient, TelegramNotifier
from .reporting import format_alert_report, get_status_icon, make_bar, strip_markdown


class SREAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.collector = InfrastructureCollector()
        self.history = HistoryRepository(settings.history_file)
        self.evaluator = AlertEvaluator(settings.thresholds)
        self.investigator = InvestigationClient(settings)
        self.telegram = TelegramNotifier(settings)

    def run(self) -> None:
        resources = self.collector.collect_resources()
        self.history.record(resources)
        telemetry = {"resources": resources, "disks": self.collector.collect_disks(), "smart_health": self.collector.collect_smart(), "containers": self.collector.collect_containers(), "updates": self.collector.collect_updates()}
        alerts = self.evaluator.evaluate(telemetry)
        print(
            "Telemetría recopilada: "
            f"CPU {resources['cpu_load_percent']}%, "
            f"RAM {resources['ram_used_percent']}%, "
            f"discos {len(telemetry['disks'])}, "
            f"contenedores {len(telemetry['containers'])}, "
            f"alertas {len(alerts)}"
        )
        if not alerts:
            print("\nSistema nominal: sin alertas que enviar.")
            return
        print(f"\nDisparando análisis con {self.settings.sre_provider}...")
        prompt = ("Eres un agente SRE de Linux. Analiza la siguiente telemetría donde se han detectado anomalías. " "Genera un reporte conciso de 3-4 líneas en texto plano: causa raíz, severidad y comando sugerido. No uses Markdown.\n\n" f"Anomalías detectadas: {alerts}\nTelemetría del equipo:\n{json.dumps(telemetry, indent=2)}")
        diagnosis = self.investigator.investigate(alerts, telemetry, prompt, "Sin respuesta del proveedor SRE")
        self.telegram.send(format_alert_report(alerts, diagnosis), parse_mode=None)

    def daily_report(self) -> None:
        stats = self.history.get_last_24_hours()
        telemetry = self.collector.collect_telemetry(stats)
        prompt = ("Eres un agente SRE de Linux. Explica en lenguaje natural el estado general del servidor " "en 1 o 2 frases, mencionando solo lo más relevante de las últimas 24 horas. No repitas la telemetría, " "no uses listas, código ni Markdown.\n\nTelemetría actual y estadísticas 24h:\n" f"{json.dumps(telemetry, indent=2)}")
        verdict = self.investigator.ask(prompt, "Servicios operando dentro de los parámetros esperados en las últimas 24 horas.")
        verdict = strip_markdown(verdict)
        self.telegram.send(self._format_report(telemetry, verdict))
        print("Reporte diario visual enviado con éxito a Telegram.")

    def command(self, command: str) -> str:
        """Return a plain-text response for a Telegram command."""
        if command == "/report":
            stats = self.history.get_last_24_hours()
            telemetry = self.collector.collect_telemetry(stats)
            verdict = self.investigator.ask(
                "Explica en lenguaje natural el estado del servidor en una o dos frases. "
                "Menciona solo lo más relevante, sin repetir datos, listas, código ni Markdown:\n"
                + json.dumps(telemetry, indent=2),
                "Servicios operando dentro de los parámetros esperados.",
            )
            return self._format_plain_report(telemetry, strip_markdown(verdict))

        if command == "/status":
            telemetry = self.collector.collect_telemetry()
            return self._format_status(telemetry)

        resources = self.collector.collect_resources()
        if command == "/cpu":
            return f"🧠 CPU\n━━━━━━━━━━━━━━━━━━━━\nCarga: {resources['cpu_load_percent']}%\nTemperatura: {resources['cpu_temp_c']}°C\nRAM: {resources['ram_used_percent']}%"
        if command == "/gpu":
            gpu = resources.get("gpu", {})
            return f"🎮 GPU\n━━━━━━━━━━━━━━━━━━━━\nTemperatura: {gpu.get('temp_c', 'N/A')}°C\nVRAM: {gpu.get('vram_used_mb', 0)} / {gpu.get('vram_total_mb', 0)} MB\nUso: {gpu.get('util_percent', 'N/A')}%"
        if command == "/disks":
            disks = self.collector.collect_disks()
            lines = [f"💾 {name}: {make_bar(value)} {value}% {get_status_icon(value)}" for name, value in disks.items()]
            return "💾 DISCOS\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
        if command == "/docker":
            containers = self.collector.collect_containers()
            lines = [f"{'🟢' if data['running'] else '🔴'} {name}: {data['status']}" for name, data in containers.items()]
            return "🐳 DOCKER\n━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join(lines) or "Sin contenedores")
        return "Comando no reconocido. Usa /help para ver los comandos disponibles."

    @staticmethod
    def _format_status(telemetry: dict[str, Any]) -> str:
        resources = telemetry["resources"]
        alerts = AlertEvaluator({"cpu_temp": 80, "gpu_temp": 82, "disk_percent": 90}).evaluate(telemetry)
        state = "🔴 CON ALERTAS" if alerts else "🟢 SISTEMA NOMINAL"
        return (
            f"📊 ESTADO DEL SERVIDOR\n━━━━━━━━━━━━━━━━━━━━\n{state}\n\n"
            f"CPU: {resources['cpu_load_percent']}% | {resources['cpu_temp_c']}°C\n"
            f"RAM: {resources['ram_used_percent']}%\n"
            f"GPU: {resources.get('gpu', {}).get('temp_c', 'N/A')}°C\n"
            f"Discos: {len(telemetry['disks'])} comprobados\n"
            f"Docker: {len(telemetry['containers'])} contenedores\n"
            f"Alertas: {len(alerts)}"
        )

    @staticmethod
    def _format_plain_report(telemetry: dict[str, Any], verdict: str) -> str:
        resources = telemetry["resources"]
        disks = telemetry["disks"]
        gpu = resources.get("gpu", {})
        containers = telemetry["containers"]
        docker_status = "\n".join(f"{'🟢' if data.get('running') else '🔴'} {name}" for name, data in containers.items()) or "Sin contenedores"
        return (
            "📊 REPORTE DIARIO DEL SERVIDOR\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧠 ESTADO ACTUAL\nCPU {make_bar(resources.get('cpu_load_percent', 0))} {resources.get('cpu_load_percent', 0)}% ({resources.get('cpu_temp_c', 0)}°C)\n"
            f"RAM {make_bar(resources.get('ram_used_percent', 0))} {resources.get('ram_used_percent', 0)}% ({resources.get('ram_used_gb', 0)} GB)\n\n"
            f"🎮 GPU\nTemperatura: {gpu.get('temp_c', 'N/A')}°C | VRAM: {gpu.get('vram_used_mb', 0)} MB\n\n"
            "💾 ALMACENAMIENTO\n"
            + "\n".join(f"{name}: {make_bar(value)} {value}% {get_status_icon(value)}" for name, value in disks.items())
            + f"\n\n🐳 DOCKER\n{docker_status}\n\n📦 ACTUALIZACIONES\n{telemetry['updates'].get('pending_updates', 0)} pendientes\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n💡 DIAGNÓSTICO SRE\n{verdict.strip()}"
        )

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
