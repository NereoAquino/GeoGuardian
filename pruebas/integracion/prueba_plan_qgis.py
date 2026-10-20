"""Pruebas de integracion del plan de incorporacion (v0.2.0, Hito 2; D-56 a D-68).

Se ejecutan con las demas: python3 pruebas/ejecutar_pruebas.py --integracion
"""

import json
import os
import sqlite3
import uuid
from pathlib import Path
from unittest import mock

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProcessingUtils,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtWidgets import QMainWindow

from geoguardian.administracion.identidad_proyecto import id_desde_geopaquete
from geoguardian.dominio.plan_incorporacion import (
    AVISO_PLAN,
    FID_CLAVE,
    FID_ENTERO_UNICO,
    FID_REPETIDO,
    FID_TIPO_INCOMPATIBLE,
    GEOPAQUETE_AJENO,
    GEOPAQUETE_NO_UTILIZABLE,
    TEMPORAL_ARCHIVO,
    TEMPORAL_MEMORIA,
    TEXTO_MOTIVO,
    Elegibilidad as El,
    MotivoAtencion as M,
    Seleccion as Se,
    texto_estado,
)
from geoguardian.dominio.revalidacion import AVISO_CAMBIOS, MotivoCambio as C
from geoguardian.incorporacion.lector_geopaquete import nombres_ocupados
from geoguardian.incorporacion.servicio_plan import ServicioPlan
from geoguardian.interfaz.dialogo_incorporacion import (
    BOTON_PREPARAR,
    COLUMNA_INCORPORAR,
    INDICE_INCORPORAR,
)

from .prueba_integracion_qgis import BaseIntegracion, procesar_eventos, suma
from .prueba_inventario_qgis import BaseInventarioQgis, escribir

UTM = QgsCoordinateReferenceSystem("EPSG:32615")


def capa_con(campos, filas, geometria="Point", crs="EPSG:32615", nombre="capa"):
    """Capa en memoria con `campos` [(nombre, tipo)] y una entidad por fila."""
    uri = geometria + ("?crs={}".format(crs) if crs else "")
    capa = QgsVectorLayer(uri, nombre, "memory")
    capa.dataProvider().addAttributes([QgsField(n, t) for n, t in campos])
    capa.updateFields()
    entidades = []
    for i, fila in enumerate(filas):
        entidad = QgsFeature(capa.fields())
        entidad.setAttributes(list(fila))
        if geometria != "None":
            entidad.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(500000 + i, 2100000 + i)))
        entidades.append(entidad)
    capa.dataProvider().addFeatures(entidades)
    return capa


def guardar(capa, ruta, controlador="ESRI Shapefile", nombre=None, conservar_archivo=False):
    opciones = QgsVectorFileWriter.SaveVectorOptions()
    opciones.driverName = controlador
    if nombre:
        opciones.layerName = nombre
    if conservar_archivo:
        opciones.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    error = QgsVectorFileWriter.writeAsVectorFormatV3(capa, str(ruta), QgsProject.instance().transformContext(), opciones)
    assert error[0] == QgsVectorFileWriter.NoError, error
    return str(ruta)


def geojson_mezclado(ruta):
    datos = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"n": 1}, "geometry": {"type": "Point", "coordinates": [-90.5, 19.8]}},
        {"type": "Feature", "properties": {"n": 2},
         "geometry": {"type": "LineString", "coordinates": [[-90.5, 19.8], [-90.4, 19.9]]}},
    ]}
    Path(ruta).write_text(json.dumps(datos), encoding="utf-8")
    return str(ruta)


class BasePlanQgis(BaseInventarioQgis):
    def setUp(self):
        super().setUp()
        self.servicio_plan = ServicioPlan(
            self.proyecto, lambda: self.administrador.contexto, self.servicio.construir, id_desde_geopaquete
        )

    def construir(self, seleccion=None):
        resultado = self.servicio_plan.construir(self.revisar(), seleccion)
        self.assertIsNotNone(resultado.plan, resultado.motivo_sin_plan)
        return resultado.plan

    def unidad(self, plan, capa):
        unidad = plan.unidad_de_capa(capa.id())
        self.assertIsNotNone(unidad, capa.name())
        return unidad

    def shp(self, nombre, campos=(("id", QVariant.Int),), filas=((1,),), crs="EPSG:32615", carpeta=None):
        ruta = (carpeta or self.externos) / (nombre + ".shp")
        guardar(capa_con(campos, filas, crs=crs), ruta)
        return ruta

    def ogr(self, fuente, nombre):
        capa = self.agregar(QgsVectorLayer(str(fuente), nombre, "ogr"))
        self.assertTrue(capa.isValid(), fuente)
        return capa


