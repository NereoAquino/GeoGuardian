"""Migraciones del esquema de Proyecto.gpkg (D-25, D-33): 1 -> 3 y 2 -> 3. Sin Qt ni QGIS."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Union

from ..constantes import TABLA_PROYECTO, VERSION_ESQUEMA
from .geopaquete import transaccion

Ruta = Union[str, Path]

COLUMNAS_ESQUEMA_2 = (
    ("nombre_academico", "TEXT"),
    ("ruta_proyecto_origen", "TEXT"),
    ("ruta_proyecto_administrado", "TEXT"),
    ("ruta_respaldo", "TEXT"),
    ("tipo_ubicacion", "TEXT"),
)

# Identidad del volumen (D-33). La migracion solo agrega las columnas; los valores los completa
# AdministradorProyecto al abrir, porque este modulo no consulta discos.
COLUMNAS_ESQUEMA_3 = COLUMNAS_ESQUEMA_2 + (
    ("etiqueta_volumen", "TEXT"),
    ("sistema_archivos", "TEXT"),
    ("ruta_en_volumen", "TEXT"),
    ("etiqueta_volumen_respaldo", "TEXT"),
    ("ruta_respaldo_en_volumen", "TEXT"),
)

COLUMNAS_ACTUALES = COLUMNAS_ESQUEMA_3


class ErrorMigracion(Exception):
    pass


def version_actual(ruta: Ruta) -> int:
    with transaccion(ruta) as con:
        filas = con.execute("SELECT version_esquema FROM {t}".format(t=TABLA_PROYECTO)).fetchall()
    if len(filas) != 1:
        raise ErrorMigracion("Proyecto.gpkg debe tener exactamente un registro de proyecto")
    return int(filas[0][0])


def migrar(
    ruta: Ruta,
    ruta_proyecto_administrado: str,
    al_agregar_columna: Optional[Callable[[str], None]] = None,
) -> Optional[int]:
    """Lleva Proyecto.gpkg al esquema actual en una sola transaccion.

    Idempotente: solo agrega columnas que falten. `version_esquema` se actualiza al final,
    despues de todos los cambios. Devuelve la version anterior si migro, o None si no hizo falta.
    `al_agregar_columna` existe para que las pruebas simulen un fallo a mitad.
    """
    with transaccion(ruta) as con:
        filas = con.execute("SELECT version_esquema FROM {t}".format(t=TABLA_PROYECTO)).fetchall()
        if len(filas) != 1:
            raise ErrorMigracion("Proyecto.gpkg debe tener exactamente un registro de proyecto")
        anterior = int(filas[0][0])
        if anterior > VERSION_ESQUEMA:
            return None  # creado por una version mas nueva de GeoGuardian: no se toca
        existentes = {f["name"] for f in con.execute("PRAGMA table_info({t})".format(t=TABLA_PROYECTO))}
        faltantes = [(n, tipo) for n, tipo in COLUMNAS_ACTUALES if n not in existentes]
        if anterior == VERSION_ESQUEMA and not faltantes:
            return None
        for nombre, tipo in faltantes:
            con.execute("ALTER TABLE {t} ADD COLUMN {n} {tipo}".format(t=TABLA_PROYECTO, n=nombre, tipo=tipo))
            if al_agregar_columna is not None:
                al_agregar_columna(nombre)
        con.execute(
            "UPDATE {t} SET ruta_proyecto_administrado = ? WHERE ruta_proyecto_administrado IS NULL".format(
                t=TABLA_PROYECTO
            ),
            (ruta_proyecto_administrado,),
        )
        con.execute("UPDATE {t} SET version_esquema = ?".format(t=TABLA_PROYECTO), (VERSION_ESQUEMA,))
    return anterior
