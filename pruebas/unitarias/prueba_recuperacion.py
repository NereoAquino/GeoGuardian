"""Unidades externas con letra cambiante (D-33, D-34)."""

import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from geoguardian.administracion.identidad_proyecto import leer_ids
from geoguardian.administracion.registro_adopciones import Adopcion, RegistroAdopciones
from geoguardian.constantes import CLAVE_ADOPCIONES
from geoguardian.dominio.modelos import EstadoRecurso as E, NivelSemaforo as N, ResumenProyecto
from geoguardian.dominio.recuperacion import (
    IdentidadUbicacion,
    Resultado,
    id_valido,
    identidad,
    raiz_unidad,
    reconstruir,
    recuperar,
    ruta_en_volumen,
    rutas_a_probar,
    unidad_ausente,
)
from geoguardian.dominio.semaforo import evaluar_semaforo
from geoguardian.dominio.ubicacion import InfoVolumen

ID = "id-esperado"
REGISTRADA = IdentidadUbicacion(
    ruta="E:/Practicas/Manglares - Ana/Manglares - Ana.qgz",
    etiqueta_volumen="USB_ANA",
    sistema_archivos="FAT32",
    ruta_en_volumen="Practicas/Manglares - Ana/Manglares - Ana.qgz",
)
QGZ_EN_F = "F:/Practicas/Manglares - Ana/Manglares - Ana.qgz"
QGZ_EN_G = "G:/Practicas/Manglares - Ana/Manglares - Ana.qgz"


def volumen(raiz, etiqueta):
    return InfoVolumen(raiz=raiz, sistema_archivos="FAT32", bytes_libres=1, etiqueta=etiqueta)


def simular(archivos):
    """`archivos`: {ruta: id_proyecto}. Devuelve las funciones existe y leer_ids."""
    def existe(ruta):
        return ruta in archivos

    def leer(ruta):
        return {"manifiesto": archivos[ruta], "geopaquete": archivos[ruta]}

    return existe, leer


class PruebaRutasDeVolumen(unittest.TestCase):
    def prueba_ruta_en_volumen_windows(self):
        self.assertEqual(ruta_en_volumen("E:\\Practicas\\X\\X.qgz", "E:/"), "Practicas/X/X.qgz")
        self.assertEqual(ruta_en_volumen("e:/Practicas/X.qgz", "E:/"), "Practicas/X.qgz")
        self.assertEqual(ruta_en_volumen("D:/Practicas/X.qgz", "E:/"), "")

    def prueba_ruta_en_volumen_posix(self):
        self.assertEqual(ruta_en_volumen("/media/usb/a/b.qgz", "/media/usb"), "a/b.qgz")
        self.assertEqual(ruta_en_volumen("/home/a.qgz", "/"), "home/a.qgz")

    def prueba_reconstruir_en_otra_letra(self):
        self.assertEqual(reconstruir("F:/", REGISTRADA.ruta_en_volumen), QGZ_EN_F)

    def prueba_identidad_no_incluye_la_letra(self):
        ident = identidad("E:/Practicas/X.qgz", volumen("E:/", "USB_ANA"))
        self.assertEqual((ident.etiqueta_volumen, ident.ruta_en_volumen), ("USB_ANA", "Practicas/X.qgz"))
        self.assertNotIn("E:", ident.ruta_en_volumen)

    def prueba_raiz_y_unidad_ausente(self):
        self.assertEqual(raiz_unidad("E:\\datos\\a.shp"), "E:/")
        self.assertEqual(raiz_unidad("\\\\srv\\aula\\a.shp"), "//srv/aula/")
        self.assertIsNone(raiz_unidad("/home/ana/a.shp"))
        self.assertTrue(unidad_ausente("E:/datos/a.shp", lambda r: False))
        self.assertFalse(unidad_ausente("E:/datos/a.shp", lambda r: r == "E:/"))
        self.assertFalse(unidad_ausente("/home/a.shp", lambda r: False))


