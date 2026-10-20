"""Dialogo "Revisar capas" con plan de incorporacion (v0.2.0, Hito 2; D-65, D-66).

Subclase del dialogo del Hito 1, que no se modifica: sus columnas y textos siguen iguales. Se
agregan una casilla en la celda "Capa", la columna "Incorporar", el conteo y "Preparar
incorporacion", que muestra el plan en una segunda pagina de la misma ventana.

No escribe, copia ni cambia nada: no hay boton "Incorporar" en el Hito 2. Recibe de complemento.py
las funciones que construyen y revalidan el plan, como el dialogo del Hito 1 recibe la del
inventario.
"""

from __future__ import annotations

from typing import Callable, Optional

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..dominio.inventario import CapaInventariada, Inventario
from ..dominio.nombres_destino import texto_destino
from ..dominio.plan_incorporacion import (
    AVISO_PLAN,
    TEXTO_NO_VECTORIAL,
    TEXTO_SIN_PLAN,
    PlanIncorporacion,
    ResultadoPlan,
    ayuda_estado,
    con_seleccion,
    seleccion_tras_revisar,
    texto_advertencias,
    texto_advertencias_breve,
    texto_capas_relacionadas,
    texto_conteo,
    texto_estado,
    texto_origen,
    texto_resumen_plan,
)
from ..dominio.revalidacion import TEXTO_CAMBIO, ResultadoRevalidacion
from .dialogo_revisar_capas import COLUMNAS, DialogoRevisarCapas

COLUMNA_INCORPORAR = "Incorporar"
INDICE_INCORPORAR = len(COLUMNAS)
COLUMNAS_PLAN = ("Elemento", "Origen", "Destino propuesto", "Capas relacionadas", "Advertencias")
BOTON_PREPARAR = "Preparar incorporación"
BOTON_VOLVER_LISTA = "← Volver a la lista"
TITULO_PLAN = "Plan de incorporación"
SIN_PLAN = "No se pudo preparar el plan de incorporación. Revisa el registro de mensajes de QGIS."
AYUDA_PLAN_OBSOLETO = "Pulsa «Volver a revisar» antes de preparar la incorporación."
ROL_CLAVE = Qt.UserRole + 1
ANCHO_MAXIMO_COLUMNA = 280  # px; el texto completo queda en la ayuda emergente


def texto_aviso_cambios(resultado: ResultadoRevalidacion) -> str:
    lineas = [resultado.texto()]
    for cambio in resultado.cambios:
        lineas.append("• {}: {}".format(cambio.nombre, " ".join(TEXTO_CAMBIO[m] for m in cambio.motivos)))
    return "\n".join(lineas)