class PruebaUnidadesEnQgis(BasePlanQgis):
    def prueba_varias_capas_de_un_mismo_archivo_son_una_unidad(self):
        ruta = self.shp("rios")
        capas = [self.ogr(ruta, "rios {}".format(i)) for i in range(3)]
        plan = self.construir()
        unidad = self.unidad(plan, capas[0])
        self.assertEqual(set(unidad.ids_capas), {c.id() for c in capas})
        self.assertEqual(unidad.seleccion, Se.PRESELECCIONADA)
        self.assertEqual(unidad.nombre_destino, "rios")
        self.assertEqual(len(plan.unidades), 1)

    def prueba_filtros_distintos_son_unidades_distintas(self):
        ruta = self.shp("pozos", filas=((1,), (2,), (3,)))
        completa = self.ogr(ruta, "pozos")
        repetida = self.ogr(ruta, "pozos (otra)")
        uno = self.ogr(ruta, "pozo 1")
        uno.setSubsetString('"id" = 1')
        dos = self.ogr(ruta, "pozo 2")
        dos.setSubsetString('"id" = 2')
        plan = self.construir()
        self.assertEqual(self.unidad(plan, completa), self.unidad(plan, repetida))
        claves = {self.unidad(plan, c).clave_unidad for c in (completa, uno, dos)}
        self.assertEqual(len(claves), 3)
        filtrada = self.unidad(plan, uno)
        self.assertEqual((filtrada.elegibilidad, filtrada.seleccion), (El.CON_ADVERTENCIA, Se.SELECCIONABLE))
        self.assertIn(M.FILTRO, filtrada.motivos)
        self.assertEqual(filtrada.nombre_destino, "pozo 1")  # nombre visible de su primera capa
        self.assertEqual(self.unidad(plan, completa).seleccion, Se.PRESELECCIONADA)

    def prueba_geojson_mezclado_y_geometrytype(self):
        ruta = geojson_mezclado(self.externos / "mezcla.geojson")
        sin_tipo = self.ogr(ruta, "mezcla")
        puntos = self.ogr(ruta + "|geometrytype=Point", "mezcla puntos")
        lineas = self.ogr(ruta + "|geometrytype=LineString", "mezcla lineas")
        plan = self.construir()
        mezclada = self.unidad(plan, sin_tipo)
        self.assertIn(M.GEOMETRIAS_MEZCLADAS, mezclada.motivos)
        self.assertEqual(mezclada.elegibilidad, El.NO_INCORPORABLE)
        for capa in (puntos, lineas):
            unidad = self.unidad(plan, capa)
            self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.CON_ADVERTENCIA, Se.SELECCIONABLE))
            self.assertIn(M.FILTRO_GEOMETRIA, unidad.motivos)
            self.assertEqual(unidad.nombre_destino, capa.name())
        self.assertNotEqual(self.unidad(plan, puntos).clave_unidad, self.unidad(plan, lineas).clave_unidad)

    def prueba_geopaquete_externo_con_varias_tablas(self):
        ruta = self.externos / "inegi.gpkg"
        escribir(ruta, "municipios")
        escribir(ruta, "localidades", conservar_archivo=True)
        guardar(capa_con([("clave", QVariant.String)], [("A",)], geometria="None"), ruta, "GPKG", "catalogo", True)
        municipios = self.ogr("{}|layername=municipios".format(ruta), "municipios")
        localidades = self.ogr("{}|layername=localidades".format(ruta), "localidades")
        catalogo = self.ogr("{}|layername=catalogo".format(ruta), "catalogo")
        sin_nombre = self.ogr(ruta, "inegi")  # varias tablas y ninguna indicada: ambiguo (D-56)
        plan = self.construir()
        unidades = [self.unidad(plan, c) for c in (municipios, localidades, catalogo, sin_nombre)]
        self.assertEqual(len({u.clave_unidad for u in unidades}), 4)
        self.assertEqual([u.nombre_destino for u in unidades[:3]], ["municipios", "localidades", "catalogo"])
        self.assertEqual(unidades[2].seleccion, Se.PRESELECCIONADA)  # tabla sin geometria
        self.assertNotIn(M.CAMPO_GEOM, unidades[2].motivos)

    def prueba_geopaquete_de_una_tabla_se_une_con_su_referencia_explicita(self):
        ruta = self.externos / "uno.gpkg"
        escribir(ruta, "rios")
        explicita = self.ogr("{}|layername=rios".format(ruta), "rios")
        implicita = self.ogr(ruta, "uno")
        plan = self.construir()
        self.assertEqual(self.unidad(plan, explicita), self.unidad(plan, implicita))
        self.assertEqual(self.unidad(plan, explicita).nombre_destino, "rios")

    def prueba_temporales(self):
        memoria = self.agregar(capa_con([("id", QVariant.Int)], [(1,)], nombre="Puntos de campo"))
        procesos = self.agregar(escribir(Path(QgsProcessingUtils.tempFolder()) / "OUTPUT.gpkg", "output"))
        procesos.setName("Buffer 100 m")
        plan = self.construir()
        for capa, tipo in ((memoria, TEMPORAL_MEMORIA), (procesos, TEMPORAL_ARCHIVO)):
            unidad = self.unidad(plan, capa)
            self.assertEqual(unidad.tipo_temporal, tipo)
            self.assertEqual(unidad.seleccion, Se.PRESELECCIONADA)
            self.assertEqual(texto_estado(unidad), "Capa temporal: se recomienda incorporar")
            self.assertEqual(unidad.nombre_destino, capa.name())
        self.assertGreater(self.unidad(plan, memoria).huella.capas[0].num_entidades, 0)

    def prueba_origenes_que_no_se_incorporan(self):
        administrada = self.agregar(escribir(self.gpkg, "sitios", conservar_archivo=True))
        virtual = self.agregar(QgsVectorLayer("?query=SELECT%201%20AS%20a", "virtual", "virtual"))
        rota = self.agregar(QgsVectorLayer(str(self.externos / "no_existe.shp"), "rota", "ogr"))
        plan = self.construir()
        for capa, motivo in ((administrada, M.YA_ADMINISTRADA), (virtual, M.VIRTUAL), (rota, M.NO_DISPONIBLE)):
            unidad = self.unidad(plan, capa)
            self.assertEqual(unidad.motivo_principal, motivo, capa.name())
            self.assertEqual(unidad.seleccion, Se.NO_SELECCIONABLE)
            self.assertIsNone(unidad.destino)