class PruebaRecuperar(unittest.TestCase):
    def prueba_ruta_registrada_existe_y_coincide(self):
        existe, leer = simular({REGISTRADA.ruta: ID})
        r = recuperar(REGISTRADA, ID, [], existe, leer)
        self.assertEqual((r.resultado, r.ruta), (Resultado.ENCONTRADA, REGISTRADA.ruta))

    def prueba_la_usb_cambio_de_letra(self):
        existe, leer = simular({QGZ_EN_F: ID})
        volumenes = [volumen("C:/", "Windows"), volumen("F:/", "usb_ana")]
        r = recuperar(REGISTRADA, ID, volumenes, existe, leer)
        self.assertEqual((r.resultado, r.ruta), (Resultado.ENCONTRADA, QGZ_EN_F))

    def prueba_misma_etiqueta_otro_proyecto_no_se_reasocia(self):
        existe, leer = simular({QGZ_EN_F: "otro-id"})
        r = recuperar(REGISTRADA, ID, [volumen("F:/", "USB_ANA")], existe, leer)
        self.assertEqual((r.resultado, r.ruta), (Resultado.ID_DISTINTO, None))

    def prueba_ruta_registrada_con_otro_proyecto_no_se_acepta(self):
        existe, leer = simular({REGISTRADA.ruta: "otro-id"})
        r = recuperar(REGISTRADA, ID, [volumen("E:/", "USB_ANA")], existe, leer)
        self.assertEqual(r.resultado, Resultado.ID_DISTINTO)

    def prueba_varias_candidatas_validas_no_se_elige(self):
        existe, leer = simular({QGZ_EN_F: ID, QGZ_EN_G: ID})
        r = recuperar(REGISTRADA, ID, [volumen("F:/", "USB_ANA"), volumen("G:/", "USB_ANA")], existe, leer)
        self.assertEqual(r.resultado, Resultado.VARIAS)
        self.assertEqual(r.candidatas, [QGZ_EN_F, QGZ_EN_G])
        self.assertIsNone(r.ruta)

    def prueba_dos_unidades_con_la_etiqueta_pero_una_sola_valida(self):
        existe, leer = simular({QGZ_EN_F: "otro-id", QGZ_EN_G: ID})
        r = recuperar(REGISTRADA, ID, [volumen("F:/", "USB_ANA"), volumen("G:/", "USB_ANA")], existe, leer)
        self.assertEqual((r.resultado, r.ruta), (Resultado.ENCONTRADA, QGZ_EN_G))

    def prueba_sin_etiqueta_o_sin_unidad(self):
        existe, leer = simular({QGZ_EN_F: ID})
        sin_etiqueta = IdentidadUbicacion(ruta=REGISTRADA.ruta, ruta_en_volumen=REGISTRADA.ruta_en_volumen)
        self.assertEqual(
            recuperar(sin_etiqueta, ID, [volumen("F:/", "")], existe, leer).resultado, Resultado.NO_ENCONTRADA
        )
        self.assertEqual(
            recuperar(REGISTRADA, ID, [volumen("F:/", "OTRA")], existe, leer).resultado, Resultado.NO_ENCONTRADA
        )

    def prueba_id_valido_exige_todas_las_fuentes(self):
        self.assertTrue(id_valido({"qgz": ID, "manifiesto": ID}, ID))
        self.assertFalse(id_valido({"qgz": ID, "manifiesto": "otro"}, ID))
        self.assertFalse(id_valido({}, ID))
        self.assertFalse(id_valido({"qgz": ID}, ""))

    def prueba_rutas_a_probar_al_localizar(self):
        rutas = rutas_a_probar("H:/", REGISTRADA)
        self.assertEqual(rutas[0], "H:/Practicas/Manglares - Ana/Manglares - Ana.qgz")  # raiz de la unidad
        self.assertIn("H:/Manglares - Ana.qgz", rutas)  # carpeta del proyecto
        self.assertIn("H:/Manglares - Ana/Manglares - Ana.qgz", rutas)  # carpeta que la contiene


