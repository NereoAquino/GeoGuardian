"""Lee el id_proyecto de un proyecto administrado desde sus tres fuentes (D-34.3).

Solo biblioteca estandar, para poder probarlo sin QGIS. Nunca escribe nada.
"""

from __future__ import annotations

import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, Optional

from ..constantes import (
    AMBITO_PROPIEDADES,
    CARPETA_GEOGUARDIAN,
    CLAVE_ID_PROYECTO,
    NOMBRE_GEOPAQUETE,
    NOMBRE_MANIFIESTO,
    TABLA_PROYECTO,
)
from ..manifiesto.manifiesto import ManifiestoInvalido, leer_manifiesto

FUENTE_QGZ = "qgz"
FUENTE_MANIFIESTO = "manifiesto"
FUENTE_GEOPAQUETE = "geopaquete"


def id_desde_qgz(ruta_qgz: Path) -> Optional[str]:
    """Entrada <properties><geoguardian><id_proyecto> del .qgs dentro del .qgz (D-08)."""
    try:
        with zipfile.ZipFile(str(ruta_qgz)) as archivo:
            nombres = [n for n in archivo.namelist() if n.lower().endswith(".qgs")]
            if not nombres:
                return None
            raiz = ET.fromstring(archivo.read(nombres[0]))
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError):
        return None
    nodo = raiz.find("properties/{}/{}".format(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO.strip("/")))
    texto = (nodo.text or "").strip() if nodo is not None else ""
    return texto or None


def id_desde_geopaquete(ruta_gpkg: Path) -> Optional[str]:
    if not ruta_gpkg.is_file():
        return None
    try:
        uri = "{}?mode=ro".format(ruta_gpkg.resolve().as_uri())
        con = sqlite3.connect(uri, uri=True)
        try:
            filas = con.execute("SELECT id_proyecto FROM {}".format(TABLA_PROYECTO)).fetchall()
        finally:
            con.close()
    except (sqlite3.Error, ValueError, OSError):
        return None
    return str(filas[0][0]) if len(filas) == 1 and filas[0][0] else None


def leer_ids(ruta_qgz) -> Dict[str, str]:
    """id_proyecto de cada fuente disponible; las que no existen o no se leen no aparecen."""
    ruta = Path(ruta_qgz)
    carpeta = ruta.parent
    ids: Dict[str, str] = {}
    valor = id_desde_qgz(ruta)
    if valor:
        ids[FUENTE_QGZ] = valor
    try:
        ids[FUENTE_MANIFIESTO] = str(
            leer_manifiesto(carpeta / CARPETA_GEOGUARDIAN / NOMBRE_MANIFIESTO)["id_proyecto"]
        )
    except ManifiestoInvalido:
        pass
    valor = id_desde_geopaquete(carpeta / NOMBRE_GEOPAQUETE)
    if valor:
        ids[FUENTE_GEOPAQUETE] = valor
    return ids