class PruebaSrcEnElPlan(BasePlanQgis):
    def prueba_src_diferente_se_puede_elegir_pero_no_se_preselecciona(self):
        capa = self.agregar(escribir(self.externos / "municipios.gpkg", "municipios", crs="EPSG:4326"))
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.CON_ADVERTENCIA, Se.SELECCIONABLE))
        self.assertEqual(texto_estado(unidad), "SRC diferente al proyecto")
        self.assertEqual(capa.crs().authid(), "EPSG:4326")

    def prueba_archivo_sin_src(self):
        ruta = self.shp("sin_prj")
        (self.externos / "sin_prj.prj").unlink()
        capa = self.ogr(ruta, "sin prj")
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual(unidad.motivo_principal, M.SIN_SRC)
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)
        self.assertEqual(TEXTO_MOTIVO[M.SIN_SRC],
                         "La capa no tiene SRC. Define correctamente su sistema de coordenadas y vuelve a revisar.")

    def prueba_src_asignado_distinto_del_archivo(self):
        capa = self.agregar(escribir(self.externos / "asignada.gpkg"))
        capa.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual(unidad.motivo_principal, M.SRC_ASIGNADO_DISTINTO)
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)
        self.assertEqual(capa.crs().authid(), "EPSG:4326")
        self.assertEqual(capa.dataProvider().crs().authid(), "EPSG:32615")

    def prueba_capa_temporal_sin_src(self):
        capa = self.agregar(capa_con([("id", QVariant.Int)], [(1,)], crs=None, nombre="sin src"))
        # QGIS 3.28 asigna un SRC por omision a la capa en memoria sin SRC; se quita como lo haria el estudiante.
        capa.setCrs(QgsCoordinateReferenceSystem())
        self.assertFalse(capa.crs().isValid())
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual(unidad.motivo_principal, M.TEMPORAL_SIN_SRC)
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)


