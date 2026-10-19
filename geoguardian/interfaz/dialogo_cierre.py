"""Dialogos de cierre: proyecto no administrado (D-26) y original con version administrada (D-37)."""

from __future__ import annotations

from qgis.PyQt.QtWidgets import QMessageBox

from ..dominio.advertencia_cierre import AccionCierre

TITULO = "Este proyecto todavía no está administrado"
MENSAJE = (
    "GeoGuardian detectó que este proyecto todavía no está administrado. Si lo cierras ahora, "
    "GeoGuardian no podrá garantizar la integridad, trazabilidad ni posterior consolidación de "
    "sus archivos. ¿Deseas inicializarlo antes de cerrar?"
)
FINALIDAD = (
    "GeoGuardian organiza tu proyecto en una carpeta propia, registra qué datos usa y te avisa si "
    "alguno puede perderse, para que puedas entregarlo completo."
)
AVISO_PANEL = (
    "Este proyecto todavía no está administrado. Si lo cierras sin inicializarlo, GeoGuardian no "
    "podrá garantizar su integridad ni su trazabilidad."
)


def preguntar_cierre(padre=None) -> AccionCierre:
    caja = QMessageBox(padre)
    caja.setIcon(QMessageBox.Warning)
    caja.setWindowTitle("GeoGuardian")
    caja.setText(TITULO)
    caja.setInformativeText(MENSAJE + "\n\n" + FINALIDAD)
    inicializar = caja.addButton("Inicializar ahora", QMessageBox.AcceptRole)
    cerrar = caja.addButton("Cerrar sin administrar", QMessageBox.DestructiveRole)
    cancelar = caja.addButton("Cancelar", QMessageBox.RejectRole)
    caja.setDefaultButton(cancelar)
    caja.setEscapeButton(cancelar)
    caja.exec_()
    pulsado = caja.clickedButton()
    if pulsado is inicializar:
        return AccionCierre.INICIALIZAR
    if pulsado is cerrar:
        return AccionCierre.CERRAR
    return AccionCierre.CANCELAR


TITULO_VERSION = "Este proyecto tiene una versión administrada"
MENSAJE_VERSION = (
    "Estás trabajando en el proyecto original. Para mantener la trazabilidad, continúa trabajando "
    "con su versión administrada."
)
BOTON_ABRIR_VERSION = "Abrir versión administrada"
BOTON_CERRAR_PROYECTO = "Cerrar proyecto"


def crear_dialogo_version(ruta_version: str, padre=None):
    """Caja y botones del cierre de un original con version administrada (sin ejecutarla)."""
    caja = QMessageBox(padre)
    caja.setIcon(QMessageBox.Information)
    caja.setWindowTitle("GeoGuardian")
    caja.setText(TITULO_VERSION)
    caja.setInformativeText(MENSAJE_VERSION + "\n\nUbicación: " + ruta_version)
    botones = {
        AccionCierre.ABRIR_VERSION: caja.addButton(BOTON_ABRIR_VERSION, QMessageBox.AcceptRole),
        AccionCierre.CERRAR: caja.addButton(BOTON_CERRAR_PROYECTO, QMessageBox.DestructiveRole),
        AccionCierre.CANCELAR: caja.addButton("Cancelar", QMessageBox.RejectRole),
    }
    caja.setDefaultButton(botones[AccionCierre.ABRIR_VERSION])
    caja.setEscapeButton(botones[AccionCierre.CANCELAR])
    return caja, botones


def preguntar_cierre_version(ruta_version: str, padre=None) -> AccionCierre:
    caja, botones = crear_dialogo_version(ruta_version, padre)
    caja.exec_()
    pulsado = caja.clickedButton()
    for accion, boton in botones.items():
        if pulsado is boton:
            return accion
    return AccionCierre.CANCELAR
