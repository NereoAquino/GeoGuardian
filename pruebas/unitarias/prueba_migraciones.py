import os
import sqlite3
import tempfile
import unittest

from geoguardian.dominio.modelos import EstadoRecurso as E
from geoguardian.manifiesto.manifiesto import construir_manifiesto, escribir_manifiesto, leer_manifiesto
from geoguardian.persistencia.migraciones import COLUMNAS_ESQUEMA_2, COLUMNAS_ESQUEMA_3, migrar, version_actual
from geoguardian.persistencia.repositorio import RepositorioGeoGuardian

from .apoyo import geopaquete_rc1, geopaquete_rc2

RUTA_QGZ = "C:/Users/ana/Manglares/Proyecto.qgz"


def columnas(ruta):
    con = sqlite3.connect(ruta)
    nombres = [f[1] for f in con.execute("PRAGMA table_info(gg_proyecto)")]
    con.close()
    return nombres


class PruebaMigraciones(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self._tmp.name, "Proyecto.gpkg")
        geopaquete_rc1(self.ruta)

    def tearDown(self):
        self._tmp.cleanup()

    def prueba_migra_rc1_a_esquema_3(self):
        self.assertEqual(version_actual(self.ruta), 1)
        self.assertEqual(migrar(self.ruta, RUTA_QGZ), 1)
        self.assertEqual(version_actual(self.ruta), 3)
        self.assertTrue({n for n, _t in COLUMNAS_ESQUEMA_3} <= set(columnas(self.ruta)))
        fila = RepositorioGeoGuardian(self.ruta).obtener_proyecto()
        self.assertEqual(fila["ruta_proyecto_administrado"], RUTA_QGZ)
        self.assertIsNone(fila["ruta_proyecto_origen"])
        self.assertIsNone(fila["nombre_academico"])
        self.assertEqual(fila["titulo"], "Manglares")  # datos rc1 intactos

    def prueba_idempotente(self):
        migrar(self.ruta, RUTA_QGZ)
        self.assertIsNone(migrar(self.ruta, "otra/ruta.qgz"))
        nombres = columnas(self.ruta)
        self.assertEqual(len(nombres), len(set(nombres)))
        self.assertEqual(RepositorioGeoGuardian(self.ruta).obtener_proyecto()["ruta_proyecto_administrado"], RUTA_QGZ)

    def prueba_fallo_a_mitad_revierte_todo(self):
        antes = columnas(self.ruta)

        def fallar(nombre):
            if nombre == COLUMNAS_ESQUEMA_2[2][0]:
                raise RuntimeError("fallo simulado")

        with self.assertRaises(RuntimeError):
            migrar(self.ruta, RUTA_QGZ, al_agregar_columna=fallar)
        self.assertEqual(columnas(self.ruta), antes)
        self.assertEqual(version_actual(self.ruta), 1)
        self.assertEqual(migrar(self.ruta, RUTA_QGZ), 1)  # se puede reintentar

    def prueba_completa_columnas_faltantes_de_una_migracion_parcial(self):
        con = sqlite3.connect(self.ruta)
        con.execute("ALTER TABLE gg_proyecto ADD COLUMN nombre_academico TEXT")
        con.commit()
        con.close()
        self.assertEqual(migrar(self.ruta, RUTA_QGZ), 1)
        self.assertTrue({n for n, _t in COLUMNAS_ESQUEMA_2} <= set(columnas(self.ruta)))

    def prueba_esquema_mas_nuevo_no_se_toca(self):
        con = sqlite3.connect(self.ruta)
        con.execute("UPDATE gg_proyecto SET version_esquema = 9")
        con.commit()
        con.close()
        self.assertIsNone(migrar(self.ruta, RUTA_QGZ))
        self.assertNotIn("nombre_academico", columnas(self.ruta))

    def prueba_lectura_estilo_rc1_tras_migrar(self):
        migrar(self.ruta, RUTA_QGZ)
        con = sqlite3.connect(self.ruta)
        con.row_factory = sqlite3.Row
        fila = con.execute("SELECT * FROM gg_proyecto").fetchone()
        con.close()
        for campo in ("id_proyecto", "titulo", "nombre_estudiante", "correo", "grupo", "asignatura",
                      "fecha_creacion", "fecha_actualizacion"):
            self.assertIsNotNone(fila[campo])

    def prueba_migra_esquema_2_a_3_sin_tocar_datos(self):
        ruta = os.path.join(self._tmp.name, "rc2.gpkg")
        geopaquete_rc2(ruta)
        self.assertEqual(version_actual(ruta), 2)
        self.assertEqual(migrar(ruta, RUTA_QGZ), 2)
        self.assertEqual(version_actual(ruta), 3)
        fila = RepositorioGeoGuardian(ruta).obtener_proyecto()
        self.assertEqual(fila["nombre_academico"], "Manglares - Ana Perez")
        self.assertEqual(fila["ruta_proyecto_administrado"], "E:/rc2/Manglares.qgz")  # no se sobrescribe
        self.assertIsNone(fila["etiqueta_volumen"])
        self.assertIsNone(migrar(ruta, RUTA_QGZ))  # idempotente

    def prueba_fallo_en_columna_del_esquema_3_revierte_todo(self):
        ruta = os.path.join(self._tmp.name, "rc2.gpkg")
        geopaquete_rc2(ruta)
        antes = columnas(ruta)

        def fallar(nombre):
            if nombre == "ruta_en_volumen":
                raise RuntimeError("fallo simulado")

        with self.assertRaises(RuntimeError):
            migrar(ruta, RUTA_QGZ, al_agregar_columna=fallar)
        self.assertEqual(columnas(ruta), antes)
        self.assertEqual(version_actual(ruta), 2)

    def prueba_manifiesto_esquema_3_y_lector_rc1(self):
        migrar(self.ruta, RUTA_QGZ)
        fila = RepositorioGeoGuardian(self.ruta).obtener_proyecto()
        datos = construir_manifiesto(fila, {E.ACTIVO: 1}, "verde", "3.28.15", "Proyecto.qgz")
        ruta = os.path.join(self._tmp.name, "manifiesto.json")
        escribir_manifiesto(ruta, datos)
        leido = leer_manifiesto(ruta)
        self.assertEqual(leido["version_esquema"], 3)
        self.assertEqual(leido["rutas"]["administrado"], RUTA_QGZ)
        self.assertEqual(set(leido["ubicacion"]), {"etiqueta_volumen", "sistema_archivos", "ruta_en_volumen"})
        # Un lector rc1 solo exige formato e id_proyecto, y los conserva.
        self.assertEqual((leido["formato"], leido["id_proyecto"]), ("geoguardian-manifiesto", "uuid-rc1"))
