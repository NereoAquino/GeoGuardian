"""Plan de incorporacion vectorial (v0.2.0, Hito 2; D-56 a D-68). Modulo puro: sin QGIS ni Qt.

El plan es una fotografia inmutable en memoria (D-68): dice que unidades podrian copiarse a
Proyecto.gpkg, con que nombre y con que advertencias, pero no copia ni cambia nada. Es paralelo a
`EstadoRecurso` y al semaforo (D-57) y parte del inventario del Hito 1 sin modificarlo.

Unidad de incorporacion (D-56): fuente del inventario + filtro (subset) + geometrytype. Varias capas
de QGIS sobre la misma unidad comparten un unico destino.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple

from ..constantes import PROVEEDOR_MEMORIA
from .inventario import (
    CapaInventariada,
    Disponibilidad,
    EstadoSrc,
    FuenteInventariada,
    Inventario,
    OrigenFuente,
)
from .nombres_destino import NombrePropuesto, resolver_nombres


class Elegibilidad(str, Enum):
    INCORPORABLE = "incorporable"
    CON_ADVERTENCIA = "con_advertencia"
    NO_INCORPORABLE = "no_incorporable"
    BLOQUEADA = "bloqueada"  # temporal: se resuelve guardando o terminando la edicion


class Seleccion(str, Enum):
    PRESELECCIONADA = "preseleccionada"
    SELECCIONABLE = "seleccionable"
    NO_SELECCIONABLE = "no_seleccionable"


class MotivoAtencion(str, Enum):
    """En orden de gravedad: el primero de una unidad es el que se muestra en la lista."""

    # No incorporable por su origen o disponibilidad.
    YA_ADMINISTRADA = "ya_administrada"
    RECURSO_EN_LINEA = "recurso_en_linea"
    BASE_EXTERNA = "base_externa"
    VIRTUAL = "virtual"
    DESCONOCIDA = "desconocida"
    NO_DISPONIBLE = "no_disponible"
    # No incorporable hasta que el estudiante lo corrija (D-59, D-61).
    SRC_ASIGNADO_DISTINTO = "src_asignado_distinto"
    SIN_SRC = "sin_src"
    TEMPORAL_SIN_SRC = "temporal_sin_src"
    CAMPO_FID_TIPO = "campo_fid_tipo"
    CAMPO_FID_REPETIDO = "campo_fid_repetido"
    CAMPOS_REPETIDOS = "campos_repetidos"
    CAMPO_GEOM = "campo_geom"
    GEOMETRIAS_MEZCLADAS = "geometrias_mezcladas"
    # Bloqueada mientras dure (D-60).
    CAMBIOS_SIN_GUARDAR = "cambios_sin_guardar"
    EN_EDICION = "en_edicion"
    # Advertencias: seleccionable, nunca preseleccionada.
    SRC_DIFERENTE = "src_diferente"
    PROYECTO_SIN_SRC = "proyecto_sin_src"
    SRC_DEFINIDO_EN_QGIS = "src_definido_en_qgis"
    FILTRO = "filtro"
    FILTRO_GEOMETRIA = "filtro_geometria"
    CAMPOS_CALCULADOS = "campos_calculados"


_ORDEN_MOTIVOS = {m: i for i, m in enumerate(MotivoAtencion)}

MOTIVOS_NO_INCORPORABLE = frozenset(
    {
        MotivoAtencion.YA_ADMINISTRADA, MotivoAtencion.RECURSO_EN_LINEA, MotivoAtencion.BASE_EXTERNA,
        MotivoAtencion.VIRTUAL, MotivoAtencion.DESCONOCIDA, MotivoAtencion.NO_DISPONIBLE,
        MotivoAtencion.SRC_ASIGNADO_DISTINTO, MotivoAtencion.SIN_SRC, MotivoAtencion.TEMPORAL_SIN_SRC,
        MotivoAtencion.CAMPO_FID_TIPO, MotivoAtencion.CAMPO_FID_REPETIDO, MotivoAtencion.CAMPOS_REPETIDOS,
        MotivoAtencion.CAMPO_GEOM, MotivoAtencion.GEOMETRIAS_MEZCLADAS,
    }
)
MOTIVOS_BLOQUEO = frozenset({MotivoAtencion.CAMBIOS_SIN_GUARDAR, MotivoAtencion.EN_EDICION})
MOTIVOS_ADVERTENCIA = frozenset(MotivoAtencion) - MOTIVOS_NO_INCORPORABLE - MOTIVOS_BLOQUEO

ORIGENES_INCORPORABLES = frozenset(
    {OrigenFuente.CARPETA_PROYECTO, OrigenFuente.ARCHIVO_EXTERNO, OrigenFuente.TEMPORAL}
)
_MOTIVO_ORIGEN = {
    OrigenFuente.ADMINISTRADA: MotivoAtencion.YA_ADMINISTRADA,
    OrigenFuente.SERVICIO_REMOTO: MotivoAtencion.RECURSO_EN_LINEA,
    OrigenFuente.BASE_DATOS_EXTERNA: MotivoAtencion.BASE_EXTERNA,
    OrigenFuente.VIRTUAL: MotivoAtencion.VIRTUAL,
    OrigenFuente.DESCONOCIDA: MotivoAtencion.DESCONOCIDA,
}

# Estado del campo fid, tal como lo lee el adaptador (D-61).
FID_AUSENTE = ""
FID_CLAVE = "clave"  # es la clave primaria entera de la fuente (GeoPackage): compatible
FID_ENTERO_UNICO = "entero_unico"  # entero sin repetidos ni vacios: GDAL lo conserva como FID
FID_REPETIDO = "repetido"  # entero con valores repetidos o vacios: la copia perderia filas
FID_TIPO_INCOMPATIBLE = "tipo_incompatible"  # no entero: la copia fallaria
FID_NO_REVISADO = "no_revisado"

# Columna de geometria que GDAL crea en GeoPackage.
COLUMNA_GEOMETRIA = "geom"

TEMPORAL_MEMORIA = "memoria"
TEMPORAL_ARCHIVO = "archivo_temporal"


@dataclass(frozen=True)
class EstadoArchivo:
    ruta: str
    existe: bool
    tamano: int = -1
    mtime_ns: int = -1


@dataclass(frozen=True)
class DatosCapaPlan:
    """Lo que el adaptador QGIS lee de una capa ademas del inventario; el dominio decide."""

    id_capa: str
    proveedor: str = ""
    fuente_publica: str = ""  # sin credenciales
    subset: str = ""
    tipo_geometria: str = ""  # parametro geometrytype de la fuente
    nombre_origen: str = ""  # tabla o archivo de origen (base del nombre destino)
    subcapa_real: str = ""  # tabla real de un GeoPackage abierto sin layername, si es inequivoca
    src_capa: str = ""
    src_fuente: str = ""
    src_fuente_valido: bool = True  # el adaptador lo pone en False si la fuente no declara SRC
    en_edicion: bool = False
    con_cambios: bool = False
    campos: Tuple[Tuple[str, str], ...] = ()  # (nombre, tipo)
    campos_calculados: Tuple[str, ...] = ()
    estado_fid: str = FID_AUSENTE
    geometrias_mezcladas: bool = False
    num_entidades: int = -1  # solo capas en memoria (huella aproximada)
    extension: str = ""
    archivos: Tuple[EstadoArchivo, ...] = ()


@dataclass(frozen=True)
class HuellaCapa:
    id_capa: str
    proveedor: str
    fuente_publica: str
    subset: str
    tipo_geometria: str
    src_capa: str
    src_fuente: str
    en_edicion: bool
    con_cambios: bool
    campos: Tuple[Tuple[str, str], ...]
    num_entidades: int
    extension: str


@dataclass(frozen=True)
class HuellaUnidad:
    """Lo que debe seguir igual entre el plan y una futura ejecucion (D-64)."""

    capas: Tuple[HuellaCapa, ...]
    archivos: Tuple[EstadoArchivo, ...]


@dataclass(frozen=True)
class DestinoPlan:
    """Proyecto.gpkg del proyecto administrado activo, leido sin escribir (D-63)."""

    ruta: str
    id_proyecto: str
    geopaquete_utilizable: bool
    nombres_ocupados: FrozenSet[str] = frozenset()


@dataclass(frozen=True)
class UnidadIncorporacion:
    clave_unidad: str
    fuente: FuenteInventariada
    origen: OrigenFuente
    disponibilidad: Disponibilidad
    ids_capas: Tuple[str, ...]
    nombres_capas: Tuple[str, ...]
    tipo_temporal: str  # "", "memoria" o "archivo_temporal"
    subset: str
    tipo_geometria: str
    elegibilidad: Elegibilidad
    motivos: Tuple[MotivoAtencion, ...]
    seleccion: Seleccion
    nombre_base: str
    destino: Optional[NombrePropuesto]  # None si no es incorporable
    huella: HuellaUnidad

    @property
    def nombre(self) -> str:
        return self.nombres_capas[0] if self.nombres_capas else self.nombre_base

    @property
    def nombre_destino(self) -> str:
        return self.destino.nombre if self.destino else ""

    @property
    def conflicto_resuelto(self) -> bool:
        return bool(self.destino and self.destino.conflicto)

    @property
    def seleccionable(self) -> bool:
        return self.seleccion != Seleccion.NO_SELECCIONABLE

    @property
    def advertencias(self) -> Tuple[MotivoAtencion, ...]:
        return tuple(m for m in self.motivos if m in MOTIVOS_ADVERTENCIA)

    @property
    def motivo_principal(self) -> Optional[MotivoAtencion]:
        return self.motivos[0] if self.motivos else None


@dataclass(frozen=True)
class PlanIncorporacion:
    """Fotografia inmutable; no se persiste (D-68)."""

    fecha: str
    destino: DestinoPlan
    unidades: Tuple[UnidadIncorporacion, ...]
    seleccionadas: FrozenSet[str] = frozenset()

    def unidad(self, clave_unidad: str) -> Optional[UnidadIncorporacion]:
        for unidad in self.unidades:
            if unidad.clave_unidad == clave_unidad:
                return unidad
        return None

    def unidad_de_capa(self, id_capa: str) -> Optional[UnidadIncorporacion]:
        for unidad in self.unidades:
            if id_capa in unidad.ids_capas:
                return unidad
        return None

    def unidades_seleccionadas(self) -> Tuple[UnidadIncorporacion, ...]:
        return tuple(u for u in self.unidades if u.clave_unidad in self.seleccionadas)

    def preseleccion(self) -> FrozenSet[str]:
        return frozenset(u.clave_unidad for u in self.unidades if u.seleccion == Seleccion.PRESELECCIONADA)


@dataclass(frozen=True)
class ResultadoPlan:
    """Plan, o motivo por el que no puede haber un plan ejecutable (D-57)."""

    plan: Optional[PlanIncorporacion]
    motivo_sin_plan: str = ""


SIN_PROYECTO = "Abre un proyecto administrado para preparar la incorporación."
GEOPAQUETE_NO_UTILIZABLE = (
    "Proyecto.gpkg no está listo, así que no se puede preparar la incorporación. "
    "Revisa el panel de GeoGuardian."
)
GEOPAQUETE_AJENO = (
    "Proyecto.gpkg no corresponde a este proyecto administrado, así que no se puede preparar la "
    "incorporación."
)
GEOPAQUETE_ILEGIBLE = "No se pudo leer Proyecto.gpkg, así que no se puede preparar la incorporación."


# --- Textos para el estudiante (D-65) -----------------------------------------------------

TEXTO_INCORPORABLE = "Se puede incorporar"
TEXTO_TEMPORAL_RECOMENDADA = "Capa temporal: se recomienda incorporar"
TEXTO_NO_VECTORIAL = "No se incorpora en esta versión"
TEXTO_SIN_PLAN = "—"

# Texto breve para la columna "Incorporar".
TEXTO_BREVE = {
    MotivoAtencion.YA_ADMINISTRADA: "Ya está en el proyecto",
    MotivoAtencion.RECURSO_EN_LINEA: "Se mantiene conectado",
    MotivoAtencion.BASE_EXTERNA: "Se mantiene conectado",
    MotivoAtencion.VIRTUAL: "Se mantiene conectado",
    MotivoAtencion.DESCONOCIDA: "No se incorpora: origen desconocido",
    MotivoAtencion.NO_DISPONIBLE: "No disponible",
    MotivoAtencion.SRC_ASIGNADO_DISTINTO: "Necesita atención: revisa el SRC asignado",
    MotivoAtencion.SIN_SRC: "Necesita atención: la capa no tiene SRC",
    MotivoAtencion.TEMPORAL_SIN_SRC: "Necesita atención: la capa no tiene SRC",
    MotivoAtencion.CAMPO_FID_TIPO: "Necesita atención: revisa el campo «fid»",
    MotivoAtencion.CAMPO_FID_REPETIDO: "Necesita atención: revisa el campo «fid»",
    MotivoAtencion.CAMPOS_REPETIDOS: "Necesita atención: hay campos con el mismo nombre",
    MotivoAtencion.CAMPO_GEOM: "Necesita atención: revisa el campo «geom»",
    MotivoAtencion.GEOMETRIAS_MEZCLADAS: "Necesita atención: mezcla tipos de geometría",
    MotivoAtencion.CAMBIOS_SIN_GUARDAR: "Tiene cambios sin guardar",
    MotivoAtencion.EN_EDICION: "Está en modo edición",
    MotivoAtencion.SRC_DIFERENTE: "SRC diferente al proyecto",
    MotivoAtencion.PROYECTO_SIN_SRC: "Necesita atención: el proyecto no tiene SRC",
    MotivoAtencion.SRC_DEFINIDO_EN_QGIS: "Necesita atención: SRC definido solo en QGIS",
    MotivoAtencion.FILTRO: "Necesita atención: la capa tiene un filtro",
    MotivoAtencion.FILTRO_GEOMETRIA: "Necesita atención: muestra un solo tipo de geometría",
    MotivoAtencion.CAMPOS_CALCULADOS: "Se puede incorporar: tiene campos calculados",
}

# Explicacion y orientacion (tooltip y vista previa).
TEXTO_MOTIVO = {
    MotivoAtencion.YA_ADMINISTRADA: "Ya está guardada en Proyecto.gpkg.",
    MotivoAtencion.RECURSO_EN_LINEA: "Es un recurso en línea: se mantiene conectado y no se copia.",
    MotivoAtencion.BASE_EXTERNA: "Está en una base de datos externa: se mantiene conectada y no se copia.",
    MotivoAtencion.VIRTUAL: "Es una capa virtual (una consulta sobre otras capas): se mantiene como está.",
    MotivoAtencion.DESCONOCIDA: "GeoGuardian no reconoce de dónde vienen los datos de esta capa.",
    MotivoAtencion.NO_DISPONIBLE: (
        "No está disponible: revisa que el archivo exista y que la unidad esté conectada."
    ),
    MotivoAtencion.SRC_ASIGNADO_DISTINTO: (
        "Revisa el SRC asignado. El SRC de la capa no coincide con el que declara el archivo. "
        "Corrige esta situación y vuelve a revisar."
    ),
    MotivoAtencion.SIN_SRC: (
        "La capa no tiene SRC. Define correctamente su sistema de coordenadas y vuelve a revisar."
    ),
    MotivoAtencion.TEMPORAL_SIN_SRC: (
        "Esta capa temporal no tiene SRC. Define su sistema de coordenadas antes de incorporarla."
    ),
    MotivoAtencion.CAMPO_FID_TIPO: (
        "El campo «fid» no es un número entero y Proyecto.gpkg lo usa como identificador de cada "
        "elemento. Cambia el nombre del campo y vuelve a revisar."
    ),
    MotivoAtencion.CAMPO_FID_REPETIDO: (
        "El campo «fid» tiene valores repetidos o vacíos y Proyecto.gpkg lo usa como identificador de "
        "cada elemento: se perderían filas. Cambia el nombre del campo o corrige sus valores y vuelve "
        "a revisar."
    ),
    MotivoAtencion.CAMPOS_REPETIDOS: (
        "Hay campos que solo se distinguen por mayúsculas y minúsculas (por ejemplo «ID» e «id»). "
        "Proyecto.gpkg no los acepta. Cambia el nombre de uno de ellos y vuelve a revisar."
    ),
    MotivoAtencion.CAMPO_GEOM: (
        "La capa tiene un campo llamado «geom», el nombre que Proyecto.gpkg usa para la geometría. "
        "Cambia el nombre del campo y vuelve a revisar."
    ),
    MotivoAtencion.GEOMETRIAS_MEZCLADAS: (
        "El archivo mezcla varios tipos de geometría (por ejemplo, puntos y líneas). Carga cada tipo "
        "como una capa separada y vuelve a revisar."
    ),
    MotivoAtencion.CAMBIOS_SIN_GUARDAR: (
        "Tiene cambios sin guardar. Guarda o descarta los cambios antes de incorporarla."
    ),
    MotivoAtencion.EN_EDICION: "Está en modo edición. Termina la edición antes de incorporarla.",
    MotivoAtencion.SRC_DIFERENTE: (
        "Su SRC es diferente al del proyecto. Se conservará su SRC original; GeoGuardian no lo cambiará. "
        "Decide si así lo necesitas antes de seleccionarla."
    ),
    MotivoAtencion.PROYECTO_SIN_SRC: (
        "El proyecto no tiene SRC, así que no se puede comparar con el de la capa."
    ),
    MotivoAtencion.SRC_DEFINIDO_EN_QGIS: (
        "El archivo original no declara un SRC; el SRC de la capa se definió en QGIS. Comprueba que "
        "sea el correcto antes de seleccionarla."
    ),
    MotivoAtencion.FILTRO: (
        "La capa tiene un filtro y muestra solo una parte de los datos del archivo. Requiere atención "
        "antes de incorporarla."
    ),
    MotivoAtencion.FILTRO_GEOMETRIA: (
        "La capa muestra solo un tipo de geometría de un archivo que tiene varios. Requiere atención "
        "antes de incorporarla."
    ),
    MotivoAtencion.CAMPOS_CALCULADOS: (
        "Los campos calculados se guardarán como valores y dejarán de recalcularse automáticamente."
    ),
}

TEXTO_ORIGEN_PLAN = {
    OrigenFuente.CARPETA_PROYECTO: "Archivo en la carpeta del proyecto",
    OrigenFuente.ARCHIVO_EXTERNO: "Archivo fuera de la carpeta del proyecto",
    OrigenFuente.TEMPORAL: "Capa temporal",
    OrigenFuente.ADMINISTRADA: "Guardada en Proyecto.gpkg",
    OrigenFuente.SERVICIO_REMOTO: "Recurso en línea",
    OrigenFuente.BASE_DATOS_EXTERNA: "Base de datos externa",
    OrigenFuente.VIRTUAL: "Capa virtual",
    OrigenFuente.DESCONOCIDA: "Origen desconocido",
}
TEXTO_TEMPORAL_ARCHIVO = "Capa temporal (resultado de Procesos)"

AVISO_PLAN = "Esto es un plan: todavía no se ha copiado ni cambiado nada."
TEXTO_ORIGINALES = "Los archivos originales no serán modificados."


# --- Reglas -----------------------------------------------------------------------------

def tipo_temporal(fuente: FuenteInventariada) -> str:
    if fuente.origen != OrigenFuente.TEMPORAL:
        return ""
    if fuente.identidad.proveedor.lower() == PROVEEDOR_MEMORIA:
        return TEMPORAL_MEMORIA
    return TEMPORAL_ARCHIVO if fuente.identidad.es_archivo else TEMPORAL_MEMORIA


def clave_unidad(fuente: FuenteInventariada, datos: DatosCapaPlan) -> str:
    """D-56: fuente + subset + geometrytype. Un GeoPackage abierto sin layername se une con la
    referencia explicita a la misma tabla cuando el adaptador la resolvio sin ambiguedad."""
    identidad = fuente.identidad
    if identidad.es_archivo and not identidad.subcapa and datos.subcapa_real:
        identidad = replace(identidad, subcapa=datos.subcapa_real)
    clave = identidad.clave
    if datos.subset:
        clave += "|subset=" + datos.subset
    if datos.tipo_geometria:
        clave += "|geometrytype=" + datos.tipo_geometria
    return clave


def _es_entero(tipo: str) -> bool:
    return tipo.lower() in ("integer", "integer64", "int", "int4", "int8", "longlong", "qlonglong")


def motivos_de_capa(
    capa: CapaInventariada, datos: DatosCapaPlan, origen: OrigenFuente, temporal: str
) -> List[MotivoAtencion]:
    """Motivos que aporta una capa de una unidad con origen incorporable."""
    motivos: List[MotivoAtencion] = []
    if capa.es_espacial:
        if not capa.src.valido:
            motivos.append(MotivoAtencion.TEMPORAL_SIN_SRC if temporal else MotivoAtencion.SIN_SRC)
        elif capa.src_fuente_distinto is not None:
            motivos.append(MotivoAtencion.SRC_ASIGNADO_DISTINTO)
        else:
            if capa.estado_src == EstadoSrc.DIFERENTE:
                motivos.append(MotivoAtencion.SRC_DIFERENTE)
            elif capa.estado_src == EstadoSrc.PROYECTO_SIN_SRC:
                motivos.append(MotivoAtencion.PROYECTO_SIN_SRC)
            if not datos.src_fuente_valido:
                motivos.append(MotivoAtencion.SRC_DEFINIDO_EN_QGIS)
    if datos.estado_fid == FID_TIPO_INCOMPATIBLE:
        motivos.append(MotivoAtencion.CAMPO_FID_TIPO)
    elif datos.estado_fid == FID_REPETIDO:
        motivos.append(MotivoAtencion.CAMPO_FID_REPETIDO)
    nombres = [n.casefold() for n, _tipo in datos.campos]
    if len(nombres) != len(set(nombres)):
        motivos.append(MotivoAtencion.CAMPOS_REPETIDOS)
    if capa.es_espacial and COLUMNA_GEOMETRIA in nombres:
        motivos.append(MotivoAtencion.CAMPO_GEOM)
    if datos.geometrias_mezcladas and not datos.tipo_geometria:
        motivos.append(MotivoAtencion.GEOMETRIAS_MEZCLADAS)
    if datos.con_cambios:
        motivos.append(MotivoAtencion.CAMBIOS_SIN_GUARDAR)
    elif datos.en_edicion:
        motivos.append(MotivoAtencion.EN_EDICION)
    if datos.subset:
        motivos.append(MotivoAtencion.FILTRO)
    if datos.tipo_geometria:
        motivos.append(MotivoAtencion.FILTRO_GEOMETRIA)
    if datos.campos_calculados:
        motivos.append(MotivoAtencion.CAMPOS_CALCULADOS)
    return motivos


def evaluar_elegibilidad(motivos: Iterable[MotivoAtencion]) -> Tuple[Elegibilidad, Seleccion]:
    conjunto = set(motivos)
    if conjunto & MOTIVOS_NO_INCORPORABLE:
        return Elegibilidad.NO_INCORPORABLE, Seleccion.NO_SELECCIONABLE
    if conjunto & MOTIVOS_BLOQUEO:
        return Elegibilidad.BLOQUEADA, Seleccion.NO_SELECCIONABLE
    if conjunto:
        return Elegibilidad.CON_ADVERTENCIA, Seleccion.SELECCIONABLE
    return Elegibilidad.INCORPORABLE, Seleccion.PRESELECCIONADA


def ordenar_motivos(motivos: Iterable[MotivoAtencion]) -> Tuple[MotivoAtencion, ...]:
    return tuple(sorted(set(motivos), key=_ORDEN_MOTIVOS.__getitem__))


_ORDEN_DISPONIBILIDAD = (
    Disponibilidad.DISPONIBLE, Disponibilidad.INVALIDA, Disponibilidad.FALTANTE, Disponibilidad.UNIDAD_AUSENTE,
)


def _huella_capa(datos: DatosCapaPlan) -> HuellaCapa:
    return HuellaCapa(
        id_capa=datos.id_capa,
        proveedor=datos.proveedor,
        fuente_publica=datos.fuente_publica,
        subset=datos.subset,
        tipo_geometria=datos.tipo_geometria,
        src_capa=datos.src_capa,
        src_fuente=datos.src_fuente,
        en_edicion=datos.en_edicion,
        con_cambios=datos.con_cambios,
        campos=datos.campos,
        num_entidades=datos.num_entidades,
        extension=datos.extension,
    )


def _nombre_base(primera: CapaInventariada, datos: DatosCapaPlan, temporal: str) -> str:
    """D-62: unidades filtradas, por geometrytype y temporales usan el nombre visible."""
    if datos.subset or datos.tipo_geometria or temporal:
        return primera.nombre
    return datos.nombre_origen or primera.nombre


def construir_plan(
    inventario: Inventario,
    datos: Mapping[str, DatosCapaPlan],
    destino: DestinoPlan,
    fecha: str,
    seleccion: Optional[Iterable[str]] = None,
) -> PlanIncorporacion:
    """Agrupa las capas vectoriales del inventario en unidades y evalua cada una.

    Las tablas gg_* y las capas no vectoriales no llegan aqui: el inventario ya las omite o las
    marca como no revisadas (D-47, D-55). Sin `seleccion` se aplica la preseleccion (D-58).
    """
    grupos: Dict[str, dict] = {}
    for capa in inventario.capas_revisadas():
        fuente = inventario.fuente_de(capa)
        if fuente is None:
            continue
        dato = datos.get(capa.id_capa) or DatosCapaPlan(id_capa=capa.id_capa)
        clave = clave_unidad(fuente, dato)
        grupo = grupos.setdefault(clave, {"fuente": fuente, "capas": [], "datos": [], "disponibilidades": []})
        grupo["capas"].append(capa)
        grupo["datos"].append(dato)
        grupo["disponibilidades"].append(fuente.disponibilidad)

    previas = []
    for clave, grupo in grupos.items():
        fuente: FuenteInventariada = grupo["fuente"]
        temporal = tipo_temporal(fuente)
        disponibilidad = max(grupo["disponibilidades"], key=_ORDEN_DISPONIBILIDAD.index)
        motivos: List[MotivoAtencion] = []
        if fuente.origen in _MOTIVO_ORIGEN:
            motivos.append(_MOTIVO_ORIGEN[fuente.origen])
        elif disponibilidad != Disponibilidad.DISPONIBLE:
            motivos.append(MotivoAtencion.NO_DISPONIBLE)
        else:
            for capa, dato in zip(grupo["capas"], grupo["datos"]):
                motivos += motivos_de_capa(capa, dato, fuente.origen, temporal)
        motivos = list(ordenar_motivos(motivos))
        elegibilidad, sel = evaluar_elegibilidad(motivos)
        archivos = {a.ruta: a for d in grupo["datos"] for a in d.archivos}
        previas.append(dict(
            clave=clave,
            fuente=fuente,
            disponibilidad=disponibilidad,
            capas=grupo["capas"],
            datos=grupo["datos"],
            temporal=temporal,
            motivos=tuple(motivos),
            elegibilidad=elegibilidad,
            seleccion=sel,
            base=_nombre_base(grupo["capas"][0], grupo["datos"][0], temporal),
            huella=HuellaUnidad(
                capas=tuple(_huella_capa(d) for d in grupo["datos"]),
                archivos=tuple(archivos[r] for r in sorted(archivos)),
            ),
        ))

    # D-62: nombres para todas las unidades incorporables, en orden de clave, sin mirar la seleccion.
    incorporables = [
        (p["clave"], p["base"]) for p in previas if p["fuente"].origen in ORIGENES_INCORPORABLES
        and p["elegibilidad"] != Elegibilidad.NO_INCORPORABLE
    ]
    nombres = resolver_nombres(incorporables, destino.nombres_ocupados)

    unidades = tuple(
        UnidadIncorporacion(
            clave_unidad=p["clave"],
            fuente=p["fuente"],
            origen=p["fuente"].origen,
            disponibilidad=p["disponibilidad"],
            ids_capas=tuple(c.id_capa for c in p["capas"]),
            nombres_capas=tuple(c.nombre for c in p["capas"]),
            tipo_temporal=p["temporal"],
            subset=p["datos"][0].subset,
            tipo_geometria=p["datos"][0].tipo_geometria,
            elegibilidad=p["elegibilidad"],
            motivos=p["motivos"],
            seleccion=p["seleccion"],
            nombre_base=p["base"],
            destino=nombres.get(p["clave"]),
            huella=p["huella"],
        )
        for p in previas
    )
    plan = PlanIncorporacion(fecha=fecha, destino=destino, unidades=unidades)
    return con_seleccion(plan, plan.preseleccion() if seleccion is None else seleccion)


def con_seleccion(plan: PlanIncorporacion, claves: Iterable[str]) -> PlanIncorporacion:
    """Mismo plan con otra seleccion; ignora lo que no es seleccionable."""
    validas = frozenset(
        u.clave_unidad for u in plan.unidades if u.clave_unidad in set(claves) and u.seleccionable
    )
    return replace(plan, seleccionadas=validas)


def seleccion_tras_revisar(
    anterior: Optional[PlanIncorporacion], nuevo: PlanIncorporacion
) -> FrozenSet[str]:
    """D-66: que queda marcado al pulsar "Volver a revisar".

    - Se conserva lo marcado que sigue siendo seleccionable y no tiene advertencias nuevas.
    - Lo que el estudiante desmarco sigue desmarcado.
    - Las unidades nuevas, o que antes no eran seleccionables, reciben la preseleccion.
    - Lo bloqueado o no incorporable nunca queda marcado.
    """
    if anterior is None:
        return nuevo.preseleccion()
    resultado = set()
    for unidad in nuevo.unidades:
        if not unidad.seleccionable:
            continue
        previa = anterior.unidad(unidad.clave_unidad)
        if previa is None or not previa.seleccionable:
            if unidad.seleccion == Seleccion.PRESELECCIONADA:
                resultado.add(unidad.clave_unidad)
        elif unidad.clave_unidad in anterior.seleccionadas:
            if set(unidad.advertencias) <= set(previa.advertencias):
                resultado.add(unidad.clave_unidad)
    return frozenset(resultado)


# --- Textos compuestos ------------------------------------------------------------------

def texto_estado(unidad: Optional[UnidadIncorporacion]) -> str:
    """Columna "Incorporar" de la lista."""
    if unidad is None:
        return TEXTO_SIN_PLAN
    if unidad.motivo_principal is None:
        return TEXTO_TEMPORAL_RECOMENDADA if unidad.tipo_temporal else TEXTO_INCORPORABLE
    return TEXTO_BREVE[unidad.motivo_principal]


def ayuda_estado(unidad: Optional[UnidadIncorporacion]) -> str:
    if unidad is None:
        return TEXTO_SIN_PLAN
    lineas = [TEXTO_MOTIVO[m] for m in unidad.motivos]
    if not lineas:
        lineas.append(
            "Es una capa temporal: si cierras QGIS sin incorporarla, se pierde."
            if unidad.tipo_temporal else "Se puede incorporar a Proyecto.gpkg."
        )
    if len(unidad.ids_capas) > 1:
        lineas.append("Se incorpora junto con: {}.".format(", ".join(unidad.nombres_capas)))
    return "\n".join(lineas)


def texto_origen(unidad: UnidadIncorporacion) -> str:
    if unidad.tipo_temporal == TEMPORAL_ARCHIVO:
        return TEXTO_TEMPORAL_ARCHIVO
    return TEXTO_ORIGEN_PLAN[unidad.origen]


def _cuenta(n: int, uno: str, varios: str) -> str:
    return uno if n == 1 else varios.format(n)


def texto_conteo(plan: Optional[PlanIncorporacion]) -> str:
    """'3 elementos por incorporar (4 capas relacionadas) · 2 advertencias pendientes'."""
    if plan is None:
        return ""
    seleccionadas = plan.unidades_seleccionadas()
    if not seleccionadas:
        return "Ningún elemento seleccionado para incorporar."
    capas = sum(len(u.ids_capas) for u in seleccionadas)
    advertencias = sum(len(u.advertencias) for u in seleccionadas)
    texto = "{} ({})".format(
        _cuenta(len(seleccionadas), "1 elemento por incorporar", "{} elementos por incorporar"),
        _cuenta(capas, "1 capa relacionada", "{} capas relacionadas"),
    )
    if advertencias:
        texto += " · " + _cuenta(advertencias, "1 advertencia pendiente", "{} advertencias pendientes")
    return texto


def texto_resumen_plan(plan: PlanIncorporacion) -> str:
    """Resumen de la vista previa (D-65)."""
    unidades = plan.unidades_seleccionadas()
    frases = [_cuenta(
        len(unidades),
        "Se incorporará un elemento en Proyecto.gpkg.",
        "Se incorporarán {} elementos en Proyecto.gpkg.",
    )]
    temporales = sum(1 for u in unidades if u.tipo_temporal)
    if temporales:
        frases.append(_cuenta(
            temporales,
            "Una capa temporal quedará guardada permanentemente.",
            "{} capas temporales quedarán guardadas permanentemente.",
        ))
    for motivo, uno, varios in (
        (MotivoAtencion.SRC_DIFERENTE, "Un elemento tiene un SRC diferente al proyecto.",
         "{} elementos tienen un SRC diferente al proyecto."),
        (MotivoAtencion.FILTRO, "Un elemento tiene un filtro y requiere atención.",
         "{} elementos tienen un filtro y requieren atención."),
        (MotivoAtencion.FILTRO_GEOMETRIA, "Un elemento muestra un solo tipo de geometría y requiere atención.",
         "{} elementos muestran un solo tipo de geometría y requieren atención."),
        (MotivoAtencion.CAMPOS_CALCULADOS, "Un elemento tiene campos calculados que se guardarán como valores.",
         "{} elementos tienen campos calculados que se guardarán como valores."),
        (MotivoAtencion.SRC_DEFINIDO_EN_QGIS, "Un elemento tiene un SRC definido solo en QGIS.",
         "{} elementos tienen un SRC definido solo en QGIS."),
        (MotivoAtencion.PROYECTO_SIN_SRC, "El proyecto no tiene SRC para comparar.",
         "El proyecto no tiene SRC para comparar."),
    ):
        n = sum(1 for u in unidades if motivo in u.motivos)
        if n:
            frases.append(_cuenta(n, uno, varios))
    renombradas = sum(1 for u in unidades if u.conflicto_resuelto)
    if renombradas:
        frases.append(_cuenta(
            renombradas,
            "Un elemento usará otro nombre porque el suyo ya está ocupado.",
            "{} elementos usarán otro nombre porque el suyo ya está ocupado.",
        ))
    frases.append(TEXTO_ORIGINALES)
    return " ".join(frases)


def texto_capas_relacionadas(unidad: UnidadIncorporacion) -> str:
    return "{}: {}".format(len(unidad.ids_capas), ", ".join(unidad.nombres_capas))


def texto_advertencias(unidad: UnidadIncorporacion) -> str:
    """Explicacion completa de las advertencias (ayuda emergente de la vista previa)."""
    return "\n".join(TEXTO_MOTIVO[m] for m in unidad.advertencias) or "Ninguna"


def texto_advertencias_breve(unidad: UnidadIncorporacion) -> str:
    return "; ".join(TEXTO_BREVE[m] for m in unidad.advertencias) or "Ninguna"
