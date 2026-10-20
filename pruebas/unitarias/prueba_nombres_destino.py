"""Nombres destino en Proyecto.gpkg, v0.2.0 Hito 2 (D-62): reglas puras, sin QGIS."""

import random
import unittest

from geoguardian.dominio.nombres_destino import (
    NombrePropuesto,
    es_reservado,
    esta_ocupado,
    nombre_valido,
    resolver_nombres,
    texto_destino,
)


class PruebaNombreValido(unittest.TestCase):
    def prueba_conserva_nombres_validos(self):
        for nombre in ("Uso de suelo", "Áreas protegidas ñ", "🌊 costa", "123", "a.b", "a-b", "Río_2024"):
            self.assertEqual(nombre_valido(nombre), nombre)

    def prueba_sin_limite_artificial_de_longitud(self):
        largo = "x" * 300
        self.assertEqual(nombre_valido(largo), largo)

    def prueba_normaliza_unicode_nfc(self):
        descompuesto = "Áreas"  # A + acento combinado, como lo puede entregar macOS
        self.assertEqual(nombre_valido(descompuesto), "Áreas")
        self.assertEqual(len(nombre_valido(descompuesto)), 5)

    def prueba_recorta_espacios_extremos(self):
        self.assertEqual(nombre_valido("  ríos  "), "ríos")
        self.assertEqual(nombre_valido("ríos y lagos"), "ríos y lagos")

    def prueba_sustituye_barra_comillas_y_control(self):
        self.assertEqual(nombre_valido("a|b"), "a_b")
        self.assertEqual(nombre_valido('com"illa'), "com_illa")
        self.assertEqual(nombre_valido("a\x01b"), "a_b")
        self.assertEqual(nombre_valido("a\tb"), "a_b")

    def prueba_conserva_secuencias_de_emoji(self):
        familia = "👩‍👩‍👧 datos"  # el union de anchura cero no es un caracter de control
        self.assertEqual(nombre_valido(familia), familia)

    def prueba_vacio(self):
        for texto in ("", "   ", None):
            self.assertEqual(nombre_valido(texto), "capa")

    def prueba_prefijos_reservados(self):
        casos = {
            "gpkg_x": "capa_gpkg_x",
            "GPKGdatos": "capa_GPKGdatos",
            "sqlite_x": "capa_sqlite_x",
            "rtree_x": "capa_rtree_x",
            "gg_eventos": "capa_gg_eventos",
            "GG_Recursos": "capa_GG_Recursos",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(nombre_valido(entrada), esperado)
            self.assertFalse(es_reservado(nombre_valido(entrada)))
        for libre in ("gpk", "sqlite", "rtree", "gg", "mis_gg_datos"):
            self.assertEqual(nombre_valido(libre), libre)


class PruebaConflictos(unittest.TestCase):
    def prueba_primer_sufijo_libre(self):
        nombres = resolver_nombres([("c1", "municipios")], {"municipios", "municipios_2", "municipios_3"})
        self.assertEqual(nombres["c1"], NombrePropuesto("municipios_4", "municipios", "existe"))

    def prueba_hueco_en_los_sufijos(self):
        nombres = resolver_nombres([("c1", "rios")], {"rios", "rios_3"})
        self.assertEqual(nombres["c1"].nombre, "rios_2")

    def prueba_sin_distinguir_mayusculas(self):
        # GDAL reemplazo `municipios` al escribir `Municipios` (sonda2.py §5).
        self.assertEqual(resolver_nombres([("c1", "municipios")], {"Municipios"})["c1"].nombre, "municipios_2")
        self.assertEqual(resolver_nombres([("c1", "MUNICIPIOS")], {"municipios"})["c1"].nombre, "MUNICIPIOS_2")
        self.assertEqual(resolver_nombres([("c1", "áreas")], {"ÁREAS"})["c1"].nombre, "áreas_2")

    def prueba_tablas_gg_y_objetos_internos_cuentan_como_ocupados(self):
        ocupados = {"gg_proyecto", "gg_recursos", "gg_eventos", "rtree_rios_geom", "gpkg_contents", "rios"}
        nombres = resolver_nombres([("a", "gg_eventos"), ("b", "rios"), ("c", "Rios")], ocupados)
        self.assertEqual(nombres["a"].nombre, "capa_gg_eventos")
        self.assertEqual(nombres["b"].nombre, "rios_2")
        self.assertEqual(nombres["c"].nombre, "Rios_3")
        for propuesto in nombres.values():
            self.assertFalse(esta_ocupado(propuesto.nombre, ocupados))

    def prueba_nombres_del_mismo_plan_cuentan_como_ocupados(self):
        nombres = resolver_nombres([("b", "rios"), ("a", "rios")], set())
        self.assertEqual(nombres["a"], NombrePropuesto("rios", "rios", ""))
        self.assertEqual(nombres["b"], NombrePropuesto("rios_2", "rios", "plan"))

    def prueba_reproducible_sin_importar_el_orden(self):
        bases = [("k{}".format(i), random.choice(["rios", "Rios", "lagos", "gg_x"])) for i in range(30)]
        esperado = resolver_nombres(bases, {"rios"})
        for _ in range(5):
            random.shuffle(bases)
            self.assertEqual(resolver_nombres(bases, {"rios"}), esperado)

    def prueba_texto_destino(self):
        self.assertEqual(texto_destino(NombrePropuesto("municipios_4", "municipios", "existe")),
                         "municipios_4 (municipios ya existe)")
        self.assertEqual(texto_destino(NombrePropuesto("rios_2", "rios", "plan")),
                         "rios_2 (rios ya se usa en este plan)")
        self.assertEqual(texto_destino(NombrePropuesto("lagos", "lagos")), "lagos")
        self.assertEqual(texto_destino(None), "—")


if __name__ == "__main__":
    unittest.main()
