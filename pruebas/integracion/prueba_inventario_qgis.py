"""Pruebas de integracion del inventario "Revisar capas" (v0.2.0, Hito 1; D-40 a D-52).

Se ejecutan con las demas: python3 pruebas/ejecutar_pruebas.py --integracion
"""

import os
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest import mock

from osgeo import gdal
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProcessingUtils,
    QgsProject,
    QgsRasterLayer,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtWidgets import QMainWindow

from geoguardian.dominio.clasificacion import clasificar_recurso
from geoguardian.dominio.clasificacion_inventario import equivalente_v010
from geoguardian.dominio.inventario import Disponibilidad as D, EstadoSrc as S, OrigenFuente as O
from geoguardian.inventario.servicio_inventario import ServicioInventario
from geoguardian.monitoreo.descriptor_fuente import describir_capa

from .prueba_integracion_qgis import BaseIntegracion, procesar_eventos, suma

UTM = QgsCoordinateReferenceSystem("EPSG:32615")


def escribir(ruta, nombre="sitios", crs="EPSG:32615", conservar_archivo=False, controlador="GPKG", geometria="Point"):
    """Escribe una capa vectorial con un punto. Con `conservar_archivo` agrega la capa a un GPKG existente."""
    origen = QgsVectorLayer("{}?crs={}&field=id:integer".format(geometria, crs), nombre, "memory")
    opciones = QgsVectorFileWriter.SaveVectorOptions()
    opciones.driverName = controlador
    if controlador == "GPKG":
        opciones.layerName = nombre
    if conservar_archivo:
        opciones.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        origen, str(ruta), QgsProject.instance().transformContext(), opciones
    )
    assert error[0] == QgsVectorFileWriter.NoError, error
    fuente = "{}|layername={}".format(ruta, nombre) if controlador == "GPKG" else str(ruta)
    return QgsVectorLayer(fuente, nombre, "ogr")


class BaseInventarioQgis(BaseIntegracion):
    def setUp(self):
        super().setUp()
        self.carpeta = self.inicializar()
        self.gpkg = self.carpeta / "Proyecto.gpkg"
        self.proyecto.setCrs(UTM)
        self.servicio = ServicioInventario(self.proyecto, lambda: self.administrador.contexto)

    def agregar(self, capa):
        self.proyecto.addMapLayer(capa)
        return capa

    def revisar(self):
        inventario = self.servicio.construir()
        self.assertIsNotNone(inventario)
        return inventario

    def fila(self, inventario, capa):
        encontrada = [c for c in inventario.capas if c.id_capa == capa.id()]
        self.assertEqual(len(encontrada), 1, capa.name())
        return encontrada[0]

    def fuente(self, inventario, capa):
        return inventario.fuente_de(self.fila(inventario, capa))


