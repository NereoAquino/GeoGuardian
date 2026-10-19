"""Ejecutor de pruebas de GeoGuardian (D-09).

Uso:
    python pruebas/ejecutar_pruebas.py                 # unitarias (sin QGIS)
    python pruebas/ejecutar_pruebas.py --integracion   # dentro de un Python con QGIS
"""

import os
import sys
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def principal():
    sys.path.insert(0, RAIZ)
    carpeta = "integracion" if "--integracion" in sys.argv else "unitarias"
    cargador = unittest.TestLoader()
    cargador.testMethodPrefix = "prueba"
    suite = cargador.discover(
        os.path.join(RAIZ, "pruebas", carpeta), pattern="prueba_*.py", top_level_dir=RAIZ
    )
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if resultado.wasSuccessful() else 1)


if __name__ == "__main__":
    principal()
