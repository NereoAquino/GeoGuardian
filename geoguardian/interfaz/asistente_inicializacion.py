"""Asistente de inicializacion (F1, F13-F15). Las reglas viven en dominio; aqui solo se presentan."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from qgis.gui import QgsFileWidget
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWizard,
    QWidget,
    QWizardPage,
)

from ..administracion import almacenamiento
from ..administracion.estructura_carpetas import carpeta_disponible
from ..constantes import CARPETAS_PROYECTO, NOMBRE_GEOPAQUETE
from ..dominio.catalogo_asignaturas import opciones_asignatura
from ..dominio.modelos import DatosProyecto, SolicitudInicializacion
from ..dominio.nombre_academico import analizar_nombre, nombre_de_archivo, validar_nombre_academico
from ..dominio.ubicacion import Aviso, TipoUbicacion, evaluar_destino, gigabytes
from ..dominio.validacion import validar_datos_proyecto

ESTILO_ERROR = "color: #c62828;"
ESTILO_AVISO = "color: #8a5a00;"
ESTILO_SECUNDARIO = "color: #555;"
ESTILO_TITULO_BLOQUE = "font-weight: bold;"
ESTILO_DESTACADO = (
    "background-color: #fff8e1; border: 1px solid #f9a825; border-radius: 4px; padding: 6px;"
)

CONVENCION = "NOMBRE DE LA PRACTICA O PROYECTO - NOMBRE DEL ESTUDIANTE"
EXPLICACION_LOCAL = "Mejor rendimiento para imágenes satelitales, ortomosaicos y datos de dron."
EXPLICACION_EXTERNA = "Verifica espacio disponible y evita desconectarla mientras QGIS esté trabajando."
NOTA_RESPALDO = (
    "GeoGuardian guardará esta ubicación para una función posterior. "
    "En esta versión todavía no copia ni sincroniza archivos."
)
INDICACION_ARCHIVO_DE_TRABAJO = (
    "Este será tu archivo de trabajo en las próximas sesiones. Ábrelo siempre para continuar tu proyecto."
)
NOTA_ORIGINAL = (
    "Se conservará sin modificaciones. Evita seguir editándolo después de crear la versión "
    "administrada para no generar dos versiones diferentes del trabajo."
)
SIN_ORIGINAL = "El proyecto actual nunca se guardó, así que no hay un archivo original que conservar."
BOTON_CREAR = "Crear proyecto administrado"
BOTON_ANTERIOR = "Anterior"
BOTON_SIGUIENTE = "Siguiente"
BOTON_CANCELAR = "Cancelar"
ANCHO_MINIMO = 720
ALTO_MINIMO = 760


def _etiqueta(estilo: str = "", texto: str = "") -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setWordWrap(True)
    if estilo:
        etiqueta.setStyleSheet(estilo)
    return etiqueta


def _poner(etiqueta: QLabel, texto: str) -> None:
    """Asigna el texto y oculta la etiqueta si queda vacia, para no dejar huecos en la pagina."""
    etiqueta.setText(texto)
    etiqueta.setVisible(bool(texto))


def _ruta(texto: str = "") -> QLabel:
    """Ruta completa, seleccionable para copiarla."""
    etiqueta = _etiqueta(ESTILO_SECUNDARIO, texto)
    etiqueta.setTextFormat(Qt.PlainText)
    etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return etiqueta


def _bloque(titulo: str, *widgets) -> QFrame:
    """Bloque visual con un titulo en negrita y su contenido debajo."""
    marco = QFrame()
    marco.setFrameShape(QFrame.StyledPanel)
    diseno = QVBoxLayout(marco)
    diseno.addWidget(_etiqueta(ESTILO_TITULO_BLOQUE, titulo))
    for widget in widgets:
        diseno.addWidget(widget)
    return marco


class PaginaDatos(QWizardPage):
    def __init__(self, nombre_actual: str = "", padre=None):
        super().__init__(padre)
        self.setTitle("Datos del proyecto")
        self.setSubTitle("Estos datos identifican tu trabajo ante el docente.")
        self.nombre = QLineEdit()
        self.correo = QLineEdit()
        self.titulo = QLineEdit(nombre_actual)
        self.descripcion = QPlainTextEdit()
        self.descripcion.setFixedHeight(70)
        self.grupo = QLineEdit()
        # Combo editable: se elige del catalogo o se escribe otra asignatura (D-39).
        self.asignatura = QComboBox()
        self.asignatura.setEditable(True)
        self.asignatura.setInsertPolicy(QComboBox.NoInsert)  # lo escrito no se agrega al catalogo
        self.asignatura.addItems(opciones_asignatura())
        self.asignatura.setCurrentIndex(-1)
        self.asignatura.setEditText("")
        self.asignatura.lineEdit().setPlaceholderText("Elige o escribe la asignatura o módulo")
        self._errores = _etiqueta(ESTILO_ERROR)

        formulario = QFormLayout()
        formulario.addRow("Nombre del estudiante*:", self.nombre)
        formulario.addRow("Correo*:", self.correo)
        formulario.addRow("Nombre de la práctica o proyecto*:", self.titulo)
        formulario.addRow("Descripción:", self.descripcion)
        formulario.addRow("Grupo*:", self.grupo)
        formulario.addRow("Asignatura o módulo*:", self.asignatura)
        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(self._errores)
        for campo in (self.nombre, self.correo, self.titulo, self.grupo):
            campo.textChanged.connect(self._revisar)
        self.asignatura.editTextChanged.connect(self._revisar)  # tambien al elegir del catalogo
        self._revisar()

    def datos(self) -> DatosProyecto:
        return DatosProyecto(
            nombre_estudiante=self.nombre.text(),
            correo=self.correo.text(),
            titulo=self.titulo.text(),
            descripcion=self.descripcion.toPlainText(),
            grupo=self.grupo.text(),
            asignatura=self.asignatura.currentText(),
        )

    def _revisar(self, *_args):
        self._errores.setText("\n".join(validar_datos_proyecto(self.datos())))
        self.completeChanged.emit()

    def isComplete(self):  # noqa: N802  (API de Qt)
        return not validar_datos_proyecto(self.datos())


class PaginaNombre(QWizardPage):
    """Nombre final del proyecto administrado: practica o proyecto + estudiante (F13, F18)."""

    def __init__(self, pagina_datos: PaginaDatos, padre=None):
        super().__init__(padre)
        self._pagina_datos = pagina_datos
        self._editado = False
        self._propuesto = ""
        self._base_sugerencia = None  # (practica, estudiante) con que se calculo la sugerencia
        self.setTitle("Nombre final del proyecto administrado")
        self.setSubTitle("Convención: " + CONVENCION)

        self.proyecto_detectado = _etiqueta()
        self.estudiante = _etiqueta()
        formulario = QFormLayout()
        formulario.addRow("Proyecto detectado:", self.proyecto_detectado)
        formulario.addRow("Estudiante:", self.estudiante)

        # Campo a todo el ancho: etiqueta arriba, campo debajo (no en una fila de formulario).
        self.nombre_academico = QLineEdit()
        self._archivo = _etiqueta(ESTILO_SECUNDARIO)
        self._advertencia = _etiqueta(ESTILO_AVISO)
        self._errores = _etiqueta(ESTILO_ERROR)

        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addSpacing(8)
        diseno.addWidget(_etiqueta(ESTILO_TITULO_BLOQUE, "Nombre final sugerido"))
        diseno.addWidget(_etiqueta(ESTILO_SECUNDARIO, "Nombre final del proyecto administrado* (puedes editarlo)"))
        diseno.addWidget(self.nombre_academico)
        diseno.addWidget(self._archivo)
        diseno.addSpacing(8)
        diseno.addWidget(self._advertencia)
        diseno.addWidget(self._errores)
        diseno.addStretch(1)
        self.nombre_academico.textEdited.connect(self._al_editar)
        self.nombre_academico.textChanged.connect(self._revisar)

    def _estudiante(self) -> str:
        return self._pagina_datos.nombre.text()

    def initializePage(self):  # noqa: N802  (API de Qt)
        texto = self._pagina_datos.titulo.text()
        base = (texto.strip(), self._estudiante().strip())
        if base != self._base_sugerencia:
            # Al volver con otro estudiante o practica, la sugerencia anterior ya no vale (D-39).
            self._editado = False
            self._base_sugerencia = base
        analisis = analizar_nombre(texto, self._estudiante())
        self.proyecto_detectado.setText(texto.strip() or "(sin nombre)")
        self.estudiante.setText(self._estudiante().strip())
        advertencias = []
        if not analisis.contiene_estudiante:
            advertencias.append("El nombre detectado no incluye el nombre del estudiante.")
        if not analisis.estructura_completa:
            advertencias.append("El nombre detectado no sigue la convención " + CONVENCION + ".")
        if advertencias and analisis.nombre_propuesto:
            advertencias.append("Se sugiere un nombre final corregido.")
        _poner(self._advertencia, "\n".join("⚠ " + a for a in advertencias))
        self._propuesto = analisis.nombre_propuesto or (texto.strip() if analisis.estructura_completa else "")
        if not self._editado:
            self.nombre_academico.setText(self._propuesto)
            self.nombre_academico.setCursorPosition(0)
        self._revisar()

    def _al_editar(self, *_args):
        self._editado = True

    def _revisar(self, *_args):
        nombre = self.nombre_academico.text()
        errores = validar_nombre_academico(nombre, self._estudiante())
        _poner(self._errores, "\n".join(errores))
        archivo = nombre_de_archivo(nombre)
        self._archivo.setText("Carpeta: «{0}» · Archivo: «{0}.qgz»".format(archivo) if archivo else "")
        self.completeChanged.emit()

    def isComplete(self):  # noqa: N802  (API de Qt)
        return not validar_nombre_academico(self.nombre_academico.text(), self._estudiante())


class PaginaUbicacion(QWizardPage):
    """Ubicacion principal de trabajo y respaldo opcional (F15)."""

    def __init__(self, pagina_nombre: PaginaNombre, padre=None):
        super().__init__(padre)
        self._pagina_nombre = pagina_nombre
        self.setTitle("Ubicación de trabajo")
        self.setSubTitle("Se creará una carpeta nueva. Ningún archivo existente se mueve ni se modifica.")

        self.opcion_local = QRadioButton("En este equipo — recomendado")
        self.opcion_externa = QRadioButton("Unidad externa")
        self.opcion_otra = QRadioButton("Otra carpeta")
        self._grupo = QButtonGroup(self)
        for boton in (self.opcion_local, self.opcion_externa, self.opcion_otra):
            self._grupo.addButton(boton)
        self.unidades = QComboBox()
        self._volumenes = []
        self.carpeta_padre = QgsFileWidget()
        self.carpeta_padre.setStorageMode(QgsFileWidget.GetDirectory)
        self.ruta_respaldo = QgsFileWidget()
        self.ruta_respaldo.setStorageMode(QgsFileWidget.GetDirectory)
        self._info = _etiqueta(ESTILO_SECUNDARIO)
        self._info.setTextFormat(Qt.PlainText)
        self._avisos = _etiqueta(ESTILO_AVISO)
        self._errores = _etiqueta(ESTILO_ERROR)

        def explicacion(texto):
            etiqueta = _etiqueta(ESTILO_SECUNDARIO, texto)
            etiqueta.setContentsMargins(24, 0, 0, 4)
            return etiqueta

        diseno = QVBoxLayout(self)
        diseno.addWidget(_etiqueta(ESTILO_TITULO_BLOQUE, "¿Dónde quieres trabajar?"))
        diseno.addWidget(self.opcion_local)
        diseno.addWidget(explicacion(EXPLICACION_LOCAL))
        diseno.addWidget(self.opcion_externa)
        diseno.addWidget(explicacion(EXPLICACION_EXTERNA))
        fila_unidades = QHBoxLayout()
        fila_unidades.setContentsMargins(24, 0, 0, 4)
        fila_unidades.addWidget(self.unidades)
        diseno.addLayout(fila_unidades)
        diseno.addWidget(self.opcion_otra)
        diseno.addSpacing(6)
        diseno.addWidget(_etiqueta(texto="Crear la carpeta del proyecto dentro de*:"))
        diseno.addWidget(self.carpeta_padre)
        diseno.addWidget(self._info)
        diseno.addWidget(self._avisos)
        diseno.addWidget(self._errores)

        respaldo = QGroupBox("Copia de respaldo — opcional")
        diseno_respaldo = QVBoxLayout(respaldo)
        diseno_respaldo.addWidget(self.ruta_respaldo)
        diseno_respaldo.addWidget(_etiqueta(ESTILO_SECUNDARIO, NOTA_RESPALDO))
        diseno.addSpacing(6)
        diseno.addWidget(respaldo)
        diseno.addStretch(1)

        self._grupo.buttonClicked.connect(self._al_cambiar_opcion)
        self.unidades.currentIndexChanged.connect(self._al_elegir_unidad)
        self.carpeta_padre.fileChanged.connect(self._revisar)
        self.ruta_respaldo.fileChanged.connect(self._revisar)
        self.opcion_local.setChecked(True)

    # --- datos -------------------------------------------------------------

    def tipo_ubicacion(self) -> TipoUbicacion:
        if self.opcion_externa.isChecked():
            return TipoUbicacion.UNIDAD_EXTERNA
        if self.opcion_otra.isChecked():
            return TipoUbicacion.OTRA
        return TipoUbicacion.DISCO_LOCAL

    def nombre_archivo(self) -> str:
        return nombre_de_archivo(self._pagina_nombre.nombre_academico.text())

    def ruta_carpeta(self) -> Optional[Path]:
        padre, nombre = self.carpeta_padre.filePath(), self.nombre_archivo()
        return Path(padre) / nombre if padre and nombre else None

    def ruta_qgz(self) -> Optional[Path]:
        carpeta = self.ruta_carpeta()
        return carpeta / (self.nombre_archivo() + ".qgz") if carpeta else None

    # --- comportamiento ----------------------------------------------------

    def initializePage(self):  # noqa: N802  (API de Qt)
        # Al regresar a esta pagina se conserva la unidad elegida si sigue conectada.
        indice = self.unidades.currentIndex()
        anterior = self._volumenes[indice].raiz if 0 <= indice < len(self._volumenes) else None
        self._volumenes = almacenamiento.volumenes_externos()
        self.unidades.blockSignals(True)
        self.unidades.clear()
        for volumen in self._volumenes:
            self.unidades.addItem("{} — {} ({}, {} libres)".format(
                volumen.raiz, volumen.nombre or "sin nombre", volumen.sistema_archivos or "?",
                gigabytes(volumen.bytes_libres),
            ))
        raices = [v.raiz for v in self._volumenes]
        if anterior in raices:
            self.unidades.setCurrentIndex(raices.index(anterior))
        self.unidades.blockSignals(False)
        self.opcion_externa.setEnabled(bool(self._volumenes))
        if not self.carpeta_padre.filePath():
            self._al_cambiar_opcion()
        self._revisar()

    def _al_cambiar_opcion(self, *_args):
        tipo = self.tipo_ubicacion()
        self.unidades.setEnabled(tipo == TipoUbicacion.UNIDAD_EXTERNA)
        if tipo == TipoUbicacion.DISCO_LOCAL:
            self.carpeta_padre.setFilePath(almacenamiento.carpeta_documentos())
        elif tipo == TipoUbicacion.UNIDAD_EXTERNA:
            self._al_elegir_unidad()
        self._revisar()

    def _al_elegir_unidad(self, *_args):
        indice = self.unidades.currentIndex()
        if self.tipo_ubicacion() == TipoUbicacion.UNIDAD_EXTERNA and 0 <= indice < len(self._volumenes):
            self.carpeta_padre.setFilePath(self._volumenes[indice].raiz)

    def _evaluar(self) -> List[Aviso]:
        qgz = self.ruta_qgz()
        volumen = almacenamiento.info_volumen(self.carpeta_padre.filePath())
        if qgz is None or volumen is None:
            return []
        respaldo = self.ruta_respaldo.filePath() or None
        return evaluar_destino(
            str(qgz),
            volumen,
            almacenamiento.raiz_documentos(),
            almacenamiento.raices_onedrive(),
            ruta_respaldo=respaldo,
            respaldo_existe=bool(respaldo) and os.path.isdir(respaldo),
            volumen_respaldo=almacenamiento.info_volumen(respaldo) if respaldo else None,
        )

    def _errores_actuales(self, avisos: List[Aviso]) -> List[str]:
        errores = [a.mensaje for a in avisos if a.bloqueante]
        padre = self.carpeta_padre.filePath()
        if not padre or not Path(padre).is_dir():
            errores.append("Elige una carpeta existente donde crear el proyecto")
        carpeta = self.ruta_carpeta()
        if carpeta is not None and not errores and not carpeta_disponible(carpeta):
            errores.append("La carpeta {} ya existe y no está vacía".format(carpeta))
        return errores

    def _revisar(self, *_args):
        padre = self.carpeta_padre.filePath()
        volumen = almacenamiento.info_volumen(padre)
        if volumen is not None:
            self._info.setText("\n".join((
                "Carpeta seleccionada: {}".format(padre),
                "Sistema de archivos: {}".format(volumen.sistema_archivos or "desconocido"),
                "Espacio disponible: {}".format(gigabytes(volumen.bytes_libres)),
            )))
        else:
            self._info.setText("")
        avisos = self._evaluar()
        _poner(self._avisos, "\n".join("⚠ " + a.mensaje for a in avisos if not a.bloqueante))
        _poner(self._errores, "\n".join(self._errores_actuales(avisos)))
        self.completeChanged.emit()

    def isComplete(self):  # noqa: N802  (API de Qt)
        return not self._errores_actuales(self._evaluar())


class PaginaResumen(QWizardPage):
    """Resumen en bloques antes de crear el proyecto administrado (F20)."""

    def __init__(self, administrador, pagina_datos, pagina_nombre, pagina_ubicacion, padre=None):
        super().__init__(padre)
        self._administrador = administrador
        self._datos = pagina_datos
        self._nombre = pagina_nombre
        self._ubicacion = pagina_ubicacion
        self.carpeta_creada = None
        self.setTitle("Resumen")
        self.setSubTitle("Revisa antes de crear el proyecto administrado.")

        self.nombre_final = _etiqueta("font-weight: bold;")
        self.archivo_trabajo = _etiqueta("font-weight: bold;")
        self.ruta_administrado = _ruta()
        self.indicacion = _etiqueta(ESTILO_DESTACADO, INDICACION_ARCHIVO_DE_TRABAJO)
        self.ruta_original = _ruta()
        self.nota_original = _etiqueta(ESTILO_SECUNDARIO)
        self.lista_creara = _etiqueta()
        self.respaldo = _etiqueta(ESTILO_SECUNDARIO)
        self.bloque_respaldo = _bloque("Copia de respaldo — opcional", self.respaldo)

        # En un area con desplazamiento las etiquetas largas (rutas) calculan bien su altura y,
        # si la pantalla es pequeña, el resumen se puede recorrer en vez de amontonarse.
        contenido = QWidget()
        diseno = QVBoxLayout(contenido)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setWidget(contenido)
        QVBoxLayout(self).addWidget(area)
        diseno.addWidget(_bloque("Proyecto que administrará GeoGuardian", self.nombre_final))
        diseno.addWidget(_bloque(
            "A partir de ahora trabajarás con", self.archivo_trabajo, self.ruta_administrado, self.indicacion
        ))
        diseno.addWidget(_bloque("Proyecto original", self.ruta_original, self.nota_original))
        diseno.addWidget(_bloque("GeoGuardian creará", self.lista_creara))
        diseno.addWidget(self.bloque_respaldo)
        diseno.addStretch(1)

    def initializePage(self):  # noqa: N802  (API de Qt)
        archivo = self._ubicacion.nombre_archivo()
        self.nombre_final.setText(self._nombre.nombre_academico.text().strip())
        self.archivo_trabajo.setText(archivo + ".qgz")
        self.ruta_administrado.setText(str(self._ubicacion.ruta_qgz() or ""))
        origen = self._administrador.ruta_proyecto_actual()
        self.ruta_original.setText(origen)
        self.ruta_original.setVisible(bool(origen))
        self.nota_original.setText(NOTA_ORIGINAL if origen else SIN_ORIGINAL)
        elementos = ["archivo {}.qgz administrado".format(archivo), NOMBRE_GEOPAQUETE]
        elementos += [c + "/" for c in CARPETAS_PROYECTO]
        self.lista_creara.setText("\n".join("• " + e for e in elementos))
        respaldo = self._ubicacion.ruta_respaldo.filePath()
        self.respaldo.setText("{}\nSolo se registra; en esta versión no se copia nada.".format(respaldo))
        self.bloque_respaldo.setVisible(bool(respaldo))

    def solicitud(self) -> SolicitudInicializacion:
        return SolicitudInicializacion(
            datos=self._datos.datos(),
            nombre_academico=self._nombre.nombre_academico.text(),
            carpeta_padre=self._ubicacion.carpeta_padre.filePath(),
            tipo_ubicacion=self._ubicacion.tipo_ubicacion().value,
            ruta_respaldo=self._ubicacion.ruta_respaldo.filePath() or None,
        )

    def validatePage(self):  # noqa: N802  (API de Qt)
        try:
            self.carpeta_creada = self._administrador.inicializar(self.solicitud())
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "GeoGuardian", "No se pudo inicializar el proyecto:\n{}".format(error))
            return False
        return True


class AsistenteInicializacion(QWizard):
    def __init__(self, administrador, padre=None):
        super().__init__(padre)
        self.setWindowTitle("GeoGuardian: inicializar proyecto")
        self.pagina_datos = PaginaDatos(administrador.nombre_actual_proyecto())
        self.pagina_nombre = PaginaNombre(self.pagina_datos)
        self.pagina_ubicacion = PaginaUbicacion(self.pagina_nombre)
        self.pagina_resumen = PaginaResumen(
            administrador, self.pagina_datos, self.pagina_nombre, self.pagina_ubicacion
        )
        for pagina in (self.pagina_datos, self.pagina_nombre, self.pagina_ubicacion, self.pagina_resumen):
            self.addPage(pagina)
        # Estilo clasico en todas las plataformas: en Windows el estilo Aero cambia "Anterior" por
        # una flecha en el titulo. Anterior no aparece en la primera pagina (D-39).
        self.setWizardStyle(QWizard.ClassicStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.setButtonText(QWizard.BackButton, BOTON_ANTERIOR)
        self.setButtonText(QWizard.NextButton, BOTON_SIGUIENTE)
        self.setButtonText(QWizard.CancelButton, BOTON_CANCELAR)
        self.setButtonText(QWizard.FinishButton, BOTON_CREAR)
        # Las etiquetas con ajuste de linea necesitan espacio; un asistente pequeño las amontona.
        self.setMinimumSize(ANCHO_MINIMO, ALTO_MINIMO)

    @property
    def carpeta_creada(self):
        return self.pagina_resumen.carpeta_creada


TITULO_CREADO = "Proyecto administrado creado"


def texto_proyecto_creado(archivo_qgz: str) -> str:
    return "GeoGuardian ya está supervisando este proyecto.\n\nA partir de ahora trabaja con:\n{}".format(
        archivo_qgz
    )


def mostrar_proyecto_creado(padre, archivo_qgz: str) -> None:
    """Confirmacion posterior a la creacion (F20). El proyecto activo ya es el administrado."""
    QMessageBox.information(padre, TITULO_CREADO, texto_proyecto_creado(archivo_qgz))
