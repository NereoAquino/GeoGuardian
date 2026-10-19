"""Cuando advertir al cerrar un proyecto no administrado (D-18). Modulo puro."""

from enum import Enum


class AccionCierre(str, Enum):
    INICIALIZAR = "inicializar"
    ABRIR_VERSION = "abrir_version"
    CERRAR = "cerrar"
    CANCELAR = "cancelar"


def requiere_advertencia(administrado: bool, tiene_archivo: bool, numero_capas: int) -> bool:
    """Un proyecto nuevo, vacio y nunca guardado no genera advertencia."""
    return not administrado and (tiene_archivo or numero_capas > 0)
