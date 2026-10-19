"""Recuerda que proyecto original se adopto y donde quedo su version administrada (D-22, D-33).

Se guarda en la configuracion del perfil de QGIS, nunca en archivos del proyecto. Cada adopcion
guarda la identidad del original y de la version administrada (etiqueta del volumen y ruta dentro
del volumen) y el id_proyecto, porque la letra de unidad puede cambiar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

from ..constantes import CLAVE_ADOPCIONES
from ..dominio.clasificacion import normalizar_ruta
from ..dominio.recuperacion import IdentidadUbicacion

VERSION_FORMATO = 2


@dataclass
class Adopcion:
    origen: IdentidadUbicacion
    administrado: IdentidadUbicacion
    id_proyecto: str = ""  # vacio en asociaciones del formato anterior

    def a_dict(self) -> dict:
        return {
            "id_proyecto": self.id_proyecto,
            "origen": self.origen.a_dict(),
            "administrado": self.administrado.a_dict(),
        }


def _misma_ubicacion(a: IdentidadUbicacion, b: Optional[IdentidadUbicacion]) -> bool:
    """Misma ruta, o misma etiqueta de volumen y misma ruta dentro del volumen."""
    if b is None:
        return False
    if a.ruta and b.ruta and normalizar_ruta(a.ruta) == normalizar_ruta(b.ruta):
        return True
    return bool(
        a.etiqueta_volumen
        and a.ruta_en_volumen
        and a.etiqueta_volumen.casefold() == b.etiqueta_volumen.casefold()
        and a.ruta_en_volumen.casefold() == b.ruta_en_volumen.casefold()
    )


class RegistroAdopciones:
    def __init__(self, configuracion=None):
        if configuracion is None:
            from qgis.core import QgsSettings  # importacion diferida: las pruebas unitarias no tienen QGIS

            configuracion = QgsSettings()
        self._configuracion = configuracion

    # --- escritura ---------------------------------------------------------

    def agregar(
        self,
        origen: Optional[IdentidadUbicacion],
        administrado: IdentidadUbicacion,
        id_proyecto: str,
    ) -> None:
        if origen is None or not origen.ruta:
            return
        adopciones = [a for a in self.adopciones() if not _misma_ubicacion(a.origen, origen)]
        adopciones.append(Adopcion(origen, administrado, id_proyecto))
        self._escribir(adopciones)

    def reemplazar(self, anterior: Adopcion, nueva: Adopcion) -> None:
        adopciones = [nueva if self._es(a, anterior) else a for a in self.adopciones()]
        self._escribir(adopciones)

    def actualizar_administrado(self, id_proyecto: str, administrado: IdentidadUbicacion) -> bool:
        """El proyecto se abrio desde otra ubicacion: se actualizan sus asociaciones (D-33)."""
        if not id_proyecto:
            return False
        adopciones = self.adopciones()
        cambio = False
        for adopcion in adopciones:
            if adopcion.id_proyecto == id_proyecto and adopcion.administrado != administrado:
                adopcion.administrado = administrado
                cambio = True
        if cambio:
            self._escribir(adopciones)
        return cambio

    # --- lectura -----------------------------------------------------------

    def buscar(self, origen: IdentidadUbicacion) -> Optional[Adopcion]:
        """Adopcion cuyo original es `origen`, aunque su unidad haya cambiado de letra."""
        for adopcion in self.adopciones():
            if _misma_ubicacion(adopcion.origen, origen):
                return adopcion
        return None

    def adopciones(self) -> List[Adopcion]:
        valor = self._configuracion.value(CLAVE_ADOPCIONES, "")
        try:
            datos = json.loads(valor) if valor else {}
        except (TypeError, ValueError):
            return []
        if isinstance(datos, dict) and datos.get("version") == VERSION_FORMATO:
            resultado = []
            for entrada in datos.get("adopciones") or []:
                if not isinstance(entrada, dict):
                    continue
                origen = IdentidadUbicacion.de_dict(entrada.get("origen"))
                administrado = IdentidadUbicacion.de_dict(entrada.get("administrado"))
                if origen and administrado:
                    resultado.append(Adopcion(origen, administrado, str(entrada.get("id_proyecto") or "")))
            return resultado
        if isinstance(datos, dict):
            # Formato anterior de rc2: {ruta_origen: ruta_administrado}, sin id_proyecto.
            return [
                Adopcion(IdentidadUbicacion(ruta=o), IdentidadUbicacion(ruta=a))
                for o, a in datos.items()
                if isinstance(o, str) and isinstance(a, str) and o and a
            ]
        return []

    # --- internos ----------------------------------------------------------

    @staticmethod
    def _es(a: Adopcion, b: Adopcion) -> bool:
        return a.id_proyecto == b.id_proyecto and _misma_ubicacion(a.origen, b.origen)

    def _escribir(self, adopciones: List[Adopcion]) -> None:
        datos = {"version": VERSION_FORMATO, "adopciones": [a.a_dict() for a in adopciones]}
        self._configuracion.setValue(CLAVE_ADOPCIONES, json.dumps(datos, ensure_ascii=False))