class DialogoRevisarCapasConPlan(DialogoRevisarCapas):
    def __init__(
        self,
        construir_inventario: Callable[[], Optional[Inventario]],
        construir_plan: Callable[[Inventario], Optional[ResultadoPlan]],
        preparar_plan: Callable[[PlanIncorporacion], Optional[ResultadoRevalidacion]],
        padre=None,
    ):
        super().__init__(construir_inventario, padre)
        self.setObjectName("DialogoRevisarCapasConPlan")
        self._construir_plan = construir_plan
        self._preparar_plan = preparar_plan
        self.plan: Optional[PlanIncorporacion] = None  # con la seleccion actual del estudiante
        self.plan_preparado: Optional[PlanIncorporacion] = None
        # D-70: verdadero cuando la revalidacion encontro cambios. Solo "Volver a revisar" lo limpia.
        self.plan_obsoleto = False
        self.motivo_sin_plan = ""
        self._llenando = False

        self.tabla.setColumnCount(len(COLUMNAS) + 1)
        self.tabla.setHorizontalHeaderLabels(COLUMNAS + (COLUMNA_INCORPORAR,))
        # Solo cambia el orden visual: "Incorporar" junto a "Capa", sin mover las columnas del Hito 1.
        self.tabla.horizontalHeader().moveSection(INDICE_INCORPORAR, 1)
        self.tabla.itemChanged.connect(self._al_cambiar_celda)

        self.aviso_plan = QLabel()
        self.aviso_plan.setTextFormat(Qt.PlainText)
        self.aviso_plan.setWordWrap(True)
        self.aviso_plan.setStyleSheet("color: #a61b1b;")
        self.aviso_plan.setVisible(False)
        self.conteo = QLabel()
        self.conteo.setTextFormat(Qt.PlainText)
        self.conteo.setWordWrap(True)
        self.conteo.setStyleSheet("font-weight: bold;")
        self.boton_preparar = QPushButton(BOTON_PREPARAR)
        self.boton_preparar.setEnabled(False)
        self.boton_preparar.clicked.connect(self.preparar)

        self.pila = QStackedWidget()
        self.pila.addWidget(self._pagina_lista())
        self.pila.addWidget(self._pagina_plan())
        self.layout().addWidget(self.pila)
        self.resize(980, 520)

    # --- construccion de las paginas ------------------------------------------------------

    def _pagina_lista(self) -> QWidget:
        """Pasa los elementos del Hito 1 a la primera pagina, en el mismo orden."""
        diseno = self.layout()
        pagina = QWidget()
        lista = QVBoxLayout(pagina)
        lista.setContentsMargins(0, 0, 0, 0)
        elementos = []
        while diseno.count():
            estiramiento = diseno.stretch(0)
            elementos.append((diseno.takeAt(0), estiramiento))
        for elemento, estiramiento in elementos:
            if elemento.widget() is not None:
                lista.addWidget(elemento.widget(), estiramiento)
            elif elemento.layout() is not None:
                # Fila de botones del Hito 1: se rehace con los mismos botones y el nuevo.
                anterior = elemento.layout()
                anterior.removeWidget(self.boton_revisar)
                anterior.removeWidget(self.boton_cerrar)
                lista.addWidget(self.aviso_plan)
                lista.addWidget(self.conteo)
                botones = QHBoxLayout()
                botones.addStretch(1)
                for boton in (self.boton_preparar, self.boton_revisar, self.boton_cerrar):
                    botones.addWidget(boton)
                lista.addLayout(botones)
        return pagina

    def _pagina_plan(self) -> QWidget:
        pagina = QWidget()
        diseno = QVBoxLayout(pagina)
        diseno.setContentsMargins(0, 0, 0, 0)
        titulo = QLabel(TITULO_PLAN)
        titulo.setStyleSheet("font-weight: bold;")
        aviso = QLabel(AVISO_PLAN)
        aviso.setWordWrap(True)
        aviso.setStyleSheet("background: #e8f1fb; color: #1d3f66; padding: 6px; border-radius: 3px;")
        self.resumen_plan = QLabel()
        self.resumen_plan.setTextFormat(Qt.PlainText)
        self.resumen_plan.setWordWrap(True)
        self.tabla_plan = QTableWidget(0, len(COLUMNAS_PLAN))
        self.tabla_plan.setHorizontalHeaderLabels(COLUMNAS_PLAN)
        self.tabla_plan.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabla_plan.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabla_plan.verticalHeader().setVisible(False)
        self.tabla_plan.setTextElideMode(Qt.ElideMiddle)  # nombres largos: se recortan a la vista
        self.tabla_plan.setWordWrap(True)
        self.tabla_plan.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla_plan.horizontalHeader().setStretchLastSection(True)
        self.boton_volver_lista = QPushButton(BOTON_VOLVER_LISTA)
        self.boton_volver_lista.clicked.connect(self.volver_a_la_lista)
        cerrar = QPushButton("Cerrar")
        cerrar.clicked.connect(self.close)
        botones = QHBoxLayout()
        botones.addWidget(self.boton_volver_lista)
        botones.addStretch(1)
        botones.addWidget(cerrar)
        for widget in (titulo, aviso, self.resumen_plan):
            diseno.addWidget(widget)
        diseno.addWidget(self.tabla_plan, 1)
        diseno.addLayout(botones)
        return pagina

    # --- lista ----------------------------------------------------------------------------

    def revisar(self, *_args):
        self.volver_a_la_lista()
        self.aviso_plan.setVisible(False)
        self.plan_obsoleto = False
        self.plan_preparado = None
        return super().revisar()

    def mostrar(self, inventario: Optional[Inventario]) -> None:
        super().mostrar(inventario)
        resultado = self._construir_plan(inventario) if inventario is not None else None
        anterior = self.plan
        if resultado is None:
            self.plan, self.motivo_sin_plan = None, (SIN_PLAN if inventario is not None else "")
        elif resultado.plan is None:
            self.plan, self.motivo_sin_plan = None, resultado.motivo_sin_plan
        else:
            nuevo = resultado.plan
            self.plan, self.motivo_sin_plan = con_seleccion(nuevo, seleccion_tras_revisar(anterior, nuevo)), ""
        self._llenando = True
        try:
            for fila, capa in enumerate(inventario.capas if inventario is not None else ()):
                self._decorar_fila(fila, capa)
        finally:
            self._llenando = False
        self.tabla.resizeColumnsToContents()
        self._actualizar_pie()

    def _decorar_fila(self, fila: int, capa: CapaInventariada) -> None:
        unidad = self.plan.unidad_de_capa(capa.id_capa) if (self.plan and capa.revisada) else None
        if not capa.revisada:
            texto, ayuda = TEXTO_NO_VECTORIAL, TEXTO_NO_VECTORIAL
        elif self.plan is None:
            texto, ayuda = TEXTO_SIN_PLAN, self.motivo_sin_plan or TEXTO_SIN_PLAN
        else:
            texto, ayuda = texto_estado(unidad), ayuda_estado(unidad)
        celda = QTableWidgetItem(texto)
        celda.setToolTip(ayuda)
        self.tabla.setItem(fila, INDICE_INCORPORAR, celda)
        if unidad is None:
            return
        celda_capa = self.tabla.item(fila, 0)
        celda_capa.setData(ROL_CLAVE, unidad.clave_unidad)
        marcada = unidad.clave_unidad in self.plan.seleccionadas
        celda_capa.setCheckState(Qt.Checked if marcada else Qt.Unchecked)
        if unidad.seleccionable:
            celda_capa.setFlags(celda_capa.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        else:
            # Casilla visible pero inactiva: el motivo esta en la columna "Incorporar".
            celda_capa.setFlags(celda_capa.flags() & ~Qt.ItemIsUserCheckable & ~Qt.ItemIsEnabled)
        celda_capa.setToolTip(ayuda)

    def _al_cambiar_celda(self, celda: QTableWidgetItem) -> None:
        if self._llenando or self.plan is None or celda.column() != 0:
            return
        clave = celda.data(ROL_CLAVE)
        if not clave:
            return
        claves = set(self.plan.seleccionadas)
        if celda.checkState() == Qt.Checked:
            claves.add(clave)
        else:
            claves.discard(clave)
        if claves == set(self.plan.seleccionadas):
            return
        self.plan = con_seleccion(self.plan, claves)
        self._sincronizar_casillas()
        if not self.plan_obsoleto:
            self.aviso_plan.setVisible(False)
        self._actualizar_pie()

    def _sincronizar_casillas(self) -> None:
        """Las capas de una misma unidad se marcan juntas (D-65)."""
        self._llenando = True
        try:
            for fila in range(self.tabla.rowCount()):
                celda = self.tabla.item(fila, 0)
                clave = celda.data(ROL_CLAVE) if celda is not None else None
                if clave:
                    celda.setCheckState(Qt.Checked if clave in self.plan.seleccionadas else Qt.Unchecked)
        finally:
            self._llenando = False

    def _actualizar_pie(self) -> None:
        if self.plan is None:
            self.conteo.setText(self.motivo_sin_plan)
        else:
            self.conteo.setText(texto_conteo(self.plan))
        self.conteo.setVisible(bool(self.conteo.text()))
        self.boton_preparar.setEnabled(self.puede_preparar())
        self.boton_preparar.setToolTip(AYUDA_PLAN_OBSOLETO if self.plan_obsoleto else "")

    def puede_preparar(self) -> bool:
        return bool(self.plan and self.plan.seleccionadas and not self.plan_obsoleto)

    # --- plan -----------------------------------------------------------------------------

    def preparar(self, *_args) -> Optional[PlanIncorporacion]:
        """Revalida contra el estado actual y, si nada cambio, muestra el plan. No escribe nada."""
        if not self.puede_preparar():
            return None
        resultado = self._preparar_plan(self.plan)
        if resultado is None:
            self._invalidar_plan(SIN_PLAN)
            return None
        if not resultado.vigente or resultado.plan_actual is None:
            self._invalidar_plan(texto_aviso_cambios(resultado))
            return None
        self.plan_preparado = resultado.plan_actual
        self._mostrar_plan(self.plan_preparado)
        self.pila.setCurrentIndex(1)
        return self.plan_preparado

    def _invalidar_plan(self, texto: str) -> None:
        """D-70: el plan queda obsoleto hasta "Volver a revisar"; ya no se puede preparar ni mostrar."""
        self.plan_obsoleto = True
        self.plan_preparado = None
        self.tabla_plan.setRowCount(0)
        self.resumen_plan.clear()
        self.aviso_plan.setText(texto)
        self.aviso_plan.setVisible(True)
        self._actualizar_pie()

    def _mostrar_plan(self, plan: PlanIncorporacion) -> None:
        self.resumen_plan.setText(texto_resumen_plan(plan))
        self.tabla_plan.setRowCount(0)
        for unidad in plan.unidades_seleccionadas():
            fila = self.tabla_plan.rowCount()
            self.tabla_plan.insertRow(fila)
            valores = (
                unidad.nombre,
                texto_origen(unidad),
                texto_destino(unidad.destino),
                texto_capas_relacionadas(unidad),
                texto_advertencias_breve(unidad),
            )
            ayudas = valores[:-1] + (texto_advertencias(unidad),)
            for columna, valor in enumerate(valores):
                celda = QTableWidgetItem(valor)
                celda.setToolTip(ayudas[columna])
                self.tabla_plan.setItem(fila, columna, celda)
        self.tabla_plan.resizeColumnsToContents()
        for columna in range(len(COLUMNAS_PLAN) - 1):
            if self.tabla_plan.columnWidth(columna) > ANCHO_MAXIMO_COLUMNA:
                self.tabla_plan.setColumnWidth(columna, ANCHO_MAXIMO_COLUMNA)
        self.tabla_plan.resizeRowsToContents()

    def volver_a_la_lista(self, *_args) -> None:
        self.pila.setCurrentIndex(0)
