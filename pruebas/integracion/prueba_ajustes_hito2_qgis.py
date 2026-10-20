"""Ajustes del Hito 2 de v0.2.0 en QGIS 3.28: D-69 (SRC definido solo en QGIS) y D-70 (plan obsoleto).

Se ejecutan con las demas: python3 pruebas/ejecutar_pruebas.py --integracion
"""

import os
from unittest import mock

from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import QMainWindow

from geoguardian.dominio.plan_incorporacion import (
    Elegibilidad as El,
    MotivoAtencion as M,
    Seleccion as Se,
    texto_estado,
)
from geoguardian.dominio.revalidacion import AVISO_CAMBIOS
from geoguardian.incorporacion.lector_geopaquete import nombres_ocupados
from geoguardian.interfaz.dialogo_incorporacion import INDICE_INCORPORAR

from .prueba_integracion_qgis import BaseIntegracion, procesar_eventos, suma
from .prueba_plan_qgis import BasePlanQgis, capa_con, guardar

UTM = QgsCoordinateReferenceSystem("EPSG:32615")


def shp_sin_prj(carpeta, nombre="parcelas"):
    ruta = carpeta / (nombre + ".shp")
    guardar(capa_con([("id", QVariant.Int)], [(1,)]), ruta)
    (carpeta / (nombre + ".prj")).unlink()
    return ruta


class PruebaD69EnQgis(BasePlanQgis):
    def prueba_fuente_sin_src_con_src_asignado_en_qgis(self):
        capa = self.ogr(shp_sin_prj(self.externos), "parcelas")
        capa.setCrs(UTM)
        self.assertTrue(capa.crs().isValid())
        self.assertFalse(capa.dataProvider().crs().isValid())
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual(unidad.motivo_principal, M.SRC_DEFINIDO_EN_QGIS)
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.NO_INCORPORABLE, Se.NO_SELECCIONABLE))
        self.assertEqual(texto_estado(unidad), "Necesita atención: SRC definido solo en QGIS")
        self.assertEqual(capa.crs().authid(), "EPSG:32615")  # GeoGuardian no corrige nada

    def prueba_fuente_sin_src_y_capa_sin_src(self):
        capa = self.ogr(shp_sin_prj(self.externos), "parcelas")
        self.assertFalse(capa.crs().isValid())
        self.assertEqual(self.unidad(self.construir(), capa).motivo_principal, M.SIN_SRC)

    def prueba_fuente_con_src(self):
        igual = self.ogr(self.shp("igual"), "igual")
        distinta = self.ogr(self.shp("distinta"), "distinta")
        distinta.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        plan = self.construir()
        self.assertEqual(self.unidad(plan, igual).seleccion, Se.PRESELECCIONADA)
        self.assertEqual(self.unidad(plan, distinta).motivo_principal, M.SRC_ASIGNADO_DISTINTO)


