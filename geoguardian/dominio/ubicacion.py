"""Reglas sobre el destino del proyecto (D-23, D-24). Modulo puro."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Optional

from .clasificacion import esta_dentro

UMBRAL_POCO_ESPACIO = 5 * 1024 ** 3
LONGITUD_MAXIMA_RUTA = 200
SISTEMAS_FAT32 = frozenset({"fat32", "vfat", "msdos"})


class TipoUbicacion(str, Enum):
    DISCO_LOCAL = "disco_local"
    UNIDAD_EXTERNA = "unidad_externa"
    OTRA = "otra"


@dataclass(frozen=True)
class InfoVolumen:
    raiz: str
    sistema_archivos: str
    bytes_libres: int
    solo_lectura: bool = False
    listo: bool = True
    nombre: str = ""  # nombre para mostrar (la etiqueta o, si no tiene, la raiz)
    etiqueta: str = ""  # etiqueta del volumen; vacia si no tiene (D-33)


@dataclass(frozen=True)
class Aviso:
    codigo: str
    mensaje: str
    bloqueante: bool = False


def es_fat32(sistema_archivos: str) -> bool:
    return (sistema_archivos or "").strip().lower() in SISTEMAS_FAT32


def gigabytes(cantidad_bytes: int) -> str:
    return "{:.1f} GB".format(max(cantidad_bytes, 0) / 1024 ** 3)


def misma_unidad(raiz_a: Optional[str], raiz_b: Optional[str]) -> bool:
    if not raiz_a or not raiz_b:
        return False

    def limpiar(raiz: str) -> str:
        return os.path.normcase(raiz).rstrip("\\/") or os.sep

    return limpiar(raiz_a) == limpiar(raiz_b)


def evaluar_destino(
    ruta_proyecto: str,
    volumen: InfoVolumen,
    raiz_documentos: Optional[str],
    raices_onedrive: Iterable[str] = (),
    ruta_respaldo: Optional[str] = None,
    respaldo_existe: bool = False,
    volumen_respaldo: Optional[InfoVolumen] = None,
) -> List[Aviso]:
    """Avisos para el destino elegido. Solo los marcados como bloqueantes impiden continuar."""
    avisos: List[Aviso] = []
    if not volumen.listo:
        avisos.append(Aviso("no_disponible", "La unidad de destino no esta disponible", True))
    if volumen.solo_lectura:
        avisos.append(Aviso("solo_lectura", "La unidad de destino es de solo lectura", True))
    if volumen.bytes_libres <= 0:
        avisos.append(Aviso("sin_espacio", "La unidad de destino no tiene espacio libre", True))
    elif volumen.bytes_libres < UMBRAL_POCO_ESPACIO:
        avisos.append(Aviso(
            "poco_espacio",
            "Quedan {} libres; las imagenes satelitales y de dron pueden ocupar mucho mas".format(
                gigabytes(volumen.bytes_libres)
            ),
        ))
    if raiz_documentos and not misma_unidad(volumen.raiz, raiz_documentos):
        avisos.append(Aviso(
            "unidad_externa",
            "El destino no esta en el disco local: puede ser mas lento, desconectarse durante "
            "el trabajo y quedarse sin espacio",
        ))
    if es_fat32(volumen.sistema_archivos):
        avisos.append(Aviso(
            "fat32",
            "La unidad usa FAT32 y no admite archivos de mas de 4 GB "
            "(imagenes satelitales, ortomosaicos)",
        ))
    if any(raiz and esta_dentro(ruta_proyecto, raiz) for raiz in raices_onedrive):
        avisos.append(Aviso(
            "onedrive",
            "El destino esta dentro de OneDrive: la sincronizacion puede bloquear o duplicar "
            "Proyecto.gpkg y subir datos pesados (aviso informativo)",
        ))
    if len(ruta_proyecto) > LONGITUD_MAXIMA_RUTA:
        avisos.append(Aviso(
            "ruta_larga",
            "La ruta del proyecto tiene {} caracteres; Windows puede fallar con rutas largas".format(
                len(ruta_proyecto)
            ),
        ))
    if ruta_respaldo:
        if not respaldo_existe:
            avisos.append(Aviso("respaldo_inexistente", "La carpeta de respaldo no existe", True))
        elif volumen_respaldo is not None and misma_unidad(volumen_respaldo.raiz, volumen.raiz):
            avisos.append(Aviso(
                "respaldo_misma_unidad",
                "La carpeta de respaldo esta en la misma unidad que el proyecto: "
                "no lo protege si el disco falla",
            ))
    return avisos
