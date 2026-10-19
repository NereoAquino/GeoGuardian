"""Frontera de errores comun a los componentes que reciben senales de QGIS."""

from __future__ import annotations

import functools
import traceback

from qgis.core import Qgis, QgsMessageLog

from .constantes import ETIQUETA_REGISTRO
from .dominio.modelos import TipoEvento


def protegido(metodo):
    """Ningun fallo de GeoGuardian se propaga a QGIS: se informa con `self.informar_error`."""

    @functools.wraps(metodo)
    def envoltura(self, *args):
        try:
            return metodo(self, *args)
        except Exception as error:  # noqa: BLE001
            self.informar_error(metodo.__name__, error)
            return None

    return envoltura


def informar_error(emisor, registro, operacion: str, error: Exception) -> None:
    """Escribe el error en el registro de QGIS, en gg_eventos si es posible, y lo emite."""
    QgsMessageLog.logMessage(
        "{}: {}\n{}".format(operacion, error, traceback.format_exc()),
        ETIQUETA_REGISTRO,
        Qgis.Critical,
    )
    if registro is not None:
        try:
            registro.registrar(
                TipoEvento.ERROR_COMPLEMENTO,
                "Error en {}".format(operacion),
                detalle={"operacion": operacion, "mensaje": str(error)},
            )
        except Exception:  # noqa: BLE001  (la base puede ser justamente lo que falla)
            pass
    emisor.error_ocurrido.emit("{}: {}".format(operacion, error))
