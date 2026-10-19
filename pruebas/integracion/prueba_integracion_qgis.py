"""Pruebas de integracion dentro de QGIS (especificacion v0.1.0, seccion 8.2).

Ejecutar con un Python que tenga QGIS, por ejemplo en Docker:
    docker run --rm -v "$PWD":/gg -e QT_QPA_PLATFORM=offscreen qgis/qgis:release-3_28 \
        python3 /gg/pruebas/ejecutar_pruebas.py --integracion
"""

import hashlib
import os
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from qgis.testing import start_app

APLICACION = start_app()

from osgeo import ogr  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsSettings,
    QgsFeature,
    QgsField,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QCoreApplication, QEvent, QVariant  # noqa: E402
from qgis.PyQt.QtWidgets import QAction, QMainWindow, QToolBar  # noqa: E402

from geoguardian.administracion.administrador_proyecto import (  # noqa: E402
    AdministradorProyecto,
    ErrorGuardado,
    ErrorInicializacion,
)
from geoguardian.constantes import AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO  # noqa: E402
from geoguardian.administracion.registro_adopciones import RegistroAdopciones  # noqa: E402
from geoguardian.dominio.advertencia_cierre import AccionCierre  # noqa: E402
from geoguardian.filtro_cierre import FiltroCierre  # noqa: E402
from geoguardian.dominio.modelos import (  # noqa: E402
    SolicitudInicializacion,
    DatosProyecto,
    EstadoRecurso as E,
    NivelSemaforo as N,
    TipoEvento as T,
)
from geoguardian.manifiesto.manifiesto import leer_manifiesto  # noqa: E402
from geoguardian.persistencia.repositorio import RepositorioGeoGuardian  # noqa: E402
from geoguardian.monitoreo.monitor_capas import MonitorCapas  # noqa: E402
from geoguardian.persistencia.migraciones import COLUMNAS_ESQUEMA_3  # noqa: E402
from geoguardian.dominio.recuperacion import IdentidadUbicacion  # noqa: E402
from geoguardian.dominio.ubicacion import InfoVolumen  # noqa: E402

DATOS = DatosProyecto("Ana Pérez López", "ana@cetmar02.edu.mx", "Manglares de Términos", "", "5A", "Módulo II")


def capa_memoria(nombre="puntos"):
    return QgsVectorLayer("Point?crs=EPSG:4326&field=id:integer", nombre, "memory")


def escribir_gpkg(ruta, nombre="sitios"):
    capa = capa_memoria(nombre)
    entidad = QgsFeature(capa.fields())
    entidad.setAttributes([1])
    capa.dataProvider().addFeatures([entidad])
    opciones = QgsVectorFileWriter.SaveVectorOptions()
    opciones.driverName = "GPKG"
    opciones.layerName = nombre
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        capa, str(ruta), QgsProject.instance().transformContext(), opciones
    )
    assert error[0] == QgsVectorFileWriter.NoError, error
    return QgsVectorLayer("{}|layername={}".format(ruta, nombre), nombre, "ogr")


COLUMNAS_NUEVAS = tuple(n for n, _t in COLUMNAS_ESQUEMA_3)


def suma(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def procesar_eventos():
    for _ in range(5):
        QCoreApplication.processEvents()


class BaseIntegracion(unittest.TestCase):
    def setUp(self):
        # Fuera de la carpeta temporal del sistema: alli todo se clasificaria como temporal.
        self.base = Path(tempfile.mkdtemp(prefix="gg_", dir=os.path.expanduser("~")))
        self.externos = self.base / "externos"
        self.externos.mkdir()
        self.proyecto = QgsProject.instance()
        self.proyecto.clear()
        self.monitor = MonitorCapas(self.proyecto)
        self.adopciones = RegistroAdopciones(QgsSettings())
        self.administrador = AdministradorProyecto(self.proyecto, self.monitor, self.adopciones)

    def tearDown(self):
        self.administrador.liberar()
        self.proyecto.clear()
        shutil.rmtree(str(self.base), ignore_errors=True)

    def inicializar(self, practica="Manglares", **cambios):
        solicitud = SolicitudInicializacion(
            datos=DATOS,
            nombre_academico="{} - Ana Pérez López".format(practica),
            carpeta_padre=str(self.base),
            tipo_ubicacion="otra",
        )
        for clave, valor in cambios.items():
            setattr(solicitud, clave, valor)
        carpeta = self.administrador.inicializar(solicitud)
        self.qgz = carpeta / (carpeta.name + ".qgz")
        return carpeta

    def repo(self):
        return self.administrador.contexto.repositorio

    def guardar_nativo(self):
        """Simula la accion "Guardar proyecto" de QGIS (iface.actionSaveProject()).

        Devuelve la accion; al dispararla QGIS guarda el proyecto y emite projectSaved.
        """
        accion = QAction("Guardar proyecto")
        self.guardados_nativos = []
        accion.triggered.connect(lambda: self.guardados_nativos.append(self.proyecto.write()))
        self.addCleanup(accion.deleteLater)
        return accion

    def guardar_ahora(self):
        if not getattr(self, "_senales_conectadas", False):
            self.administrador.conectar_senales()
            self._senales_conectadas = True
        return self.administrador.guardar_ahora(self.guardar_nativo().trigger)


class PruebaInicializacion(BaseIntegracion):
    def prueba_inicializacion_completa_adopta_capas(self):
        externa = escribir_gpkg(self.externos / "inegi.gpkg")
        self.proyecto.addMapLayers([capa_memoria(), externa])
        carpeta = self.inicializar()

        self.assertEqual(carpeta.name, "Manglares - Ana Perez Lopez")
        for nombre in ("Manglares - Ana Perez Lopez.qgz", "Proyecto.gpkg", ".geoguardian/manifiesto.json", "datos", "salidas", "documentos"):
            self.assertTrue((carpeta / nombre).exists(), nombre)

        fuente = ogr.Open(str(carpeta / "Proyecto.gpkg"))
        self.assertIsNotNone(fuente)
        nombres = {fuente.GetLayer(i).GetName() for i in range(fuente.GetLayerCount())}
        self.assertTrue({"gg_proyecto", "gg_recursos", "gg_eventos"} <= nombres)
        fuente = None

        estados = sorted(r.estado.value for r in self.repo().recursos_vigentes())
        self.assertEqual(estados, ["externo", "temporal"])
        tipos = [e.tipo_evento for e in self.repo().eventos()]
        self.assertEqual(tipos, [T.PROYECTO_INICIALIZADO, T.CAPA_AGREGADA, T.CAPA_AGREGADA])

        id_proyecto = self.proyecto.readEntry(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO, "")[0]
        manifiesto = leer_manifiesto(carpeta / ".geoguardian" / "manifiesto.json")
        self.assertEqual(manifiesto["id_proyecto"], id_proyecto)
        self.assertEqual(self.repo().obtener_proyecto()["id_proyecto"], id_proyecto)
        self.assertEqual(manifiesto["resumen_recursos"]["temporal"], 1)
        self.assertEqual(manifiesto["estado_semaforo"], "amarillo")
        self.assertFalse(list(carpeta.glob("*-wal")))

    def prueba_rutas_relativas_y_capa_activa(self):
        carpeta = self.inicializar()
        capa = escribir_gpkg(carpeta / "datos" / "manglares.gpkg", "manglares")
        self.proyecto.addMapLayer(capa)
        self.assertEqual(self.repo().recurso_vigente(capa.id()).estado, E.ACTIVO)
        self.assertEqual(self.repo().recurso_vigente(capa.id()).ruta_relativa, "datos/manglares.gpkg")
        self.guardar_ahora()
        with zipfile.ZipFile(str(self.qgz)) as qgz:
            qgs = qgz.read([n for n in qgz.namelist() if n.endswith(".qgs")][0]).decode("utf-8")
        self.assertIn("./datos/manglares.gpkg", qgs)
        self.assertNotIn(str(carpeta / "datos"), qgs)
        nivel, _motivos, _r = self.administrador.estado_semaforo()
        self.assertEqual(nivel, N.VERDE)

    def prueba_no_reinicializa_ni_usa_carpeta_ocupada(self):
        ocupada = self.base / "Ocupada - Ana Perez Lopez"
        ocupada.mkdir()
        (ocupada / "tarea.docx").write_text("x")
        with self.assertRaises(ErrorInicializacion):
            self.inicializar("Ocupada")
        self.assertEqual([p.name for p in ocupada.iterdir()], ["tarea.docx"])
        self.inicializar()
        with self.assertRaises(ErrorInicializacion):
            self.inicializar("Otro")

    def prueba_datos_invalidos(self):
        with self.assertRaises(ErrorInicializacion):
            self.administrador.inicializar(SolicitudInicializacion(
                DatosProyecto("", "no-es-correo", "T", "", "5A", "M"), "X - Ana", str(self.base), "otra"
            ))
        with self.assertRaises(ErrorInicializacion):
            self.inicializar("Sin estudiante", nombre_academico="Solo la practica")
        with self.assertRaises(ErrorInicializacion):
            self.inicializar(ruta_respaldo=str(self.base / "no_existe"))
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["externos"])