class PruebaEdicionEnElPlan(BasePlanQgis):
    def tearDown(self):
        for capa in self.proyecto.mapLayers().values():
            if isinstance(capa, QgsVectorLayer) and capa.isEditable():
                capa.rollBack()
        self.proyecto.setTransactionMode(Qgis.TransactionMode.Disabled)
        super().tearDown()

    def prueba_modo_edicion_y_cambios_sin_guardar(self):
        en_edicion = self.ogr(self.shp("a"), "a")
        con_cambios = self.ogr(self.shp("b"), "b")
        en_edicion.startEditing()
        con_cambios.startEditing()
        con_cambios.changeAttributeValue(next(con_cambios.getFeatures()).id(), 0, 9)
        plan = self.construir()
        a, b = self.unidad(plan, en_edicion), self.unidad(plan, con_cambios)
        self.assertEqual((a.elegibilidad, a.seleccion), (El.BLOQUEADA, Se.NO_SELECCIONABLE))
        self.assertEqual(a.motivos, (M.EN_EDICION,))
        self.assertEqual(texto_estado(b), "Tiene cambios sin guardar")
        self.assertEqual(b.motivo_principal, M.CAMBIOS_SIN_GUARDAR)
        self.assertTrue(en_edicion.isEditable() and con_cambios.isModified())  # no se termina ninguna edicion

    def prueba_una_capa_en_edicion_bloquea_toda_la_unidad(self):
        ruta = self.shp("rios")
        quieta = self.ogr(ruta, "rios")
        editada = self.ogr(ruta, "rios (edicion)")
        editada.startEditing()
        unidad = self.unidad(self.construir(), quieta)
        self.assertEqual(unidad.elegibilidad, El.BLOQUEADA)
        self.assertFalse(quieta.isEditable())

    def prueba_grupos_de_transaccion(self):
        for modo in (Qgis.TransactionMode.AutomaticGroups, Qgis.TransactionMode.BufferedGroups):
            self.proyecto.removeAllMapLayers()
            self.proyecto.setTransactionMode(modo)
            ruta = self.externos / "grupo_{}.gpkg".format(int(modo))
            escribir(ruta, "uno")
            escribir(ruta, "dos", conservar_archivo=True)
            uno = self.ogr("{}|layername=uno".format(ruta), "uno")
            dos = self.ogr("{}|layername=dos".format(ruta), "dos")
            uno.startEditing()
            self.assertTrue(dos.isEditable(), modo)  # QGIS pone en edicion todo el grupo
            plan = self.construir()
            for capa in (uno, dos):
                self.assertEqual(self.unidad(plan, capa).elegibilidad, El.BLOQUEADA, (modo, capa.name()))
            uno.rollBack()
            self.proyecto.setTransactionMode(Qgis.TransactionMode.Disabled)


