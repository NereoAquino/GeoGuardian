import unittest

from geoguardian.dominio.modelos import DatosProyecto
from geoguardian.dominio.seguridad import ocultar_contrasenas
from geoguardian.dominio.validacion import (
    sugerir_nombre_carpeta,
    validar_datos_proyecto,
    validar_nombre_carpeta,
)


def datos(**cambios):
    base = dict(
        nombre_estudiante="Ana Pérez", correo="ana@cetmar02.edu.mx", titulo="Manglares",
        descripcion="", grupo="5A", asignatura="Módulo II",
    )
    base.update(cambios)
    return DatosProyecto(**base)


class PruebaValidacion(unittest.TestCase):
    def prueba_datos_completos_sin_errores(self):
        self.assertEqual(validar_datos_proyecto(datos()), [])

    def prueba_descripcion_es_opcional(self):
        self.assertEqual(validar_datos_proyecto(datos(descripcion="   ")), [])

    def prueba_obligatorios_vacios(self):
        errores = validar_datos_proyecto(datos(nombre_estudiante=" ", grupo="", asignatura=""))
        self.assertEqual(len(errores), 3)

    def prueba_correos(self):
        for correo in ("ana", "ana@", "ana@dominio", "a b@x.mx", "@x.mx"):
            with self.subTest(correo=correo):
                self.assertTrue(validar_datos_proyecto(datos(correo=correo)))
        self.assertEqual(validar_datos_proyecto(datos(correo="a.b+c@x.edu.mx")), [])

    def prueba_nombres_de_carpeta(self):
        self.assertEqual(validar_nombre_carpeta("Manglares_2026"), [])
        for invalido in ("", "a/b", "a:b", "CON", "nul.txt", "COM3", " a", "a.", "x" * 101):
            with self.subTest(nombre=invalido):
                self.assertTrue(validar_nombre_carpeta(invalido))

    def prueba_sugerir_nombre_quita_acentos_y_signos(self):
        self.assertEqual(sugerir_nombre_carpeta("Laguna de Términos: año 2026"), "Laguna_de_Terminos_ano_2026")
        self.assertEqual(validar_nombre_carpeta(sugerir_nombre_carpeta("¿Qué? <mapa> *final*")), [])


class PruebaSeguridad(unittest.TestCase):
    def prueba_oculta_contrasenas(self):
        casos = {
            "dbname='g' user='u' password='s3cr3t' host=x": "s3cr3t",
            'password="otra clave"': "otra clave",
            "url=https://srv/wms?user=u&password=abc&layers=1": "abc",
            "https://usuario:clave@servidor/wms": "clave",
        }
        for texto, secreto in casos.items():
            with self.subTest(texto=texto):
                self.assertNotIn(secreto, ocultar_contrasenas(texto))

    def prueba_no_altera_rutas_normales(self):
        ruta = "C:/Users/ana/datos/manglares.shp|layername=manglares"
        self.assertEqual(ocultar_contrasenas(ruta), ruta)
