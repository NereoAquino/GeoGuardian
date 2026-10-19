"""La version de metadata.txt coincide con VERSION_COMPLEMENTO (D-51)."""

import configparser
import os
import unittest

from geoguardian.constantes import VERSION_COMPLEMENTO

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PruebaVersion(unittest.TestCase):
    def prueba_metadata_coincide_con_la_constante(self):
        metadatos = configparser.ConfigParser()
        metadatos.read(os.path.join(RAIZ, "geoguardian", "metadata.txt"), encoding="utf-8")
        self.assertEqual(metadatos["general"]["version"], VERSION_COMPLEMENTO)


if __name__ == "__main__":
    unittest.main()
