"""Adaptador del sistema de archivos para las reglas de dominio/ubicacion (D-23)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from qgis.PyQt.QtCore import QStandardPaths, QStorageInfo

from ..dominio.ubicacion import InfoVolumen, misma_unidad

VARIABLES_ONEDRIVE = ("OneDrive", "OneDriveCommercial", "OneDriveConsumer")
_SISTEMAS_VIRTUALES = frozenset({"tmpfs", "devtmpfs", "proc", "sysfs", "overlay", "squashfs", "cgroup", "cgroup2"})


def _ruta_existente(ruta: str) -> Path:
    actual = Path(ruta)
    while not actual.exists() and actual.parent != actual:
        actual = actual.parent
    return actual


def _desde_qt(almacen: QStorageInfo) -> InfoVolumen:
    sistema = bytes(almacen.fileSystemType()).decode("utf-8", "replace")
    return InfoVolumen(
        raiz=almacen.rootPath(),
        sistema_archivos=sistema,
        bytes_libres=int(almacen.bytesAvailable()),
        solo_lectura=almacen.isReadOnly(),
        listo=almacen.isReady(),
        nombre=almacen.displayName(),
        etiqueta=almacen.name(),
    )


def info_volumen(ruta: str) -> Optional[InfoVolumen]:
    """Volumen que contiene `ruta` (o su ancestro existente mas cercano)."""
    if not ruta:
        return None
    almacen = QStorageInfo(str(_ruta_existente(ruta)))
    if not almacen.isValid():
        return None
    return _desde_qt(almacen)


def carpeta_documentos() -> str:
    return QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)


def raiz_documentos() -> Optional[str]:
    volumen = info_volumen(carpeta_documentos())
    return volumen.raiz if volumen else None


def volumenes_montados() -> List[InfoVolumen]:
    """Volumenes listos, sin sistemas de archivos virtuales. Para buscar por etiqueta (D-34)."""
    volumenes = []
    for almacen in QStorageInfo.mountedVolumes():
        if not (almacen.isValid() and almacen.isReady()):
            continue
        volumen = _desde_qt(almacen)
        if volumen.sistema_archivos.lower() in _SISTEMAS_VIRTUALES:
            continue
        volumenes.append(volumen)
    return volumenes


class Almacenamiento:
    """Lo que AdministradorProyecto necesita del sistema; las pruebas lo sustituyen (D-33)."""

    def info_volumen(self, ruta: str) -> Optional[InfoVolumen]:
        return info_volumen(ruta)

    def volumenes(self) -> List[InfoVolumen]:
        return volumenes_montados()

    def existe(self, ruta: str) -> bool:
        return os.path.exists(ruta)


def volumenes_externos() -> List[InfoVolumen]:
    """Volumenes listos, con escritura y distintos del de Documentos.

    No se decide si son "removibles": Qt 5 no lo expone y Windows reporta muchos discos USB
    como fijos (D-23). El estudiante elige.
    """
    documentos = raiz_documentos()
    volumenes = []
    for almacen in QStorageInfo.mountedVolumes():
        if not (almacen.isValid() and almacen.isReady()) or almacen.isReadOnly():
            continue
        volumen = _desde_qt(almacen)
        if volumen.sistema_archivos.lower() in _SISTEMAS_VIRTUALES or almacen.bytesTotal() <= 0:
            continue
        if misma_unidad(volumen.raiz, documentos):
            continue
        volumenes.append(volumen)
    return volumenes


def raices_onedrive() -> List[str]:
    return [os.environ[v] for v in VARIABLES_ONEDRIVE if os.environ.get(v)]
