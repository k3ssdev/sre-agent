"""Application use cases and orchestration."""

from __future__ import annotations

import json
from typing import Any

from .alerts import AlertEvaluator
from .collectors import InfrastructureCollector
from .config import Settings
from .history import HistoryRepository
from .integrations import InvestigationClient, TelegramNotifier
from .reporting import format_alert_report, get_hostname, get_status_icon, make_bar, strip_markdown
from .tools import auditar_red_sockets, buscar_archivo, obtener_telemetria_sistema

STATUS_THRESHOLDS = {"cpu_temp": 80, "gpu_temp": 82, "disk_percent": 90}


class SREAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.collector = InfrastructureCollector()
        self.history = HistoryRepository(settings.history_file)
        self.evaluator = AlertEvaluator(settings.thresholds)
        self.investigator = InvestigationClient(settings)
        self.telegram = TelegramNotifier(settings)
        self.hostname = get_hostname()

    def run(self) -> None:
        resources = self.collector.collect_resources()
        self.history.record(resources)
        telemetry = self.collector.collect_telemetry(resources=resources)
        alerts = self.evaluator.evaluate(telemetry)
        self._print_telemetry_summary(resources, telemetry, alerts)
        if not alerts:
            print("\nSistema nominal: sin alertas que enviar.")
            return

        print(f"\nDisparando análisis con {self.settings.sre_provider}...")
        diagnosis = self.investigator.investigate(
            alerts,
            telemetry,
            self._build_alert_prompt(alerts, telemetry),
            "Sin respuesta del proveedor SRE",
        )
        self.telegram.send(format_alert_report(alerts, diagnosis, self.hostname), parse_mode="Markdown")

    def daily_report(self) -> None:
        stats = self.history.get_last_24_hours()
        telemetry = self.collector.collect_telemetry(stats=stats)
        verdict = self._request_verdict(
            telemetry,
            (
                "Eres un agente SRE de Linux. Explica en lenguaje natural el estado general "
                "del servidor en 1 o 2 frases, mencionando solo lo más relevante de las "
                "últimas 24 horas. No repitas la telemetría, no uses listas, código ni Markdown."
            ),
            "Telemetría actual y estadísticas 24h",
            "Servicios operando dentro de los parámetros esperados en las últimas 24 horas.",
        )
        self.telegram.send(self._format_report(telemetry, verdict, self.hostname))
        print("Reporte diario visual enviado con éxito a Telegram.")

    def command(self, full_command: str) -> str:
        """Return a plain-text response for a Telegram command."""
        cmd, args = self._split_command(full_command)
        if cmd == "/report":
            return self._build_report_command_response()
        if cmd == "/status":
            return self._format_status(self.collector.collect_telemetry(), self.hostname)
        if cmd == "/info":
            return self._format_info(self.collector.collect_system_info(), self.hostname)
        if cmd == "/cpu":
            return self._format_cpu(self.collector.collect_resources(), self.hostname)
        if cmd == "/gpu":
            return self._format_gpu(self.collector.collect_resources(), self.hostname)
        if cmd == "/disks":
            return self._format_disks(self.collector.collect_disks(), self.hostname)
        if cmd == "/docker":
            return self._format_docker(self.collector.collect_containers(), self.hostname)
        if cmd == "/wake":
            return f"🟢 Equipo `{self.hostname}` esta despierto."
        if cmd == "/sre":
            if not args:
                return "⚠️ Necesito contexto para investigar. Ejemplo: `/sre Revisa por qué el disco root está al 90%`"
            return self._investigate_command(args)
        return f"*{self.hostname}:* comando no reconocido. Usa /help para ver los comandos disponibles."

    @staticmethod
    def _split_command(full_command: str) -> tuple[str, str]:
        parts = full_command.split(maxsplit=1)
        return parts[0].lower(), parts[1] if len(parts) > 1 else ""

    def _build_report_command_response(self) -> str:
        stats = self.history.get_last_24_hours()
        telemetry = self.collector.collect_telemetry(stats=stats)
        verdict = self._request_verdict(
            telemetry,
            (
                "Explica en lenguaje natural el estado del servidor en una o dos frases. "
                "Menciona solo lo más relevante, sin repetir datos, listas, código ni Markdown:"
            ),
            None,
            "Servicios operando dentro de los parámetros esperados.",
        )
        return self._format_plain_report(telemetry, verdict, self.hostname)

    def _request_verdict(
        self,
        telemetry: dict[str, Any],
        prompt: str,
        context_label: str | None,
        fallback: str,
    ) -> str:
        context = json.dumps(telemetry, indent=2)
        if context_label:
            prompt = f"{prompt}\n\n{context_label}:\n{context}"
        else:
            prompt = f"{prompt}\n{context}"
        return strip_markdown(self.investigator.ask(prompt, fallback))

    @staticmethod
    def _print_telemetry_summary(
        resources: dict[str, Any],
        telemetry: dict[str, Any],
        alerts: list[str],
    ) -> None:
        print(
            "Telemetría recopilada: "
            f"CPU {resources['cpu_load_percent']}%, "
            f"RAM {resources['ram_used_percent']}%, "
            f"discos {len(telemetry['disks'])}, "
            f"contenedores {len(telemetry['containers'])}, "
            f"alertas {len(alerts)}"
        )

    @staticmethod
    def _build_alert_prompt(alerts: list[str], telemetry: dict[str, Any]) -> str:
        return (
            "Eres un agente SRE de Linux. Analiza la siguiente telemetría donde se han "
            "detectado anomalías. Genera un reporte conciso de 3-4 líneas en texto plano: "
            "causa raíz, severidad y comando sugerido. No uses Markdown.\n\n"
            f"Anomalías detectadas: {alerts}\n"
            f"Telemetría del equipo:\n{json.dumps(telemetry, indent=2)}"
        )

    @staticmethod
    def _format_cpu(resources: dict[str, Any], hostname: str) -> str:
        return (
            f"🧠 *CPU - {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Carga:* `{resources['cpu_load_percent']}%`\n"
            f"• *Temperatura:* `{resources['cpu_temp_c']}°C`\n"
            f"• *RAM:* `{float(resources['ram_used_percent']):.1f}%`"
        )

    @staticmethod
    def _format_gpu(resources: dict[str, Any], hostname: str) -> str:
        gpu = resources.get("gpu", {})
        return (
            f"🎮 *GPU - {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"• *Temperatura:* `{gpu.get('temp_c', 'N/A')}°C`\n"
            f"• *VRAM:* `{gpu.get('vram_used_mb', 0)} / {gpu.get('vram_total_mb', 0)} MB`\n"
            f"• *Uso:* `{gpu.get('util_percent', 'N/A')}%`"
        )

    @staticmethod
    def _format_disks(disks: dict[str, float], hostname: str) -> str:
        lines = [
            f"• *{name}:* `{make_bar(value)} {value}%` {get_status_icon(value)}"
            for name, value in disks.items()
        ]
        return f"💾 *DISCOS - {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)

    @staticmethod
    def _format_docker(containers: dict[str, dict[str, Any]], hostname: str) -> str:
        lines = [
            f"{'🟢' if data['running'] else '🔴'} *{name}:* `{data['status']}`"
            for name, data in containers.items()
        ]
        return f"🐳 *DOCKER - {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join(lines) or "Sin contenedores")

    def _investigate_command(self, query: str) -> str:
        query_lower = query.lower()
        tools: dict[str, Any] = {"system": obtener_telemetria_sistema}
        if "socket" in query_lower or "red" in query_lower:
            tools["network_sockets"] = auditar_red_sockets
        if any(word in query_lower for word in ("archivo", "flag", "busca")):
            tools["file_search"] = lambda: buscar_archivo("flag.txt")
        tool_results = {name: tool() for name, tool in tools.items()}
        prompt = (
            "Actúa como un Ingeniero SRE Senior y responde completamente en español. "
            "Responde a la petición concreta con suficiente detalle: incluye los datos "
            "relevantes observados, el impacto, la causa probable y acciones concretas. "
            "Organiza la respuesta con las secciones Hallazgo, Evidencia, Severidad y "
            "Acción. No repitas la consulta ni la telemetría, no incluyas saludos, "
            "introducciones, despedidas o explicaciones genéricas. Analiza únicamente "
            "los datos reales y no inventes resultados.\n\n"
            f"Consulta del usuario:\n{query}\n\n"
            f"Resultados de herramientas de solo lectura:\n{json.dumps(tool_results, ensure_ascii=False, indent=2)}"
        )
        response = self.investigator.ask(prompt, "No se pudo consultar Ollama.")
        return f"Análisis SRE:\n----------------------------------------\n{response}"

    @staticmethod
    def _status_alerts(telemetry: dict[str, Any]) -> list[str]:
        return AlertEvaluator(STATUS_THRESHOLDS).evaluate(telemetry)

    @staticmethod
    def _format_status(telemetry: dict[str, Any], hostname: str) -> str:
        resources = telemetry["resources"]
        ram_percent = float(resources.get("ram_used_percent", 0))
        alerts = SREAgent._status_alerts(telemetry)
        state = "🔴 CON ALERTAS" if alerts else "🟢 SISTEMA NOMINAL"
        return (
            f"📊 *ESTADO DEL SERVIDOR: {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n{state}\n\n"
            f"• *CPU:* `{resources['cpu_load_percent']}%` | `{resources['cpu_temp_c']}°C`\n"
            f"• *RAM:* `{ram_percent:.1f}%`\n"
            f"• *GPU:* `{resources.get('gpu', {}).get('temp_c', 'N/A')}°C`\n"
            f"• *Discos comprobados:* `{len(telemetry['disks'])}`\n"
            f"• *Contenedores Docker:* `{len(telemetry['containers'])}`\n"
            f"• *Alertas:* `{len(alerts)}`"
        )

    @staticmethod
    def _format_history_section(stats: dict[str, Any] | None) -> str:
        if not stats:
            return "\n📈 *MÉTRICAS 24H*\n• Recopilando primeras muestras..."
        return (
            f"\n📈 *MÉTRICAS 24H ({stats['samples']} muestras)*\n"
            f"• `CPU Carga` Min {stats['cpu_load'][0]:.1f}% | Avg {stats['cpu_load'][2]:.1f}% | Max *{stats['cpu_load'][1]:.1f}%*\n"
            f"• `CPU Temp` Min {stats['cpu_temp'][0]:.1f}°C | Avg {stats['cpu_temp'][2]:.1f}°C | Max *{stats['cpu_temp'][1]:.1f}°C*\n"
            f"• `RAM Carga` Min {stats['ram_load'][0]:.1f}% | Avg {stats['ram_load'][2]:.1f}% | Max *{stats['ram_load'][1]:.1f}%*\n"
            f"• `GPU Temp` Min {stats['gpu_temp'][0]:.1f}°C | Avg {stats['gpu_temp'][2]:.1f}°C | Max *{stats['gpu_temp'][1]:.1f}°C*"
        )

    @staticmethod
    def _format_docker_summary(containers: dict[str, dict[str, Any]], *, indented: bool) -> str:
        if not containers:
            return "  ⚪ Sin contenedores" if indented else "Sin contenedores"
        prefix = "  " if indented else ""
        return "\n".join(
            f"{prefix}{'🟢' if data.get('running') else '🔴'} `{name}`"
            for name, data in containers.items()
        )

    @staticmethod
    def _smart_status(telemetry: dict[str, Any]) -> str:
        smart_failed = any(
            isinstance(info, dict) and not info.get("health_passed", True)
            for info in telemetry["smart_health"].values()
        )
        return "🔴 Fallo detectado" if smart_failed else "🟢 Todos saludables"

    @staticmethod
    def _format_plain_report(telemetry: dict[str, Any], verdict: str, hostname: str) -> str:
        resources = telemetry["resources"]
        ram_percent = float(resources.get("ram_used_percent", 0))
        disks = telemetry["disks"]
        gpu = resources.get("gpu", {})
        history = SREAgent._format_history_section(telemetry.get("stats_24h"))
        docker_status = SREAgent._format_docker_summary(telemetry["containers"], indented=False)
        return (
            f"📊 *REPORTE DIARIO DEL SERVIDOR: {hostname}*\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🧠 *ESTADO ACTUAL*\n• *CPU:* `{make_bar(resources.get('cpu_load_percent', 0))} {resources.get('cpu_load_percent', 0)}% ({resources.get('cpu_temp_c', 0)}°C)`\n"
            f"• *RAM:* `{make_bar(ram_percent)} {ram_percent:.1f}% ({resources.get('ram_used_gb', 0)} GB)`\n\n"
            f"🎮 *GPU*\n• *Temperatura:* `{gpu.get('temp_c', 'N/A')}°C` \n• *VRAM:* `{gpu.get('vram_used_mb', 0)} / {gpu.get('vram_total_mb', 0)} MB`\n\n"
            f"{history}\n\n"
            "💾 *ALMACENAMIENTO*\n"
            + "\n".join(
                f"• *{name}:* `{make_bar(value)} {value}%` {get_status_icon(value)}"
                for name, value in disks.items()
            )
            + f"\n\n🐳 *DOCKER*\n{docker_status}\n\n📦 *ACTUALIZACIONES*\n• *Pendientes:* `{telemetry['updates'].get('pending_updates', 0)}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n💡 *DIAGNÓSTICO SRE*\n{verdict.strip()}"
        )

    @staticmethod
    def _format_report(telemetry: dict[str, Any], verdict: str, hostname: str) -> str:
        resources, disks = telemetry["resources"], telemetry["disks"]
        ram_percent = float(resources.get("ram_used_percent", 0))
        gpu = resources.get("gpu", {})
        try:
            gpu_vram_used_mb = int(gpu.get("vram_used_mb", 0))
        except (TypeError, ValueError):
            gpu_vram_used_mb = 0
        history = SREAgent._format_history_section(telemetry.get("stats_24h"))
        docker_status = SREAgent._format_docker_summary(telemetry["containers"], indented=True)
        return f"""📊 *REPORTE DIARIO DEL SERVIDOR: {hostname}*
━━━━━━━━━━━━━━━━━━━━

🧠 *ESTADO ACTUAL*
• `CPU` `{make_bar(resources.get('cpu_load_percent', 0))}` {resources.get('cpu_load_percent', 0)}% ({resources.get('cpu_temp_c', 0)}°C)
• `RAM` `{make_bar(ram_percent)}` {ram_percent:.1f}% ({resources.get('ram_used_gb', 0)} GB)

🎮 *GPU*
• `Núcleo` {gpu.get('temp_c', 'N/A')}°C | `VRAM` {gpu_vram_used_mb} MB
{history}

💾 *ALMACENAMIENTO*
• `240GB SSD` `{make_bar(disks.get('root', 0))}` {disks.get('root', 0)}% {get_status_icon(disks.get('root', 0))}
• `8TB HDD` `{make_bar(disks.get('hdd8tb', 0))}` {disks.get('hdd8tb', 0)}% {get_status_icon(disks.get('hdd8tb', 0))}
• `1TB HDD` `{make_bar(disks.get('hdd1tb', 0))}` {disks.get('hdd1tb', 0)}% {get_status_icon(disks.get('hdd1tb', 0))}
• `SMART` {SREAgent._smart_status(telemetry)}

🐳 *DOCKER*
{docker_status}

📦 *SISTEMA*
• `Actualizaciones` {telemetry['updates'].get('pending_updates', 0)} pendientes

━━━━━━━━━━━━━━━━━━━━
💡 *Diagnóstico SRE:*
_{verdict}_"""

    @staticmethod
    def _format_info(info: dict[str, Any], hostname: str) -> str:
        system, cpu = info["system"], info["cpu"]
        memory, gpu = info["memory"], info["gpu"]
        if gpu.get("name"):
            gpu_memory = int(gpu.get("memory_total_mb", 0))
            gpu_text = f"`{gpu['name']}`\n  *VRAM:* `{gpu_memory} MB`\n  *Driver:* `{gpu.get('driver', 'N/A')}`"
        else:
            gpu_text = "`No disponible`"
        disk_lines = "\n".join(f"• *{name}:* `{value}%`" for name, value in info["disks"].items()) or "• No detectados"
        return (
            "🖥️ *INFORMACIÓN DEL EQUIPO*\n"
            f"📍 *Hostname:* `{hostname}`\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🧩 *SISTEMA*\n"
            f"• *SO:* `{system['os']}`\n"
            f"• *Kernel:* `{system['kernel']}`\n"
            f"• *Arquitectura:* `{system['architecture']}`\n"
            f"• *Procesador:* `{system['processor']}`\n\n"
            "⚙️ *CPU Y MEMORIA*\n"
            f"• *Núcleos:* `{cpu['physical_cores']} físicos / {cpu['logical_cores']} lógicos`\n"
            f"• *Frecuencia máxima:* `{cpu['frequency_mhz']} MHz`\n"
            f"• *RAM total:* `{memory['total_gb']} GB`\n\n"
            "🎮 *GRÁFICOS*\n"
            f"• *GPU:* {gpu_text}\n\n"
            "💾 *ALMACENAMIENTO*\n"
            f"{disk_lines}\n\n"
            "🐳 *DOCKER*\n"
            f"• *Contenedores:* `{info['docker_containers']}`"
        )