class PruebaMonitoreo(BaseIntegracion):
    def prueba_agregar_y_quitar_diez_capas(self):
        self.inicializar()
        antes = len(self.repo().eventos())
        capas = [capa_memoria("c{}".format(i)) for i in range(10)]
        self.proyecto.addMapLayers(capas)
        self.proyecto.removeMapLayers([c.id() for c in capas])
        eventos = self.repo().eventos()[antes:]
        self.assertEqual(len(eventos), 20)
        self.assertEqual(sum(e.tipo_evento == T.CAPA_AGREGADA for e in eventos), 10)
        self.assertEqual(sum(e.tipo_evento == T.CAPA_ELIMINADA for e in eventos), 10)
        self.assertEqual(self.repo().conteo_por_estado()[E.HISTORICO], 10)
        self.assertEqual(self.repo().recursos_vigentes(), [])

    def prueba_tablas_de_control_no_se_monitorean(self):
        carpeta = self.inicializar()
        capa = QgsVectorLayer("{}|layername=gg_eventos".format(carpeta / "Proyecto.gpkg"), "gg_eventos", "ogr")
        self.assertTrue(capa.isValid())
        self.proyecto.addMapLayer(capa)
        self.assertEqual(self.repo().recursos_vigentes(), [])

    def prueba_contrasenas_no_se_guardan(self):
        self.inicializar()
        capa = QgsVectorLayer(
            "dbname='gis' host=127.0.0.1 port=1 user='ana' password='s3cr3t' table=\"public\".\"x\" (geom)",
            "bd", "postgres",
        )
        self.proyecto.addMapLayer(capa, addToLegend=False)
        recurso = self.repo().recurso_vigente(capa.id())
        self.assertIsNotNone(recurso)
        self.assertNotIn("s3cr3t", recurso.fuente)
        self.assertEqual(recurso.estado, E.FALTANTE)  # capa invalida: no hay servidor


class PruebaAperturaYGuardado(BaseIntegracion):
    def prueba_ruta_rota_pasa_a_faltante_al_reabrir(self):
        self.administrador.conectar_senales()
        archivo = self.externos / "usb.gpkg"
        self.proyecto.addMapLayer(escribir_gpkg(archivo))
        carpeta = self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        self.assertFalse(self.administrador.es_administrado)

        archivo.rename(self.externos / "usb_movida.gpkg")  # simula la USB retirada
        self.assertTrue(self.proyecto.read(str(self.qgz)))
        procesar_eventos()
        self.assertTrue(self.administrador.es_administrado)
        recursos = self.repo().recursos_vigentes()
        self.assertEqual([r.estado for r in recursos], [E.FALTANTE])
        tipos = [e.tipo_evento for e in self.repo().eventos()]
        self.assertIn(T.PROYECTO_ABIERTO, tipos)
        self.assertIn(T.ESTADO_RECURSO_CAMBIADO, tipos)
        self.assertEqual(self.administrador.estado_semaforo()[0], N.ROJO)

    def prueba_manifiesto_borrado_pone_rojo(self):
        self.administrador.conectar_senales()
        carpeta = self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        os.remove(str(carpeta / ".geoguardian" / "manifiesto.json"))
        self.proyecto.read(str(self.qgz))
        procesar_eventos()
        nivel, motivos, _r = self.administrador.estado_semaforo()
        self.assertEqual(nivel, N.ROJO)
        self.assertIn("No se encuentra el manifiesto", motivos)

    def prueba_guardar_ahora_no_confirma_ediciones(self):
        archivo = self.externos / "edicion.gpkg"
        capa = escribir_gpkg(archivo)
        self.proyecto.addMapLayer(capa)
        self.inicializar()
        suma_antes = suma(archivo)
        self.assertTrue(capa.startEditing())
        entidad = QgsFeature(capa.fields())
        entidad.setAttributes([None, 99])
        self.assertTrue(capa.addFeature(entidad))

        pendientes = self.guardar_ahora()

        self.assertEqual(pendientes, 1)
        self.assertTrue(capa.isEditable())
        self.assertTrue(capa.isModified())
        self.assertEqual(suma(archivo), suma_antes)
        guardados = self.repo().eventos(T.PROYECTO_GUARDADO)
        self.assertEqual(len(guardados), 1)  # un solo registro aunque QGIS emite projectSaved
        self.assertEqual(guardados[0].detalle, {"origen": "boton", "capas_con_ediciones": 1})
        self.assertEqual(self.guardados_nativos, [True])  # guardo la accion nativa de QGIS
        capa.rollBack()

    def prueba_guardar_ahora_usa_el_guardado_nativo_y_no_escribe_por_su_cuenta(self):
        self.administrador.conectar_senales()
        self.inicializar()
        accion = QAction("Guardar proyecto")  # no conectada: simula que QGIS no guardo
        with mock.patch.object(QgsProject, "write", wraps=self.proyecto.write) as escritura:
            with self.assertRaises(ErrorGuardado):
                self.administrador.guardar_ahora(accion.trigger)
            escritura.assert_not_called()
        self.assertEqual(self.repo().eventos(T.PROYECTO_GUARDADO), [])

    def prueba_guardar_ahora_y_despues_ctrl_s_distinguen_el_origen(self):
        self.inicializar()
        self.guardar_ahora()
        self.assertTrue(self.proyecto.write())  # Ctrl+S de QGIS
        origenes = [e.detalle["origen"] for e in self.repo().eventos(T.PROYECTO_GUARDADO)]
        self.assertEqual(origenes, ["boton", "qgis"])
        manifiesto = leer_manifiesto(self.qgz.parent / ".geoguardian" / "manifiesto.json")
        self.assertEqual(manifiesto["fecha_actualizacion"], self.repo().obtener_proyecto()["fecha_actualizacion"])

    def prueba_guardado_desde_qgis_se_registra(self):
        self.administrador.conectar_senales()
        self.inicializar()
        self.proyecto.addMapLayer(capa_memoria())
        self.assertTrue(self.proyecto.write())
        guardados = self.repo().eventos(T.PROYECTO_GUARDADO)
        self.assertEqual(len(guardados), 1)
        self.assertEqual(guardados[0].detalle["origen"], "qgis")