class PruebaOrigenEnQgis(BaseInventarioQgis):
    def prueba_capa_en_proyecto_gpkg_activo_es_administrada(self):
        capa = self.agregar(escribir(self.gpkg, "sitios", conservar_archivo=True))
        self.assertTrue(capa.isValid())
        fuente = self.fuente(self.revisar(), capa)
        self.assertEqual((fuente.origen, fuente.disponibilidad), (O.ADMINISTRADA, D.DISPONIBLE))
        self.assertEqual(fuente.subcapa, "sitios")

    def prueba_gpkg_ajeno_llamado_proyecto_gpkg_no_es_administrado(self):
        (self.carpeta / "datos" / "otro").mkdir()
        dentro = self.agregar(escribir(self.carpeta / "datos" / "otro" / "Proyecto.gpkg"))
        fuera = self.agregar(escribir(self.externos / "Proyecto.gpkg"))
        inventario = self.revisar()
        self.assertEqual(self.fuente(inventario, dentro).origen, O.CARPETA_PROYECTO)
        self.assertEqual(self.fuente(inventario, dentro).ruta_relativa, "datos/otro/Proyecto.gpkg")
        self.assertEqual(self.fuente(inventario, fuera).origen, O.ARCHIVO_EXTERNO)

    def prueba_gpkg_no_validado_nada_es_administrado(self):
        capa = self.agregar(escribir(self.gpkg, "sitios", conservar_archivo=True))
        con = sqlite3.connect(str(self.gpkg))
        con.execute("UPDATE gg_proyecto SET id_proyecto = ?", (str(uuid.uuid4()),))
        con.commit()
        con.close()
        self.administrador.detectar_administrado()
        self.assertFalse(self.administrador.contexto.geopaquete_utilizable)
        self.assertEqual(self.fuente(self.revisar(), capa).origen, O.CARPETA_PROYECTO)

    def prueba_tablas_gg_se_omiten(self):
        self.agregar(QgsVectorLayer("{}|layername=gg_eventos".format(self.gpkg), "gg_eventos", "ogr"))
        inventario = self.revisar()
        self.assertEqual(inventario.capas, ())
        self.assertEqual(inventario.tablas_control_omitidas, 1)

    def prueba_temporales(self):
        memoria = self.agregar(QgsVectorLayer("Point?crs=EPSG:32615", "memoria", "memory"))
        procesos = self.agregar(escribir(Path(QgsProcessingUtils.tempFolder()) / "salida.gpkg"))
        inventario = self.revisar()
        self.assertEqual(self.fuente(inventario, memoria).origen, O.TEMPORAL)
        self.assertEqual(self.fuente(inventario, procesos).origen, O.TEMPORAL)

    def prueba_virtual(self):
        virtual = self.agregar(QgsVectorLayer("?query=SELECT%201%20AS%20a", "virtual", "virtual"))
        self.assertTrue(virtual.isValid())
        inventario = self.revisar()
        self.assertEqual(self.fuente(inventario, virtual).origen, O.VIRTUAL)
        self.assertEqual(self.fila(inventario, virtual).estado_src, S.NO_APLICA)

    def prueba_servicios_sin_credenciales(self):
        wfs = self.agregar(QgsVectorLayer(
            "srsname='EPSG:4326' typename='a:b' url='http://ana:secreto@127.0.0.1:9/wfs?MAP=x&token=t0k' "
            "version='auto' username='ana' password='secreto'", "wfs", "WFS"))
        remoto = self.agregar(QgsVectorLayer("/vsicurl/http://127.0.0.1:9/datos.gpkg", "remoto", "ogr"))
        inventario = self.revisar()
        fuente = self.fuente(inventario, wfs)
        self.assertEqual((fuente.origen, fuente.disponibilidad), (O.SERVICIO_REMOTO, D.INVALIDA))
        self.assertEqual(fuente.contenedor, "http://127.0.0.1:9/wfs?MAP=x")
        self.assertEqual(fuente.subcapa, "a:b")
        self.assertEqual(self.fuente(inventario, remoto).origen, O.SERVICIO_REMOTO)
        for fuente in inventario.fuentes:
            for secreto in ("secreto", "t0k", "ana"):
                self.assertNotIn(secreto, fuente.clave)

    def prueba_base_de_datos_externa(self):
        bd = self.agregar(QgsVectorLayer(
            "dbname='sig' host=127.0.0.1 port=9 user='ana' password='secreto' table=\"public\".\"rios\" (geom)",
            "rios", "postgres"))
        fuente = self.fuente(self.revisar(), bd)
        self.assertEqual((fuente.origen, fuente.disponibilidad), (O.BASE_DATOS_EXTERNA, D.INVALIDA))
        self.assertEqual(fuente.contenedor, "postgres://127.0.0.1:9/sig")
        self.assertEqual(fuente.subcapa, "public.rios")
        self.assertNotIn("secreto", fuente.clave)
        self.assertNotIn("ana", fuente.clave)

    def prueba_tabla_sin_geometria(self):
        tabla = self.agregar(escribir(self.carpeta / "datos" / "tabla.gpkg", "tabla", geometria="None"))
        self.assertFalse(tabla.isSpatial())
        inventario = self.revisar()
        self.assertEqual(self.fuente(inventario, tabla).origen, O.CARPETA_PROYECTO)
        self.assertEqual(self.fila(inventario, tabla).estado_src, S.NO_APLICA)

    def prueba_archivo_borrado_y_agrupacion_por_contenedor(self):
        ruta = self.externos / "varias.gpkg"
        rios = self.agregar(escribir(ruta, "rios"))
        lagos = self.agregar(escribir(ruta, "lagos", conservar_archivo=True))
        otra_vez_rios = self.agregar(QgsVectorLayer("{}|layername=rios".format(ruta), "rios 2", "ogr"))
        inventario = self.revisar()
        self.assertEqual(self.fila(inventario, rios).clave_fuente, self.fila(inventario, otra_vez_rios).clave_fuente)
        self.assertNotEqual(self.fila(inventario, rios).clave_fuente, self.fila(inventario, lagos).clave_fuente)
        self.assertEqual(self.fuente(inventario, rios).contenedor, self.fuente(inventario, lagos).contenedor)
        borrada = self.agregar(escribir(self.externos / "borrada.shp", controlador="ESRI Shapefile"))
        for extension in (".shp", ".shx", ".dbf", ".prj", ".cpg"):
            ruta_parte = self.externos / ("borrada" + extension)
            if ruta_parte.exists():
                ruta_parte.unlink()
        self.assertEqual(self.fuente(self.revisar(), borrada).disponibilidad, D.FALTANTE)

    def prueba_capas_no_vectoriales_no_se_revisan(self):
        ruta = str(self.externos / "imagen.tif")
        raster = gdal.GetDriverByName("GTiff").Create(ruta, 2, 2, 1)
        raster.SetGeoTransform([0, 1, 0, 0, 0, -1])
        raster = None
        capa = self.agregar(QgsRasterLayer(ruta, "imagen", "gdal"))
        self.assertTrue(capa.isValid())
        inventario = self.revisar()
        fila = self.fila(inventario, capa)
        self.assertFalse(fila.revisada)
        self.assertIsNone(inventario.fuente_de(fila))

    def prueba_solo_proyectos_administrados(self):
        self.proyecto.clear()
        self.administrador.detectar_administrado()
        self.assertIsNone(self.servicio.construir())
        self.assertFalse(self.servicio.disponible())


