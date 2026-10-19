"""Dialogo "Revisar capas" (D-50). Solo presenta el inventario; no cambia nada del proyecto.

No importa el paquete `inventario`: recibe de complemento.py la funcion que construye el
inventario, como el panel recibe el resumen del semaforo.
"""

from __future__ import annotations

from typing import Callable, List, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..dominio.clasificacion_inventario import resumen_por_origen
from ..dominio.inventario import (
    TEXTO_DISPONIBILIDAD,
    TEXTO_NO_REVISADA,
    TEXTO_ORIGEN,
    TEXTO_SRC,
    CapaInventariada,
    Disponibilidad,
    EstadoSrc,
    Inventario,
    OrigenFuente,
)

TITULO = "Revisar capas"
BOTON_VOLVER_A_REVISAR = "Volver a revisar"
NOTA_SOLO_LECTURA = (
    "Esta revisión solo lee el proyecto: no mueve, copia ni modifica capas, archivos ni sistemas "
    "de coordenadas."
)
SIN_INVENTARIO = "No se pudieron revisar las capas. Revisa que el proyecto administrado siga abierto."
COLUMNAS = ("Capa", "Dónde está", "Estado", "SRC", "Ubicación")
NOMBRES_TIPO = {"raster": "ráster", "malla": "malla", "nube_puntos": "nube de puntos", "otro": "otro tipo"}
# Resumen: (singular, plural) de cada origen.
RESUMEN_ORIGEN = {
    OrigenFuente.ADMINISTRADA: ("en Proyecto.gpkg", "en Proyecto.gpkg"),
    OrigenFuente.CARPETA_PROYECTO: ("en la carpeta del proyecto", "en la carpeta del proyecto"),
    OrigenFuente.ARCHIVO_EXTERNO: ("fuera de la carpeta del proyecto", "fuera de la carpeta del proyecto"),
    OrigenFuente.TEMPORAL: ("temporal", "temporales"),
    OrigenFuente.SERVICIO_REMOTO: ("de un servicio en internet", "de servicios en internet"),
    OrigenFuente.BASE_DATOS_EXTERNA: ("de una base de datos externa", "de bases de datos externas"),
    OrigenFuente.VIRTUAL: ("virtual", "virtuales"),
    OrigenFuente.DESCONOCIDA: ("de origen desconocido", "de origen desconocido"),
}
# Columna SRC: texto breve; la explicacion completa (TEXTO_SRC) va en el tooltip.
BREVE_SRC = {
    EstadoSrc.COINCIDE: "igual al proyecto",
    EstadoSrc.DIFERENTE: "distinto al proyecto",
    EstadoSrc.SRC_DE_SERVICIO: "definido por el servicio",
}


def texto_ubicacion(inventario: Inventario, capa: CapaInventariada) -> str:
    fuente = inventario.fuente_de(capa)
    if fuente is None:
        return "—"
    if fuente.origen == OrigenFuente.TEMPORAL and fuente.contenedor == "memoria":
        return "En memoria"
    if fuente.origen == OrigenFuente.ADMINISTRADA:
        return "Proyecto.gpkg › {}".format(fuente.subcapa) if fuente.subcapa else "Proyecto.gpkg"
    principal = fuente.ruta_relativa or fuente.contenedor
    return "{} › {}".format(principal, fuente.subcapa) if fuente.subcapa else principal


def texto_src(capa: CapaInventariada) -> str:
    if capa.estado_src in BREVE_SRC:
        return "{} · {}".format(capa.src.identificador or capa.src.descripcion, BREVE_SRC[capa.estado_src])
    return TEXTO_SRC[capa.estado_src]


def ayuda_src(capa: CapaInventariada) -> str:
    if capa.estado_src in BREVE_SRC:
        return "{}: {}".format(capa.src.texto(), TEXTO_SRC[capa.estado_src])
    return TEXTO_SRC[capa.estado_src]


def advertencias(inventario: Inventario) -> List[str]:
    """Advertencias de revision de SRC (D-48). Solo informan."""
    lineas = []
    for capa in inventario.capas_revisadas():
        if capa.src_fuente_distinto is not None:
            lineas.append(
                "«{}»: el SRC asignado a la capa ({}) es distinto del que declara su fuente ({}). "
                "Revisa si se asignó por error.".format(
                    capa.nombre, capa.src.texto(), capa.src_fuente_distinto.texto()
                )
            )
    return lineas


def texto_resumen(inventario: Inventario) -> str:
    revisadas = inventario.capas_revisadas()
    partes = [
        "{} {}".format(n, RESUMEN_ORIGEN[o][0 if n == 1 else 1]) for o, n in resumen_por_origen(inventario)
    ]
    texto = "{} {} revisada{}".format(
        len(revisadas), "capa" if len(revisadas) == 1 else "capas", "" if len(revisadas) == 1 else "s"
    )
    if partes:
        texto += ": " + "; ".join(partes)
    no_revisadas = len(inventario.capas_no_revisadas())
    if no_revisadas:
        texto += ". {} {} no {} en esta versión".format(
            no_revisadas,
            "capa" if no_revisadas == 1 else "capas",
            "revisada" if no_revisadas == 1 else "revisadas",
        )
    return texto + "."