class PruebaInterfaz(BaseIntegracion):
    def prueba_asistente_de_cuatro_paginas_crea_el_proyecto(self):
        from geoguardian.interfaz.asistente_inicializacion import AsistenteInicializacion

        self.proyecto.setTitle("PRACTICA_3_MANGLARES")
        asistente = AsistenteInicializacion(self.administrador)
        datos = asistente.pagina_datos
        self.assertEqual(datos.titulo.text(), "PRACTICA_3_MANGLARES")  # tomado de QgsProject.title()
        self.assertFalse(datos.isComplete())
        datos.nombre.setText(DATOS.nombre_estudiante)
        datos.correo.setText(DATOS.correo)
        datos.grupo.setText(DATOS.grupo)
        datos.asignatura.setEditText(DATOS.asignatura)
        self.assertTrue(datos.isComplete())

        nombre = asistente.pagina_nombre
        nombre.initializePage()
        self.assertEqual(nombre.nombre_academico.text(), "PRACTICA 3 MANGLARES - Ana Pérez López")
        self.assertTrue(nombre.isComplete())
        nombre.nombre_academico.setText("PRACTICA 3")
        self.assertFalse(nombre.isComplete())
        nombre.nombre_academico.setText("PRACTICA 3 MANGLARES - Ana Pérez López")

        ubicacion = asistente.pagina_ubicacion
        ubicacion.initializePage()
        self.assertTrue(ubicacion.opcion_local.isChecked())
        ubicacion.opcion_otra.setChecked(True)
        ubicacion.carpeta_padre.setFilePath(str(self.base))
        self.assertTrue(ubicacion.isComplete())
        self.assertIn("Espacio disponible", ubicacion._info.text())
        ubicacion.ruta_respaldo.setFilePath(str(self.base / "no_existe"))
        self.assertFalse(ubicacion.isComplete())  # respaldo inexistente bloquea
        ubicacion.ruta_respaldo.setFilePath(str(self.externos))
        self.assertTrue(ubicacion.isComplete())

        resumen = asistente.pagina_resumen
        resumen.initializePage()
        self.assertTrue(resumen.validatePage())
        carpeta = self.base / "PRACTICA 3 MANGLARES - Ana Perez Lopez"
        self.assertTrue((carpeta / "PRACTICA 3 MANGLARES - Ana Perez Lopez.qgz").exists())
        fila = self.repo().obtener_proyecto()
        self.assertEqual(fila["nombre_academico"], "PRACTICA 3 MANGLARES - Ana Pérez López")
        self.assertEqual(fila["titulo"], "PRACTICA 3 MANGLARES")
        self.assertEqual(fila["tipo_ubicacion"], "otra")
        self.assertEqual(fila["ruta_respaldo"], str(self.externos))
        self.assertEqual(self.proyecto.title(), "PRACTICA 3 MANGLARES - Ana Pérez López")
        self.assertEqual(os.listdir(str(self.externos)), [])  # nada se escribe en el respaldo

    def prueba_panel_muestra_proyecto_activo_y_abre_carpeta(self):
        from geoguardian.interfaz.panel_estado import PanelEstado

        panel = PanelEstado()
        self.proyecto.addMapLayer(capa_memoria())
        panel.mostrar(*self.administrador.estado_semaforo())
        self.assertTrue(panel._aviso.isVisibleTo(panel))
        self.assertEqual(panel.boton_inicializar.text(), "Inicializar ahora")

        carpeta = self.inicializar()
        panel.mostrar(*self.administrador.estado_semaforo())
        self.assertEqual(panel._titulo.text(), "Manglares - Ana Pérez López")
        self.assertEqual(panel._ruta.toolTip(), str(self.qgz))
        self.assertFalse(panel._aviso.isVisibleTo(panel))
        self.assertTrue(panel.boton_abrir_carpeta.isVisibleTo(panel))
        pulsaciones = []
        panel.abrir_carpeta_solicitada.connect(lambda: pulsaciones.append(1))
        panel.boton_abrir_carpeta.click()
        self.assertEqual(pulsaciones, [1])
        self.assertEqual(self.administrador.contexto.carpeta, carpeta)


class PruebaAdopcionYMigracion(BaseIntegracion):
    def _guardar_original(self):
        original = self.externos / "mi_proyecto.qgz"
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "datos.gpkg"))
        self.assertTrue(self.proyecto.write(str(original)))
        return original

    def prueba_adoptar_no_modifica_el_original_y_registra_rutas(self):
        original = self._guardar_original()
        suma_original = suma(original)
        carpeta = self.inicializar()
        self.assertEqual(suma(original), suma_original)
        self.assertEqual(Path(self.proyecto.fileName()), self.qgz)
        fila = self.repo().obtener_proyecto()
        self.assertEqual(fila["ruta_proyecto_origen"], str(original))
        self.assertEqual(fila["ruta_proyecto_administrado"], str(self.qgz))
        self.assertEqual(fila["version_esquema"], 3)
        manifiesto = leer_manifiesto(carpeta / ".geoguardian" / "manifiesto.json")
        self.assertEqual(manifiesto["rutas"]["origen"], str(original))
        self.assertEqual(manifiesto["archivos"]["proyecto"], self.qgz.name)

    def prueba_reabrir_original_ofrece_la_version_administrada_solo_si_existe(self):
        self.administrador.conectar_senales()
        ofertas = []
        self.administrador.version_administrada_disponible.connect(ofertas.append)
        original = self._guardar_original()
        self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        self.proyecto.read(str(original))
        procesar_eventos()
        self.assertFalse(self.administrador.es_administrado)
        self.assertEqual(ofertas, [str(self.qgz)])

        self.qgz.rename(self.qgz.with_name("movido.qgz"))
        self.proyecto.clear()
        procesar_eventos()
        self.proyecto.read(str(original))
        procesar_eventos()
        self.assertEqual(ofertas, [str(self.qgz)])  # no se ofrece un archivo que ya no existe

    def prueba_proyecto_rc1_se_migra_al_abrir(self):
        self.administrador.conectar_senales()
        carpeta = self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        con = sqlite3.connect(str(carpeta / "Proyecto.gpkg"))
        for columna in COLUMNAS_NUEVAS:
            con.execute("ALTER TABLE gg_proyecto DROP COLUMN {}".format(columna))
        con.execute("UPDATE gg_proyecto SET version_esquema = 1")
        con.commit()
        con.close()

        self.assertTrue(self.proyecto.read(str(self.qgz)))
        procesar_eventos()
        self.assertTrue(self.administrador.es_administrado)
        fila = self.repo().obtener_proyecto()
        self.assertEqual(fila["version_esquema"], 3)
        self.assertEqual(fila["ruta_proyecto_administrado"], str(self.qgz))
        migraciones = self.repo().eventos(T.ESQUEMA_MIGRADO)
        self.assertEqual(len(migraciones), 1)
        self.assertEqual(migraciones[0].detalle, {"version_anterior": 1, "version_nueva": 3})
        nivel, motivos, _r = self.administrador.estado_semaforo()
        self.assertNotEqual(nivel, N.ROJO, motivos)

        self.proyecto.clear()
        procesar_eventos()
        self.proyecto.read(str(self.qgz))
        procesar_eventos()
        self.assertEqual(len(self.repo().eventos(T.ESQUEMA_MIGRADO)), 1)  # idempotente


class PruebaFiltroCierre(BaseIntegracion):
    def _filtro(self, accion):
        self.ventana = QMainWindow()
        self.preguntas = []
        self.asistentes = []

        def preguntar():
            self.preguntas.append(1)
            return accion

        filtro = FiltroCierre(self.ventana, self.administrador, preguntar, lambda: self.asistentes.append(1))
        filtro.instalar()
        return filtro

    def prueba_proyecto_vacio_cierra_sin_preguntar(self):
        self._filtro(AccionCierre.CANCELAR)
        self.assertTrue(self.ventana.close())
        self.assertEqual(self.preguntas, [])

    def prueba_acciones(self):
        self.proyecto.addMapLayer(capa_memoria())
        for accion, cierra, asistente in (
            (AccionCierre.CANCELAR, False, 0),
            (AccionCierre.INICIALIZAR, False, 1),
            (AccionCierre.CERRAR, True, 0),
        ):
            with self.subTest(accion=accion):
                filtro = self._filtro(accion)
                self.assertEqual(self.ventana.close(), cierra)
                procesar_eventos()
                self.assertEqual(self.preguntas, [1])
                self.assertEqual(len(self.asistentes), asistente)
                filtro.desinstalar()

    def prueba_proyecto_administrado_no_pregunta_y_desinstalar_funciona(self):
        self.inicializar()
        self._filtro(AccionCierre.CANCELAR)
        self.assertTrue(self.ventana.close())
        self.assertEqual(self.preguntas, [])

        self.proyecto.clear()
        self.proyecto.addMapLayer(capa_memoria())
        filtro = self._filtro(AccionCierre.CANCELAR)
        filtro.desinstalar()
        self.assertTrue(self.ventana.close())
        self.assertEqual(self.preguntas, [])


