"""Construye el inventario bajo demanda (D-49). Solo lectura y solo en memoria (D-40)."""

from __future__ import annotations

import tempfile
from typing import Callable, List, Optional

from qgis.core import QgsProcessingUtils, QgsProject

from ..contexto import ContextoProyecto
from ..dominio.clasificacion_inventario import construir_inventario
from ..dominio.inventario import ContextoInventario, Inventario
from ..dominio.tiempo import ahora_iso
from .lector_capas import datos_src, leer_capa


class ServicioInventario:
    """No conecta senales: el inventario se recalcula solo cuando el estudiante lo pide (D-49)."""

    def __init__(self, proyecto: QgsProject, obtener_contexto: Callable[[], Optional[ContextoProyecto]]):
        """`obtener_contexto` devuelve el contexto del proyecto administrado activo, o None."""
        self._proyecto = proyecto
        self._obtener_contexto = obtener_contexto

    def disponible(self) -> bool:
        return self._obtener_contexto() is not None

    def construir(self) -> Optional[Inventario]:
        """Inventario del proyecto administrado activo; None si no hay proyecto administrado."""
        contexto = self._obtener_contexto()
        if contexto is None:
            return None
        src_proyecto = self._proyecto.crs()
        entradas = [leer_capa(capa, contexto, src_proyecto) for capa in self._capas_en_orden()]
        fila = contexto.fila_proyecto or {}
        nombre = str(fila.get("nombre_academico") or self._proyecto.title() or contexto.ruta_proyecto.stem)
        return construir_inventario(
            entradas,
            ContextoInventario(
                carpeta_proyecto=str(contexto.carpeta),
                carpetas_temporales=(tempfile.gettempdir(), QgsProcessingUtils.tempFolder()),
                geopaquete_utilizable=contexto.geopaquete_utilizable,
            ),
            datos_src(src_proyecto),
            ahora_iso(),
            nombre,
        )

    def _capas_en_orden(self) -> List:
        """Capas en el orden del panel de capas; despues, las que no esten en el arbol."""
        capas = self._proyecto.mapLayers()
        ordenadas = []
        vistas = set()
        for nodo in self._proyecto.layerTreeRoot().findLayers():
            capa = nodo.layer()
            if capa is not None and capa.id() in capas and capa.id() not in vistas:
                ordenadas.append(capa)
                vistas.add(capa.id())
        ordenadas += [c for i, c in capas.items() if i not in vistas]
        return ordenadas