class PruebaLeerIds(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.carpeta = Path(self._tmp.name)
        self.qgz = self.carpeta / "P.qgz"

    def tearDown(self):
        self._tmp.cleanup()

    def _crear(self, id_qgz=None, id_manifiesto=None, id_gpkg=None):
        if id_qgz:
            qgs = '<qgis><properties><geoguardian><id_proyecto type="QString">{}</id_proyecto></geoguardian></properties></qgis>'
            with zipfile.ZipFile(str(self.qgz), "w") as z:
                z.writestr("P.qgs", qgs.format(id_qgz))
        if id_manifiesto:
            (self.carpeta / ".geoguardian").mkdir()
            (self.carpeta / ".geoguardian" / "manifiesto.json").write_text(
                json.dumps({"formato": "geoguardian-manifiesto", "id_proyecto": id_manifiesto}), encoding="utf-8"
            )
        if id_gpkg:
            con = sqlite3.connect(str(self.carpeta / "Proyecto.gpkg"))
            con.execute("CREATE TABLE gg_proyecto (id_proyecto TEXT)")
            con.execute("INSERT INTO gg_proyecto VALUES (?)", (id_gpkg,))
            con.commit()
            con.close()

    def prueba_lee_las_tres_fuentes(self):
        self._crear(ID, ID, ID)
        self.assertEqual(leer_ids(self.qgz), {"qgz": ID, "manifiesto": ID, "geopaquete": ID})
        self.assertTrue(id_valido(leer_ids(self.qgz), ID))

    def prueba_fuentes_que_no_coinciden_se_rechazan(self):
        self._crear(ID, "otro", ID)
        self.assertFalse(id_valido(leer_ids(self.qgz), ID))

    def prueba_fuentes_ausentes_no_cuentan(self):
        self._crear(id_qgz=ID)
        self.assertEqual(leer_ids(self.qgz), {"qgz": ID})
        self.assertEqual(leer_ids(self.carpeta / "no_existe.qgz"), {})


class ConfiguracionFalsa:
    def __init__(self):
        self.valores = {}

    def value(self, clave, omision=None):
        return self.valores.get(clave, omision)

    def setValue(self, clave, valor):  # noqa: N802  (API de QgsSettings)
        self.valores[clave] = valor


class PruebaRegistroAdopciones(unittest.TestCase):
    def setUp(self):
        self.config = ConfiguracionFalsa()
        self.registro = RegistroAdopciones(self.config)
        self.origen = IdentidadUbicacion("E:/orig/Manglares.qgz", "USB_ANA", "FAT32", "orig/Manglares.qgz")

    def prueba_persiste_identidad_e_id(self):
        self.registro.agregar(self.origen, REGISTRADA, ID)
        otra_sesion = RegistroAdopciones(self.config)
        adopcion = otra_sesion.buscar(IdentidadUbicacion("E:/orig/Manglares.qgz"))
        self.assertEqual(adopcion, Adopcion(self.origen, REGISTRADA, ID))

    def prueba_reconoce_el_original_aunque_cambie_de_letra(self):
        self.registro.agregar(self.origen, REGISTRADA, ID)
        en_f = IdentidadUbicacion("F:/orig/Manglares.qgz", "usb_ana", "FAT32", "orig/Manglares.qgz")
        self.assertIsNotNone(self.registro.buscar(en_f))
        otra_usb = IdentidadUbicacion("F:/orig/Manglares.qgz", "OTRA", "FAT32", "orig/Manglares.qgz")
        self.assertIsNone(self.registro.buscar(otra_usb))

    def prueba_actualizar_administrado_por_id(self):
        self.registro.agregar(self.origen, REGISTRADA, ID)
        nueva = IdentidadUbicacion(QGZ_EN_F, "USB_ANA", "FAT32", REGISTRADA.ruta_en_volumen)
        self.assertTrue(self.registro.actualizar_administrado(ID, nueva))
        self.assertEqual(self.registro.buscar(self.origen).administrado, nueva)
        self.assertFalse(self.registro.actualizar_administrado("otro", nueva))

    def prueba_lee_el_formato_anterior(self):
        self.config.setValue(CLAVE_ADOPCIONES, json.dumps({"E:/orig/Manglares.qgz": "E:/adm/M.qgz"}))
        adopcion = self.registro.buscar(IdentidadUbicacion("E:/orig/Manglares.qgz"))
        self.assertEqual((adopcion.administrado.ruta, adopcion.id_proyecto), ("E:/adm/M.qgz", ""))

    def prueba_valor_corrupto_no_falla(self):
        self.config.setValue(CLAVE_ADOPCIONES, "{no es json")
        self.assertEqual(self.registro.adopciones(), [])


class PruebaMotivoUnidadNoEncontrada(unittest.TestCase):
    def prueba_faltantes_en_unidad_desconectada(self):
        resumen = ResumenProyecto(administrado=True, conteo={E.FALTANTE: 3}, faltantes_sin_unidad=2)
        nivel, motivos = evaluar_semaforo(resumen)
        self.assertEqual(nivel, N.ROJO)  # siguen siendo faltantes (D-02)
        self.assertEqual(
            motivos[0],
            "2 recursos están en una unidad que no se encuentra (puede estar desconectada o tener otra letra)",
        )
        self.assertIn("1 recurso apunta a archivos que no existen", motivos[1])