class PruebaCamposEnElPlan(BasePlanQgis):
    def prueba_fid(self):
        repetido = self.ogr(self.shp("rep", [("fid", QVariant.Int)], [(1,), (1,)]), "rep")
        unico = self.ogr(self.shp("uni", [("fid", QVariant.Int)], [(1,), (2,)]), "uni")
        texto = self.ogr(self.shp("txt", [("fid", QVariant.String)], [("a",)]), "txt")
        clave = self.agregar(escribir(self.externos / "clave.gpkg", "clave"))
        plan = self.construir()
        self.assertEqual(self.unidad(plan, repetido).motivo_principal, M.CAMPO_FID_REPETIDO)
        self.assertEqual(self.unidad(plan, texto).motivo_principal, M.CAMPO_FID_TIPO)
        self.assertEqual(self.unidad(plan, unico).seleccion, Se.PRESELECCIONADA)
        self.assertEqual(self.unidad(plan, clave).seleccion, Se.PRESELECCIONADA)
        self.assertEqual(clave.dataProvider().pkAttributeIndexes(), [0])  # fid del GPKG es la clave
        from geoguardian.incorporacion.lector_plan import estado_fid
        self.assertEqual([estado_fid(c, True) for c in (repetido, unico, texto, clave)],
                         [FID_REPETIDO, FID_ENTERO_UNICO, FID_TIPO_INCOMPATIBLE, FID_CLAVE])

    def prueba_id_e_ID_y_campo_geom(self):
        repetidos = self.agregar(capa_con([("ID", QVariant.Int), ("id", QVariant.Int)], [(1, 2)], nombre="rep"))
        geom = self.agregar(capa_con([("geom", QVariant.String)], [("x",)], nombre="geom"))
        sin_geometria = self.agregar(capa_con([("geom", QVariant.String)], [("x",)], geometria="None", nombre="tabla"))
        plan = self.construir()
        self.assertEqual(self.unidad(plan, repetidos).motivo_principal, M.CAMPOS_REPETIDOS)
        self.assertEqual(self.unidad(plan, geom).motivo_principal, M.CAMPO_GEOM)
        self.assertNotIn(M.CAMPO_GEOM, self.unidad(plan, sin_geometria).motivos)

    def prueba_campos_calculados(self):
        capa = self.ogr(self.shp("zonas"), "zonas")
        capa.addExpressionField("$x", QgsField("x_calc", QVariant.Double))
        unidad = self.unidad(self.construir(), capa)
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.CON_ADVERTENCIA, Se.SELECCIONABLE))
        self.assertEqual(TEXTO_MOTIVO[M.CAMPOS_CALCULADOS],
                         "Los campos calculados se guardarán como valores y dejarán de recalcularse automáticamente.")
        self.assertIn(M.CAMPOS_CALCULADOS, unidad.motivos)


class PruebaNombresEnElGeopaquete(BasePlanQgis):
    def prueba_conflictos_con_tablas_existentes(self):
        escribir(self.gpkg, "municipios", conservar_archivo=True)
        escribir(self.gpkg, "municipios_2", conservar_archivo=True)
        ocupados = nombres_ocupados(self.gpkg)
        for nombre in ("gg_proyecto", "gg_recursos", "gg_eventos", "gpkg_contents", "municipios", "municipios_2"):
            self.assertIn(nombre, ocupados)
        self.assertTrue(any(n.startswith("rtree_municipios") for n in ocupados))
        mayusculas = self.ogr(self.shp("Municipios"), "Municipios")
        (self.externos / "otra").mkdir()
        otra = self.ogr(self.shp("municipios", carpeta=self.externos / "otra"), "municipios")
        control = self.ogr(self.shp("gg_eventos"), "gg_eventos")
        plan = self.construir()
        self.assertEqual(self.unidad(plan, mayusculas).nombre_destino, "Municipios_3")
        self.assertEqual(self.unidad(plan, otra).nombre_destino, "municipios_4")
        self.assertEqual(self.unidad(plan, control).nombre_destino, "capa_gg_eventos")
        self.assertTrue(self.unidad(plan, mayusculas).conflicto_resuelto)
        self.assertEqual(self.unidad(plan, mayusculas).destino.conflicto, "existe")

    def prueba_nombres_unicode(self):
        capa = self.agregar(capa_con([("id", QVariant.Int)], [(1,)], nombre="Áreas protegidas 🌊 ñ"))
        self.assertEqual(self.unidad(self.construir(), capa).nombre_destino, "Áreas protegidas 🌊 ñ")

    def prueba_lectura_sin_bloqueos_ni_archivos_nuevos(self):
        antes = sorted(os.listdir(self.carpeta))
        con = sqlite3.connect(str(self.gpkg))
        con.execute("BEGIN IMMEDIATE")  # otro programa escribiendo
        try:
            self.assertIsNotNone(nombres_ocupados(self.gpkg))
        finally:
            con.rollback()
            con.close()
        self.assertEqual(sorted(os.listdir(self.carpeta)), antes)
        self.assertIsNone(nombres_ocupados(self.externos / "no_existe.gpkg"))
        self.assertFalse((self.externos / "no_existe.gpkg").exists())