class PruebaAjustesUX(BaseIntegracion):
    """Ajustes de UX de rc2 (especificacion §12, D-28 a D-32)."""

    def _complemento(self):
        from geoguardian import classFactory

        self.ventana = QMainWindow()
        iface = mock.Mock()
        iface.mainWindow.return_value = self.ventana
        iface.addDockWidget.side_effect = self.ventana.addDockWidget
        self.ventana.show()
        self.addCleanup(self.ventana.hide)
        complemento = classFactory(iface)
        complemento.initGui()
        self.addCleanup(complemento.unload)
        return complemento

    def _usar_administrador_de(self, complemento):
        # Las ayudas de BaseIntegracion operan sobre el administrador del complemento.
        self.administrador.liberar()
        self.administrador = complemento.administrador

    def prueba_indicador_cambia_de_estado(self):
        complemento = self._complemento()
        self._usar_administrador_de(complemento)
        indicador = complemento.indicador
        self.assertEqual(indicador.text(), "Proyecto no administrado")
        self.inicializar()
        procesar_eventos()
        self.assertEqual(indicador.text(), "Proyecto en buen estado")
        self.proyecto.addMapLayer(capa_memoria())
        procesar_eventos()
        self.assertEqual(indicador.text(), "Proyecto requiere atención")
        self.assertIn("capa temporal se perderá", indicador.toolTip())
        Path(self.qgz.parent / ".geoguardian" / "manifiesto.json").unlink()
        self.administrador.detectar_administrado()
        procesar_eventos()
        self.assertEqual(indicador.text(), "Proyecto con problemas")
        self.assertEqual(indicador.accessibleName(), "GeoGuardian: Proyecto con problemas")

    def prueba_clic_en_el_indicador_muestra_y_oculta_el_panel(self):
        complemento = self._complemento()
        panel, indicador = complemento.panel, complemento.indicador
        inicial = panel.isUserVisible()
        indicador.click()
        procesar_eventos()
        self.assertEqual(panel.isUserVisible(), not inicial)
        self.assertEqual(indicador.isChecked(), panel.isUserVisible())
        indicador.click()
        procesar_eventos()
        self.assertEqual(panel.isUserVisible(), inicial)
        self.assertEqual(indicador.isChecked(), panel.isUserVisible())

    def prueba_tooltip_con_el_motivo_principal(self):
        complemento = self._complemento()
        self._usar_administrador_de(complemento)
        for i in range(10):
            self.proyecto.addMapLayer(escribir_gpkg(self.externos / "datos{}.gpkg".format(i)))
        self.inicializar()
        procesar_eventos()
        self.assertEqual(
            complemento.indicador.toolTip(),
            "GeoGuardian — Proyecto requiere atención: "
            "10 recursos se encuentran fuera de la carpeta administrada.",
        )
        complemento.panel.mostrar(*self.administrador.estado_semaforo())
        self.assertEqual(complemento.panel._frase.text(), "Proyecto requiere atención")
        self.assertEqual(complemento.panel._total.text(), "Recursos en el proyecto: 10")

    def prueba_resumen_en_bloques_y_qgz_administrado_activo(self):
        from geoguardian.interfaz.asistente_inicializacion import (
            BOTON_CREAR,
            INDICACION_ARCHIVO_DE_TRABAJO,
            NOTA_ORIGINAL,
            AsistenteInicializacion,
            texto_proyecto_creado,
        )
        from qgis.PyQt.QtWidgets import QWizard

        original = self.externos / "MAPA DE INDICES ESPECTRALES.qgz"
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "indices.gpkg"))
        self.assertTrue(self.proyecto.write(str(original)))
        suma_original = suma(original)
        asistente = AsistenteInicializacion(self.administrador)
        self.assertEqual(asistente.buttonText(QWizard.FinishButton), BOTON_CREAR)
        datos = asistente.pagina_datos
        self.assertEqual(datos.titulo.text(), "MAPA DE INDICES ESPECTRALES")
        for campo, valor in ((datos.nombre, "NEREO ADENNY AQUINO SANTANA"), (datos.correo, DATOS.correo),
                             (datos.grupo, DATOS.grupo)):
            campo.setText(valor)
        datos.asignatura.setEditText(DATOS.asignatura)

        nombre = asistente.pagina_nombre
        nombre.initializePage()
        self.assertEqual(nombre.proyecto_detectado.text(), "MAPA DE INDICES ESPECTRALES")
        self.assertEqual(nombre.estudiante.text(), "NEREO ADENNY AQUINO SANTANA")
        final = "MAPA DE INDICES ESPECTRALES - NEREO ADENNY AQUINO SANTANA"
        self.assertEqual(nombre.nombre_academico.text(), final)
        self.assertIn("no incluye el nombre del estudiante", nombre._advertencia.text())
        nombre.nombre_academico.setText("mapa de índices espectrales  -  nereo aquino")
        self.assertTrue(nombre.isComplete())
        nombre.nombre_academico.setText(final)

        ubicacion = asistente.pagina_ubicacion
        ubicacion.initializePage()
        self.assertEqual(ubicacion.opcion_local.text(), "En este equipo — recomendado")
        ubicacion.opcion_otra.setChecked(True)
        ubicacion.carpeta_padre.setFilePath(str(self.base))
        self.assertIn("Carpeta seleccionada: " + str(self.base), ubicacion._info.text())
        self.assertIn("Sistema de archivos:", ubicacion._info.text())
        self.assertIn("Espacio disponible:", ubicacion._info.text())

        resumen = asistente.pagina_resumen
        resumen.initializePage()
        qgz = self.base / final / (final + ".qgz")
        self.assertEqual(resumen.nombre_final.text(), final)
        self.assertEqual(resumen.archivo_trabajo.text(), final + ".qgz")
        self.assertEqual(resumen.ruta_administrado.text(), str(qgz))
        self.assertEqual(resumen.indicacion.text(), INDICACION_ARCHIVO_DE_TRABAJO)
        self.assertEqual(resumen.ruta_original.text(), str(original))
        self.assertEqual(resumen.nota_original.text(), NOTA_ORIGINAL)
        for elemento in (".qgz administrado", "Proyecto.gpkg", "datos/", "salidas/", "documentos/", ".geoguardian/"):
            self.assertIn(elemento, resumen.lista_creara.text())
        self.assertFalse(resumen.bloque_respaldo.isVisibleTo(resumen))

        self.assertTrue(resumen.validatePage())
        self.assertTrue(qgz.is_file())
        self.assertEqual(Path(self.proyecto.fileName()), qgz)  # el proyecto activo es el administrado
        self.assertEqual(suma(original), suma_original)
        self.assertIn(final + ".qgz", texto_proyecto_creado(self.administrador.contexto.archivo_proyecto))

    def prueba_asociacion_original_administrado_persiste(self):
        original = self.externos / "original.qgz"
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "datos.gpkg"))
        self.assertTrue(self.proyecto.write(str(original)))
        self.inicializar()
        otra_sesion = RegistroAdopciones(QgsSettings())  # como si QGIS se hubiera reiniciado
        adopcion = otra_sesion.buscar(IdentidadUbicacion(str(original)))
        self.assertEqual(adopcion.administrado.ruta, str(self.qgz))
        self.assertEqual(adopcion.id_proyecto, self.administrador.contexto.fila_proyecto["id_proyecto"])

    def prueba_proyecto_migrado_desde_rc1_se_muestra_sin_rojo(self):
        from geoguardian.interfaz.indicador_barra import IndicadorBarra

        self.administrador.conectar_senales()
        carpeta = self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        con = sqlite3.connect(str(carpeta / "Proyecto.gpkg"))
        for columna in COLUMNAS_NUEVAS:
            con.execute("ALTER TABLE gg_proyecto DROP COLUMN {}".format(columna))
        con.execute("UPDATE gg_proyecto SET version_esquema = 1")
        con.commit()
        con.close()
        self.assertTrue(self.proyecto.read(str(self.qgz)))
        procesar_eventos()
        indicador = IndicadorBarra()
        nivel, motivos, resumen = self.administrador.estado_semaforo()
        indicador.mostrar(nivel, motivos)
        self.assertEqual(indicador.text(), "Proyecto en buen estado", motivos)
        self.assertEqual(resumen.nombre_academico, "Manglares")  # rc1 no tenia nombre final: usa el titulo


