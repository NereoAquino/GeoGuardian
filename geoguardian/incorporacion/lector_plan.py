"""Adaptador QGIS del plan: lee de cada capa lo que el inventario no guarda (D-56, D-60, D-61, D-64).

Solo lectura: consulta la capa, su proveedor y el sistema de archivos. Nunca escribe, nunca cambia
fuentes, filtros ni SRC, y nunca inicia ni termina una edicion. Reutiliza funciones publicas del
Hito 1 (`inventario.lector_capas`) y de `monitoreo.descriptor_fuente` sin modificarlas.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

from qgis.core import (
    QgsDataProvider,
    QgsFeatureRequest,
    QgsFields,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from ..constantes import PROVEEDOR_MEMORIA
from ..dominio.plan_incorporacion import (
    FID_AUSENTE,
    FID_CLAVE,
    FID_ENTERO_UNICO,
    FID_NO_REVISADO,
    FID_REPETIDO,
    FID_TIPO_INCOMPATIBLE,
    DatosCapaPlan,
    EstadoArchivo,
)
from ..dominio.seguridad import ocultar_contrasenas
from ..inventario.lector_capas import partes_de_fuente
from ..monitoreo.descriptor_fuente import ruta_de_capa

TIPOS_ENTEROS = (QVariant.Int, QVariant.LongLong, QVariant.UInt, QVariant.ULongLong)
# Archivos que forman un mismo conjunto de datos (huella, D-64).
AUXILIARES_SHAPEFILE = (".shp", ".shx", ".dbf", ".prj", ".cpg")
AUXILIARES_DBF = (".dbf", ".cpg")
# En modo WAL los cambios se escriben primero en "-wal"; "-shm" cambia solo con leer.
AUXILIARES_SQLITE = ("", "-wal")
EXTENSIONES_SQLITE = (".gpkg", ".sqlite", ".db")


def _texto(valor) -> str:
    return valor if isinstance(valor, str) else ""


def estado_archivo(ruta: str) -> EstadoArchivo:
    try:
        datos = os.stat(ruta)
    except OSError:
        return EstadoArchivo(ruta=ruta, existe=False)
    return EstadoArchivo(ruta=ruta, existe=True, tamano=datos.st_size, mtime_ns=datos.st_mtime_ns)


def archivos_del_conjunto(ruta: Optional[str]) -> Tuple[EstadoArchivo, ...]:
    if not ruta:
        return ()
    raiz, extension = os.path.splitext(ruta)
    extension = extension.lower()
    if extension == ".shp":
        rutas = [raiz + e for e in AUXILIARES_SHAPEFILE]
    elif extension == ".dbf":
        rutas = [raiz + e for e in AUXILIARES_DBF]
    elif extension in EXTENSIONES_SQLITE:
        rutas = [ruta + s for s in AUXILIARES_SQLITE]
    else:
        rutas = [ruta]
    # Solo el archivo principal puede faltar con significado; los auxiliares ausentes se omiten.
    estados = [estado_archivo(r) for r in rutas]
    return tuple(e for i, e in enumerate(estados) if i == 0 or e.existe)


def subcapas(capa) -> List[Tuple[str, str, str]]:
    """(indice, nombre, tipo de geometria) de cada subcapa que ofrece el proveedor OGR."""
    try:
        lista = capa.dataProvider().subLayers()
    except Exception:  # noqa: BLE001
        return []
    separador = QgsDataProvider.sublayerSeparator()
    resultado = []
    for texto in lista:
        partes = texto.split(separador)
        if len(partes) >= 4:
            resultado.append((partes[0], partes[1], partes[3]))
    return resultado


def resolver_subcapa(capa, partes: dict) -> Tuple[str, str, List[Tuple[str, str, str]]]:
    """(nombre de la tabla de origen, subcapa real si es inequivoca, subcapas de esa tabla)."""
    lista = subcapas(capa) if capa.providerType() == "ogr" else []
    nombre = _texto(partes.get("layerName"))
    if nombre:
        return nombre, "", [s for s in lista if s[1] == nombre]
    nombres = sorted({s[1] for s in lista})
    if len(nombres) == 1:
        # Un solo nombre de tabla: GeoPackage de una capa, Shapefile, GeoJSON... (D-56).
        return nombres[0], nombres[0], lista
    # Varias tablas y ninguna indicada: QGIS abre la primera. No se une con nada (ambiguo).
    return "", "", [s for s in lista if s[0] == "0"]


def geometrias_mezcladas(lista: List[Tuple[str, str, str]]) -> bool:
    tipos = {t for _i, _n, t in lista if t and t.lower() not in ("unknown", "nogeometry", "none")}
    return len(tipos) > 1


def estado_fid(capa: QgsVectorLayer, revisar_valores: bool) -> str:
    campos = capa.fields()
    indices = [i for i, campo in enumerate(campos) if campo.name().casefold() == "fid"]
    if not indices:
        return FID_AUSENTE
    indice = indices[0]
    campo = campos.at(indice)
    entero = campo.type() in TIPOS_ENTEROS
    if entero and indice in capa.dataProvider().pkAttributeIndexes():
        return FID_CLAVE
    if not entero:
        return FID_TIPO_INCOMPATIBLE
    if not revisar_valores:
        return FID_NO_REVISADO
    # Solo se lee esa columna, sin geometria. Respeta el filtro de la capa: la unidad incluye el filtro.
    peticion = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry).setSubsetOfAttributes([indice])
    vistos = set()
    for entidad in capa.getFeatures(peticion):
        valor = entidad.attribute(indice)
        if valor is None or (isinstance(valor, QVariant) and valor.isNull()) or valor in vistos:
            return FID_REPETIDO
        vistos.add(valor)
    return FID_ENTERO_UNICO


def _src(src) -> str:
    if src is None or not src.isValid():
        return ""
    return src.authid() or src.toWkt()


def _nombre_archivo(ruta: Optional[str]) -> str:
    if not ruta:
        return ""
    return os.path.splitext(os.path.basename(ruta))[0]


def leer_datos_capa(capa, revisar_valores: bool = True) -> DatosCapaPlan:
    """`revisar_valores` recorre la columna fid cuando hace falta; solo para origenes incorporables."""
    proveedor = capa.providerType()
    partes = partes_de_fuente(capa)
    vectorial = isinstance(capa, QgsVectorLayer)
    ruta = ruta_de_capa(capa)
    nombre_origen, subcapa_real, lista = resolver_subcapa(capa, partes) if vectorial else ("", "", [])
    if not nombre_origen:
        nombre_origen = _nombre_archivo(_texto(partes.get("vsiSuffix")) or ruta) or capa.name()
    memoria = proveedor.lower() == PROVEEDOR_MEMORIA
    proveedor_datos = capa.dataProvider() if vectorial else None
    src_fuente = proveedor_datos.crs() if proveedor_datos is not None else None
    campos = capa.fields() if vectorial else QgsFields()
    return DatosCapaPlan(
        id_capa=capa.id(),
        proveedor=proveedor,
        fuente_publica=ocultar_contrasenas(capa.publicSource()),
        subset=capa.subsetString() if vectorial else "",
        tipo_geometria=_texto(partes.get("geometryType")),
        nombre_origen=nombre_origen,
        subcapa_real=subcapa_real,
        src_capa=_src(capa.crs()),
        src_fuente=_src(src_fuente),
        src_fuente_valido=bool(src_fuente is not None and src_fuente.isValid()),
        en_edicion=bool(vectorial and capa.isEditable()),
        con_cambios=bool(vectorial and capa.isModified()),
        campos=tuple((c.name(), c.typeName()) for c in campos),
        campos_calculados=tuple(
            c.name() for i, c in enumerate(campos) if campos.fieldOrigin(i) == QgsFields.OriginExpression
        ),
        estado_fid=estado_fid(capa, revisar_valores) if vectorial else FID_AUSENTE,
        geometrias_mezcladas=geometrias_mezcladas(lista),
        num_entidades=capa.featureCount() if (vectorial and memoria) else -1,
        extension=capa.extent().toString() if (vectorial and memoria) else "",
        archivos=archivos_del_conjunto(ruta),
    )