class DialogoRevisarCapas(QDialog):
    def __init__(self, construir: Callable[[], Optional[Inventario]], padre=None):
        super().__init__(padre)
        self.setObjectName("DialogoRevisarCapas")
        self.setWindowTitle("GeoGuardian — " + TITULO)
        self._construir = construir
        self.inventario: Optional[Inventario] = None

        diseno = QVBoxLayout(self)
        self.encabezado = QLabel()
        self.encabezado.setStyleSheet("font-weight: bold;")
        self.encabezado.setTextFormat(Qt.PlainText)
        self.encabezado.setWordWrap(True)
        self.src_proyecto = QLabel()
        self.src_proyecto.setTextFormat(Qt.PlainText)
        self.resumen = QLabel()
        self.resumen.setTextFormat(Qt.PlainText)
        self.resumen.setWordWrap(True)
        for widget in (self.encabezado, self.src_proyecto, self.resumen):
            diseno.addWidget(widget)

        self.tabla = QTableWidget(0, len(COLUMNAS))
        self.tabla.setHorizontalHeaderLabels(COLUMNAS)
        self.tabla.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla.verticalHeader().setVisible(False)
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        diseno.addWidget(self.tabla, 1)

        self.avisos = QLabel()
        self.avisos.setTextFormat(Qt.PlainText)
        self.avisos.setWordWrap(True)
        self.avisos.setStyleSheet("color: #8a5a00;")
        diseno.addWidget(self.avisos)

        nota = QLabel(NOTA_SOLO_LECTURA)
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #555;")
        diseno.addWidget(nota)

        botones = QHBoxLayout()
        botones.addStretch(1)
        self.boton_revisar = QPushButton(BOTON_VOLVER_A_REVISAR)
        self.boton_revisar.clicked.connect(self.revisar)
        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.clicked.connect(self.close)
        botones.addWidget(self.boton_revisar)
        botones.addWidget(self.boton_cerrar)
        diseno.addLayout(botones)
        self.resize(820, 460)

    def revisar(self, *_args) -> Optional[Inventario]:
        """Construye el inventario de nuevo y lo muestra (D-49)."""
        self.inventario = self._construir()
        self.mostrar(self.inventario)
        return self.inventario

    def mostrar(self, inventario: Optional[Inventario]) -> None:
        self.tabla.setRowCount(0)
        if inventario is None:
            self.encabezado.setText(SIN_INVENTARIO)
            self.src_proyecto.setText("")
            self.resumen.setText("")
            self.avisos.setVisible(False)
            return
        self.encabezado.setText("{} · revisado {}".format(inventario.nombre_proyecto, _hora(inventario.fecha)))
        self.src_proyecto.setText("SRC del proyecto: " + inventario.src_proyecto.texto())
        self.resumen.setText(texto_resumen(inventario))
        for capa in inventario.capas:
            self._agregar_fila(inventario, capa)
        self.tabla.resizeColumnsToContents()
        lineas = advertencias(inventario)
        self.avisos.setText("\n".join("• " + l for l in lineas))
        self.avisos.setVisible(bool(lineas))

    def _agregar_fila(self, inventario: Inventario, capa: CapaInventariada) -> None:
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        if not capa.revisada:
            valores = [
                capa.nombre,
                "{} ({})".format(TEXTO_NO_REVISADA, NOMBRES_TIPO.get(capa.tipo_capa, capa.tipo_capa)),
                "—",
                "—",
                "—",
            ]
            ayudas = list(valores)
        else:
            fuente = inventario.fuente_de(capa)
            valores = [
                capa.nombre,
                TEXTO_ORIGEN[fuente.origen] if fuente else "—",
                TEXTO_DISPONIBILIDAD[fuente.disponibilidad] if fuente else "—",
                texto_src(capa),
                texto_ubicacion(inventario, capa),
            ]
            ayudas = list(valores)
            ayudas[3] = ayuda_src(capa)
            if fuente is not None and fuente.disponibilidad != Disponibilidad.DISPONIBLE:
                valores[2] = "⚠ " + valores[2]
        for columna, valor in enumerate(valores):
            celda = QTableWidgetItem(valor)
            celda.setToolTip(ayudas[columna])
            self.tabla.setItem(fila, columna, celda)


def _hora(fecha_iso: str) -> str:
    """'2026-10-19T12:30:05-06:00' -> '2026-10-19 12:30'."""
    return fecha_iso[:16].replace("T", " ") if fecha_iso else ""
