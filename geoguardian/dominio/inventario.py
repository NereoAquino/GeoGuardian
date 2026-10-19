"""Tipos del inventario de capas (v0.2.0, Hito 1; D-40 a D-48). Modulo puro: sin QGIS ni Qt.

El inventario es de solo lectura y vive en memoria (D-40): describe las capas del proyecto y sus
fuentes, nunca se guarda en Proyecto.gpkg ni en el manifiesto. Es paralelo a la clasificacion de
v0.1.0 (`EstadoRecurso`), que no cambia (D-42).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

from .clasificacion import normalizar_ruta

# Tipo de capa que el Hito 1 revisa (valor de monitoreo.descriptor_fuente.tipo_de_capa).
TIPO_VECTORIAL = "vectorial"


class OrigenFuente(str, Enum):
    """Donde vive la fuente de una capa (D-41, primer eje)."""

    ADMINISTRADA = "administrada"  # dentro del Proyecto.gpkg del proyecto activo y validado (D-45)
    CARPETA_PROYECTO = "carpeta_proyecto"
    ARCHIVO_EXTERNO = "archivo_externo"
    TEMPORAL = "temporal"
    SERVICIO_REMOTO = "servicio_remoto"
    BASE_DATOS_EXTERNA = "base_datos_externa"  # D-46
    VIRTUAL = "virtual"
    DESCONOCIDA = "desconocida"


class Disponibilidad(str, Enum):
    """Si la fuente se puede usar ahora (D-41, segundo eje, independiente del origen)."""

    DISPONIBLE = "disponible"
    FALTANTE = "faltante"  # el archivo no existe
    UNIDAD_AUSENTE = "unidad_ausente"  # la unidad de Windows no esta conectada o cambio de letra
    INVALIDA = "invalida"  # QGIS no puede abrir la capa por otra causa


class EstadoSrc(str, Enum):
    """Comparacion informativa del SRC de una capa con el del proyecto (D-48)."""

    COINCIDE = "coincide"
    DIFERENTE = "diferente"
    CAPA_SIN_SRC = "capa_sin_src"
    PROYECTO_SIN_SRC = "proyecto_sin_src"
    NO_APLICA = "no_aplica"
    SRC_DE_SERVICIO = "src_de_servicio"


# --- textos para el estudiante (lenguaje sencillo; los valores internos son tecnicos) -----------

TEXTO_ORIGEN = {
    OrigenFuente.ADMINISTRADA: "Guardada en Proyecto.gpkg",
    OrigenFuente.CARPETA_PROYECTO: "En la carpeta del proyecto",
    OrigenFuente.ARCHIVO_EXTERNO: "Archivo fuera de la carpeta del proyecto",
    OrigenFuente.TEMPORAL: "Temporal: se pierde al cerrar QGIS",
    OrigenFuente.SERVICIO_REMOTO: "Servicio en internet",
    OrigenFuente.BASE_DATOS_EXTERNA: "Base de datos externa",
    OrigenFuente.VIRTUAL: "Capa virtual (consulta sobre otras capas)",
    OrigenFuente.DESCONOCIDA: "Origen desconocido",
}

TEXTO_DISPONIBILIDAD = {
    Disponibilidad.DISPONIBLE: "Disponible",
    Disponibilidad.FALTANTE: "El archivo no existe",
    Disponibilidad.UNIDAD_AUSENTE: "La unidad no está conectada o cambió de letra",
    Disponibilidad.INVALIDA: "QGIS no puede abrirla",
}

TEXTO_SRC = {
    EstadoSrc.COINCIDE: "Igual al del proyecto",
    EstadoSrc.DIFERENTE: "Distinto al del proyecto (QGIS la reproyecta al mostrarla)",
    EstadoSrc.CAPA_SIN_SRC: "La capa no tiene SRC",
    EstadoSrc.PROYECTO_SIN_SRC: "El proyecto no tiene SRC",
    EstadoSrc.NO_APLICA: "No aplica",
    EstadoSrc.SRC_DE_SERVICIO: "Definido por el servicio",
}

TEXTO_NO_REVISADA = "No revisada en esta versión"  # D-47


@dataclass(frozen=True)
class DatosSrc:
    """Un sistema de referencia de coordenadas, tal como lo describe QGIS."""

    valido: bool
    identificador: str = ""  # authid, por ejemplo EPSG:32615
    descripcion: str = ""

    def texto(self) -> str:
        if not self.valido:
            return "sin SRC"
        if self.identificador and self.descripcion:
            return "{} – {}".format(self.identificador, self.descripcion)
        return self.identificador or self.descripcion


SIN_SRC = DatosSrc(valido=False)


@dataclass(frozen=True)
class IdentidadFuente:
    """Contenedor + subcapa o dataset + parametros relevantes (D-44). Nunca lleva credenciales.

    `contenedor` es el archivo, la URL del servicio o la base de datos; se conserva aparte para
    poder agrupar por contenedor (por ejemplo, varias capas de un mismo .gpkg).
    """

    proveedor: str
    contenedor: str
    subcapa: str = ""
    parametros: Tuple[Tuple[str, str], ...] = ()
    es_archivo: bool = False

    @property
    def clave(self) -> str:
        contenedor = normalizar_ruta(self.contenedor) if self.es_archivo else self.contenedor
        partes = [self.proveedor, contenedor, self.subcapa]
        partes += ["{}={}".format(n, v) for n, v in self.parametros]
        return "|".join(partes)


@dataclass(frozen=True)
class EntradaCapa:
    """Lo que el adaptador QGIS lee de una capa; el dominio decide todo lo demas."""

    id_capa: str
    nombre: str
    tipo_capa: str
    proveedor: str
    es_valida: bool = True
    es_espacial: bool = False
    ruta_local: Optional[str] = None  # archivo local que contiene la capa, si lo hay
    ruta_remota: bool = False  # URL o /vsicurl/...: archivo servido por red
    contenedor: str = ""  # identidad sin credenciales cuando no hay archivo local
    subcapa: str = ""
    parametros: Tuple[Tuple[str, str], ...] = ()
    existe: bool = False
    unidad_ausente: bool = False
    es_geopaquete_activo: bool = False  # mismo archivo que el Proyecto.gpkg del contexto
    es_tabla_control: bool = False  # tabla gg_* del Proyecto.gpkg activo
    src: DatosSrc = SIN_SRC
    src_fuente: DatosSrc = SIN_SRC  # SRC que declara la fuente (proveedor de datos)
    src_igual_proyecto: bool = False
    src_igual_fuente: bool = True


@dataclass(frozen=True)
class ContextoInventario:
    """Proyecto administrado activo, visto por la clasificacion."""

    carpeta_proyecto: str
    carpetas_temporales: Tuple[str, ...] = ()
    geopaquete_utilizable: bool = False


@dataclass(frozen=True)
class FuenteInventariada:
    identidad: IdentidadFuente
    origen: OrigenFuente
    disponibilidad: Disponibilidad
    ruta_relativa: Optional[str] = None  # relativa a la carpeta del proyecto, si esta dentro
    ids_capas: Tuple[str, ...] = ()

    @property
    def clave(self) -> str:
        return self.identidad.clave

    @property
    def contenedor(self) -> str:
        return self.identidad.contenedor

    @property
    def subcapa(self) -> str:
        return self.identidad.subcapa


@dataclass(frozen=True)
class CapaInventariada:
    id_capa: str
    nombre: str
    tipo_capa: str
    proveedor: str
    revisada: bool  # False para capas no vectoriales en v0.2.0 (D-47)
    clave_fuente: Optional[str] = None
    es_valida: bool = True
    es_espacial: bool = False
    src: DatosSrc = SIN_SRC
    estado_src: EstadoSrc = EstadoSrc.NO_APLICA
    # D-48: el SRC asignado a la capa difiere del que declara su fuente; solo se informa.
    src_fuente_distinto: Optional[DatosSrc] = None


@dataclass(frozen=True)
class Inventario:
    """Fotografia de las capas de un proyecto administrado en un momento dado."""

    fecha: str
    nombre_proyecto: str
    src_proyecto: DatosSrc
    capas: Tuple[CapaInventariada, ...] = ()
    fuentes: Tuple[FuenteInventariada, ...] = ()
    tablas_control_omitidas: int = 0

    def fuente_de(self, capa: CapaInventariada) -> Optional[FuenteInventariada]:
        for fuente in self.fuentes:
            if fuente.clave == capa.clave_fuente:
                return fuente
        return None

    def capas_revisadas(self) -> Tuple[CapaInventariada, ...]:
        return tuple(c for c in self.capas if c.revisada)

    def capas_no_revisadas(self) -> Tuple[CapaInventariada, ...]:
        return tuple(c for c in self.capas if not c.revisada)

    def conteo_por_origen(self) -> Dict[OrigenFuente, int]:
        """Capas revisadas por origen de su fuente."""
        conteo: Counter = Counter()
        for capa in self.capas_revisadas():
            fuente = self.fuente_de(capa)
            if fuente is not None:
                conteo[fuente.origen] += 1
        return dict(conteo)