class AlmacenFalso:
    """Volumenes simulados: cada uno es una carpeta con una etiqueta, como una USB (D-33)."""

    def __init__(self):
        self.montados = []

    def montar(self, carpeta, etiqueta):
        Path(carpeta).mkdir(parents=True, exist_ok=True)
        self.montados.append(InfoVolumen(raiz=str(carpeta), sistema_archivos="FAT32", bytes_libres=10, etiqueta=etiqueta))

    def info_volumen(self, ruta):
        candidatos = [v for v in self.montados if str(ruta).startswith(v.raiz + os.sep) or str(ruta) == v.raiz]
        return max(candidatos, key=lambda v: len(v.raiz)) if candidatos else None

    def volumenes(self):
        return list(self.montados)

    def existe(self, ruta):
        return os.path.exists(ruta)


class PruebaUnidadesExternas(BaseIntegracion):
    """F23: la USB cambia de letra (D-33, D-34). Las letras se simulan con carpetas E, F, G."""

    def setUp(self):
        super().setUp()
        self.administrador.liberar()
        self.almacen = AlmacenFalso()
        self.almacen.montar(self.base / "E", "USB_ANA")
        self.administrador = AdministradorProyecto(self.proyecto, self.monitor, self.adopciones, self.almacen)
        self.administrador.conectar_senales()
        self.ofertas, self.no_encontradas, self.candidatas = [], [], []
        self.administrador.version_administrada_disponible.connect(self.ofertas.append)
        self.administrador.unidad_no_encontrada.connect(self.no_encontradas.append)
        self.administrador.candidatas_administradas.connect(lambda o, c: self.candidatas.append(c))

    def _adoptar_en_e(self, practica="Manglares"):
        original = self.externos / "{}.qgz".format(practica)
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "{}.gpkg".format(practica)))
        self.assertTrue(self.proyecto.write(str(original)))
        carpeta = self.inicializar(practica, carpeta_padre=str(self.base / "E"))
        self.id = self.administrador.contexto.fila_proyecto["id_proyecto"]
        self.proyecto.clear()
        procesar_eventos()
        return original, carpeta

    def _cambiar_letra(self, de, a):
        (self.base / de).rename(self.base / a)
        self.almacen.montados = [v for v in self.almacen.montados if not v.raiz.endswith(os.sep + de)]
        self.almacen.montar(self.base / a, "USB_ANA")

    def _abrir(self, ruta):
        self.proyecto.clear()
        procesar_eventos()
        self.assertTrue(self.proyecto.read(str(ruta)))
        procesar_eventos()

    def prueba_registra_identidad_sin_la_letra(self):
        _original, carpeta = self._adoptar_en_e()
        fila = RepositorioGeoGuardian(carpeta / "Proyecto.gpkg").obtener_proyecto()
        self.assertEqual(fila["version_esquema"], 3)
        self.assertEqual(fila["etiqueta_volumen"], "USB_ANA")
        self.assertEqual(fila["sistema_archivos"], "FAT32")
        self.assertEqual(fila["ruta_en_volumen"], "{0}/{0}.qgz".format(carpeta.name))
        manifiesto = leer_manifiesto(carpeta / ".geoguardian" / "manifiesto.json")
        self.assertEqual(manifiesto["ubicacion"]["etiqueta_volumen"], "USB_ANA")

    def prueba_la_usb_cambia_de_e_a_f_y_se_recupera(self):
        original, carpeta = self._adoptar_en_e()
        self._cambiar_letra("E", "F")
        self._abrir(original)
        esperado = str(self.base / "F" / carpeta.name / (carpeta.name + ".qgz"))
        self.assertEqual(self.ofertas, [esperado])
        self.assertEqual(self.no_encontradas, [])
        self.assertEqual(self.adopciones.buscar(IdentidadUbicacion(str(original))).administrado.ruta, esperado)

    def prueba_misma_etiqueta_con_otro_proyecto_no_se_reasocia(self):
        original, carpeta = self._adoptar_en_e()
        (self.base / "E").rename(self.base / "desconectada")
        self.almacen.montados = []
        self.almacen.montar(self.base / "F", "USB_ANA")
        self.inicializar("Manglares", carpeta_padre=str(self.base / "F"))  # otro proyecto, misma ruta relativa
        self.assertNotEqual(self.administrador.contexto.fila_proyecto["id_proyecto"], self.id)
        self._abrir(original)
        self.assertEqual(self.ofertas, [])
        self.assertEqual(self.no_encontradas, [str(original)])
        self.assertIn(str(self.base / "E"), self.adopciones.buscar(IdentidadUbicacion(str(original))).administrado.ruta)

    def prueba_varias_candidatas_no_se_elige(self):
        original, _carpeta = self._adoptar_en_e()
        shutil.copytree(str(self.base / "E"), str(self.base / "G"))
        self._cambiar_letra("E", "F")
        self.almacen.montar(self.base / "G", "USB_ANA")
        self._abrir(original)
        self.assertEqual(self.ofertas, [])
        self.assertEqual(len(self.candidatas), 1)
        self.assertEqual(len(self.candidatas[0]), 2)

    def prueba_localizar_valida_el_id_proyecto(self):
        original, carpeta = self._adoptar_en_e()
        (self.base / "E").rename(self.base / "Z")
        self.almacen.montados = []
        self.almacen.montar(self.base / "Z", "OTRA_ETIQUETA")
        self._abrir(original)
        self.assertEqual(self.no_encontradas, [str(original)])
        self.assertIsNone(self.administrador.localizar_version_administrada(str(original), str(self.externos)))
        ruta = self.administrador.localizar_version_administrada(str(original), str(self.base / "Z"))
        esperado = str(self.base / "Z" / carpeta.name / (carpeta.name + ".qgz"))
        self.assertEqual(ruta, esperado)
        self.assertEqual(
            self.administrador.localizar_version_administrada(str(original), str(self.base / "Z" / carpeta.name)),
            esperado,
        )
        self.assertEqual(self.adopciones.buscar(IdentidadUbicacion(str(original))).administrado.ruta, esperado)

    def prueba_localizar_rechaza_otro_proyecto(self):
        original, _carpeta = self._adoptar_en_e()
        (self.base / "E").rename(self.base / "desconectada")
        otro = self.inicializar("Manglares", carpeta_padre=str(self.base / "externos"))
        self.proyecto.clear()
        procesar_eventos()
        self.assertIsNone(self.administrador.localizar_version_administrada(str(original), str(otro)))
        self.assertIn(str(self.base / "E"), self.adopciones.buscar(IdentidadUbicacion(str(original))).administrado.ruta)

    def prueba_abrir_el_administrado_desde_otra_letra_actualiza_la_ubicacion(self):
        original, carpeta = self._adoptar_en_e()
        anterior = str(carpeta / (carpeta.name + ".qgz"))
        self._cambiar_letra("E", "F")
        nuevo = self.base / "F" / carpeta.name / (carpeta.name + ".qgz")
        self._abrir(nuevo)
        self.assertTrue(self.administrador.es_administrado)
        fila = self.repo().obtener_proyecto()
        self.assertEqual(fila["ruta_proyecto_administrado"], str(nuevo))
        self.assertEqual(fila["etiqueta_volumen"], "USB_ANA")
        eventos = self.repo().eventos(T.UBICACION_ACTUALIZADA)
        self.assertEqual(len(eventos), 1)
        self.assertEqual(eventos[0].detalle, {"ruta_anterior": anterior, "ruta_nueva": str(nuevo)})
        self.assertEqual(self.adopciones.buscar(IdentidadUbicacion(str(original))).administrado.ruta, str(nuevo))
        nivel, motivos, _r = self.administrador.estado_semaforo()
        self.assertNotEqual(nivel, N.ROJO, motivos)
        self._abrir(nuevo)
        self.assertEqual(len(self.repo().eventos(T.UBICACION_ACTUALIZADA)), 1)  # no se repite
        self._senales_conectadas = True  # setUp ya conecto las senales
        self.guardar_ahora()  # guardado nativo despues de la recuperacion
        guardados = self.repo().eventos(T.PROYECTO_GUARDADO)
        self.assertEqual([g.detalle["origen"] for g in guardados], ["boton"])
        self.assertEqual(self.repo().obtener_proyecto()["ruta_proyecto_administrado"], str(nuevo))