class PruebaSrcEnQgis(BaseInventarioQgis):
    def prueba_epsg_frente_a_wkt_equivalente(self):
        """D-48: QGIS 3.28 reconoce como iguales EPSG:32615 y sus WKT (WKT2, WKT1 GDAL y ESRI)."""
        for formato in (QgsCoordinateReferenceSystem.WKT2_2019, QgsCoordinateReferenceSystem.WKT1_GDAL,
                        QgsCoordinateReferenceSystem.WKT1_ESRI):
            desde_wkt = QgsCoordinateReferenceSystem.fromWkt(UTM.toWkt(formato))
            self.assertTrue(desde_wkt == UTM, formato)
        # Un shapefile guarda un .prj con WKT de ESRI: la capa coincide con el proyecto en EPSG:32615.
        shp = self.agregar(escribir(self.externos / "utm.shp", controlador="ESRI Shapefile"))
        self.assertEqual(self.fila(self.revisar(), shp).estado_src, S.COINCIDE)

    def prueba_crs84_y_epsg_4326_son_distintos_para_qgis(self):
        """Hallazgo: QGIS 3.28 distingue OGC:CRS84 de EPSG:4326 (orden de ejes); se informa como diferente."""
        self.assertFalse(QgsCoordinateReferenceSystem("OGC:CRS84") == QgsCoordinateReferenceSystem("EPSG:4326"))

    def prueba_estados_de_src(self):
        coincide = self.agregar(escribir(self.carpeta / "datos" / "a.gpkg", "a"))
        diferente = self.agregar(escribir(self.carpeta / "datos" / "b.gpkg", "b", crs="EPSG:4326"))
        sin_src = self.agregar(escribir(self.externos / "sin_prj.shp", controlador="ESRI Shapefile"))
        (self.externos / "sin_prj.prj").unlink()
        sin_src_recargada = self.agregar(QgsVectorLayer(str(self.externos / "sin_prj.shp"), "sin prj", "ogr"))
        self.proyecto.removeMapLayer(sin_src.id())
        inventario = self.revisar()
        self.assertEqual(self.fila(inventario, coincide).estado_src, S.COINCIDE)
        self.assertEqual(self.fila(inventario, diferente).estado_src, S.DIFERENTE)
        self.assertEqual(self.fila(inventario, sin_src_recargada).estado_src, S.CAPA_SIN_SRC)
        self.proyecto.setCrs(QgsCoordinateReferenceSystem())
        self.assertEqual(self.fila(self.revisar(), coincide).estado_src, S.PROYECTO_SIN_SRC)

    def prueba_src_asignado_distinto_del_de_la_fuente(self):
        capa = self.agregar(escribir(self.externos / "asignada.gpkg"))
        capa.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        # Hallazgo: en QGIS 3.28 sourceCrs() sigue al SRC asignado; el de la fuente lo da el proveedor.
        self.assertEqual(capa.sourceCrs().authid(), "EPSG:4326")
        self.assertEqual(capa.dataProvider().crs().authid(), "EPSG:32615")
        fila = self.fila(self.revisar(), capa)
        self.assertEqual(fila.estado_src, S.DIFERENTE)
        self.assertEqual(fila.src_fuente_distinto.identificador, "EPSG:32615")
        self.assertEqual(capa.crs().authid(), "EPSG:4326")  # no se corrige nada


