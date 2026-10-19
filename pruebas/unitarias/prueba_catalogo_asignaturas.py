import unittest

from geoguardian.dominio.catalogo_asignaturas import ASIGNATURAS, opciones_asignatura
from geoguardian.dominio.modelos import DatosProyecto
from geoguardian.dominio.validacion import validar_datos_proyecto


class PruebaCatalogoAsignaturas(unittest.TestCase):
    def prueba_cinco_modulos_profesionales_en_orden(self):
        self.assertEqual([a.split(" — ")[0] for a in ASIGNATURAS], ["M1", "M2", "M3", "M4", "M5"])
        self.assertEqual(len(set(ASIGNATURAS)), 5)

    def prueba_opciones_es_una_copia(self):
        opciones = opciones_asignatura()
        opciones.append("Otra")
        self.assertEqual(len(ASIGNATURAS), 5)

    def prueba_valor_manual_vale_igual_que_uno_del_catalogo(self):
        for asignatura in (ASIGNATURAS[0], "Topografía aplicada"):
            datos = DatosProyecto("Ana Pérez López", "ana@cetmar02.edu.mx", "Manglares", "", "5A", asignatura)
            self.assertEqual(validar_datos_proyecto(datos), [])
