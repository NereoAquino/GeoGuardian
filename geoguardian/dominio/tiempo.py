"""Fechas y horas en ISO 8601 con desplazamiento local (D-14)."""

from datetime import datetime


def ahora_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