class PruebaDestinoDelPlan(BasePlanQgis):
    def prueba_sin_geopaquete_utilizable_no_hay_plan(self):
        self.agregar(capa_con([("id", QVariant.Int)], [(1,)]))
        con = sqlite3.connect(str(self.gpkg))
        con.execute("UPDATE gg_proyecto SET id_proyecto = ?", (str(uuid.uuid4()),))
        con.commit()
        con.close()
        self.administrador.detectar_administrado()
        resultado = self.servicio_plan.construir(self.revisar())
        self.assertIsNone(resultado.plan)
        self.assertEqual(resultado.motivo_sin_plan, GEOPAQUETE_NO_UTILIZABLE)

    def prueba_geopaquete_de_otro_proyecto(self):
        servicio = ServicioPlan(self.proyecto, lambda: self.administrador.contexto, self.servicio.construir,
                                lambda _ruta: "otro-id")
        resultado = servicio.construir(self.revisar())
        self.assertIsNone(resultado.plan)
        self.assertEqual(resultado.motivo_sin_plan, GEOPAQUETE_AJENO)


class PruebaRevalidacionEnQgis(BasePlanQgis):
    def preparar(self):
        self.ruta = self.shp("rios", filas=((1,), (2,)))
        self.rios = self.ogr(self.ruta, "rios")
        self.memoria = self.agregar(capa_con([("id", QVariant.Int)], [(1,)], nombre="campo"))
        self.plan = self.construir()
        self.clave = self.unidad(self.plan, self.rios).clave_unidad
        self.assertTrue(self.servicio_plan.revalidar(self.plan).vigente)

    def cambios(self):
        resultado = self.servicio_plan.revalidar(self.plan)
        self.assertFalse(resultado.vigente)
        self.assertEqual(resultado.texto(), AVISO_CAMBIOS)
        return {c.clave_unidad: c.motivos for c in resultado.cambios}

    def prueba_capa_quitada(self):
        self.preparar()
        self.proyecto.removeMapLayer(self.rios.id())
        self.assertEqual(self.cambios()[self.clave], (C.CAPA_ELIMINADA,))

    def prueba_cambio_de_fuente(self):
        self.preparar()
        otra = self.shp("lagos")
        self.rios.setDataSource(str(otra), "rios", "ogr")
        self.assertIn(C.FUENTE_CAMBIADA, self.cambios()[self.clave])

    def prueba_cambio_de_filtro(self):
        self.preparar()
        self.rios.setSubsetString('"id" = 1')
        self.assertIn(C.FILTRO_CAMBIADO, self.cambios()[self.clave])

    def prueba_edicion_iniciada(self):
        self.preparar()
        self.rios.startEditing()
        try:
            motivos = self.cambios()[self.clave]
        finally:
            self.rios.rollBack()
        self.assertIn(C.EDICION_INICIADA, motivos)
        self.assertIn(C.YA_NO_SELECCIONABLE, motivos)

    def prueba_archivo_modificado(self):
        self.preparar()
        dbf = self.externos / "rios.dbf"
        estado = os.stat(dbf)
        os.utime(dbf, ns=(estado.st_atime_ns, estado.st_mtime_ns + 5_000_000_000))
        self.assertEqual(self.cambios()[self.clave], (C.ARCHIVO_MODIFICADO,))

    def prueba_capa_en_memoria_con_entidades_nuevas(self):
        self.preparar()
        self.memoria.dataProvider().addFeatures([QgsFeature(self.memoria.fields())])
        clave = self.unidad(self.plan, self.memoria).clave_unidad
        self.assertIn(C.DATOS_CAMBIADOS, self.cambios()[clave])

    def prueba_nombre_ocupado_despues_de_revisar(self):
        self.preparar()
        escribir(self.gpkg, "RIOS", conservar_archivo=True)
        motivos = self.cambios()[self.clave]
        self.assertIn(C.NOMBRE_OCUPADO, motivos)

    def prueba_otro_proyecto(self):
        self.preparar()
        con = sqlite3.connect(str(self.gpkg))
        con.execute("UPDATE gg_proyecto SET id_proyecto = ?", (str(uuid.uuid4()),))
        con.commit()
        con.close()
        resultado = self.servicio_plan.revalidar(self.plan)
        self.assertFalse(resultado.vigente)
        self.assertTrue(resultado.destino_cambiado)


