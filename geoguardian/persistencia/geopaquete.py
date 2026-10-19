"""Creacion de Proyecto.gpkg y de las tablas de control (D-05, D-07, D-10).

El contenedor se crea con GDAL; todo lo demas usa sqlite3 de la biblioteca estandar.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, List, Set, Union

from ..constantes import TABLA_EVENTOS, TABLA_PROYECTO, TABLA_RECURSOS, TABLAS_CONTROL
from ..dominio.modelos import EstadoRecurso

Ruta = Union[str, Path]

TIEMPO_ESPERA_SEGUNDOS = 5

_ESTADOS_SQL = ", ".join("'{}'".format(e.value) for e in EstadoRecurso)

ESQUEMA_SQL = (
    """
    CREATE TABLE {t} (
        id_proyecto          TEXT PRIMARY KEY,
        titulo               TEXT NOT NULL,
        descripcion          TEXT,
        nombre_estudiante    TEXT NOT NULL,
        correo               TEXT NOT NULL,
        grupo                TEXT NOT NULL,
        asignatura           TEXT NOT NULL,
        fecha_creacion       TEXT NOT NULL,
        fecha_actualizacion  TEXT NOT NULL,
        version_esquema      INTEGER NOT NULL,
        version_complemento  TEXT NOT NULL,
        version_qgis         TEXT NOT NULL,
        nombre_academico           TEXT,
        ruta_proyecto_origen       TEXT,
        ruta_proyecto_administrado TEXT,
        ruta_respaldo              TEXT,
        tipo_ubicacion             TEXT,
        etiqueta_volumen           TEXT,
        sistema_archivos           TEXT,
        ruta_en_volumen            TEXT,
        etiqueta_volumen_respaldo  TEXT,
        ruta_respaldo_en_volumen   TEXT
    )
    """.format(t=TABLA_PROYECTO),
    """
    CREATE TABLE {t} (
        id_recurso           INTEGER PRIMARY KEY AUTOINCREMENT,
        id_capa              TEXT NOT NULL,
        nombre               TEXT NOT NULL,
        tipo_capa            TEXT NOT NULL,
        proveedor            TEXT NOT NULL,
        fuente               TEXT NOT NULL,
        ruta_relativa        TEXT,
        estado               TEXT NOT NULL CHECK (estado IN ({estados})),
        fecha_alta           TEXT NOT NULL,
        fecha_baja           TEXT,
        fecha_verificacion   TEXT NOT NULL
    )
    """.format(t=TABLA_RECURSOS, estados=_ESTADOS_SQL),
    "CREATE INDEX gg_recursos_id_capa ON {t}(id_capa)".format(t=TABLA_RECURSOS),
    """
    CREATE TABLE {t} (
        id_evento            INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_hora           TEXT NOT NULL,
        tipo_evento          TEXT NOT NULL,
        id_capa              TEXT,
        descripcion          TEXT NOT NULL,
        detalle              TEXT,
        version_complemento  TEXT NOT NULL
    )
    """.format(t=TABLA_EVENTOS),
    "CREATE INDEX gg_eventos_fecha ON {t}(fecha_hora)".format(t=TABLA_EVENTOS),
)

_DESCRIPCIONES_TABLAS = {
    TABLA_PROYECTO: "GeoGuardian: datos del proyecto administrado",
    TABLA_RECURSOS: "GeoGuardian: recursos (capas) del proyecto y su estado",
    TABLA_EVENTOS: "GeoGuardian: registro de eventos",
}


class ErrorGeopaquete(Exception):
    pass


def conectar(ruta: Ruta) -> sqlite3.Connection:
    """Conexion de vida corta (D-05).

    No se cambia el modo de diario: GDAL crea el archivo en modo DELETE, y si QGIS tiene
    el GeoPackage abierto puede haberlo pasado a WAL; forzar el cambio bloquearia la base.
    """
    conexion = sqlite3.connect(str(ruta), timeout=TIEMPO_ESPERA_SEGUNDOS)
    conexion.row_factory = sqlite3.Row
    return conexion


@contextmanager
def transaccion(ruta: Ruta) -> Iterator[sqlite3.Connection]:
    """Abre, ejecuta en una transaccion (confirma o revierte) y cierra.

    BEGIN explicito: el modulo sqlite3 no abre transaccion antes de CREATE o ALTER TABLE, y la
    migracion (D-25) debe revertirse completa si falla a mitad.
    """
    conexion = conectar(ruta)
    conexion.isolation_level = None
    try:
        conexion.execute("BEGIN")
        try:
            yield conexion
        except BaseException:
            conexion.execute("ROLLBACK")
            raise
        conexion.execute("COMMIT")
    finally:
        conexion.close()


def crear_contenedor_gdal(ruta: Ruta) -> None:
    """Crea un GeoPackage vacio y valido con el controlador GPKG de GDAL."""
    from osgeo import ogr  # incluido en QGIS; importacion diferida

    controlador = ogr.GetDriverByName("GPKG")
    if controlador is None:
        raise ErrorGeopaquete("GDAL no tiene disponible el controlador GPKG")
    fuente = controlador.CreateDataSource(str(ruta))
    if fuente is None:
        raise ErrorGeopaquete("GDAL no pudo crear {}".format(ruta))
    fuente = None  # cierra el archivo


def aplicar_esquema(ruta: Ruta, fecha: str) -> None:
    """Crea las tablas gg_* y las registra en gpkg_contents como 'attributes'."""
    with transaccion(ruta) as con:
        for sentencia in ESQUEMA_SQL:
            con.execute(sentencia)
        for tabla in TABLAS_CONTROL:
            con.execute(
                "INSERT INTO gpkg_contents (table_name, data_type, identifier, description, last_change)"
                " VALUES (?, 'attributes', ?, ?, ?)",
                (tabla, tabla, _DESCRIPCIONES_TABLAS[tabla], _fecha_gpkg(fecha)),
            )


def crear_geopaquete(
    ruta: Ruta,
    fecha: str,
    crear_contenedor: Callable[[Ruta], None] = crear_contenedor_gdal,
) -> None:
    ruta = Path(ruta)
    if ruta.exists():
        raise ErrorGeopaquete("Ya existe {}; no se sobrescribe".format(ruta))
    crear_contenedor(ruta)
    aplicar_esquema(ruta, fecha)


def tablas_presentes(ruta: Ruta) -> Set[str]:
    with transaccion(ruta) as con:
        filas = con.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {f["name"] for f in filas}


def problemas_esquema(ruta: Ruta) -> List[str]:
    """Lista legible de problemas del GeoPackage; vacia si esta bien."""
    ruta = Path(ruta)
    if not ruta.is_file():
        return ["No se encuentra {}".format(ruta.name)]
    try:
        presentes = tablas_presentes(ruta)
    except sqlite3.DatabaseError as error:
        return ["{} no se puede leer: {}".format(ruta.name, error)]
    faltantes = [t for t in TABLAS_CONTROL if t not in presentes]
    if faltantes:
        return ["Faltan tablas de control en {}: {}".format(ruta.name, ", ".join(faltantes))]
    return []


def _fecha_gpkg(fecha_iso: str) -> str:
    """gpkg_contents.last_change exige el formato 'YYYY-MM-DDTHH:MM:SS.SSSZ' en UTC."""
    from datetime import datetime, timezone

    momento = datetime.fromisoformat(fecha_iso).astimezone(timezone.utc)
    return momento.strftime("%Y-%m-%dT%H:%M:%S.") + "{:03d}Z".format(momento.microsecond // 1000)
