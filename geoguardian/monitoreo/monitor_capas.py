"""Monitoreo de capas agregadas y eliminadas (F7, F8)."""

from __future__ import annotations

import tempfile
from typing import Dict, Iterable, List, Optional, Tuple

from qgis.core import QgsProcessingUtils, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ..contexto import ContextoProyecto
from ..dominio.clasificacion import clasificar_recurso, ruta_relativa
from ..dominio.modelos import EstadoRecurso, Recurso, TipoEvento
from ..dominio.tiempo import ahora_iso
from ..errores import informar_error, protegido
from .descriptor_fuente import (
    describir_capa,
    es_tabla_de_control,
    fuente_publica,
    tipo_de_capa,
)


class MonitorCapas(QObject):
    estado_actualizado = pyqtSignal()
    error_ocurrido = pyqtSignal(str)

    def __init__(self, proyecto: Optional[QgsProject] = None, padre: Optional[QObject] = None):
        super().__init__(padre)
        self._proyecto = proyecto or QgsProject.instance()
        self._contexto: Optional[ContextoProyecto] = None
        self._conexiones_proyecto: List[Tuple[object, object]] = []
        self._conexiones_capas: Dict[str, List[Tuple[object, object]]] = {}
        self._carpetas_temporales: List[str] = []

    @property
    def activo(self) -> bool:
        return self._contexto is not None

    # --- ciclo de vida -----------------------------------------------------

    def activar(self, contexto: ContextoProyecto) -> None:
        self.desactivar()
        self._contexto = contexto
        self._carpetas_temporales = [tempfile.gettempdir(), QgsProcessingUtils.tempFolder()]
        for senal, ranura in (
            (self._proyecto.layersAdded, self._al_agregar_capas),
            (self._proyecto.layersWillBeRemoved, self._al_quitar_capas),
            (self._proyecto.removeAll, self._al_cerrar_proyecto),
        ):
            senal.connect(ranura)
            self._conexiones_proyecto.append((senal, ranura))
        for capa in self._proyecto.mapLayers().values():
            self._vigilar_ediciones(capa)

    def desactivar(self) -> None:
        for senal, ranura in self._conexiones_proyecto:
            _desconectar(senal, ranura)
        self._conexiones_proyecto = []
        for id_capa in list(self._conexiones_capas):
            self._dejar_de_vigilar(id_capa)
        self._contexto = None

    # --- operaciones -------------------------------------------------------

    def registrar_capas(self, capas: Iterable) -> int:
        """Da de alta las capas nuevas y reclasifica las ya registradas. Devuelve las altas."""
        if not self.activo:
            return 0
        altas = 0
        for capa in capas:
            if es_tabla_de_control(capa, self._contexto.ruta_geopaquete):
                continue
            vigente = self._contexto.repositorio.recurso_vigente(capa.id())
            if vigente is None:
                self._dar_de_alta(capa)
                altas += 1
            else:
                self._actualizar(capa, vigente)
        return altas

    def reclasificar(self) -> None:
        """Sincroniza gg_recursos con las capas del proyecto (al abrir y al guardar)."""
        if not self.activo:
            return
        capas = self._proyecto.mapLayers()
        repositorio = self._contexto.repositorio
        for recurso in repositorio.recursos_vigentes():
            if recurso.id_capa not in capas:
                # Se quito mientras GeoGuardian no estaba activo.
                self._dar_de_baja(recurso.id_capa, detectada_despues=True)
        self.registrar_capas(capas.values())
        self.estado_actualizado.emit()

    def capas_con_ediciones(self) -> int:
        return sum(
            1
            for capa in self._proyecto.mapLayers().values()
            if isinstance(capa, QgsVectorLayer) and capa.isEditable() and capa.isModified()
        )

    def informar_error(self, operacion: str, error: Exception) -> None:
        informar_error(self, self._contexto.registro if self._contexto else None, operacion, error)

    # --- ranuras -----------------------------------------------------------

    @protegido
    def _al_agregar_capas(self, capas) -> None:
        for capa in capas:
            self._vigilar_ediciones(capa)
        self.registrar_capas(capas)
        self.estado_actualizado.emit()

    @protegido
    def _al_quitar_capas(self, ids_capas) -> None:
        for id_capa in ids_capas:
            self._dejar_de_vigilar(id_capa)
            self._dar_de_baja(id_capa)
        self.estado_actualizado.emit()

    @protegido
    def _al_cerrar_proyecto(self) -> None:
        # QgsProject.clear() emite removeAll antes de quitar cada capa. Cerrar o cambiar
        # de proyecto no es retirar capas: se deja de monitorear para no marcarlas historicas.
        self.desactivar()

    @protegido
    def _al_cambiar_edicion(self, *_args) -> None:
        self.estado_actualizado.emit()

    # --- internos ----------------------------------------------------------

    def _clasificar(self, capa) -> EstadoRecurso:
        return clasificar_recurso(
            describir_capa(capa), str(self._contexto.carpeta), self._carpetas_temporales
        )

    def _dar_de_alta(self, capa) -> None:
        fecha = ahora_iso()
        descripcion = describir_capa(capa)
        estado = self._clasificar(capa)
        recurso = Recurso(
            id_capa=capa.id(),
            nombre=capa.name(),
            tipo_capa=tipo_de_capa(capa),
            proveedor=capa.providerType(),
            fuente=fuente_publica(capa),
            ruta_relativa=ruta_relativa(descripcion.ruta_archivo, str(self._contexto.carpeta)),
            estado=estado,
            fecha_alta=fecha,
            fecha_verificacion=fecha,
        )
        self._contexto.repositorio.alta_recurso(recurso)
        self._contexto.registro.registrar(
            TipoEvento.CAPA_AGREGADA,
            "Se agrego la capa «{}» ({})".format(capa.name(), estado.value),
            id_capa=capa.id(),
            detalle={"nombre": capa.name(), "proveedor": capa.providerType(), "estado": estado.value},
        )

    def _actualizar(self, capa, recurso: Recurso) -> None:
        anterior = recurso.estado
        descripcion = describir_capa(capa)
        recurso.estado = self._clasificar(capa)
        recurso.nombre = capa.name()
        recurso.fuente = fuente_publica(capa)
        recurso.ruta_relativa = ruta_relativa(descripcion.ruta_archivo, str(self._contexto.carpeta))
        recurso.fecha_verificacion = ahora_iso()
        self._contexto.repositorio.actualizar_recurso(recurso)
        if recurso.estado != anterior:
            self._contexto.registro.registrar(
                TipoEvento.ESTADO_RECURSO_CAMBIADO,
                "La capa «{}» paso de {} a {}".format(capa.name(), anterior.value, recurso.estado.value),
                id_capa=capa.id(),
                detalle={"estado_anterior": anterior.value, "estado_nuevo": recurso.estado.value},
            )

    def _dar_de_baja(self, id_capa: str, detectada_despues: bool = False) -> None:
        anterior = self._contexto.repositorio.marcar_historico(id_capa, ahora_iso())
        if anterior is None:
            return  # capa no registrada (por ejemplo, una tabla gg_*)
        detalle = {"nombre": anterior.nombre, "estado_anterior": anterior.estado.value}
        if detectada_despues:
            detalle["detectada_al_verificar"] = True
        self._contexto.registro.registrar(
            TipoEvento.CAPA_ELIMINADA,
            "Se quito la capa «{}» del proyecto".format(anterior.nombre),
            id_capa=id_capa,
            detalle=detalle,
        )

    def _vigilar_ediciones(self, capa) -> None:
        if not isinstance(capa, QgsVectorLayer) or capa.id() in self._conexiones_capas:
            return
        conexiones = []
        for senal in (capa.editingStarted, capa.editingStopped, capa.layerModified):
            senal.connect(self._al_cambiar_edicion)
            conexiones.append((senal, self._al_cambiar_edicion))
        self._conexiones_capas[capa.id()] = conexiones

    def _dejar_de_vigilar(self, id_capa: str) -> None:
        for senal, ranura in self._conexiones_capas.pop(id_capa, []):
            _desconectar(senal, ranura)


def _desconectar(senal, ranura) -> None:
    try:
        senal.disconnect(ranura)
    except (TypeError, RuntimeError):
        # Ya desconectada, o el objeto C++ de la capa ya fue destruido.
        pass
