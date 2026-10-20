"""Nombres ocupados en Proyecto.gpkg, leidos sin escribir (D-63).

Conexion SQLite de solo lectura (`mode=ro`) y de vida corta, como
`administracion.identidad_proyecto.id_desde_geopaquete`. No se usa
`persistencia.geopaquete.tablas_presentes()`, que abre el archivo en lectura y escritura.

Se leen todos los objetos de `sqlite_master` (tablas, vistas, indices, disparadores, rtree_* y
gg_*): comparten el espacio de nombres de SQLite y ninguno puede pisarse. `gpkg_contents` se lee
tambien por si registra algun nombre que aun no tenga tabla.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import FrozenSet, Optional, Union

TIEMPO_ESPERA_SEGUNDOS = 2

CONSULTA_OBJETOS = "SELECT name FROM sqlite_master WHERE name IS NOT NULL"
CONSULTA_CONTENIDOS = "SELECT table_name FROM gpkg_contents WHERE table_name IS NOT NULL"


def uri_solo_lectura(ruta: Union[str, Path]) -> str:
    return "{}?mode=ro".format(Path(ruta).resolve().as_uri())


def nombres_ocupados(ruta: Union[str, Path]) -> Optional[FrozenSet[str]]:
    """Todos los nombres de Proyecto.gpkg; None si no se puede leer."""
    if not Path(ruta).is_file():
        return None
    try:
        conexion = sqlite3.connect(uri_solo_lectura(ruta), uri=True, timeout=TIEMPO_ESPERA_SEGUNDOS)
        try:
            nombres = {fila[0] for fila in conexion.execute(CONSULTA_OBJETOS)}
            try:
                nombres |= {fila[0] for fila in conexion.execute(CONSULTA_CONTENIDOS)}
            except sqlite3.Error:
                pass  # sin gpkg_contents no es un GeoPackage completo, pero sqlite_master basta
        finally:
            conexion.close()
    except (sqlite3.Error, ValueError, OSError):
        return None
    return frozenset(str(n) for n in nombres)
