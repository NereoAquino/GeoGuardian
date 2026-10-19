"""Clasificacion del inventario por origen, disponibilidad y SRC (D-41, D-44 a D-48). Modulo puro.

No sustituye a `clasificacion.clasificar_recurso` (D-42): `equivalente_v010` traduce el resultado
a `EstadoRecurso` solo para comprobar en las pruebas que ambas clasificaciones coinciden.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..constantes import PROVEEDOR_MEMORIA
from .clasificacion import esta_dentro, ruta_relativa
from .inventario import (
    TIPO_VECTORIAL,
    CapaInventariada,
    ContextoInventario,
    DatosSrc,
    Disponibilidad,
    EntradaCapa,
    EstadoSrc,
    FuenteInventariada,
    IdentidadFuente,
    Inventario,
    OrigenFuente,
)
from .modelos import EstadoRecurso
from .seguridad import ocultar_contrasenas

# Proveedores de QGIS (valores de la API) que no se basan en archivos.
PROVEEDOR_VIRTUAL = "virtual"
PROVEEDORES_BASE_DATOS = frozenset({"postgres", "mssql", "oracle", "hana", "db2"})
PROVEEDORES_SERVICIO = frozenset(
    {"wfs", "oapif", "arcgisfeatureserver", "arcgismapserver", "wms", "wcs", "vectortile"}
)

# Parametros de URL que son credenciales y nunca forman parte de la identidad (D-44).
PARAMETROS_CREDENCIALES = frozenset(
    {
        "password", "passwd", "pwd", "pass", "user", "username", "token", "access_token",
        "apikey", "api_key", "key", "secret", "client_secret", "signature", "sig", "authcfg",
    }
)

# Gravedad para combinar varias capas de una misma fuente: gana la peor.
_ORDEN_DISPONIBILIDAD = (
    Disponibilidad.DISPONIBLE,
    Disponibilidad.INVALIDA,
    Disponibilidad.FALTANTE,
    Disponibilidad.UNIDAD_AUSENTE,
)


def url_sin_credenciales(url: str) -> str:
    """Quita usuario, contrasena y parametros de credenciales de una URL."""
    if not url:
        return ""
    try:
        partes = urlsplit(url)
    except ValueError:
        return ocultar_contrasenas(url)
    servidor = partes.netloc.rsplit("@", 1)[-1]
    consulta = urlencode(
        [(n, v) for n, v in parse_qsl(partes.query, keep_blank_values=True)
         if n.lower() not in PARAMETROS_CREDENCIALES]
    )
    return urlunsplit((partes.scheme, servidor, partes.path, consulta, partes.fragment))


def clasificar_origen(entrada: EntradaCapa, contexto: ContextoInventario) -> OrigenFuente:
    """Donde vive la fuente. Las tablas gg_* se excluyen antes de llegar aqui."""
    proveedor = entrada.proveedor.lower()  # QGIS usa claves como "WFS" u "OAPIF"
    if proveedor == PROVEEDOR_MEMORIA:
        return OrigenFuente.TEMPORAL
    if entrada.ruta_remota:
        return OrigenFuente.SERVICIO_REMOTO
    ruta = entrada.ruta_local
    if ruta:
        # D-45: solo el Proyecto.gpkg del contexto activo, validado, y sin tablas gg_*.
        if entrada.es_geopaquete_activo and contexto.geopaquete_utilizable and not entrada.es_tabla_control:
            return OrigenFuente.ADMINISTRADA
        if any(esta_dentro(ruta, t) for t in contexto.carpetas_temporales if t):
            return OrigenFuente.TEMPORAL
        if esta_dentro(ruta, contexto.carpeta_proyecto):
            return OrigenFuente.CARPETA_PROYECTO
        return OrigenFuente.ARCHIVO_EXTERNO
    if proveedor == PROVEEDOR_VIRTUAL:
        return OrigenFuente.VIRTUAL
    if proveedor in PROVEEDORES_BASE_DATOS:
        return OrigenFuente.BASE_DATOS_EXTERNA
    if proveedor in PROVEEDORES_SERVICIO:
        return OrigenFuente.SERVICIO_REMOTO
    return OrigenFuente.DESCONOCIDA


def evaluar_disponibilidad(entrada: EntradaCapa) -> Disponibilidad:
    if entrada.ruta_local and not entrada.existe:
        return Disponibilidad.UNIDAD_AUSENTE if entrada.unidad_ausente else Disponibilidad.FALTANTE
    if not entrada.es_valida:
        return Disponibilidad.INVALIDA
    return Disponibilidad.DISPONIBLE


def evaluar_src(entrada: EntradaCapa, origen: OrigenFuente, src_proyecto: DatosSrc) -> EstadoSrc:
    """Solo informa (D-48): nunca cambia el semaforo ni el SRC de nada."""
    if entrada.tipo_capa != TIPO_VECTORIAL or not entrada.es_espacial or not entrada.es_valida:
        return EstadoSrc.NO_APLICA
    if not src_proyecto.valido:
        return EstadoSrc.PROYECTO_SIN_SRC
    if not entrada.src.valido:
        return EstadoSrc.CAPA_SIN_SRC
    if entrada.src_igual_proyecto:
        return EstadoSrc.COINCIDE
    if origen == OrigenFuente.SERVICIO_REMOTO:
        return EstadoSrc.SRC_DE_SERVICIO
    return EstadoSrc.DIFERENTE


def src_fuente_distinto(entrada: EntradaCapa) -> Optional[DatosSrc]:
    """SRC de la fuente cuando ambos son validos y distintos del asignado a la capa (D-48)."""
    if (
        entrada.tipo_capa == TIPO_VECTORIAL
        and entrada.es_espacial
        and entrada.es_valida
        and entrada.src.valido
        and entrada.src_fuente.valido
        and not entrada.src_igual_fuente
    ):
        return entrada.src_fuente
    return None


def identidad_de(entrada: EntradaCapa) -> IdentidadFuente:
    if entrada.ruta_local:
        return IdentidadFuente(
            proveedor=entrada.proveedor,
            contenedor=entrada.ruta_local,
            subcapa=entrada.subcapa,
            parametros=entrada.parametros,
            es_archivo=True,
        )
    if entrada.proveedor == PROVEEDOR_MEMORIA:
        # Cada capa en memoria es su propia fuente.
        return IdentidadFuente(proveedor=entrada.proveedor, contenedor="memoria", subcapa=entrada.id_capa)
    return IdentidadFuente(
        proveedor=entrada.proveedor,
        contenedor=ocultar_contrasenas(entrada.contenedor),
        subcapa=ocultar_contrasenas(entrada.subcapa),
        parametros=entrada.parametros,
    )


def equivalente_v010(origen: OrigenFuente, disponibilidad: Disponibilidad) -> EstadoRecurso:
    """Estado que v0.1.0 asignaria a la misma capa (D-42). Solo para pruebas de coherencia."""
    if disponibilidad != Disponibilidad.DISPONIBLE:
        return EstadoRecurso.FALTANTE
    if origen == OrigenFuente.TEMPORAL:
        return EstadoRecurso.TEMPORAL
    if origen in (OrigenFuente.ADMINISTRADA, OrigenFuente.CARPETA_PROYECTO):
        return EstadoRecurso.ACTIVO
    return EstadoRecurso.EXTERNO


def construir_inventario(
    entradas: Iterable[EntradaCapa],
    contexto: ContextoInventario,
    src_proyecto: DatosSrc,
    fecha: str,
    nombre_proyecto: str = "",
) -> Inventario:
    capas: List[CapaInventariada] = []
    acumuladas: Dict[str, dict] = {}
    omitidas = 0
    for entrada in entradas:
        if entrada.es_tabla_control:
            omitidas += 1  # registro propio de GeoGuardian, como en v0.1.0
            continue
        if entrada.tipo_capa != TIPO_VECTORIAL:
            capas.append(CapaInventariada(
                id_capa=entrada.id_capa,
                nombre=entrada.nombre,
                tipo_capa=entrada.tipo_capa,
                proveedor=entrada.proveedor,
                revisada=False,
                es_valida=entrada.es_valida,
            ))
            continue
        origen = clasificar_origen(entrada, contexto)
        disponibilidad = evaluar_disponibilidad(entrada)
        identidad = identidad_de(entrada)
        clave = identidad.clave
        if clave not in acumuladas:
            acumuladas[clave] = {
                "identidad": identidad,
                "origen": origen,
                "disponibilidades": [],
                "ruta_relativa": ruta_relativa(entrada.ruta_local, contexto.carpeta_proyecto),
                "ids": [],
            }
        acumuladas[clave]["disponibilidades"].append(disponibilidad)
        acumuladas[clave]["ids"].append(entrada.id_capa)
        capas.append(CapaInventariada(
            id_capa=entrada.id_capa,
            nombre=entrada.nombre,
            tipo_capa=entrada.tipo_capa,
            proveedor=entrada.proveedor,
            revisada=True,
            clave_fuente=clave,
            es_valida=entrada.es_valida,
            es_espacial=entrada.es_espacial,
            src=entrada.src,
            estado_src=evaluar_src(entrada, origen, src_proyecto),
            src_fuente_distinto=src_fuente_distinto(entrada),
        ))
    fuentes = tuple(
        FuenteInventariada(
            identidad=datos["identidad"],
            origen=datos["origen"],
            disponibilidad=max(datos["disponibilidades"], key=_ORDEN_DISPONIBILIDAD.index),
            ruta_relativa=datos["ruta_relativa"],
            ids_capas=tuple(datos["ids"]),
        )
        for datos in acumuladas.values()
    )
    return Inventario(
        fecha=fecha,
        nombre_proyecto=nombre_proyecto,
        src_proyecto=src_proyecto,
        capas=tuple(capas),
        fuentes=fuentes,
        tablas_control_omitidas=omitidas,
    )


def resumen_por_origen(inventario: Inventario) -> List[Tuple[OrigenFuente, int]]:
    """Conteo en el orden de OrigenFuente, sin los origenes ausentes."""
    conteo = inventario.conteo_por_origen()
    return [(origen, conteo[origen]) for origen in OrigenFuente if conteo.get(origen)]