class PruebaAvisoVersionAdministrada(BaseIntegracion):
    """El aviso azul es breve, tiene prioridad sobre el amarillo y se retira solo al abrir la version."""

    def _complemento_con_barra(self):
        from geoguardian import classFactory
        from qgis.gui import QgsMessageBar

        self._ventana = QMainWindow()
        barra = QgsMessageBar()
        iface = mock.Mock()
        iface.mainWindow.return_value = self._ventana
        iface.messageBar.return_value = barra
        iface.addProject.side_effect = lambda ruta: self.proyecto.read(ruta)
        self.administrador.liberar()
        complemento = classFactory(iface)
        complemento.initGui()
        self.addCleanup(complemento.unload)
        self.administrador = complemento.administrador
        return complemento, barra

    def _original_adoptado(self):
        original = self.externos / "original.qgz"
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "datos.gpkg"))
        self.assertTrue(self.proyecto.write(str(original)))
        self.inicializar()
        self.proyecto.clear()
        procesar_eventos()
        return original

    @staticmethod
    def _textos(barra):
        return [i.text() for i in barra.items()]

    def prueba_barra_breve_panel_con_detalle_y_retiro_al_abrir(self):
        from geoguardian.interfaz.dialogo_cierre import AVISO_PANEL

        complemento, barra = self._complemento_con_barra()
        original = self._original_adoptado()
        barra.pushInfo("QGIS", "mensaje de otro origen")  # no debe borrarse
        self.proyecto.read(str(original))
        procesar_eventos()

        mensajes = [i for i in barra.items() if i.title() == "GeoGuardian" and "versión administrada" in i.text()]
        self.assertEqual(len(mensajes), 1)
        self.assertEqual(mensajes[0].text(), "este proyecto tiene una versión administrada disponible.")
        self.assertNotIn(str(self.qgz), mensajes[0].text())
        self.assertNotIn(AVISO_PANEL, self._textos(barra))  # el especifico tiene prioridad
        panel = complemento.panel
        self.assertTrue(panel._caja_version.isVisibleTo(panel))
        self.assertEqual(panel._nombre_version.text(), self.qgz.stem)
        self.assertEqual(panel._ubicacion_version.text(), "Ubicación: " + str(self.qgz))
        self.assertFalse(panel.boton_inicializar.isVisibleTo(panel))

        # Cambios posteriores del original (capas, sin guardar) no hacen aparecer el amarillo.
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "otra.gpkg"))
        procesar_eventos()
        self.assertNotIn(AVISO_PANEL, self._textos(barra))

        panel.boton_abrir_version.click()
        procesar_eventos()
        self.assertEqual(Path(self.proyecto.fileName()), self.qgz)
        self.assertTrue(self.administrador.es_administrado)
        restantes = self._textos(barra)
        self.assertNotIn("este proyecto tiene una versión administrada disponible.", restantes)
        self.assertIn("mensaje de otro origen", restantes)
        self.assertFalse(panel._caja_version.isVisibleTo(panel))

    def prueba_version_no_localizada_muestra_recuperacion_y_no_el_amarillo(self):
        from geoguardian.dominio.recuperacion import MENSAJE_UNIDAD_NO_ENCONTRADA
        from geoguardian.interfaz.dialogo_cierre import AVISO_PANEL

        complemento, barra = self._complemento_con_barra()
        original = self._original_adoptado()
        self.qgz.parent.rename(self.qgz.parent.with_name("movida"))  # unidad "desconectada"
        self.proyecto.read(str(original))
        procesar_eventos()

        textos = self._textos(barra)
        self.assertEqual(textos.count(MENSAJE_UNIDAD_NO_ENCONTRADA), 1)
        self.assertNotIn(AVISO_PANEL, textos)
        self.assertNotIn("este proyecto tiene una versión administrada disponible.", textos)

        # Otro proyecto sin asociacion vuelve al aviso generico y retira el de recuperacion.
        self.proyecto.clear()
        procesar_eventos()
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "suelto.gpkg"))
        self.assertTrue(self.proyecto.write(str(self.externos / "suelto.qgz")))
        procesar_eventos()
        textos = self._textos(barra)
        self.assertIn(AVISO_PANEL, textos)
        self.assertNotIn(MENSAJE_UNIDAD_NO_ENCONTRADA, textos)


    # --- original asociado: panel, indicador, cierre (D-37) -----------------

    def _abrir_original_asociado(self):
        complemento, barra = self._complemento_con_barra()
        original = self._original_adoptado()
        self.proyecto.read(str(original))
        procesar_eventos()
        self.assertEqual(self.administrador.version_administrada, str(self.qgz))
        return complemento, barra, original

    def prueba_original_asociado_panel_e_indicador(self):
        from geoguardian.dominio.semaforo import MOTIVO_NO_ADMINISTRADO

        complemento, _barra, _original = self._abrir_original_asociado()
        panel = complemento.panel
        self.assertNotIn(MOTIVO_NO_ADMINISTRADO, panel._motivos.text())
        self.assertFalse(panel._aviso.isVisibleTo(panel))
        self.assertFalse(panel.boton_inicializar.isVisibleTo(panel))
        self.assertTrue(panel._caja_version.isVisibleTo(panel))
        self.assertEqual(complemento.indicador.text(), "Versión administrada disponible")
        self.assertNotIn("no administrado", complemento.indicador.toolTip())
        self.assertFalse(complemento.accion_inicializar.isEnabled())

        # Al abrir la version administrada, el indicador vuelve a su estado normal.
        panel.boton_abrir_version.click()
        procesar_eventos()
        self.assertNotEqual(complemento.indicador.text(), "Versión administrada disponible")
        self.assertEqual(self.administrador.version_administrada, "")

    def prueba_original_asociado_no_crea_una_segunda_version(self):
        from geoguardian.administracion.administrador_proyecto import ErrorInicializacion

        complemento, barra, _original = self._abrir_original_asociado()
        with mock.patch("geoguardian.complemento.AsistenteInicializacion") as asistente:
            complemento.abrir_asistente()
        asistente.assert_not_called()
        azules = [i for i in barra.items() if i.text() == "este proyecto tiene una versión administrada disponible."]
        self.assertEqual(len(azules), 1)
        carpetas_antes = sorted(p.name for p in self.base.iterdir())
        with self.assertRaises(ErrorInicializacion):
            self.inicializar(practica="Otra")
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), carpetas_antes)

    def prueba_cierre_de_original_asociado(self):
        complemento, _barra, original = self._abrir_original_asociado()
        for accion, cierra, abre_version in (
            (AccionCierre.CANCELAR, False, False),
            (AccionCierre.ABRIR_VERSION, False, True),
            (AccionCierre.CERRAR, True, False),
        ):
            with self.subTest(accion=accion):
                if Path(self.proyecto.fileName()) != original:
                    self.proyecto.read(str(original))
                    procesar_eventos()
                ventana = QMainWindow()
                genericas, especificas = [], []
                filtro = FiltroCierre(
                    ventana,
                    self.administrador,
                    lambda: genericas.append(1) or AccionCierre.INICIALIZAR,
                    lambda: self.fail("no debe ofrecer inicializar"),
                    preguntar_version=lambda ruta: especificas.append(ruta) or accion,
                    abrir_version=complemento.abrir_version_administrada,
                )
                filtro.instalar()
                self.assertEqual(ventana.close(), cierra)
                procesar_eventos()
                self.assertEqual(genericas, [])
                self.assertEqual(especificas, [str(self.qgz)])
                self.assertEqual(Path(self.proyecto.fileName()) == self.qgz, abre_version)
                filtro.desinstalar()

    def prueba_dialogo_de_cierre_con_version(self):
        from geoguardian.interfaz.dialogo_cierre import crear_dialogo_version

        caja, botones = crear_dialogo_version("/ruta/Manglares.qgz")
        self.addCleanup(caja.deleteLater)
        # El orden en pantalla lo decide Qt según el rol y la plataforma.
        self.assertEqual(
            sorted(b.text() for b in caja.buttons()),
            sorted(["Abrir versión administrada", "Cerrar proyecto", "Cancelar"]),
        )
        self.assertIs(caja.defaultButton(), botones[AccionCierre.ABRIR_VERSION])
        self.assertIs(caja.escapeButton(), botones[AccionCierre.CANCELAR])
        self.assertEqual(set(botones), {AccionCierre.ABRIR_VERSION, AccionCierre.CERRAR, AccionCierre.CANCELAR})
        self.assertIn("versión administrada", caja.text())
        self.assertIn("/ruta/Manglares.qgz", caja.informativeText())
        self.assertNotIn("Inicializar", " ".join(b.text() for b in caja.buttons()))


