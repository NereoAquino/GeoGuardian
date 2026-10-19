"""Rutas y servicios de un proyecto administrado abierto. Sin Qt ni QGIS."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .constantes import CARPETA_GEOGUARDIAN, NOMBRE_ARCHIVO_PROYECTO, NOMBRE_GEOPAQUETE, NOMBRE_MANIFIESTO
from .eventos.registro_eventos import RegistroEventos
from .persistencia.repositorio import RepositorioGeoGuardian


class ContextoProyecto:
    def __init__(self, carpeta: Path, archivo_proyecto: str = NOMBRE_ARCHIVO_PROYECTO):
        self.carpeta = Path(carpeta)
        self.archivo_proyecto = archivo_proyecto
        self.repositorio = RepositorioGeoGuardian(self.ruta_geopaquete)
        self.registro = RegistroEventos(self.repositorio)
        # Verdadero cuando Proyecto.gpkg tiene sus tablas y la fila de gg_proyecto correcta.
        self.geopaquete_utilizable = False
        self.fila_proyecto: Optional[dict] = None

    @property
    def ruta_proyecto(self) -> Path:
        return self.carpeta / self.archivo_proyecto

    @property
    def ruta_geopaquete(self) -> Path:
        return self.carpeta / NOMBRE_GEOPAQUETE

    @property
    def ruta_manifiesto(self) -> Path:
        return self.carpeta / CARPETA_GEOGUARDIAN / NOMBRE_MANIFIESTO