class PruebaPlanSoloLectura(BasePlanQgis):
    def prueba_preparar_revalidar_y_ver_no_escribe_ni_cambia_nada(self):
        (self.carpeta / "datos").mkdir(exist_ok=True)
        shp = self.shp("rios", filas=((1,), (2,)))
        capas = [
            self.ogr(shp, "rios"),
            self.ogr(shp, "rios filtrado"),
            self.agregar(escribir(self.carpeta / "datos" / "lagos.gpkg", "lagos")),
            self.agregar(escribir(self.externos / "municipios.gpkg", "municipios", crs="EPSG:4326")),
            self.agregar(capa_con([("id", QVariant.Int)], [(1,)], nombre="campo")),
            self.ogr(geojson_mezclado(self.externos / "mezcla.geojson") + "|geometrytype=Point", "mezcla"),
            self.agregar(escribir(self.gpkg, "sitios", conservar_archivo=True)),
        ]
        capas[1].setSubsetString('"id" = 1')
        editada = self.ogr(self.shp("editada"), "editada")
        editada.startEditing()
        capas.append(editada)
        # QGIS aplica cambios diferidos al agregar capas (D-38): se vacian antes de la fotografia.
        procesar_eventos()
        self.proyecto.write()
        procesar_eventos()
        manifiesto = self.carpeta / ".geoguardian" / "manifiesto.json"
        archivos = [self.gpkg, manifiesto, self.qgz, self.carpeta / "datos" / "lagos.gpkg",
                    self.externos / "municipios.gpkg", self.externos / "mezcla.geojson"]
        archivos += sorted(self.externos.glob("rios.*")) + sorted(self.externos.glob("editada.*"))

        def foto():
            return dict(
                sumas={str(a): suma(a) for a in archivos},
                fechas={str(a): os.stat(a).st_mtime_ns for a in archivos},
                listados={str(c): sorted(os.listdir(c)) for c in (self.carpeta, self.externos)},
                eventos=len(self.repo().eventos()),
                recursos=len(self.repo().todos_los_recursos()),
                capas={c.id(): (c.source(), c.subsetString(), c.crs().authid(), c.dataProvider().crs().authid(),
                                c.isEditable(), c.isModified(), c.featureCount()) for c in capas},
                sucio=self.proyecto.isDirty(),
                src=self.proyecto.crs().authid(),
                tablas=sorted(nombres_ocupados(self.gpkg)),
            )

        antes = foto()
        plan = self.construir()
        self.assertTrue(plan.seleccionadas)
        resultado = self.servicio_plan.revalidar(plan)
        self.assertTrue(resultado.vigente)
        # Ver el plan en el dialogo tampoco escribe.
        from geoguardian.interfaz.dialogo_incorporacion import DialogoRevisarCapasConPlan
        dialogo = DialogoRevisarCapasConPlan(self.servicio.construir, self.servicio_plan.construir,
                                             self.servicio_plan.revalidar)
        dialogo.revisar()
        self.assertIsNotNone(dialogo.preparar())
        dialogo.close()
        procesar_eventos()
        self.assertEqual(foto(), antes)
        editada.rollBack()