class PruebaFinDeInicializacion(BaseIntegracion):
    """Tras inicializar, el proyecto queda guardado del todo: cerrar QGIS no pide guardar (D-38)."""

    def prueba_proyecto_nuevo_queda_sin_cambios_pendientes(self):
        from geoguardian import classFactory
        from qgis.gui import QgsLayerTreeMapCanvasBridge, QgsMapCanvas

        ventana = QMainWindow()
        iface = mock.Mock()
        iface.mainWindow.return_value = ventana
        iface.actionSaveProject.return_value = self.guardar_nativo()
        # Como QGIS: el lienzo sigue al arbol de capas en diferido y, cuando cambia su
        # lista de capas, QGIS marca el proyecto como modificado (QgisApp::markDirty).
        lienzo = QgsMapCanvas()
        self.addCleanup(lienzo.deleteLater)
        puente = QgsLayerTreeMapCanvasBridge(self.proyecto.layerTreeRoot(), lienzo)
        self.addCleanup(puente.deleteLater)
        lienzo.layersChanged.connect(lambda: self.proyecto.setDirty(True))
        self.administrador.liberar()
        complemento = classFactory(iface)
        complemento.initGui()
        self.addCleanup(complemento.unload)
        self.administrador = complemento.administrador

        # Proyecto nuevo, nunca guardado, con capas cargadas antes de inicializar.
        self.assertEqual(self.proyecto.fileName(), "")
        self.proyecto.addMapLayer(escribir_gpkg(self.externos / "sitios.gpkg"))
        self.proyecto.addMapLayer(capa_memoria())

        prueba = self

        class AsistenteFalso:
            def __init__(self, *_args):
                self.carpeta_creada = None

            def exec_(self):
                self.carpeta_creada = prueba.inicializar()
                return True

        with mock.patch("geoguardian.complemento.AsistenteInicializacion", AsistenteFalso), mock.patch(
            "geoguardian.complemento.mostrar_proyecto_creado"
        ) as mostrado:
            complemento.abrir_asistente()
            procesar_eventos()
        mostrado.assert_called_once()

        # Sin ninguna accion posterior: nada pendiente de guardar y el ultimo guardado fue el nativo.
        self.assertFalse(self.proyecto.isDirty())
        self.assertEqual(self.guardados_nativos, [True])
        self.assertEqual(Path(self.proyecto.fileName()), self.qgz)
        procesar_eventos()
        self.assertFalse(self.proyecto.isDirty())
        tipos = [e.tipo_evento for e in self.repo().eventos()]
        self.assertEqual(tipos.count(T.PROYECTO_INICIALIZADO), 1)
        self.assertNotIn(T.PROYECTO_GUARDADO, tipos)  # el guardado final es parte de la inicializacion


