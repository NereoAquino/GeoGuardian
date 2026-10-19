import unittest

from geoguardian.dominio.nombre_academico import (
    analizar_nombre,
    contiene_estudiante,
    nombre_de_archivo,
    practica_de,
    validar_nombre_academico,
)

ESTUDIANTE = "Ana Pérez López"


class PruebaAnalisis(unittest.TestCase):
    def prueba_tabla_de_la_especificacion(self):
        casos = [
            # (nombre actual, contiene, estructura, propuesta)
            ("manglares", False, False, "manglares - Ana Pérez López"),
            ("Practica 3 Manglares - ana perez", True, True, None),
            ("PRACTICA_3_MANGLARES_ANA_PEREZ_LOPEZ", True, False, "PRACTICA 3 MANGLARES - Ana Pérez López"),
            ("Ana Pérez - Manglares", True, False, "Manglares - Ana Pérez López"),
            ("Pérez - Manglares", False, False, "Manglares - Ana Pérez López"),
            ("", False, False, None),
        ]
        for nombre, contiene, estructura, propuesta in casos:
            with self.subTest(nombre=nombre):
                a = analizar_nombre(nombre, ESTUDIANTE)
                self.assertEqual(
                    (a.contiene_estudiante, a.estructura_completa, a.nombre_propuesto),
                    (contiene, estructura, propuesta),
                )

    def prueba_tolera_mayusculas_acentos_y_espacios(self):
        for nombre in ("Manglares - ANA PEREZ", "Manglares  -   ána   pérez", "Manglares_-_ana_perez_lopez"):
            with self.subTest(nombre=nombre):
                self.assertTrue(analizar_nombre(nombre, ESTUDIANTE).estructura_completa)

    def prueba_guion_dentro_de_palabra_no_es_separador(self):
        a = analizar_nombre("Uso-de-suelo Ana Perez", ESTUDIANTE)
        self.assertFalse(a.estructura_completa)
        self.assertEqual(a.nombre_propuesto, "Uso-de-suelo - Ana Pérez López")

    def prueba_solo_el_estudiante_no_tiene_practica(self):
        a = analizar_nombre("Ana Pérez López", ESTUDIANTE)
        self.assertTrue(a.contiene_estudiante)
        self.assertIsNone(a.nombre_propuesto)

    def prueba_particulas_no_cuentan(self):
        estudiante = "María de la Luz"
        self.assertFalse(contiene_estudiante("Manglares de la", estudiante))
        self.assertTrue(contiene_estudiante("Manglares maria luz", estudiante))

    def prueba_estudiante_de_una_palabra(self):
        self.assertTrue(analizar_nombre("Mapa - Xochitl", "Xóchitl").estructura_completa)

    def prueba_practica_de(self):
        self.assertEqual(practica_de("Practica 3 - Ana Pérez López", ESTUDIANTE), "Practica 3")


class PruebaNombreDeArchivo(unittest.TestCase):
    def prueba_quita_acentos_enie_e_invalidos(self):
        self.assertEqual(
            nombre_de_archivo("Año: Términos/Campeche? - Ana Pérez"),
            "Ano Terminos Campeche - Ana Perez",
        )

    def prueba_respeta_mayusculas_y_separador(self):
        self.assertEqual(nombre_de_archivo("MANGLARES - Ana"), "MANGLARES - Ana")

    def prueba_longitud_y_final(self):
        nombre = nombre_de_archivo("x" * 79 + " . y")
        self.assertLessEqual(len(nombre), 80)
        self.assertFalse(nombre.endswith((".", " ")))

    def prueba_nombre_reservado(self):
        self.assertEqual(nombre_de_archivo("CON"), "CON_")


class PruebaValidacion(unittest.TestCase):
    def prueba_valido(self):
        self.assertEqual(validar_nombre_academico("Practica 3 - Ana Pérez López", ESTUDIANTE), [])

    def prueba_invalidos(self):
        for nombre in ("", "Practica 3", "Ana Pérez López", "Practica 3 - Juan"):
            with self.subTest(nombre=nombre):
                self.assertTrue(validar_nombre_academico(nombre, ESTUDIANTE))


class PruebaNombreFinalSugerido(unittest.TestCase):
    """F18 (D-28): nombre final del proyecto administrado."""

    ALUMNO = "NEREO ADENNY AQUINO SANTANA"

    def prueba_propone_practica_mas_estudiante(self):
        a = analizar_nombre("MAPA DE INDICES ESPECTRALES", self.ALUMNO)
        self.assertEqual(a.practica_detectada, "MAPA DE INDICES ESPECTRALES")
        self.assertEqual(a.nombre_propuesto, "MAPA DE INDICES ESPECTRALES - NEREO ADENNY AQUINO SANTANA")

    def prueba_valida_sin_distinguir_mayusculas_acentos_ni_espacios(self):
        for nombre in (
            "MAPA DE INDICES ESPECTRALES - NEREO ADENNY AQUINO SANTANA",
            "mapa de índices espectrales - nereo  adenny aquino santana",
            "  Mapa de Índices Espectrales  -  Nereo Aquino ",
        ):
            with self.subTest(nombre=nombre):
                self.assertEqual(validar_nombre_academico(nombre, self.ALUMNO), [])

    def prueba_archivo_del_nombre_final(self):
        self.assertEqual(
            nombre_de_archivo("Mapa de Índices Espectrales - Nereo Aquino"),
            "Mapa de Indices Espectrales - Nereo Aquino",
        )
