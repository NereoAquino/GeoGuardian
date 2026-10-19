"""Estructura de carpetas del proyecto administrado (D-03). Sin QGIS."""

from __future__ import annotations

from pathlib import Path
from typing import List, Union

from ..constantes import CARPETAS_PROYECTO


class CarpetaNoDisponible(Exception):
    pass


def carpeta_disponible(carpeta: Union[str, Path]) -> bool:
    """Verdadero si la carpeta no existe o existe y esta vacia."""
    carpeta = Path(carpeta)
    if not carpeta.exists():
        return True
    return carpeta.is_dir() and not any(carpeta.iterdir())


def crear_estructura(carpeta: Union[str, Path]) -> List[Path]:
    """Crea la carpeta del proyecto y sus subcarpetas. Nunca escribe en una carpeta con contenido."""
    carpeta = Path(carpeta)
    if not carpeta_disponible(carpeta):
        raise CarpetaNoDisponible(
            "La carpeta {} ya existe y no esta vacia; elige otra".format(carpeta)
        )
    creadas = []
    if not carpeta.exists():
        carpeta.mkdir(parents=True)
        creadas.append(carpeta)
    for nombre in CARPETAS_PROYECTO:
        subcarpeta = carpeta / nombre
        subcarpeta.mkdir()
        creadas.append(subcarpeta)
    return creadas
