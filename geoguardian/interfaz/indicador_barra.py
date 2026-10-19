"""Indicador permanente en la barra de herramientas (F21, D-31). Solo presenta datos."""

from __future__ import annotations

import os
from typing import List

from qgis.PyQt.QtCore import QRect, QSize, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QIcon, QPainter, QPen
from qgis.PyQt.QtWidgets import QStyle, QStyleOptionToolButton, QStylePainter, QToolButton

from ..dominio.modelos import NivelSemaforo
from ..dominio.semaforo import texto_indicador
from .colores import COLORES_NIVEL

RUTA_ICONO = os.path.join(os.path.dirname(__file__), "iconos", "geoguardian.svg")
LADO_ICONO = 24
MARGEN = 4


class IndicadorBarra(QToolButton):
    """Un solo control: icono de GeoGuardian + punto del semaforo + texto del estado.

    Al ser un unico boton, el clic en cualquier parte emite `clicked` y el complemento
    muestra u oculta el panel. El boton (fondo al pasar el raton, marcado, foco) lo dibuja el
    estilo de Qt; logo, punto y texto se dibujan aqui para controlar tamaños, separacion y
    alineacion vertical.
    """

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setObjectName("IndicadorGeoGuardian")
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setAutoRaise(True)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._logo = QIcon(RUTA_ICONO)
        self._lado = LADO_ICONO
        self.nivel = NivelSemaforo.GRIS
        self.ajustar_tamano(LADO_ICONO)
        self.mostrar(NivelSemaforo.GRIS, [])

    def ajustar_tamano(self, lado) -> None:
        """Sigue el tamaño de iconos de la barra: el logo mide lo mismo que los iconos de QGIS."""
        if isinstance(lado, QSize):
            lado = lado.height()
        self._lado = max(16, int(lado))
        self.setIconSize(QSize(self._lado, self._lado))
        self.updateGeometry()
        self.update()

    def mostrar(self, nivel: NivelSemaforo, motivos: List[str], frase: str = "") -> None:
        frase, tooltip = texto_indicador(nivel, motivos, frase)
        self.setText(frase)
        self.setToolTip(tooltip)
        self.setAccessibleName("GeoGuardian: " + frase)
        self.setAccessibleDescription(tooltip)
        if nivel != self.nivel:
            self.nivel = nivel
            self.update()

    # --- medidas -----------------------------------------------------------

    def _diametro_punto(self) -> int:
        """Algo mas de la mitad del logo (14 px con iconos de 24 px)."""
        return max(10, round(self._lado * 0.58))

    def _espacio(self) -> int:
        """Separacion entre logo, punto y texto (6 px con iconos de 24 px)."""
        return max(5, self._lado // 4)

    def sizeHint(self) -> QSize:  # noqa: N802  (API de Qt)
        metricas = self.fontMetrics()
        ancho = (
            MARGEN + self._lado + self._espacio() + self._diametro_punto() + self._espacio()
            + metricas.horizontalAdvance(self.text()) + MARGEN + 2
        )
        alto = max(self._lado, metricas.height()) + 2 * MARGEN
        return QSize(ancho, alto)

    def minimumSizeHint(self) -> QSize:  # noqa: N802  (API de Qt)
        return self.sizeHint()

    # --- dibujo ------------------------------------------------------------

    def paintEvent(self, _evento):  # noqa: N802  (API de Qt)
        pintor = QStylePainter(self)
        opcion = QStyleOptionToolButton()
        self.initStyleOption(opcion)
        opcion.text = ""
        opcion.icon = QIcon()
        pintor.drawComplexControl(QStyle.CC_ToolButton, opcion)  # solo el fondo del boton

        pintor.setRenderHint(QPainter.Antialiasing)
        centro = self.height() // 2
        x = MARGEN
        modo = QIcon.Normal if self.isEnabled() else QIcon.Disabled
        self._logo.paint(pintor, QRect(x, centro - self._lado // 2, self._lado, self._lado), Qt.AlignCenter, modo)
        x += self._lado + self._espacio()

        diametro = self._diametro_punto()
        pintor.setPen(QPen(QColor("#555555"), 1))
        pintor.setBrush(QBrush(QColor(COLORES_NIVEL[self.nivel])))
        pintor.drawEllipse(x, centro - diametro // 2, diametro - 1, diametro - 1)
        x += diametro + self._espacio()

        pintor.setPen(self.palette().color(self.foregroundRole()))
        pintor.drawText(QRect(x, 0, self.width() - x, self.height()), int(Qt.AlignLeft | Qt.AlignVCenter), self.text())
