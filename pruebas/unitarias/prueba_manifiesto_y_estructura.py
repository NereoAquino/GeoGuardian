import json
import os
import tempfile
import unittest
from pathlib import Path

from geoguardian.administracion.estructura_carpetas import (
    CarpetaNoDisponible,
    carpeta_disponible,
    crear_estructura,
)
from geoguardian.dominio.modelos import EstadoRecurso as E, NivelSemaforo as N
from geoguardian.manifiesto.manifiesto import (
    ManifiestoInvalido,
    construir_manifiesto,
    escribir_manifiesto,
    leer_manifiesto,
)

PROYECTO = {
    "id_proyecto": "uuid-1", "titulo": "Laguna de Términos", "descripcion": None,
    "nombre_estudiante": "Ana Pérez", "correo": "ana@x.mx", "grupo": "5A",
    "asignatura": "Módulo II", "fecha_creacion": "f1", "fecha_actualizacion": "f2",
}


class PruebaManifiesto(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / ".geoguardian" / "manifiesto.json"

    def tearDown(self):
        self._tmp.cleanup()

    def prueba_ida_y_vuelta_con_acentos(self):
        datos = construir_manifiesto(PROYECTO, {E.EXTERNO: 3}, N.AMARILLO, "3.28.15")
        escribir_manifiesto(self.ruta, datos)
        texto = self.ruta.read_text(encoding="utf-8")
        self.assertIn("Términos", texto)  # ensure_ascii=False
        leido = leer_manifiesto(self.ruta)
        self.assertEqual(leido, datos)
        self.assertEqual(leido["resumen_recursos"]["externo"], 3)
        self.assertEqual(leido["resumen_recursos"]["faltante"], 0)
        self.assertEqual(leido["estado_semaforo"], "amarillo")
        self.assertEqual(leido["descripcion"], "")

    def prueba_escritura_atomica_no_deja_temporales(self):
        escribir_manifiesto(self.ruta, {"a": 1})
        escribir_manifiesto(self.ruta, {"a": 2})
        self.assertEqual(os.listdir(str(self.ruta.parent)), ["manifiesto.json"])

    def prueba_error_al_serializar_conserva_el_anterior(self):
        escribir_manifiesto(self.ruta, {"a": 1})
        with self.assertRaises(TypeError):
            escribir_manifiesto(self.ruta, {"a": object()})
        self.assertEqual(json.loads(self.ruta.read_text(encoding="utf-8")), {"a": 1})
        self.assertEqual(os.listdir(str(self.ruta.parent)), ["manifiesto.json"])

    def prueba_manifiestos_invalidos(self):
        with self.assertRaises(ManifiestoInvalido):
            leer_manifiesto(self.ruta)
        escribir_manifiesto(self.ruta, {"formato": "otro", "id_proyecto": "x"})
        with self.assertRaises(ManifiestoInvalido):
            leer_manifiesto(self.ruta)
        self.ruta.write_text("{no es json", encoding="utf-8")
        with self.assertRaises(ManifiestoInvalido):
            leer_manifiesto(self.ruta)


class PruebaEstructura(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def prueba_crea_carpetas(self):
        carpeta = self.base / "Manglares"
        crear_estructura(carpeta)
        self.assertEqual(
            sorted(p.name for p in carpeta.iterdir()),
            [".geoguardian", "datos", "documentos", "salidas"],
        )

    def prueba_acepta_carpeta_vacia_existente(self):
        carpeta = self.base / "Vacia"
        carpeta.mkdir()
        crear_estructura(carpeta)
        self.assertTrue((carpeta / "datos").is_dir())

    def prueba_rechaza_carpeta_con_contenido_sin_tocarla(self):
        carpeta = self.base / "Ocupada"
        carpeta.mkdir()
        (carpeta / "tarea.docx").write_text("x")
        self.assertFalse(carpeta_disponible(carpeta))
        with self.assertRaises(CarpetaNoDisponible):
            crear_estructura(carpeta)
        self.assertEqual([p.name for p in carpeta.iterdir()], ["tarea.docx"])
