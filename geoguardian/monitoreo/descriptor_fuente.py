"""Traduce una QgsMapLayer a los datos que necesitan el dominio y la persistencia."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from qgis.core import (
    QgsMeshLayer,
    QgsPointCloudLayer,
    QgsProviderRegistry,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QUrl

from ..constantes import PROVEEDOR_MEMORIA, TABLAS_CONTROL
from ..dominio.modelos import DescripcionFuente
from ..dominio.seguridad import ocultar_contrasenas

# Prefijos GDAL de archivos remotos: no son rutas locales.
_PREFIJOS_REMOTOS = ("/vsicurl", "/vsis3", "/vsigs", "/vsiaz", "/vsiadls", "/vsioss", "/vsiswift", "/vsihdfs", "/vsiwebhdfs")


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def _partes_fuente(capa) -> dict:
    try:
        return dict(QgsProviderRegistry.instance().decodeUri(capa.providerType(), capa.source()))
    except Exception:
        return {}


def ruta_de_capa(capa) -> Optional[str]:
    """Ruta del archivo local de la capa, o None si no tiene (memoria, servicio, BD)."""
    if capa.providerType() == PROVEEDOR_MEMORIA:
        return None
    ruta = _texto(_partes_fuente(capa).get("path"))
    if not ruta:
        fuente = capa.source()
        if fuente.lower().startswith("file:"):
            ruta = QUrl(fuente.split("?")[0]).toLocalFile()
    if not ruta or ruta.lower().startswith(("http:", "https:", "ftp:")):
        return None
    if ruta.startswith(_PREFIJOS_REMOTOS):
        return None
    return ruta


def tipo_de_capa(capa) -> str:
    if isinstance(capa, QgsVectorLayer):
        return "vectorial"
    if isinstance(capa, QgsRasterLayer):
        return "raster"
    if isinstance(capa, QgsMeshLayer):
        return "malla"
    if isinstance(capa, QgsPointCloudLayer):
        return "nube_puntos"
    return "otro"


def describir_capa(capa) -> DescripcionFuente:
    ruta = ruta_de_capa(capa)
    return DescripcionFuente(
        proveedor=capa.providerType(),
        ruta_archivo=ruta,
        existe=bool(ruta) and os.path.exists(ruta),
        es_valida=capa.isValid(),
    )


def fuente_publica(capa) -> str:
    """Fuente sin contrasenas (D-13)."""
    return ocultar_contrasenas(capa.publicSource())


def es_tabla_de_control(capa, ruta_geopaquete: Path) -> bool:
    """Las tablas gg_* cargadas como capa no se monitorean."""
    ruta = ruta_de_capa(capa)
    if not ruta or not os.path.exists(ruta) or not ruta_geopaquete.exists():
        return False
    try:
        mismo_archivo = os.path.samefile(ruta, str(ruta_geopaquete))
    except OSError:
        return False
    return mismo_archivo and _texto(_partes_fuente(capa).get("layerName")) in TABLAS_CONTROL