class PruebaCoherenciaYSoloLectura(BaseInventarioQgis):
    def _proyecto_variado(self):
        (self.carpeta / "datos").mkdir(exist_ok=True)
        capas = [
            escribir(self.gpkg, "sitios", conservar_archivo=True),
            escribir(self.carpeta / "datos" / "rios.gpkg", "rios"),
            escribir(self.externos / "municipios.gpkg", "municipios", crs="EPSG:4326"),
            QgsVectorLayer("Point?crs=EPSG:32615", "memoria", "memory"),
            QgsVectorLayer("?query=SELECT%201%20AS%20a", "virtual", "virtual"),
            QgsVectorLayer("/vsicurl/http://127.0.0.1:9/datos.gpkg", "remoto", "ogr"),
            QgsVectorLayer(str(self.externos / "no_existe.shp"), "rota", "ogr"),
        ]
        for capa in capas:
            self.agregar(capa)
        return capas

    def prueba_coincide_con_la_clasificacion_de_v010(self):
        """D-42: lo que registra el monitor de v0.1.0 en gg_recursos coincide con el inventario."""
        capas = self._proyecto_variado()
        inventario = self.revisar()
        temporales = [tempfile.gettempdir(), QgsProcessingUtils.tempFolder()]
        for capa in capas:
            fuente = self.fuente(inventario, capa)
            nuevo = equivalente_v010(fuente.origen, fuente.disponibilidad)
            self.assertEqual(nuevo, clasificar_recurso(describir_capa(capa), str(self.carpeta), temporales), capa.name())
            self.assertEqual(nuevo, self.repo().recurso_vigente(capa.id()).estado, capa.name())

    def prueba_revisar_no_escribe_ni_cambia_nada(self):
        capas = self._proyecto_variado()
        # QGIS aplica cambios diferidos al agregar capas (D-38): se vacian antes de la fotografia.
        procesar_eventos()
        self.proyecto.write()
        procesar_eventos()
        manifiesto = self.carpeta / ".geoguardian" / "manifiesto.json"
        archivos = [self.gpkg, manifiesto, self.qgz, self.carpeta / "datos" / "rios.gpkg", self.externos / "municipios.gpkg"]
        antes_sumas = {str(a): suma(a) for a in archivos}
        antes_fechas = {str(a): os.stat(a).st_mtime_ns for a in archivos}
        antes_eventos = len(self.repo().eventos())
        antes_recursos = len(self.repo().todos_los_recursos())
        antes_capas = {c.id(): (c.source(), c.crs().authid(), c.isValid()) for c in capas}
        antes_sucio = self.proyecto.isDirty()
        antes_src = self.proyecto.crs().authid()
        for _ in range(2):
            self.revisar()
        procesar_eventos()
        self.assertEqual({str(a): suma(a) for a in archivos}, antes_sumas)
        self.assertEqual({str(a): os.stat(a).st_mtime_ns for a in archivos}, antes_fechas)
        self.assertEqual(len(self.repo().eventos()), antes_eventos)
        self.assertEqual(len(self.repo().todos_los_recursos()), antes_recursos)
        self.assertEqual({c.id(): (c.source(), c.crs().authid(), c.isValid()) for c in capas}, antes_capas)
        self.assertEqual(self.proyecto.isDirty(), antes_sucio)
        self.assertEqual(self.proyecto.crs().authid(), antes_src)