class PruebaAsistenteNavegacion(BaseIntegracion):
    """Anterior/Siguiente en el asistente y combo de asignatura (D-39)."""

    def _asistente(self):
        from geoguardian.interfaz.asistente_inicializacion import AsistenteInicializacion

        asistente = AsistenteInicializacion(self.administrador)
        self.addCleanup(asistente.deleteLater)
        asistente.show()
        self.addCleanup(asistente.hide)
        procesar_eventos()
        return asistente

    def _llenar_datos(self, asistente, estudiante=DATOS.nombre_estudiante, practica="Manglares"):
        datos = asistente.pagina_datos
        datos.nombre.setText(estudiante)
        datos.correo.setText(DATOS.correo)
        datos.titulo.setText(practica)
        datos.descripcion.setPlainText("Cobertura de manglar")
        datos.grupo.setText(DATOS.grupo)
        datos.asignatura.setCurrentIndex(2)

    def _avanzar(self, asistente, veces=1):
        for _ in range(veces):
            asistente.next()
            procesar_eventos()
            ubicacion = asistente.pagina_ubicacion
            if asistente.currentPage() is ubicacion and not ubicacion.opcion_otra.isChecked():
                # Primera visita: se elige "Otra carpeta". Al volver, la eleccion debe seguir ahi.
                ubicacion.opcion_otra.setChecked(True)
                ubicacion._al_cambiar_opcion()
                ubicacion.carpeta_padre.setFilePath(str(self.base))

    def _regresar(self, asistente, veces=1):
        for _ in range(veces):
            asistente.back()
            procesar_eventos()

    def _visibles(self, asistente):
        from qgis.PyQt.QtWidgets import QWizard

        botones = {
            QWizard.BackButton: "Anterior",
            QWizard.NextButton: "Siguiente",
            QWizard.FinishButton: "Crear proyecto administrado",
            QWizard.CancelButton: "Cancelar",
        }
        visibles = []
        for boton, texto in botones.items():
            if asistente.button(boton).isVisible():
                self.assertEqual(asistente.button(boton).text(), texto)
                visibles.append(texto)
        return visibles

    def prueba_botones_de_cada_pagina(self):
        asistente = self._asistente()
        self.assertEqual(self._visibles(asistente), ["Siguiente", "Cancelar"])
        self._llenar_datos(asistente)
        for _ in range(2):  # Nombre final y Ubicación
            self._avanzar(asistente)
            self.assertEqual(self._visibles(asistente), ["Anterior", "Siguiente", "Cancelar"])
        self._avanzar(asistente)
        self.assertIs(asistente.currentPage(), asistente.pagina_resumen)
        self.assertEqual(self._visibles(asistente), ["Anterior", "Crear proyecto administrado", "Cancelar"])

    def prueba_ida_y_vuelta_conserva_los_datos_y_no_crea_nada(self):
        antes = sorted(p.name for p in self.base.iterdir())
        asistente = self._asistente()
        self._llenar_datos(asistente)
        self._avanzar(asistente, 3)
        nombre_final = asistente.pagina_nombre.nombre_academico.text()
        self.assertEqual(nombre_final, "Manglares - Ana Pérez López")
        self._regresar(asistente, 3)
        self.assertIs(asistente.currentPage(), asistente.pagina_datos)

        datos = asistente.pagina_datos.datos()
        self.assertEqual(
            (datos.nombre_estudiante, datos.correo, datos.titulo, datos.descripcion, datos.grupo, datos.asignatura),
            (DATOS.nombre_estudiante, DATOS.correo, "Manglares", "Cobertura de manglar", DATOS.grupo,
             "M3 — Realiza análisis espacial para proyectos"),
        )
        self._avanzar(asistente, 3)
        self.assertEqual(asistente.pagina_nombre.nombre_academico.text(), nombre_final)
        self.assertTrue(asistente.pagina_ubicacion.opcion_otra.isChecked())
        self.assertEqual(asistente.pagina_ubicacion.carpeta_padre.filePath(), str(self.base))
        self.assertEqual(asistente.pagina_resumen.nombre_final.text(), nombre_final)

        # Hasta pulsar Crear proyecto administrado no se crea ni se modifica nada.
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), antes)
        self.assertEqual(self.proyecto.readEntry(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO, "")[0], "")
        self.assertEqual(self.proyecto.fileName(), "")
        self.assertFalse(self.administrador.es_administrado)

    def prueba_recalcula_nombre_final_y_validaciones(self):
        from qgis.PyQt.QtWidgets import QWizard

        asistente = self._asistente()
        self._llenar_datos(asistente)
        self._avanzar(asistente)
        nombre = asistente.pagina_nombre
        self.assertEqual(nombre.nombre_academico.text(), "Manglares - Ana Pérez López")

        # Una edicion propia se conserva si los datos no cambian.
        nombre.nombre_academico.setText("Manglares de Términos - Ana Pérez López")
        nombre._al_editar()
        self._regresar(asistente)
        self._avanzar(asistente)
        self.assertEqual(nombre.nombre_academico.text(), "Manglares de Términos - Ana Pérez López")

        # Cambia el estudiante: se regenera el nombre final sugerido.
        self._regresar(asistente)
        asistente.pagina_datos.nombre.setText("Luis Gómez Can")
        self._avanzar(asistente)
        self.assertEqual(nombre.estudiante.text(), "Luis Gómez Can")
        self.assertEqual(nombre.nombre_academico.text(), "Manglares - Luis Gómez Can")

        # Cambia la practica: tambien se regenera.
        self._regresar(asistente)
        asistente.pagina_datos.titulo.setText("Dunas costeras")
        self._avanzar(asistente)
        self.assertEqual(nombre.nombre_academico.text(), "Dunas costeras - Luis Gómez Can")

        # Las validaciones se recalculan al volver: sin correo no se puede avanzar.
        self._regresar(asistente)
        asistente.pagina_datos.correo.setText("")
        procesar_eventos()
        self.assertFalse(asistente.button(QWizard.NextButton).isEnabled())
        asistente.pagina_datos.correo.setText(DATOS.correo)
        procesar_eventos()
        self.assertTrue(asistente.button(QWizard.NextButton).isEnabled())

        # El resumen refleja el nombre recalculado.
        self._avanzar(asistente, 3)
        self.assertEqual(asistente.pagina_resumen.nombre_final.text(), "Dunas costeras - Luis Gómez Can")

    def prueba_combo_de_asignatura(self):
        from geoguardian.dominio.catalogo_asignaturas import ASIGNATURAS

        asistente = self._asistente()
        combo = asistente.pagina_datos.asignatura
        self.assertTrue(combo.isEditable())
        self._llenar_datos(asistente)
        combo.setCurrentIndex(-1)
        combo.setEditText("")
        self.assertFalse(asistente.pagina_datos.isComplete())  # la asignatura es obligatoria
        self.assertEqual([combo.itemText(i) for i in range(combo.count())], list(ASIGNATURAS))
        self.assertEqual(
            list(ASIGNATURAS),
            [
                "M1 — Maneja e integra información geográfica",
                "M2 — Produce y mantiene información georreferenciada para proyectos",
                "M3 — Realiza análisis espacial para proyectos",
                "M4 — Genera cartografía temática para proyectos",
                "M5 — Obtiene, gestiona y manipula información geográfica a distancia",
            ],
        )
        self.assertEqual(combo.currentText(), "")  # sin eleccion previa: es obligatoria
        for indice, modulo in enumerate(ASIGNATURAS):  # se puede elegir cada modulo, de M1 a M5
            combo.setCurrentIndex(indice)
            self.assertEqual(asistente.pagina_datos.datos().asignatura, modulo)
            self.assertTrue(asistente.pagina_datos.isComplete())
        combo.setEditText("Topografía aplicada")
        self.assertEqual(asistente.pagina_datos.datos().asignatura, "Topografía aplicada")
        self.assertEqual(combo.count(), len(ASIGNATURAS))  # lo escrito no se agrega al catalogo

    def prueba_asignatura_elegida_o_escrita_se_guarda_igual(self):
        from qgis.PyQt.QtWidgets import QWizard

        for practica, eleccion, esperado in (
            ("Manglares", 0, "M1 — Maneja e integra información geográfica"),
            ("Dunas", 4, "M5 — Obtiene, gestiona y manipula información geográfica a distancia"),
            ("Humedales", "Topografía aplicada", "Topografía aplicada"),
        ):
            with self.subTest(asignatura=esperado):
                self.administrador.liberar()
                self.proyecto.clear()
                self.administrador = AdministradorProyecto(self.proyecto, self.monitor, self.adopciones)
                asistente = self._asistente()
                self._llenar_datos(asistente, practica=practica)
                combo = asistente.pagina_datos.asignatura
                if isinstance(eleccion, int):
                    combo.setCurrentIndex(eleccion)
                else:
                    combo.setEditText(eleccion)
                self._avanzar(asistente, 3)
                asistente.button(QWizard.FinishButton).click()
                procesar_eventos()
                carpeta = asistente.carpeta_creada
                self.assertIsNotNone(carpeta)
                self.assertEqual(self.repo().obtener_proyecto()["asignatura"], esperado)
                manifiesto = leer_manifiesto(self.administrador.contexto.ruta_manifiesto)
                self.assertEqual(manifiesto["asignatura"], esperado)


class PruebaCicloDeVida(unittest.TestCase):
    def _iface(self):
        iface = mock.Mock()
        self._ventana = QMainWindow()
        iface.mainWindow.return_value = self._ventana
        return iface

    def prueba_cargar_y_descargar_cinco_veces_sin_receptores_huerfanos(self):
        from geoguardian import classFactory

        proyecto = QgsProject.instance()
        senales = ("layersAdded", "layersWillBeRemoved", "readProject", "cleared", "isDirtyChanged", "projectSaved")

        def receptores():
            return {s: proyecto.receivers(getattr(proyecto, s)) for s in senales}

        inicial = receptores()
        for _ in range(5):
            iface = self._iface()
            complemento = classFactory(iface)
            complemento.initGui()
            self.assertNotEqual(receptores(), inicial)
            complemento.unload()
            procesar_eventos()
            self.assertEqual(receptores(), inicial)
            iface.removeDockWidget.assert_called_once()
            self.assertEqual(iface.removePluginMenu.call_count, 3)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertEqual(self._ventana.findChildren(QToolBar, "BarraGeoGuardian"), [])


if __name__ == "__main__":
    unittest.main()
