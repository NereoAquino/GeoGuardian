import unittest

from geoguardian.dominio.modelos import EstadoRecurso as E, NivelSemaforo as N, ResumenProyecto
from geoguardian.dominio.semaforo import (
    FRASE_VERSION_DISPONIBLE,
    FRASES_NIVEL,
    MOTIVO_NO_ADMINISTRADO,
    MOTIVO_VERSION_DISPONIBLE,
    evaluar_semaforo,
    recursos_en_proyecto,
    texto_indicador,
)


def resumen(**kwargs):
    conteo = kwargs.pop("conteo", {})
    return ResumenProyecto(administrado=kwargs.pop("administrado", True), conteo=conteo, **kwargs)


class PruebaSemaforo(unittest.TestCase):
    def prueba_no_administrado_es_gris(self):
        self.assertEqual(evaluar_semaforo(resumen(administrado=False))[0], N.GRIS)

    def prueba_todo_en_orden_es_verde(self):
        nivel, motivos = evaluar_semaforo(resumen(conteo={E.ACTIVO: 3, E.HISTORICO: 5}))
        self.assertEqual(nivel, N.VERDE)
        self.assertEqual(len(motivos), 1)

    def prueba_faltante_es_rojo(self):
        nivel, motivos = evaluar_semaforo(resumen(conteo={E.FALTANTE: 2}))
        self.assertEqual(nivel, N.ROJO)
        self.assertIn("2 recursos apuntan", motivos[0])

    def prueba_inconsistencia_es_rojo(self):
        nivel, motivos = evaluar_semaforo(resumen(problemas_consistencia=["No se encuentra el manifiesto"]))
        self.assertEqual(nivel, N.ROJO)
        self.assertEqual(motivos, ["No se encuentra el manifiesto"])

    def prueba_cada_condicion_amarilla(self):
        casos = [
            dict(cambios_sin_guardar=True),
            dict(capas_con_ediciones=1),
            dict(conteo={E.TEMPORAL: 1}),
            dict(conteo={E.EXTERNO: 1}),
        ]
        for caso in casos:
            with self.subTest(caso=caso):
                nivel, motivos = evaluar_semaforo(resumen(**caso))
                self.assertEqual(nivel, N.AMARILLO)
                self.assertEqual(len(motivos), 1)

    def prueba_rojo_gana_y_motivos_rojos_van_primero(self):
        nivel, motivos = evaluar_semaforo(
            resumen(conteo={E.FALTANTE: 1, E.EXTERNO: 2}, cambios_sin_guardar=True)
        )
        self.assertEqual(nivel, N.ROJO)
        self.assertEqual(len(motivos), 3)
        self.assertIn("1 recurso apunta", motivos[0])

    def prueba_historicos_no_afectan(self):
        self.assertEqual(evaluar_semaforo(resumen(conteo={E.HISTORICO: 10}))[0], N.VERDE)


class PruebaIndicadorYPanel(unittest.TestCase):
    """F21 y F22 (D-31, D-32)."""

    def prueba_frases_de_los_cuatro_niveles(self):
        esperadas = {
            N.GRIS: "Proyecto no administrado",
            N.VERDE: "Proyecto en buen estado",
            N.AMARILLO: "Proyecto requiere atención",
            N.ROJO: "Proyecto con problemas",
        }
        self.assertEqual(FRASES_NIVEL, esperadas)

    def prueba_el_indicador_cambia_con_el_estado(self):
        textos = set()
        for caso in (
            resumen(administrado=False),
            resumen(conteo={E.ACTIVO: 1}),
            resumen(conteo={E.EXTERNO: 1}),
            resumen(conteo={E.FALTANTE: 1}),
        ):
            nivel, motivos = evaluar_semaforo(caso)
            textos.add(texto_indicador(nivel, motivos)[0])
        self.assertEqual(textos, set(FRASES_NIVEL.values()))

    def prueba_original_con_version_administrada(self):
        nivel, motivos = evaluar_semaforo(resumen(administrado=False, version_administrada="G:/p/p.qgz"))
        self.assertEqual(nivel, N.GRIS)
        self.assertEqual(motivos, [MOTIVO_VERSION_DISPONIBLE])
        self.assertNotIn(MOTIVO_NO_ADMINISTRADO, motivos)
        frase, tooltip = texto_indicador(nivel, motivos, FRASE_VERSION_DISPONIBLE)
        self.assertEqual(frase, "Versión administrada disponible")
        self.assertNotIn("no administrado", tooltip)

    def prueba_tooltip_lleva_solo_el_motivo_principal(self):
        nivel, motivos = evaluar_semaforo(
            resumen(conteo={E.EXTERNO: 10}, cambios_sin_guardar=True, capas_con_ediciones=0)
        )
        frase, tooltip = texto_indicador(nivel, motivos)
        self.assertEqual(frase, "Proyecto requiere atención")
        self.assertEqual(
            tooltip,
            "GeoGuardian — Proyecto requiere atención: "
            "10 recursos se encuentran fuera de la carpeta administrada.",
        )
        self.assertNotIn("sin guardar", tooltip)

    def prueba_orden_de_motivos_amarillos(self):
        _nivel, motivos = evaluar_semaforo(
            resumen(conteo={E.TEMPORAL: 1, E.EXTERNO: 2}, cambios_sin_guardar=True, capas_con_ediciones=1)
        )
        self.assertIn("temporal", motivos[0])
        self.assertIn("ediciones", motivos[1])
        self.assertIn("fuera de la carpeta administrada", motivos[2])
        self.assertEqual(motivos[3], "Hay cambios sin guardar")

    def prueba_recursos_en_proyecto_excluye_historicos(self):
        caso = resumen(conteo={E.ACTIVO: 3, E.EXTERNO: 2, E.TEMPORAL: 1, E.FALTANTE: 1, E.HISTORICO: 9})
        self.assertEqual(recursos_en_proyecto(caso), 7)