class PruebaDialogoRevisarCapas(BaseIntegracion):
    def _complemento(self):
        from geoguardian import classFactory

        self.ventana = QMainWindow()
        iface = mock.Mock()
        iface.mainWindow.return_value = self.ventana
        complemento = classFactory(iface)
        complemento.initGui()
        self.addCleanup(lambda: complemento.unload() if complemento.administrador else None)
        self.administrador.liberar()
        self.administrador = complemento.administrador
        return complemento, iface

    def prueba_solo_para_proyectos_administrados(self):
        complemento, iface = self._complemento()
        self.assertFalse(complemento.accion_revisar.isEnabled())
        complemento.revisar_capas()
        self.assertIsNone(complemento.dialogo_revisar)
        iface.messageBar().pushInfo.assert_called()

    def prueba_abrir_volver_a_revisar_y_cerrar(self):
        complemento, _iface = self._complemento()
        carpeta = self.inicializar()
        complemento.refrescar_panel()
        self.assertTrue(complemento.accion_revisar.isEnabled())
        self.proyecto.addMapLayer(escribir(carpeta / "datos" / "rios.gpkg", "rios"))
        self.proyecto.addMapLayer(QgsVectorLayer("Point?crs=EPSG:4326", "puntos", "memory"))
        complemento.accion_revisar.trigger()
        dialogo = complemento.dialogo_revisar
        self.assertTrue(dialogo.isVisible())
        self.assertEqual(dialogo.tabla.rowCount(), 2)
        self.assertIn("2 capas revisadas", dialogo.resumen.text())
        celdas = {
            dialogo.tabla.item(f, c).text()
            for f in range(dialogo.tabla.rowCount())
            for c in range(dialogo.tabla.columnCount())
        }
        self.assertIn("En la carpeta del proyecto", celdas)
        self.assertIn("datos/rios.gpkg › rios", celdas)
        # Volver a revisar: el inventario se reconstruye solo al pedirlo (D-49).
        self.proyecto.addMapLayer(QgsVectorLayer("Point?crs=EPSG:4326", "otra", "memory"))
        self.assertEqual(dialogo.tabla.rowCount(), 2)
        dialogo.boton_revisar.click()
        self.assertEqual(dialogo.tabla.rowCount(), 3)
        # Al cambiar de proyecto el dialogo se cierra.
        self.proyecto.clear()
        procesar_eventos()
        self.assertIsNone(complemento.dialogo_revisar)
        complemento.unload()
        procesar_eventos()
        self.assertIsNone(complemento.accion_revisar)
