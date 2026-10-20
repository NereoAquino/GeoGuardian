"""Revalidacion de un plan de incorporacion (D-64). Modulo puro: sin QGIS ni Qt.

Compara el plan que vio el estudiante con uno construido de nuevo a partir del estado actual de
QGIS y de Proyecto.gpkg. Solo dice si el plan sigue valiendo; no corrige nada. Es la condicion
previa de "Preparar incorporacion" y lo sera de cualquier ejecucion futura (Hito 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from .nombres_destino import esta_ocupado
from .plan_incorporacion import PlanIncorporacion, UnidadIncorporacion


class MotivoCambio(str, Enum):
    CAPA_ELIMINADA = "capa_eliminada"
    CAPAS_DISTINTAS = "capas_distintas"
    FUENTE_CAMBIADA = "fuente_cambiada"
    FILTRO_CAMBIADO = "filtro_cambiado"
    SRC_CAMBIADO = "src_cambiado"
    EDICION_INICIADA = "edicion_iniciada"
    CAMPOS_CAMBIADOS = "campos_cambiados"
    DATOS_CAMBIADOS = "datos_cambiados"  # capas en memoria: numero de entidades o extension
    ARCHIVO_MODIFICADO = "archivo_modificado"
    YA_NO_SELECCIONABLE = "ya_no_seleccionable"
    ADVERTENCIAS_NUEVAS = "advertencias_nuevas"
    NOMBRE_CAMBIADO = "nombre_cambiado"
    NOMBRE_OCUPADO = "nombre_ocupado"


TEXTO_CAMBIO = {
    MotivoCambio.CAPA_ELIMINADA: "Se quitó una de sus capas del proyecto.",
    MotivoCambio.CAPAS_DISTINTAS: "Cambiaron las capas que usan estos datos.",
    MotivoCambio.FUENTE_CAMBIADA: "La capa ahora usa otros datos.",
    MotivoCambio.FILTRO_CAMBIADO: "Cambió el filtro de la capa.",
    MotivoCambio.SRC_CAMBIADO: "Cambió su SRC.",
    MotivoCambio.EDICION_INICIADA: "Se empezó a editar.",
    MotivoCambio.CAMPOS_CAMBIADOS: "Cambiaron sus campos.",
    MotivoCambio.DATOS_CAMBIADOS: "Cambiaron sus datos.",
    MotivoCambio.ARCHIVO_MODIFICADO: "El archivo cambió.",
    MotivoCambio.YA_NO_SELECCIONABLE: "Ya no se puede incorporar.",
    MotivoCambio.ADVERTENCIAS_NUEVAS: "Tiene advertencias nuevas.",
    MotivoCambio.NOMBRE_CAMBIADO: "Cambió el nombre que tendría en Proyecto.gpkg.",
    MotivoCambio.NOMBRE_OCUPADO: "El nombre que tendría en Proyecto.gpkg ya está ocupado.",
}

AVISO_CAMBIOS = "Algunas capas cambiaron desde la última revisión. Vuelve a revisar antes de continuar."
AVISO_DESTINO = (
    "Proyecto.gpkg cambió o ya no corresponde a este proyecto administrado. Vuelve a revisar antes de "
    "continuar."
)


@dataclass(frozen=True)
class CambioUnidad:
    clave_unidad: str
    nombre: str
    motivos: Tuple[MotivoCambio, ...]


@dataclass(frozen=True)
class ResultadoRevalidacion:
    vigente: bool
    destino_cambiado: bool = False
    cambios: Tuple[CambioUnidad, ...] = ()
    plan_actual: Optional[PlanIncorporacion] = None  # el plan reconstruido, si lo hay

    def texto(self) -> str:
        if self.vigente:
            return ""
        return AVISO_DESTINO if self.destino_cambiado else AVISO_CAMBIOS


def _cambios_de_capas(anterior: UnidadIncorporacion, huellas_actuales: dict) -> list:
    """Compara cada capa de la unidad con su huella actual, este en la unidad que este (D-64).

    Un filtro o un geometrytype distinto llevan la capa a otra unidad; por eso se busca por id_capa
    en todo el plan reconstruido y no solo en la unidad con la misma clave.
    """
    motivos = []
    for previa in anterior.huella.capas:
        huella = huellas_actuales.get(previa.id_capa)
        if huella is None:
            motivos.append(MotivoCambio.CAPA_ELIMINADA)
            continue
        if (huella.proveedor, huella.fuente_publica) != (previa.proveedor, previa.fuente_publica):
            motivos.append(MotivoCambio.FUENTE_CAMBIADA)
        if (huella.subset, huella.tipo_geometria) != (previa.subset, previa.tipo_geometria):
            motivos.append(MotivoCambio.FILTRO_CAMBIADO)
        if (huella.src_capa, huella.src_fuente) != (previa.src_capa, previa.src_fuente):
            motivos.append(MotivoCambio.SRC_CAMBIADO)
        if (huella.en_edicion, huella.con_cambios) != (previa.en_edicion, previa.con_cambios):
            motivos.append(MotivoCambio.EDICION_INICIADA)
        if huella.campos != previa.campos:
            motivos.append(MotivoCambio.CAMPOS_CAMBIADOS)
        if (huella.num_entidades, huella.extension) != (previa.num_entidades, previa.extension):
            motivos.append(MotivoCambio.DATOS_CAMBIADOS)
    return motivos


def _cambios_de_unidad(
    anterior: UnidadIncorporacion,
    actual: Optional[UnidadIncorporacion],
    huellas_actuales: dict,
    plan_actual: PlanIncorporacion,
) -> Tuple[MotivoCambio, ...]:
    motivos = _cambios_de_capas(anterior, huellas_actuales)
    if actual is None:
        # La unidad ya no existe con esa clave: sus capas se quitaron o ahora apuntan a otros datos.
        if not motivos:
            motivos.append(MotivoCambio.FUENTE_CAMBIADA)
        return tuple(dict.fromkeys(motivos))
    if set(actual.ids_capas) != set(anterior.ids_capas):  # el orden del panel no importa
        motivos.append(MotivoCambio.CAPAS_DISTINTAS)
    if actual.huella.archivos != anterior.huella.archivos:
        motivos.append(MotivoCambio.ARCHIVO_MODIFICADO)
    if not actual.seleccionable:
        motivos.append(MotivoCambio.YA_NO_SELECCIONABLE)
    elif set(actual.advertencias) - set(anterior.advertencias):
        motivos.append(MotivoCambio.ADVERTENCIAS_NUEVAS)
    if actual.nombre_destino != anterior.nombre_destino:
        motivos.append(MotivoCambio.NOMBRE_CAMBIADO)
    if anterior.nombre_destino and esta_ocupado(anterior.nombre_destino, plan_actual.destino.nombres_ocupados):
        motivos.append(MotivoCambio.NOMBRE_OCUPADO)
    return tuple(dict.fromkeys(motivos))


def revalidar(anterior: PlanIncorporacion, actual: Optional[PlanIncorporacion]) -> ResultadoRevalidacion:
    """Comprueba, para cada unidad seleccionada en `anterior`, que nada cambio en `actual`.

    `actual` es None cuando ya no puede haber plan (sin proyecto administrado o Proyecto.gpkg no
    valido): el plan anterior deja de valer entero.
    """
    if actual is None:
        return ResultadoRevalidacion(vigente=False, destino_cambiado=True)
    destino_anterior, destino_actual = anterior.destino, actual.destino
    destino_cambiado = (
        destino_anterior.ruta != destino_actual.ruta
        or destino_anterior.id_proyecto != destino_actual.id_proyecto
        or not destino_actual.geopaquete_utilizable
    )
    huellas_actuales = {h.id_capa: h for u in actual.unidades for h in u.huella.capas}
    cambios = []
    for unidad in anterior.unidades_seleccionadas():
        motivos = _cambios_de_unidad(unidad, actual.unidad(unidad.clave_unidad), huellas_actuales, actual)
        if motivos:
            cambios.append(CambioUnidad(unidad.clave_unidad, unidad.nombre, motivos))
    return ResultadoRevalidacion(
        vigente=not destino_cambiado and not cambios,
        destino_cambiado=destino_cambiado,
        cambios=tuple(cambios),
        plan_actual=actual,
    )
