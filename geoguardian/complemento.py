"""Punto de entrada del complemento: raiz de composicion. Crea, conecta y desconecta componentes."""

from __future__ import annotations

import os

from qgis.core import Qgis, QgsMessageLog, QgsProject
from qgis.PyQt.QtCore import Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QPushButton, QToolBar

from .administracion.administrador_proyecto import AdministradorProyecto
from .administracion.identidad_proyecto import id_desde_geopaquete
from .administracion.registro_adopciones import RegistroAdopciones
from .constantes import ETIQUETA_REGISTRO, NOMBRE_COMPLEMENTO
from .dominio.advertencia_cierre import requiere_advertencia
from .dominio.recuperacion import BOTON_LOCALIZAR, MENSAJE_UNIDAD_NO_ENCONTRADA
from .dominio.semaforo import FRASE_VERSION_DISPONIBLE
from .filtro_cierre import FiltroCierre
from .incorporacion.servicio_plan import ServicioPlan
from .interfaz.asistente_inicializacion import AsistenteInicializacion, mostrar_proyecto_creado
from .interfaz.dialogo_cierre import AVISO_PANEL, preguntar_cierre, preguntar_cierre_version
from .interfaz.dialogo_revisar_capas import TITULO as TITULO_REVISAR_CAPAS
from .interfaz.dialogo_incorporacion import DialogoRevisarCapasConPlan
from .interfaz.indicador_barra import IndicadorBarra
from .interfaz.panel_estado import BOTON_ABRIR_VERSION, TEXTO_BARRA_VERSION, PanelEstado
from .inventario.servicio_inventario import ServicioInventario
from .monitoreo.monitor_capas import MonitorCapas

MENU = "&GeoGuardian"
RUTA_ICONO = os.path.join(os.path.dirname(__file__), "interfaz", "iconos", "geoguardian.svg")