class PruebaDialogoConPlan(BaseIntegracion):
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
        return complemento

    def filas(self, dialogo):
        resultado = {}
        for fila in range(dialogo.tabla.rowCount()):
            celda = dialogo.tabla.item(fila, 0)
            resultado[celda.text()] = (celda, dialogo.tabla.item(fila, INDICE_INCORPORAR).text())
        return resultado

    def prueba_seleccion_vista_previa_y_volver(self):
        complemento = self._complemento()
        carpeta = self.inicializar()
        self.proyecto.setCrs(UTM)
        complemento.refrescar_panel()
        shp = self.externos / "rios.shp"
        guardar(capa_con([("id", QVariant.Int)], [(1,)]), shp)
        self.proyecto.addMapLayer(QgsVectorLayer(str(shp), "rios", "ogr"))
        self.proyecto.addMapLayer(QgsVectorLayer(str(shp), "rios (copia)", "ogr"))
        self.proyecto.addMapLayer(capa_con([("id", QVariant.Int)], [(1,)], nombre="campo"))
        self.proyecto.addMapLayer(escribir(self.externos / "municipios.gpkg", "municipios", crs="EPSG:4326"))
        self.proyecto.addMapLayer(escribir(carpeta / "Proyecto.gpkg", "sitios", conservar_archivo=True))
        complemento.accion_revisar.trigger()
        dialogo = complemento.dialogo_revisar
        self.assertEqual(dialogo.tabla.horizontalHeaderItem(INDICE_INCORPORAR).text(), COLUMNA_INCORPORAR)
        self.assertEqual(dialogo.boton_preparar.text(), BOTON_PREPARAR)
        filas = self.filas(dialogo)
        self.assertEqual(filas["rios"][1], "Se puede incorporar")
        self.assertEqual(filas["campo"][1], "Capa temporal: se recomienda incorporar")
        self.assertEqual(filas["municipios"][1], "SRC diferente al proyecto")
        self.assertEqual(filas["sitios"][1], "Ya está en el proyecto")
        marcadas = {n for n, (c, _t) in filas.items() if c.checkState() == Qt.Checked}
        self.assertEqual(marcadas, {"rios", "rios (copia)", "campo"})
        self.assertFalse(filas["sitios"][0].flags() & Qt.ItemIsEnabled)
        self.assertTrue(filas["municipios"][0].flags() & Qt.ItemIsUserCheckable)
        self.assertEqual(dialogo.conteo.text(), "2 elementos por incorporar (3 capas relacionadas)")
        # Seleccion enlazada: desmarcar una capa desmarca la otra de la misma unidad.
        filas["rios (copia)"][0].setCheckState(Qt.Unchecked)
        self.assertEqual(filas["rios"][0].checkState(), Qt.Unchecked)
        filas["municipios"][0].setCheckState(Qt.Checked)
        self.assertEqual(dialogo.conteo.text(),
                         "2 elementos por incorporar (2 capas relacionadas) · 1 advertencia pendiente")
        # Vista previa en la segunda pagina, sin boton para incorporar.
        dialogo.boton_preparar.click()
        self.assertEqual(dialogo.pila.currentIndex(), 1)
        self.assertIn(AVISO_PLAN, {w.text() for w in dialogo.findChildren(type(dialogo.conteo))})
        self.assertIn("Se incorporarán 2 elementos en Proyecto.gpkg.", dialogo.resumen_plan.text())
        self.assertIn("Una capa temporal quedará guardada permanentemente.", dialogo.resumen_plan.text())
        self.assertIn("Un elemento tiene un SRC diferente al proyecto.", dialogo.resumen_plan.text())
        self.assertEqual(dialogo.tabla_plan.rowCount(), 2)
        destinos = {dialogo.tabla_plan.item(f, 2).text() for f in range(2)}
        self.assertEqual(destinos, {"campo", "municipios"})
        textos_botones = {b.text() for b in dialogo.findChildren(type(dialogo.boton_preparar))}
        self.assertNotIn("Incorporar", textos_botones)
        dialogo.boton_volver_lista.click()
        self.assertEqual(dialogo.pila.currentIndex(), 0)
        # Volver a revisar conserva lo elegido y preselecciona lo nuevo (D-66).
        self.proyecto.addMapLayer(capa_con([("id", QVariant.Int)], [(1,)], nombre="nueva"))
        dialogo.boton_revisar.click()
        filas = self.filas(dialogo)
        marcadas = {n for n, (c, _t) in filas.items() if c.checkState() == Qt.Checked}
        self.assertEqual(marcadas, {"campo", "municipios", "nueva"})

    def prueba_preparar_con_cambios_pide_volver_a_revisar(self):
        complemento = self._complemento()
        self.inicializar()
        self.proyecto.setCrs(UTM)
        complemento.refrescar_panel()
        capa = capa_con([("id", QVariant.Int)], [(1,)], nombre="campo")
        self.proyecto.addMapLayer(capa)
        complemento.accion_revisar.trigger()
        dialogo = complemento.dialogo_revisar
        capa.startEditing()
        try:
            self.assertIsNone(dialogo.preparar())
        finally:
            capa.rollBack()
        self.assertEqual(dialogo.pila.currentIndex(), 0)
        self.assertTrue(dialogo.aviso_plan.text().startswith(AVISO_CAMBIOS))
        self.assertIn("campo: ", dialogo.aviso_plan.text())
        # Una unidad que ahora tiene advertencias se desmarca al volver a revisar.
        capa.addExpressionField("1", QgsField("uno", QVariant.Int))
        dialogo.boton_revisar.click()
        self.assertEqual(self.filas(dialogo)["campo"][0].checkState(), Qt.Unchecked)
        self.assertFalse(dialogo.boton_preparar.isEnabled())
