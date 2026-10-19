"""Advertencia al cerrar QGIS con un proyecto no administrado (D-17, D-18, F12) o con un
original que tiene version administrada (D-37).

QGIS 3.28 no permite a un complemento cancelar "Proyecto nuevo" ni "Abrir proyecto"; el cierre de
la ventana principal si se puede cancelar con un filtro de eventos, que recibe el QCloseEvent
antes que QGIS.
"""

from __future__ import annotations

from typing import Callable, Optional

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QEvent, QObject, QTimer

from .constantes import ETIQUETA_REGISTRO
from .dominio.advertencia_cierre import AccionCierre, requiere_advertencia


class FiltroCierre(QObject):
    def __init__(
        self,
        ventana,
        administrador,
        preguntar: Callable[[], AccionCierre],
        abrir_asistente: Callable[[], None],
        preguntar_version: Optional[Callable[[str], AccionCierre]] = None,
        abrir_version: Optional[Callable[[str], None]] = None,
        padre=None,
    ):
        super().__init__(padre)
        self._ventana = ventana
        self._administrador = administrador
        self._preguntar = preguntar
        self._abrir_asistente = abrir_asistente
        self._preguntar_version = preguntar_version
        self._abrir_version = abrir_version
        self._instalado = False

    @property
    def instalado(self) -> bool:
        return self._instalado

    def instalar(self) -> None:
        if not self._instalado:
            self._ventana.installEventFilter(self)
            self._instalado = True

    def desinstalar(self) -> None:
        if self._instalado:
            try:
                self._ventana.removeEventFilter(self)
            except RuntimeError:
                pass  # la ventana ya se destruyo
            self._instalado = False

    def version_administrada(self) -> str:
        """Con un original asociado se ofrece abrir su version, nunca inicializar otra (D-37)."""
        if self._preguntar_version is None:
            return ""
        return getattr(self._administrador, "version_administrada", "") or ""

    def debe_advertir(self) -> bool:
        resumen = self._administrador.resumen_actual()
        return requiere_advertencia(resumen.administrado, resumen.tiene_archivo, resumen.numero_capas)

    def eventFilter(self, objeto, evento):  # noqa: N802  (API de Qt)
        if evento.type() != QEvent.Close or objeto is not self._ventana:
            return False
        try:
            ruta_version = self.version_administrada()
            if ruta_version:
                accion = self._preguntar_version(ruta_version)
            elif not self.debe_advertir():
                return False
            else:
                accion = self._preguntar()
        except Exception as error:  # noqa: BLE001  (un fallo nunca impide cerrar QGIS)
            QgsMessageLog.logMessage("FiltroCierre: {}".format(error), ETIQUETA_REGISTRO, Qgis.Critical)
            return False
        if accion == AccionCierre.CERRAR:
            return False
        evento.ignore()
        if accion == AccionCierre.INICIALIZAR:
            QTimer.singleShot(0, self._abrir_asistente)
        elif accion == AccionCierre.ABRIR_VERSION and self._abrir_version is not None:
            QTimer.singleShot(0, lambda: self._abrir_version(ruta_version))
        return True