class ComplementoGeoGuardian:
    def __init__(self, iface):
        self.iface = iface
        self.monitor = None
        self.administrador = None
        self.panel = None
        self.filtro_cierre = None
        self.barra = None
        self.indicador = None
        self.servicio_inventario = None
        self.servicio_plan = None
        self.accion_revisar = None
        self.dialogo_revisar = None
        self._acciones = []
        self._conexiones = []
        self._aviso_barra = None
        self._aviso_activo = False
        self._aviso_version = None  # mensaje azul de version administrada; se retira solo este
        self._aviso_recuperacion = None  # mensaje de unidad no encontrada o de varias candidatas
        self._aviso_especifico = False  # hay asociacion con version administrada: oculta el amarillo

    # --- contrato de QGIS --------------------------------------------------

    def initGui(self):  # noqa: N802  (nombre exigido por QGIS)
        icono = QIcon(RUTA_ICONO)
        ventana = self.iface.mainWindow()

        self.accion_inicializar = QAction(icono, "Inicializar proyecto…", ventana)
        self.accion_guardar = QAction("Guardar ahora", ventana)
        self.accion_panel = QAction(icono, "Panel GeoGuardian", ventana)
        self.accion_panel.setCheckable(True)
        for accion in (self.accion_inicializar, self.accion_guardar, self.accion_panel):
            self.iface.addPluginToMenu(MENU, accion)
            self._acciones.append(accion)

        # Indicador permanente (D-31): una barra propia con un unico control.
        self.barra = QToolBar(NOMBRE_COMPLEMENTO, ventana)
        self.barra.setObjectName("BarraGeoGuardian")
        self.indicador = IndicadorBarra(self.barra)
        self.barra.addWidget(self.indicador)
        # "Revisar capas" (D-50) va en esta barra y no en el menu: el menu conserva sus tres acciones.
        self.accion_revisar = QAction(TITULO_REVISAR_CAPAS, ventana)
        self.accion_revisar.setToolTip("Revisa dónde están las capas del proyecto y su SRC (solo lectura)")
        self.barra.addAction(self.accion_revisar)
        ventana.addToolBar(self.barra)
        self.indicador.ajustar_tamano(self.barra.iconSize())

        # Raiz de composicion: aqui se crean los componentes y se inyectan sus dependencias.
        proyecto = QgsProject.instance()
        self.monitor = MonitorCapas(proyecto)
        self.administrador = AdministradorProyecto(proyecto, self.monitor, RegistroAdopciones())
        self.administrador.conectar_senales()
        self.servicio_inventario = ServicioInventario(proyecto, self._contexto_administrado)
        self.servicio_plan = ServicioPlan(
            proyecto, self._contexto_administrado, self.servicio_inventario.construir, id_desde_geopaquete
        )

        self.panel = PanelEstado(ventana)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)

        self.filtro_cierre = FiltroCierre(
            ventana,
            self.administrador,
            preguntar=lambda: preguntar_cierre(self.iface.mainWindow()),
            abrir_asistente=self.abrir_asistente,
            preguntar_version=lambda ruta: preguntar_cierre_version(ruta, self.iface.mainWindow()),
            abrir_version=self.abrir_version_administrada,
        )
        self.filtro_cierre.instalar()

        self._conectar(self.accion_inicializar.triggered, self.abrir_asistente)
        self._conectar(self.accion_guardar.triggered, self.guardar_ahora)
        self._conectar(self.accion_panel.toggled, self.panel.setUserVisible)
        self._conectar(self.accion_revisar.triggered, self.revisar_capas)
        self._conectar(self.panel.visibilityChanged, self.accion_panel.setChecked)
        self._conectar(self.panel.visibilityChanged, self.indicador.setChecked)
        self._conectar(self.indicador.clicked, self.alternar_panel)
        self._conectar(self.barra.iconSizeChanged, self.indicador.ajustar_tamano)
        self._conectar(self.panel.guardar_solicitado, self.guardar_ahora)
        self._conectar(self.panel.inicializar_solicitado, self.abrir_asistente)
        self._conectar(self.panel.abrir_carpeta_solicitada, self.abrir_carpeta)
        self._conectar(self.panel.abrir_version_solicitada, self.abrir_version_administrada)
        self._conectar(self.administrador.administracion_cambiada, self._al_cambiar_administracion)
        self._conectar(self.administrador.estado_actualizado, self.refrescar_panel)
        self._conectar(self.administrador.error_ocurrido, self._mostrar_error)
        self._conectar(
            self.administrador.version_administrada_disponible, self._ofrecer_version_administrada
        )
        self._conectar(self.administrador.unidad_no_encontrada, self._avisar_unidad_no_encontrada)
        self._conectar(self.administrador.candidatas_administradas, self._avisar_candidatas)

        # Por si QGIS ya tenia un proyecto abierto al cargar el complemento.
        self.administrador.detectar_administrado()
        self.refrescar_panel()

    def unload(self):
        # Primero el filtro de cierre: QGIS debe poder cerrarse aunque falle lo demas.
        if self.filtro_cierre is not None:
            self.filtro_cierre.desinstalar()
            self.filtro_cierre.deleteLater()
            self.filtro_cierre = None
        for senal, ranura in reversed(self._conexiones):
            try:
                senal.disconnect(ranura)
            except (TypeError, RuntimeError):
                pass
        self._conexiones = []
        self._retirar_aviso()
        self._retirar_oferta_version()
        self._retirar_aviso_recuperacion()
        self._cerrar_revision()
        self.servicio_inventario = None
        self.servicio_plan = None
        if self.administrador is not None:
            self.administrador.liberar()
            self.administrador.deleteLater()
            self.administrador = None
        if self.monitor is not None:
            self.monitor.deleteLater()
            self.monitor = None
        if self.panel is not None:
            self.iface.removeDockWidget(self.panel)
            self.panel.deleteLater()
            self.panel = None
        if self.barra is not None:
            self.iface.mainWindow().removeToolBar(self.barra)
            self.barra.deleteLater()
            self.barra = None
            self.indicador = None
        if self.accion_revisar is not None:
            self.accion_revisar.deleteLater()
            self.accion_revisar = None
        for accion in self._acciones:
            self.iface.removePluginMenu(MENU, accion)
            accion.deleteLater()
        self._acciones = []

    # --- acciones ----------------------------------------------------------

    def abrir_asistente(self, *_args):
        if self.administrador is None:
            return
        if self.administrador.es_administrado:
            self.iface.messageBar().pushInfo(NOMBRE_COMPLEMENTO, "Este proyecto ya esta administrado.")
            return
        if self.administrador.version_administrada:
            # Original con version administrada: no se crea otra; se recuerda cual abrir (D-37).
            self._ofrecer_version_administrada(self.administrador.version_administrada)
            return
        asistente = AsistenteInicializacion(self.administrador, self.iface.mainWindow())
        if asistente.exec_() and asistente.carpeta_creada:
            # En diferido: QGIS termina antes lo que dejo pendiente la primera escritura (D-38).
            QTimer.singleShot(0, self._completar_inicializacion)

    def _completar_inicializacion(self):
        if self.administrador is None:
            return
        try:
            self.administrador.completar_inicializacion(self.iface.actionSaveProject().trigger)
        except Exception as error:  # noqa: BLE001
            self._mostrar_error(str(error))
        contexto = self.administrador.contexto
        mostrar_proyecto_creado(self.iface.mainWindow(), contexto.archivo_proyecto if contexto else "")

    def alternar_panel(self, *_args):
        if self.panel is not None:
            self.panel.setUserVisible(not self.panel.isUserVisible())

    def guardar_ahora(self, *_args):
        try:
            # Guardado nativo de QGIS, no QgsProject.write(): asi QGIS no avisa despues de que
            # el proyecto cambio en el disco.
            pendientes = self.administrador.guardar_ahora(self.iface.actionSaveProject().trigger)
        except Exception as error:  # noqa: BLE001
            self._mostrar_error(str(error))
            return
        if pendientes:
            self.iface.messageBar().pushWarning(
                NOMBRE_COMPLEMENTO,
                "Proyecto guardado. {} capa(s) siguen con ediciones sin confirmar.".format(pendientes),
            )
        else:
            self.iface.messageBar().pushSuccess(NOMBRE_COMPLEMENTO, "Proyecto guardado.")

    def abrir_carpeta(self, *_args):
        contexto = self.administrador.contexto if self.administrador else None
        if contexto is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(contexto.carpeta)))

    def refrescar_panel(self, *_args):
        if self.panel is None or self.administrador is None:
            return
        try:
            nivel, motivos, resumen = self.administrador.estado_semaforo()
        except Exception as error:  # noqa: BLE001
            self.administrador.informar_error("refrescar_panel", error)
            return
        self.panel.mostrar(nivel, motivos, resumen)
        if self.indicador is not None:
            frase = FRASE_VERSION_DISPONIBLE if resumen.version_administrada else ""
            self.indicador.mostrar(nivel, motivos, frase)
        self.accion_guardar.setEnabled(resumen.administrado)
        self.accion_inicializar.setEnabled(not resumen.administrado and not resumen.version_administrada)
        self.accion_revisar.setEnabled(resumen.administrado)  # solo proyectos administrados (D-49)
        self._actualizar_aviso(
            requiere_advertencia(resumen.administrado, resumen.tiene_archivo, resumen.numero_capas)
        )

    # --- Revisar capas (v0.2.0, Hito 1: D-40 a D-52) -------------------------

    def revisar_capas(self, *_args):
        """Abre el dialogo y construye el inventario en ese momento (D-49). Solo lectura."""
        if self.servicio_inventario is None or not self.servicio_inventario.disponible():
            self.iface.messageBar().pushInfo(
                NOMBRE_COMPLEMENTO, "Revisar capas está disponible en proyectos administrados."
            )
            return
        if self.dialogo_revisar is None:
            self.dialogo_revisar = DialogoRevisarCapasConPlan(
                self._construir_inventario, self._construir_plan, self._preparar_plan, self.iface.mainWindow()
            )
        self.dialogo_revisar.revisar()
        self.dialogo_revisar.show()
        self.dialogo_revisar.raise_()
        self.dialogo_revisar.activateWindow()

    def _contexto_administrado(self):
        if self.administrador is None or not self.administrador.es_administrado:
            return None
        return self.administrador.contexto

    def _construir_inventario(self):
        # Un fallo no se anota en gg_eventos: el inventario no escribe nada (D-40).
        try:
            return self.servicio_inventario.construir() if self.servicio_inventario else None
        except Exception as error:  # noqa: BLE001
            QgsMessageLog.logMessage("revisar_capas: {}".format(error), ETIQUETA_REGISTRO, Qgis.Critical)
            self._mostrar_error("No se pudieron revisar las capas: {}".format(error))
            return None

    # --- Preparar incorporacion (v0.2.0, Hito 2: D-56 a D-68) -----------------

    def _construir_plan(self, inventario):
        # Como el inventario: un fallo va al registro de mensajes, nunca a gg_eventos (D-68).
        try:
            return self.servicio_plan.construir(inventario) if self.servicio_plan else None
        except Exception as error:  # noqa: BLE001
            QgsMessageLog.logMessage("preparar_incorporacion: {}".format(error), ETIQUETA_REGISTRO, Qgis.Critical)
            return None

    def _preparar_plan(self, plan):
        try:
            return self.servicio_plan.revalidar(plan) if self.servicio_plan else None
        except Exception as error:  # noqa: BLE001
            QgsMessageLog.logMessage("preparar_incorporacion: {}".format(error), ETIQUETA_REGISTRO, Qgis.Critical)
            return None

    def _cerrar_revision(self):
        """El dialogo muestra un proyecto concreto: se cierra si cambia el proyecto."""
        if self.dialogo_revisar is not None:
            self.dialogo_revisar.close()
            self.dialogo_revisar.deleteLater()
            self.dialogo_revisar = None

    # --- aviso persistente de proyecto no administrado (D-17 A.2) ----------

    def _actualizar_aviso(self, requerido: bool):
        # El aviso especifico (version administrada o recuperacion) tiene prioridad sobre el generico.
        if not requerido or self._aviso_especifico:
            self._retirar_aviso()
            return
        if self._aviso_activo:
            return  # ya se mostro; si el estudiante lo cerro, no se repite hasta que cambie la condicion
        barra = self.iface.messageBar()
        mensaje = barra.createMessage(NOMBRE_COMPLEMENTO, AVISO_PANEL)
        boton = QPushButton("Inicializar ahora")
        boton.clicked.connect(self.abrir_asistente)
        mensaje.layout().addWidget(boton)
        self._aviso_barra = barra.pushWidget(mensaje, Qgis.Warning, 0)
        self._aviso_activo = True

    def _retirar_aviso(self):
        if self._aviso_barra is not None:
            try:
                self.iface.messageBar().popWidget(self._aviso_barra)
            except (RuntimeError, TypeError):
                pass  # el estudiante ya lo cerro
        self._aviso_barra = None
        self._aviso_activo = False

    def _ofrecer_version_administrada(self, ruta):
        """Una linea en la barra; nombre, ruta y explicacion van en el panel."""
        self._retirar_oferta_version()
        self._retirar_aviso_recuperacion()
        self._dar_prioridad_al_aviso_especifico()
        barra = self.iface.messageBar()
        mensaje = barra.createMessage(NOMBRE_COMPLEMENTO, TEXTO_BARRA_VERSION)
        boton = QPushButton(BOTON_ABRIR_VERSION)
        boton.clicked.connect(lambda: self.abrir_version_administrada(ruta))
        mensaje.layout().addWidget(boton)
        self._aviso_version = barra.pushWidget(mensaje, Qgis.Info, 0)
        if self.panel is not None:
            self.panel.mostrar_version_disponible(ruta)
            self.refrescar_panel()

    def abrir_version_administrada(self, ruta):
        if ruta and self.iface.addProject(ruta):
            self._retirar_oferta_version()

    def _al_cambiar_administracion(self, administrado):
        # Otro proyecto o la version administrada ya abierta: la oferta deja de aplicar. Si se
        # reabre el original, el administrador la vuelve a emitir despues de esta senal.
        self._retirar_oferta_version()
        self._retirar_aviso_recuperacion()
        self._aviso_especifico = False
        self._cerrar_revision()

    def _dar_prioridad_al_aviso_especifico(self):
        self._aviso_especifico = True
        self._retirar_aviso()

    def _retirar_oferta_version(self):
        """Retira solo el mensaje de GeoGuardian; nunca clearWidgets(), que borraria los de QGIS."""
        if self._aviso_version is not None:
            try:
                self.iface.messageBar().popWidget(self._aviso_version)
            except (RuntimeError, TypeError):
                pass  # el estudiante ya lo cerro
            self._aviso_version = None
        if self.panel is not None:
            self.panel.mostrar_version_disponible("")

    # --- unidad externa no encontrada (D-34) -------------------------------

    def _avisar_unidad_no_encontrada(self, ruta_origen):
        self._aviso_con_localizar(MENSAJE_UNIDAD_NO_ENCONTRADA, ruta_origen)

    def _avisar_candidatas(self, ruta_origen, candidatas):
        mensaje = (
            "Varias unidades con la misma etiqueta contienen la versión administrada de este proyecto: "
            "{}. GeoGuardian no elige una por ti; localiza la correcta.".format("; ".join(candidatas))
        )
        self._aviso_con_localizar(mensaje, ruta_origen)

    def _aviso_con_localizar(self, texto, ruta_origen):
        self._retirar_aviso_recuperacion()
        self._dar_prioridad_al_aviso_especifico()
        barra = self.iface.messageBar()
        mensaje = barra.createMessage(NOMBRE_COMPLEMENTO, texto)
        boton = QPushButton(BOTON_LOCALIZAR)
        boton.clicked.connect(lambda: self.localizar(ruta_origen))
        mensaje.layout().addWidget(boton)
        self._aviso_recuperacion = barra.pushWidget(mensaje, Qgis.Warning, 0)

    def _retirar_aviso_recuperacion(self):
        if self._aviso_recuperacion is not None:
            try:
                self.iface.messageBar().popWidget(self._aviso_recuperacion)
            except (RuntimeError, TypeError):
                pass  # el estudiante ya lo cerro
            self._aviso_recuperacion = None

    def localizar(self, ruta_origen, carpeta=None):
        """Recuperacion manual: el estudiante elige la unidad o la carpeta (D-34.7)."""
        if self.administrador is None:
            return None
        if carpeta is None:
            carpeta = QFileDialog.getExistingDirectory(self.iface.mainWindow(), BOTON_LOCALIZAR)
        if not carpeta:
            return None
        ruta = self.administrador.localizar_version_administrada(ruta_origen, carpeta)
        if ruta:
            self._ofrecer_version_administrada(ruta)
        else:
            self.iface.messageBar().pushWarning(
                NOMBRE_COMPLEMENTO,
                "En {} no está la versión administrada de este proyecto (no se encontró o su "
                "identificador no coincide). La asociación no se cambió.".format(carpeta),
            )
        return ruta

    # --- internos ----------------------------------------------------------

    def _conectar(self, senal, ranura):
        senal.connect(ranura)
        self._conexiones.append((senal, ranura))

    def _mostrar_error(self, mensaje):
        self.iface.messageBar().pushCritical(NOMBRE_COMPLEMENTO, mensaje)
