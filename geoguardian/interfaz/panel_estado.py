"""Panel lateral con el semaforo del proyecto (F10, F22). Solo presenta datos."""

from __future__ import annotations

from pathlib import Path
from typing import List

from qgis.gui import QgsDockWidget
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QFontMetrics
from qgis.PyQt.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..dominio.advertencia_cierre import requiere_advertencia
from ..dominio.modelos import EstadoRecurso, NivelSemaforo, ResumenProyecto
from ..dominio.semaforo import FRASES_NIVEL, recursos_en_proyecto
from .colores import COLORES_NIVEL
from .dialogo_cierre import AVISO_PANEL

ANCHO_RUTA = 260

# Proyecto original con version administrada (D-22): la barra de mensajes lleva solo una linea;
# el nombre y la ruta se muestran aqui, en el panel.
TEXTO_BARRA_VERSION = "este proyecto tiene una versión administrada disponible."
TITULO_VERSION = "Versión administrada disponible"
NOTA_VERSION = "Para mantener la trazabilidad, continúa trabajando con esta versión."
BOTON_ABRIR_VERSION = "Abrir versión administrada"

MOTIVOS_VISIBLES = 5

ETIQUETAS_ESTADO = (
    (EstadoRecurso.ACTIVO, "Activos"),
    (EstadoRecurso.EXTERNO, "Externos"),
    (EstadoRecurso.TEMPORAL, "Temporales"),
    (EstadoRecurso.FALTANTE, "Faltantes"),
    (EstadoRecurso.HISTORICO, "Históricos"),
)


