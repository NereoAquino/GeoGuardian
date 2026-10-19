"""Clasificacion de recursos (especificacion v0.1.0, seccion 5). Modulo puro."""

from __future__ import annotations

import os
from typing import Iterable, Optional

from ..constantes import PROVEEDOR_MEMORIA
from .modelos import DescripcionFuente, EstadoRecurso


def normalizar_ruta(ruta: str) -> str:
    """Ruta absoluta, sin enlaces simbolicos y sin distinguir mayusculas en Windows."""
    return os.path.normcase(os.path.realpath(os.path.abspath(ruta)))


def esta_dentro(ruta: str, carpeta: str) -> bool:
    """Indica si `ruta` es `carpeta` o esta dentro de ella."""
    ruta_n = normalizar_ruta(ruta)
    carpeta_n = normalizar_ruta(carpeta)
    try:
        return os.path.commonpath([ruta_n, carpeta_n]) == carpeta_n
    except ValueError:
        # Unidades distintas en Windows (C: frente a D:).
        return False


def ruta_relativa(ruta: Optional[str], carpeta: str) -> Optional[str]:
    """Ruta relativa a la carpeta del proyecto, con '/' como separador, o None."""
    if not ruta or not esta_dentro(ruta, carpeta):
        return None
    relativa = os.path.relpath(normalizar_ruta(ruta), normalizar_ruta(carpeta))
    return relativa.replace(os.sep, "/")


def clasificar_recurso(
    descripcion: DescripcionFuente,
    carpeta_proyecto: str,
    carpetas_temporales: Iterable[str] = (),
) -> EstadoRecurso:
    """Prioridad: faltante > temporal > activo > externo.

    `historico` nunca sale de aqui: solo se asigna al eliminar una capa.
    """
    ruta = descripcion.ruta_archivo
    if not descripcion.es_valida or (ruta and not descripcion.existe):
        return EstadoRecurso.FALTANTE
    if descripcion.proveedor == PROVEEDOR_MEMORIA:
        return EstadoRecurso.TEMPORAL
    if ruta and any(esta_dentro(ruta, t) for t in carpetas_temporales if t):
        return EstadoRecurso.TEMPORAL
    if ruta and esta_dentro(ruta, carpeta_proyecto):
        return EstadoRecurso.ACTIVO
    return EstadoRecurso.EXTERNO
