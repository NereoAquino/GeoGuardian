"""Ajustes del Hito 2 de v0.2.0: D-69 (SRC definido solo en QGIS). Reglas puras, sin QGIS."""

import unittest

from geoguardian.dominio.plan_incorporacion import (
    MOTIVOS_NO_INCORPORABLE,
    TEXTO_BREVE,
    TEXTO_MOTIVO,
    Elegibilidad as El,
    MotivoAtencion as M,
    Seleccion as Se,
    ayuda_estado,
    con_seleccion,
    texto_estado,
    texto_resumen_plan,
)
from pruebas.unitarias.prueba_plan_incorporacion import BasePlan, GEO, SIN, UTM


class PruebaD69(BasePlan):
    def unidad_src(self, src, src_fuente, src_fuente_valido, **cambios):
        entrada = self.externo("c", src=src, src_fuente=src_fuente,
                               src_igual_proyecto=src.valido and src.identificador == UTM.identificador,
                               src_igual_fuente=src_fuente.valido and src.identificador == src_fuente.identificador,
                               **cambios)
        datos = {"c": self.datos("c", nombre_origen="parcelas", src_fuente_valido=src_fuente_valido)}
        plan = self.plan([entrada], datos)
        return plan, plan.unidad_de_capa("c")

    def prueba_fuente_sin_src_y_capa_sin_src(self):
        _plan, unidad = self.unidad_src(SIN, SIN, False)
        self.assertEqual(unidad.motivos, (M.SIN_SRC,))
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.NO_INCORPORABLE, Se.NO_SELECCIONABLE))

    def prueba_fuente_sin_src_y_src_asignado_en_qgis(self):
        _plan, unidad = self.unidad_src(UTM, SIN, False)
        self.assertEqual(unidad.motivos, (M.SRC_DEFINIDO_EN_QGIS,))
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.NO_INCORPORABLE, Se.NO_SELECCIONABLE))
        self.assertFalse(unidad.seleccionable)
        self.assertIsNone(unidad.destino)
        self.assertIn(M.SRC_DEFINIDO_EN_QGIS, MOTIVOS_NO_INCORPORABLE)

    def prueba_d69_prevalece_sobre_src_diferente(self):
        _plan, unidad = self.unidad_src(GEO, SIN, False)
        self.assertEqual(unidad.motivos, (M.SRC_DEFINIDO_EN_QGIS,))

    def prueba_fuente_y_capa_con_el_mismo_src(self):
        _plan, unidad = self.unidad_src(UTM, UTM, True)
        self.assertEqual(unidad.motivos, ())
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.INCORPORABLE, Se.PRESELECCIONADA))

    def prueba_fuente_con_src_y_capa_con_otro_sigue_d59(self):
        _plan, unidad = self.unidad_src(GEO, UTM, True)
        self.assertEqual(unidad.motivos, (M.SRC_ASIGNADO_DISTINTO,))
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)

    def prueba_no_se_puede_seleccionar_ni_entra_en_el_plan(self):
        plan, unidad = self.unidad_src(UTM, SIN, False)
        self.assertNotIn(unidad.clave_unidad, plan.preseleccion())
        forzado = con_seleccion(plan, {unidad.clave_unidad})
        self.assertEqual(forzado.seleccionadas, frozenset())
        self.assertEqual(forzado.unidades_seleccionadas(), ())
        self.assertNotIn("SRC definido", texto_resumen_plan(forzado))

    def prueba_textos(self):
        _plan, unidad = self.unidad_src(UTM, SIN, False)
        self.assertEqual(texto_estado(unidad), "Necesita atención: SRC definido solo en QGIS")
        self.assertEqual(
            ayuda_estado(unidad),
            "El archivo original no declara un sistema de coordenadas. Define correctamente su SRC y "
            "vuelve a revisar antes de incorporarlo.",
        )
        for texto in (TEXTO_BREVE[M.SRC_DEFINIDO_EN_QGIS], TEXTO_MOTIVO[M.SRC_DEFINIDO_EN_QGIS]):
            self.assertNotIn("incorrect", texto.lower())
            self.assertNotIn("reproyect", texto.lower())

    def prueba_tabla_sin_geometria_no_se_afecta(self):
        entrada = self.externo("c", "t.dbf", es_espacial=False, src=SIN, src_fuente=SIN, src_igual_proyecto=False)
        unidad = self.unidad([entrada], datos={"c": self.datos("c", src_fuente_valido=False)})
        self.assertEqual(unidad.seleccion, Se.PRESELECCIONADA)


if __name__ == "__main__":
    unittest.main()
