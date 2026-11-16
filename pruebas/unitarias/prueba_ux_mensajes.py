"""Regresión UX-01/UX-02: mensajes del Hito 2 y límites de la propuesta, sin QGIS."""

import ast
from pathlib import Path
import unittest

from geoguardian.dominio.plan_incorporacion import (
    AVISO_PLAN,
    TEXTO_INCORPORABLE,
    TEXTO_ORIGINALES,
    TEXTO_BREVE,
    TEXTO_MOTIVO,
    MotivoAtencion,
)

RAIZ = Path(__file__).resolve().parents[2]


class PruebaComunicacionHito2(unittest.TestCase):
    def prueba_plan_deja_claro_que_no_es_ejecucion(self):
        self.assertIn("solo un plan", AVISO_PLAN)
        self.assertIn("no se ha copiado ni modificado", AVISO_PLAN)
        self.assertIn("conservaría", TEXTO_ORIGINALES)

    def prueba_estado_elegible_es_comprensible(self):
        self.assertEqual(TEXTO_INCORPORABLE, "Se puede organizar")
        self.assertIn("Se puede organizar", TEXTO_BREVE[MotivoAtencion.CAMPOS_CALCULADOS])

    def prueba_src_solo_en_qgis_menciona_fuente_y_bloqueo(self):
        corto = TEXTO_BREVE[MotivoAtencion.SRC_DEFINIDO_EN_QGIS]
        detalle = TEXTO_MOTIVO[MotivoAtencion.SRC_DEFINIDO_EN_QGIS]
        self.assertIn("archivo", corto)
        self.assertIn("original", detalle)
        self.assertIn("QGIS", detalle)
        self.assertIn("bloqueada", detalle)
        self.assertIn("Volver a revisar", detalle)

    def prueba_src_distinto_de_fuente_es_bloqueante(self):
        detalle = TEXTO_MOTIVO[MotivoAtencion.SRC_ASIGNADO_DISTINTO]
        self.assertIn("asignado en QGIS", detalle)
        self.assertIn("declarado por el archivo", detalle)
        self.assertIn("bloqueada", detalle)

    def prueba_src_distinto_del_proyecto_se_conserva(self):
        detalle = TEXTO_MOTIVO[MotivoAtencion.SRC_DIFERENTE]
        self.assertIn("diferente al del proyecto", detalle)
        self.assertIn("conservaría el SRC de la fuente", detalle)

    def prueba_interfaz_ux01_ux02_sin_modificar_dialogo_del_hito1(self):
        ruta = RAIZ / "geoguardian" / "interfaz" / "dialogo_incorporacion.py"
        fuente = ruta.read_text(encoding="utf-8")
        ast.parse(fuente, filename=str(ruta))
        self.assertIn('BOTON_PREPARAR = "Ver plan de organización"', fuente)
        self.assertIn('COLUMNA_INCORPORAR = "Organizar"', fuente)
        self.assertIn("¿Por qué aparece esta advertencia?", fuente)
        self.assertIn("SRC declarado por el archivo", fuente)
        self.assertIn("self.intro_organizacion", fuente)
        # El diseño se adapta mediante la subclase, sin cambiar el Hito 1.
        archivo_hito1 = RAIZ / "geoguardian" / "interfaz" / "dialogo_revisar_capas.py"
        original = archivo_hito1.read_text(encoding="utf-8")
        self.assertIn('COLUMNAS = ("Capa", "Dónde está", "Estado", "SRC", "Ubicación")', original)


if __name__ == "__main__":
    unittest.main()
