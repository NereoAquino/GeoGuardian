"""Adaptador QGIS del inventario: lee cada capa y la traduce a `EntradaCapa` (D-44, D-52).

Solo lectura: consulta la capa, su proveedor y el sistema de archivos; nunca escribe, nunca cambia
fuentes ni SRC y nunca abre Proyecto.gpkg (D-40). Reutiliza las funciones publicas de
monitoreo/descriptor_fuente.py; la decodificacion adicional vive aqui (D-52).
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDataSourceUri,
    QgsProviderRegistry,
    QgsVectorLayer,
)

from ..constantes import PROVEEDOR_MEMORIA
from ..contexto import ContextoProyecto
from ..dominio.clasificacion_inventario import (
    PROVEEDOR_VIRTUAL,
    PROVEEDORES_BASE_DATOS,
    url_sin_credenciales,
)
from ..dominio.inventario import DatosSrc, EntradaCapa
from ..dominio.recuperacion import unidad_ausente
from ..dominio.seguridad import ocultar_contrasenas
from ..monitoreo.descriptor_fuente import es_tabla_de_control, ruta_de_capa, tipo_de_capa

_PREFIJOS_REMOTOS = ("/vsicurl", "/vsis3", "/vsigs", "/vsiaz", "/vsiadls", "/vsioss", "/vsiswift", "/vsihdfs", "/vsiwebhdfs")
_ESQUEMAS_REMOTOS = ("http:", "https:", "ftp:")


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def partes_de_fuente(capa) -> dict:
    """decodeUri del proveedor. Puede traer la contrasena (postgres): nunca registrar el resultado."""
    try:
        return dict(QgsProviderRegistry.instance().decodeUri(capa.providerType(), capa.source()))
    except Exception:  # noqa: BLE001
        return {}


def es_ruta_remota(ruta: str) -> bool:
    return ruta.startswith(_PREFIJOS_REMOTOS) or ruta.lower().startswith(_ESQUEMAS_REMOTOS)


def datos_src(src: QgsCoordinateReferenceSystem) -> DatosSrc:
    if src is None or not src.isValid():
        return DatosSrc(valido=False)
    return DatosSrc(valido=True, identificador=src.authid(), descripcion=src.description())


def _subcapa_de_archivo(partes: dict) -> str:
    sufijo = _texto(partes.get("vsiSuffix")).strip("/")
    nombre = _texto(partes.get("layerName"))
    if not nombre and partes.get("layerId") not in (None, ""):
        nombre = "id:{}".format(partes.get("layerId"))
    return "/".join(p for p in (sufijo, nombre) if p)


def _parametros_de_archivo(partes: dict) -> Tuple[Tuple[str, str], ...]:
    """Opciones que cambian el dataset (por ejemplo, columnas X/Y de un CSV)."""
    opciones = partes.get("openOptions") or []
    if not isinstance(opciones, (list, tuple)):
        return ()
    pares = []
    for opcion in opciones:
        nombre, _, valor = str(opcion).partition("=")
        if nombre.lower() not in ("password", "pwd", "passwd", "user", "username"):
            pares.append((nombre, valor))
    return tuple(sorted(pares))


def _identidad_sin_archivo(capa) -> Tuple[str, str, Tuple[Tuple[str, str], ...]]:
    """Contenedor, subcapa y parametros de servicios, bases de datos y capas virtuales."""
    proveedor = capa.providerType().lower()
    if proveedor == PROVEEDOR_MEMORIA:
        return "memoria", "", ()
    if proveedor == PROVEEDOR_VIRTUAL:
        return "virtual", ocultar_contrasenas(capa.publicSource()), ()
    uri = QgsDataSourceUri(capa.source())
    if proveedor in PROVEEDORES_BASE_DATOS:
        if uri.service():
            contenedor = "{}://service={}".format(proveedor, uri.service())
        else:
            contenedor = "{}://{}:{}/{}".format(proveedor, uri.host(), uri.port(), uri.database())
        tabla = ".".join(p for p in (uri.schema(), uri.table()) if p)
        parametros = (("geometria", uri.geometryColumn()),) if uri.geometryColumn() else ()
        return contenedor, tabla, parametros
    url = uri.param("url")
    if url:
        return url_sin_credenciales(url), uri.param("typename"), ()
    return ocultar_contrasenas(capa.publicSource()), "", ()


def _es_mismo_archivo(ruta: Optional[str], otra: str) -> bool:
    if not ruta or not os.path.exists(ruta) or not os.path.exists(otra):
        return False
    try:
        return os.path.samefile(ruta, otra)
    except OSError:
        return False


def leer_capa(capa, contexto: ContextoProyecto, src_proyecto: QgsCoordinateReferenceSystem) -> EntradaCapa:
    proveedor = capa.providerType()
    tipo = tipo_de_capa(capa)
    partes = partes_de_fuente(capa)
    ruta_decodificada = _texto(partes.get("path"))
    ruta_local = ruta_de_capa(capa)  # misma ruta que usa v0.1.0 (D-42)
    remota = bool(ruta_decodificada) and es_ruta_remota(ruta_decodificada) and not ruta_local
    if ruta_local:
        contenedor, subcapa, parametros = "", _subcapa_de_archivo(partes), _parametros_de_archivo(partes)
    elif remota:
        contenedor, subcapa, parametros = url_sin_credenciales(ruta_decodificada), _subcapa_de_archivo(partes), ()
    else:
        contenedor, subcapa, parametros = _identidad_sin_archivo(capa)
    existe = bool(ruta_local) and os.path.exists(ruta_local)
    es_vector = isinstance(capa, QgsVectorLayer)
    src = capa.crs()
    proveedor_datos = capa.dataProvider() if es_vector else None
    # D-48: en QGIS 3.28 sourceCrs() devuelve el SRC asignado a la capa; el de la fuente es el
    # del proveedor de datos.
    src_fuente = proveedor_datos.crs() if proveedor_datos is not None else QgsCoordinateReferenceSystem()
    return EntradaCapa(
        id_capa=capa.id(),
        nombre=capa.name(),
        tipo_capa=tipo,
        proveedor=proveedor,
        es_valida=capa.isValid(),
        es_espacial=bool(es_vector and capa.isSpatial()),
        ruta_local=ruta_local,
        ruta_remota=remota,
        contenedor=contenedor,
        subcapa=subcapa,
        parametros=parametros,
        existe=existe,
        unidad_ausente=bool(ruta_local) and not existe and unidad_ausente(ruta_local, os.path.exists),
        es_geopaquete_activo=_es_mismo_archivo(ruta_local, str(contexto.ruta_geopaquete)),
        es_tabla_control=es_tabla_de_control(capa, contexto.ruta_geopaquete),
        src=datos_src(src),
        src_fuente=datos_src(src_fuente),
        src_igual_proyecto=bool(src.isValid() and src_proyecto.isValid() and src == src_proyecto),
        src_igual_fuente=bool(not src.isValid() or not src_fuente.isValid() or src == src_fuente),
    )