class PanelEstado(QgsDockWidget):
    guardar_solicitado = pyqtSignal()
    inicializar_solicitado = pyqtSignal()
    abrir_carpeta_solicitada = pyqtSignal()
    abrir_version_solicitada = pyqtSignal(str)

    def __init__(self, padre=None):
        super().__init__("GeoGuardian", padre)
        self.setObjectName("PanelEstadoGeoGuardian")

        contenido = QWidget()
        diseno = QVBoxLayout(contenido)

        fila_semaforo = QHBoxLayout()
        self._luz = QLabel()
        self._luz.setFixedSize(28, 28)
        self._frase = QLabel()
        self._frase.setStyleSheet("font-weight: bold; font-size: 14px;")
        fila_semaforo.addWidget(self._luz)
        fila_semaforo.addWidget(self._frase, 1)
        diseno.addLayout(fila_semaforo)

        self._encabezado = QLabel("Proyecto administrado activo")
        self._encabezado.setStyleSheet("color: #555;")
        diseno.addWidget(self._encabezado)
        self._titulo = QLabel()
        self._titulo.setWordWrap(True)
        self._titulo.setStyleSheet("font-weight: bold;")
        diseno.addWidget(self._titulo)
        self._ruta = QLabel()
        self._ruta.setTextFormat(Qt.PlainText)
        diseno.addWidget(self._ruta)

        self._ruta_version = ""
        self._titulo_version = QLabel(TITULO_VERSION)
        self._titulo_version.setStyleSheet("font-weight: bold;")
        self._nombre_version = QLabel()
        self._nombre_version.setWordWrap(True)
        self._nombre_version.setTextFormat(Qt.PlainText)
        self._ubicacion_version = QLabel()
        self._ubicacion_version.setWordWrap(True)
        self._ubicacion_version.setTextFormat(Qt.PlainText)
        self._ubicacion_version.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._ubicacion_version.setStyleSheet("color: #555;")
        self._nota_version = QLabel(NOTA_VERSION)
        self._nota_version.setWordWrap(True)
        self.boton_abrir_version = QPushButton(BOTON_ABRIR_VERSION)
        self.boton_abrir_version.clicked.connect(self._al_pedir_version)
        self._caja_version = QWidget()
        diseno_version = QVBoxLayout(self._caja_version)
        diseno_version.setContentsMargins(0, 0, 0, 0)
        for widget in (self._titulo_version, self._nombre_version, self._ubicacion_version,
                       self._nota_version, self.boton_abrir_version):
            diseno_version.addWidget(widget)
        self._caja_version.setVisible(False)
        diseno.addWidget(self._caja_version)

        self._aviso = QLabel()
        self._aviso.setWordWrap(True)
        self._aviso.setStyleSheet("color: #8a5a00;")
        diseno.addWidget(self._aviso)

        self._motivos = QLabel()
        self._motivos.setWordWrap(True)
        self._motivos.setTextFormat(Qt.PlainText)
        diseno.addWidget(self._motivos)

        self._total = QLabel()
        self._total.setStyleSheet("font-weight: bold;")
        diseno.addWidget(self._total)

        self._conteos = {}
        formulario = QFormLayout()
        for estado, etiqueta in ETIQUETAS_ESTADO:
            valor = QLabel("0")
            formulario.addRow(etiqueta + ":", valor)
            self._conteos[estado] = valor
        self._caja_conteos = QWidget()
        self._caja_conteos.setLayout(formulario)
        diseno.addWidget(self._caja_conteos)

        self.boton_abrir_carpeta = QPushButton("Abrir carpeta")
        self.boton_abrir_carpeta.clicked.connect(self.abrir_carpeta_solicitada)
        self.boton_guardar = QPushButton("Guardar ahora")
        self.boton_guardar.clicked.connect(self.guardar_solicitado)
        self.boton_inicializar = QPushButton("Inicializar proyecto")
        self.boton_inicializar.clicked.connect(self.inicializar_solicitado)
        diseno.addWidget(self.boton_guardar)
        diseno.addWidget(self.boton_abrir_carpeta)
        diseno.addWidget(self.boton_inicializar)
        diseno.addStretch(1)
        self.setWidget(contenido)

    def mostrar(self, nivel: NivelSemaforo, motivos: List[str], resumen: ResumenProyecto) -> None:
        color = COLORES_NIVEL[nivel]
        self._luz.setStyleSheet(
            "background-color: {}; border-radius: 14px; border: 1px solid #555;".format(color)
        )
        self._luz.setToolTip(nivel.value)
        self._frase.setText(FRASES_NIVEL[nivel])

        administrado = resumen.administrado
        self._encabezado.setVisible(administrado)
        self._titulo.setVisible(administrado)
        self._ruta.setVisible(administrado)
        if administrado:
            self._titulo.setText(resumen.nombre_academico or resumen.titulo or "Proyecto sin titulo")
            metricas = QFontMetrics(self._ruta.font())
            self._ruta.setText(metricas.elidedText(resumen.ruta_proyecto, Qt.ElideMiddle, ANCHO_RUTA))
            self._ruta.setToolTip(resumen.ruta_proyecto)

        # Con una version administrada disponible, el panel invita a abrirla, no a inicializar otra.
        if resumen.version_administrada and not self._ruta_version:
            self.mostrar_version_disponible(resumen.version_administrada)
        con_version = bool(self._ruta_version) and not administrado
        self._caja_version.setVisible(con_version)
        advertir = not con_version and requiere_advertencia(
            administrado, resumen.tiene_archivo, resumen.numero_capas
        )
        self._aviso.setText(AVISO_PANEL if advertir else "")
        self._aviso.setVisible(advertir)
        self.boton_inicializar.setText("Inicializar ahora" if advertir else "Inicializar proyecto")

        visibles = motivos[:MOTIVOS_VISIBLES]
        lineas = ["• " + m for m in visibles]
        if len(motivos) > MOTIVOS_VISIBLES:
            lineas.append("y {} mas".format(len(motivos) - MOTIVOS_VISIBLES))
        self._motivos.setText("\n".join(lineas))
        self._motivos.setVisible(not advertir)  # el aviso ya explica que falta inicializar

        self._total.setText("Recursos en el proyecto: {}".format(recursos_en_proyecto(resumen)))
        self._total.setVisible(administrado)
        for estado, etiqueta in self._conteos.items():
            etiqueta.setText(str(resumen.cantidad(estado)))
        self._caja_conteos.setVisible(resumen.administrado)
        self.boton_guardar.setEnabled(resumen.administrado)
        self.boton_guardar.setVisible(resumen.administrado)
        self.boton_abrir_carpeta.setVisible(administrado and bool(resumen.carpeta))
        self.boton_inicializar.setVisible(not resumen.administrado and not con_version)

    def mostrar_version_disponible(self, ruta: str) -> None:
        """Muestra (o, con ruta vacia, oculta) la version administrada de un proyecto original."""
        self._ruta_version = ruta or ""
        if self._ruta_version:
            self._nombre_version.setText(Path(self._ruta_version).stem)
            self._ubicacion_version.setText("Ubicación: " + self._ruta_version)
        self._caja_version.setVisible(bool(self._ruta_version))

    def _al_pedir_version(self):
        if self._ruta_version:
            self.abrir_version_solicitada.emit(self._ruta_version)
