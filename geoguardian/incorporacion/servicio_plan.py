"""Construye y revalida el plan de incorporacion bajo demanda (D-49, D-64). Solo lectura y en memoria (D-68).

No conecta senales. Depende del contexto activo y de `id_desde_geopaquete`, que llega inyectado
desde complemento.py (D-67): este paquete no importa `administracion`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from qgis.core import QgsProject

from ..contexto import ContextoProyecto
from ..dominio.inventario import Inventario
from ..dominio.plan_incorporacion import (
    GEOPAQUETE_AJENO,
    GEOPAQUETE_ILEGIBLE,
    GEOPAQUETE_NO_UTILIZABLE,
    ORIGENES_INCORPORABLES,
    SIN_PROYECTO,
    DatosCapaPlan,
    DestinoPlan,
    PlanIncorporacion,
    ResultadoPlan,
    construir_plan,
)
from ..dominio.revalidacion import ResultadoRevalidacion, revalidar
from ..dominio.tiempo import ahora_iso
from .lector_geopaquete import nombres_ocupados
from .lector_plan import leer_datos_capa


class ServicioPlan:
    def __init__(
        self,
        proyecto: QgsProject,
        obtener_contexto: Callable[[], Optional[ContextoProyecto]],
        construir_inventario: Callable[[], Optional[Inventario]],
        leer_id_geopaquete: Callable[[Path], Optional[str]],
    ):
        self._proyecto = proyecto
        self._obtener_contexto = obtener_contexto
        self._construir_inventario = construir_inventario
        self._leer_id = leer_id_geopaquete

    def destino(self) -> Tuple[Optional[DestinoPlan], str]:
        """Proyecto.gpkg del contexto activo, o el motivo por el que no puede ser destino (D-57)."""
        contexto = self._obtener_contexto()
        if contexto is None:
            return None, SIN_PROYECTO
        if not contexto.geopaquete_utilizable:
            return None, GEOPAQUETE_NO_UTILIZABLE
        ruta = contexto.ruta_geopaquete
        esperado = str((contexto.fila_proyecto or {}).get("id_proyecto") or "")
        if not esperado or self._leer_id(ruta) != esperado:
            return None, GEOPAQUETE_AJENO
        ocupados = nombres_ocupados(ruta)
        if ocupados is None:
            return None, GEOPAQUETE_ILEGIBLE
        return DestinoPlan(str(ruta), esperado, True, ocupados), ""

    def construir(self, inventario: Optional[Inventario], seleccion: Optional[Iterable[str]] = None) -> ResultadoPlan:
        """Plan sobre un inventario ya construido; sin `seleccion` se aplica la preseleccion."""
        if inventario is None:
            return ResultadoPlan(None, SIN_PROYECTO)
        destino, motivo = self.destino()
        if destino is None:
            return ResultadoPlan(None, motivo)
        return ResultadoPlan(construir_plan(inventario, self._datos(inventario), destino, ahora_iso(), seleccion))

    def revalidar(self, plan: PlanIncorporacion) -> ResultadoRevalidacion:
        """Reconstruye inventario y plan desde QGIS y los compara con `plan` (D-64)."""
        actual = self.construir(self._construir_inventario(), plan.seleccionadas)
        return revalidar(plan, actual.plan)

    def _datos(self, inventario: Inventario) -> Dict[str, DatosCapaPlan]:
        datos = {}
        for capa_inventariada in inventario.capas_revisadas():
            capa = self._proyecto.mapLayer(capa_inventariada.id_capa)
            if capa is None:
                continue
            fuente = inventario.fuente_de(capa_inventariada)
            incorporable = fuente is not None and fuente.origen in ORIGENES_INCORPORABLES
            datos[capa.id()] = leer_datos_capa(capa, revisar_valores=incorporable)
        return datos