class PruebaDialogoAjustes(BaseIntegracion):
    def setUp(self):
        super().setUp()
        from geoguardian import classFactory

        self.ventana = QMainWindow()
        iface = mock.Mock()
        iface.mainWindow.return_value = self.ventana
        self.complemento = classFactory(iface)
        self.complemento.initGui()
        self.addCleanup(lambda: self.complemento.unload() if self.complemento.administrador else None)
        self.administrador.liberar()
        self.administrador = self.complemento.administrador
        self.carpeta = self.inicializar()
        self.proyecto.setCrs(UTM)
        self.complemento.refrescar_panel()

    def tearDown(self):
        for capa in self.proyecto.mapLayers().values():
            if isinstance(capa, QgsVectorLayer) and capa.isEditable():
                capa.rollBack()
        super().tearDown()

    def abrir(self):
        self.complemento.accion_revisar.trigger()
        return self.complemento.dialogo_revisar

    def fila(self, dialogo, nombre):
        for fila in range(dialogo.tabla.rowCount()):
            if dialogo.tabla.item(fila, 0).text() == nombre:
                return dialogo.tabla.item(fila, 0), dialogo.tabla.item(fila, INDICE_INCORPORAR).text()
        self.fail(nombre)

    def rios(self):
        ruta = self.externos / "rios.shp"
        guardar(capa_con([("id", QVariant.Int)], [(1,)]), ruta)
        capa = QgsVectorLayer(str(ruta), "rios", "ogr")
        self.proyecto.addMapLayer(capa)
        return capa

    # --- D-69 -----------------------------------------------------------------------------

    def prueba_d69_casilla_inactiva_y_fuera_de_la_vista_previa(self):
        parcelas = QgsVectorLayer(str(shp_sin_prj(self.externos)), "parcelas", "ogr")
        parcelas.setCrs(UTM)
        self.proyecto.addMapLayer(parcelas)
        self.rios()
        dialogo = self.abrir()
        celda, texto = self.fila(dialogo, "parcelas")
        self.assertEqual(texto, "Necesita atención: SRC definido solo en QGIS")
        self.assertEqual(celda.checkState(), Qt.Unchecked)
        self.assertFalse(celda.flags() & Qt.ItemIsEnabled)
        self.assertFalse(celda.flags() & Qt.ItemIsUserCheckable)
        for texto_visible in (texto, celda.toolTip()):
            self.assertNotIn("incorrect", texto_visible.lower())
            self.assertNotIn("reproyect", texto_visible.lower())
        # Aunque se forzara la casilla, no entra en la seleccion ni en la vista previa.
        celda.setCheckState(Qt.Checked)
        clave = dialogo.plan.unidad_de_capa(parcelas.id()).clave_unidad
        self.assertNotIn(clave, dialogo.plan.seleccionadas)
        self.assertIsNotNone(dialogo.preparar())
        elementos = {dialogo.tabla_plan.item(f, 0).text() for f in range(dialogo.tabla_plan.rowCount())}
        self.assertEqual(elementos, {"rios"})

    # --- D-70 -----------------------------------------------------------------------------

    def prueba_d70_plan_obsoleto_hasta_volver_a_revisar(self):
        rios = self.rios()
        dialogo = self.abrir()
        # 1. Plan vigente: se puede preparar.
        self.assertTrue(dialogo.boton_preparar.isEnabled())
        self.assertIsNotNone(dialogo.preparar())
        self.assertEqual(dialogo.pila.currentIndex(), 1)
        dialogo.boton_volver_lista.click()
        # 2. Una capa cambia y la revalidacion lo detecta.
        rios.startEditing()
        dialogo.boton_preparar.click()
        self.assertEqual(dialogo.pila.currentIndex(), 0)
        self.assertTrue(dialogo.aviso_plan.text().startswith(AVISO_CAMBIOS))
        # 3. El plan queda obsoleto y "Preparar incorporacion" deshabilitado.
        self.assertTrue(dialogo.plan_obsoleto)
        self.assertIsNone(dialogo.plan_preparado)
        self.assertFalse(dialogo.boton_preparar.isEnabled())
        self.assertEqual(dialogo.tabla_plan.rowCount(), 0)
        # 4. "Volver a revisar" sigue habilitado.
        self.assertTrue(dialogo.boton_revisar.isEnabled())
        # 8. Aunque la capa vuelva a su estado, el plan anterior no se muestra sin revisar.
        rios.rollBack()
        with mock.patch.object(dialogo, "_preparar_plan", wraps=dialogo._preparar_plan) as preparar:
            self.assertIsNone(dialogo.preparar())
            preparar.assert_not_called()
        self.assertEqual(dialogo.pila.currentIndex(), 0)
        # Cambiar casillas tampoco lo reactiva ni oculta el aviso.
        celda, _texto = self.fila(dialogo, "rios")
        celda.setCheckState(Qt.Unchecked)
        celda.setCheckState(Qt.Checked)
        self.assertFalse(dialogo.boton_preparar.isEnabled())
        self.assertFalse(dialogo.aviso_plan.isHidden())
        # 5 y 6. "Volver a revisar" reconstruye y, si el estado lo permite, se vuelve a habilitar.
        dialogo.boton_revisar.click()
        self.assertFalse(dialogo.plan_obsoleto)
        self.assertTrue(dialogo.aviso_plan.isHidden())
        self.assertTrue(dialogo.boton_preparar.isEnabled())
        self.assertIsNotNone(dialogo.preparar())
        self.assertEqual(dialogo.pila.currentIndex(), 1)

    def prueba_d70_si_el_nuevo_estado_no_lo_permite_sigue_deshabilitado(self):
        rios = self.rios()
        dialogo = self.abrir()
        rios.startEditing()
        dialogo.boton_preparar.click()
        self.assertFalse(dialogo.boton_preparar.isEnabled())
        dialogo.boton_revisar.click()  # la capa sigue en edicion: ya no hay nada que preparar
        self.assertFalse(dialogo.plan_obsoleto)
        self.assertEqual(self.fila(dialogo, "rios")[1], "Está en modo edición")
        self.assertFalse(dialogo.boton_preparar.isEnabled())

    def prueba_d70_no_escribe_nada(self):
        rios = self.rios()
        procesar_eventos()
        self.proyecto.write()
        procesar_eventos()
        gpkg = self.carpeta / "Proyecto.gpkg"
        archivos = [gpkg, self.carpeta / ".geoguardian" / "manifiesto.json", self.qgz]
        archivos += sorted(self.externos.glob("rios.*"))

        def foto():
            repo = self.administrador.contexto.repositorio
            return dict(
                sumas={str(a): suma(a) for a in archivos},
                fechas={str(a): os.stat(a).st_mtime_ns for a in archivos},
                listados={str(c): sorted(os.listdir(c)) for c in (self.carpeta, self.externos)},
                eventos=len(repo.eventos()),
                recursos=len(repo.todos_los_recursos()),
                capa=(rios.source(), rios.subsetString(), rios.crs().authid(), rios.isEditable()),
                sucio=self.proyecto.isDirty(),
                tablas=sorted(nombres_ocupados(gpkg)),
            )

        antes = foto()
        dialogo = self.abrir()
        dialogo.preparar()
        dialogo.boton_volver_lista.click()
        rios.startEditing()
        dialogo.boton_preparar.click()
        rios.rollBack()
        dialogo.preparar()
        dialogo.boton_revisar.click()
        dialogo.preparar()
        dialogo.close()
        procesar_eventos()
        self.assertEqual(foto(), antes)
