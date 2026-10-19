"""Modelos del dominio. Modulo puro: sin QGIS ni Qt."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EstadoRecurso(str, Enum):
    """Estado de un recurso (fuente de datos) del proyecto (D-02)."""

    ACTIVO = "activo"
    EXTERNO = "externo"
    TEMPORAL = "temporal"
    HISTORICO = "historico"
    FALTANTE = "faltante"


class NivelSemaforo(str, Enum):
    GRIS = "gris"
    ROJO = "rojo"
    AMARILLO = "amarillo"
    VERDE = "verde"


class TipoEvento(str, Enum):
    """Catalogo de eventos de la especificacion v0.1.0, seccion 7."""

    PROYECTO_INICIALIZADO = "proyecto_inicializado"
    PROYECTO_ABIERTO = "proyecto_abierto"
    PROYECTO_GUARDADO = "proyecto_guardado"
    CAPA_AGREGADA = "capa_agregada"
    CAPA_ELIMINADA = "capa_eliminada"
    ESTADO_RECURSO_CAMBIADO = "estado_recurso_cambiado"
    ERROR_COMPLEMENTO = "error_complemento"
    ESQUEMA_MIGRADO = "esquema_migrado"
    UBICACION_ACTUALIZADA = "ubicacion_actualizada"


@dataclass
class DatosProyecto:
    """Datos que captura el asistente de inicializacion."""

    nombre_estudiante: str
    correo: str
    titulo: str
    descripcion: str
    grupo: str
    asignatura: str


@dataclass
class SolicitudInicializacion:
    """Todo lo que el asistente entrega para inicializar (F13-F15)."""

    datos: DatosProyecto
    nombre_academico: str
    carpeta_padre: str
    tipo_ubicacion: str  # valor de dominio.ubicacion.TipoUbicacion
    ruta_respaldo: Optional[str] = None


@dataclass(frozen=True)
class DescripcionFuente:
    """Lo que la clasificacion necesita saber de la fuente de una capa."""

    proveedor: str
    ruta_archivo: Optional[str]
    existe: bool
    es_valida: bool


@dataclass
class Recurso:
    id_capa: str
    nombre: str
    tipo_capa: str
    proveedor: str
    fuente: str
    ruta_relativa: Optional[str]
    estado: EstadoRecurso
    fecha_alta: str
    fecha_verificacion: str
    fecha_baja: Optional[str] = None
    id_recurso: Optional[int] = None


@dataclass
class Evento:
    tipo_evento: TipoEvento
    descripcion: str
    fecha_hora: str
    version_complemento: str
    id_capa: Optional[str] = None
    detalle: Optional[Dict[str, Any]] = None
    id_evento: Optional[int] = None


@dataclass
class ResumenProyecto:
    """Fotografia del proyecto que evalua el semaforo."""

    administrado: bool
    conteo: Dict[EstadoRecurso, int] = field(default_factory=dict)
    cambios_sin_guardar: bool = False
    capas_con_ediciones: int = 0
    problemas_consistencia: List[str] = field(default_factory=list)
    titulo: str = ""
    nombre_estudiante: str = ""
    tiene_archivo: bool = False
    numero_capas: int = 0
    nombre_academico: str = ""
    ruta_proyecto: str = ""
    carpeta: str = ""
    faltantes_sin_unidad: int = 0  # faltantes cuya unidad no esta conectada (D-34)
    version_administrada: str = ""  # original con asociacion valida: ruta de su version (D-37)

    def cantidad(self, estado: EstadoRecurso) -> int:
        return self.conteo.get(estado, 0)
