"""Manifiesto JSON del proyecto administrado (D-06). Sin Qt ni QGIS."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Union

from ..constantes import (
    FORMATO_MANIFIESTO,
    NOMBRE_ARCHIVO_PROYECTO,
    NOMBRE_GEOPAQUETE,
    VERSION_COMPLEMENTO,
    VERSION_ESQUEMA,
)
from ..dominio.modelos import EstadoRecurso, NivelSemaforo

Ruta = Union[str, Path]


class ManifiestoInvalido(Exception):
    pass


def construir_manifiesto(
    proyecto: Mapping[str, Any],
    conteo: Mapping[EstadoRecurso, int],
    nivel: NivelSemaforo,
    version_qgis: str,
    archivo_proyecto: str = NOMBRE_ARCHIVO_PROYECTO,
) -> Dict[str, Any]:
    """`proyecto` es la fila de gg_proyecto como diccionario."""
    return {
        "formato": FORMATO_MANIFIESTO,
        "version_esquema": VERSION_ESQUEMA,
        "version_complemento": VERSION_COMPLEMENTO,
        "version_qgis": version_qgis,
        "id_proyecto": proyecto["id_proyecto"],
        "titulo": proyecto["titulo"],
        "descripcion": proyecto.get("descripcion") or "",
        "autor": {
            "nombre": proyecto["nombre_estudiante"],
            "correo": proyecto["correo"],
            "grupo": proyecto["grupo"],
        },
        "asignatura": proyecto["asignatura"],
        "archivos": {"proyecto": archivo_proyecto, "geopaquete": NOMBRE_GEOPAQUETE},
        "fecha_creacion": proyecto["fecha_creacion"],
        "fecha_actualizacion": proyecto["fecha_actualizacion"],
        # Esquema 2 (D-25): un lector rc1 ignora estas claves.
        "nombre_academico": proyecto.get("nombre_academico") or "",
        "tipo_ubicacion": proyecto.get("tipo_ubicacion") or "",
        "rutas": {
            "origen": proyecto.get("ruta_proyecto_origen"),
            "administrado": proyecto.get("ruta_proyecto_administrado"),
            "respaldo": proyecto.get("ruta_respaldo"),
        },
        # Esquema 3 (D-33): identidad del volumen; la letra de unidad no forma parte de ella.
        "ubicacion": {
            "etiqueta_volumen": proyecto.get("etiqueta_volumen") or "",
            "sistema_archivos": proyecto.get("sistema_archivos") or "",
            "ruta_en_volumen": proyecto.get("ruta_en_volumen") or "",
        },
        "respaldo": {
            "etiqueta_volumen": proyecto.get("etiqueta_volumen_respaldo") or "",
            "ruta_en_volumen": proyecto.get("ruta_respaldo_en_volumen") or "",
        },
        "resumen_recursos": {e.value: int(conteo.get(e, 0)) for e in EstadoRecurso},
        "estado_semaforo": NivelSemaforo(nivel).value,
    }


def escribir_manifiesto(ruta: Ruta, datos: Mapping[str, Any]) -> None:
    """Escritura atomica: archivo temporal en la misma carpeta y os.replace."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporal = tempfile.mkstemp(prefix=".manifiesto-", suffix=".tmp", dir=str(ruta.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
            archivo.write("\n")
        os.replace(temporal, str(ruta))
    except BaseException:
        if os.path.exists(temporal):
            os.remove(temporal)  # temporal propio del complemento, nunca un archivo del usuario
        raise


def leer_manifiesto(ruta: Ruta) -> Dict[str, Any]:
    ruta = Path(ruta)
    try:
        with open(str(ruta), encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except FileNotFoundError:
        raise ManifiestoInvalido("No se encuentra el manifiesto")
    except (OSError, ValueError) as error:
        raise ManifiestoInvalido("El manifiesto no se puede leer: {}".format(error))
    if not isinstance(datos, dict) or datos.get("formato") != FORMATO_MANIFIESTO:
        raise ManifiestoInvalido("El manifiesto no tiene el formato de GeoGuardian")
    if not datos.get("id_proyecto"):
        raise ManifiestoInvalido("El manifiesto no tiene id_proyecto")
    return datos
