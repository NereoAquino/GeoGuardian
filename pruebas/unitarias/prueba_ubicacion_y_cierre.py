import itertools
import os
import unittest

from geoguardian.dominio.advertencia_cierre import requiere_advertencia
from geoguardian.dominio.ubicacion import (
    UMBRAL_POCO_ESPACIO,
    InfoVolumen,
    es_fat32,
    evaluar_destino,
    misma_unidad,
)

GB = 1024 ** 3
LOCAL = InfoVolumen(raiz="C:/", sistema_archivos="NTFS", bytes_libres=100 * GB)
USB = InfoVolumen(raiz="E:/", sistema_archivos="FAT32", bytes_libres=10 * GB)
RUTA = "C:/Users/ana/Documents/P - Ana/P - Ana.qgz"


def codigos(avisos):
    return sorted(a.codigo for a in avisos)


class PruebaUbicacion(unittest.TestCase):
    def prueba_disco_local_sin_avisos(self):
        self.assertEqual(evaluar_destino(RUTA, LOCAL, "C:/"), [])

    def prueba_usb_fat32(self):
        avisos = evaluar_destino("E:/P - Ana/P - Ana.qgz", USB, "C:/")
        self.assertEqual(codigos(avisos), ["fat32", "unidad_externa"])
        self.assertFalse(any(a.bloqueante for a in avisos))

    def prueba_fat32_portable(self):
        for fs in ("FAT32", "vfat", "msdos", " fat32 "):
            self.assertTrue(es_fat32(fs))
        for fs in ("NTFS", "exFAT", "ext4", ""):
            self.assertFalse(es_fat32(fs))

    def prueba_umbral_de_espacio(self):
        justo = InfoVolumen("C:/", "NTFS", UMBRAL_POCO_ESPACIO)
        menos = InfoVolumen("C:/", "NTFS", UMBRAL_POCO_ESPACIO - 1)
        self.assertEqual(evaluar_destino(RUTA, justo, "C:/"), [])
        self.assertEqual(codigos(evaluar_destino(RUTA, menos, "C:/")), ["poco_espacio"])

    def prueba_bloqueantes(self):
        for volumen, codigo in (
            (InfoVolumen("C:/", "NTFS", 0), "sin_espacio"),
            (InfoVolumen("C:/", "NTFS", 9 * GB, solo_lectura=True), "solo_lectura"),
            (InfoVolumen("C:/", "NTFS", 9 * GB, listo=False), "no_disponible"),
        ):
            with self.subTest(codigo=codigo):
                avisos = evaluar_destino(RUTA, volumen, "C:/")
                self.assertIn(codigo, codigos(avisos))
                self.assertTrue(any(a.bloqueante for a in avisos))

    def prueba_onedrive_es_informativo(self):
        base = os.path.abspath("onedrive_prueba")
        avisos = evaluar_destino(os.path.join(base, "Documentos", "P.qgz"), LOCAL, None, [base])
        self.assertEqual(codigos(avisos), ["onedrive"])
        self.assertFalse(avisos[0].bloqueante)
        self.assertEqual(evaluar_destino(os.path.abspath("otro/P.qgz"), LOCAL, None, [base]), [])

    def prueba_ruta_larga(self):
        self.assertEqual(codigos(evaluar_destino("C:/" + "a" * 201, LOCAL, "C:/")), ["ruta_larga"])

    def prueba_respaldo(self):
        self.assertEqual(
            codigos(evaluar_destino(RUTA, LOCAL, "C:/", ruta_respaldo="C:/r", respaldo_existe=True, volumen_respaldo=LOCAL)),
            ["respaldo_misma_unidad"],
        )
        self.assertEqual(
            evaluar_destino(RUTA, LOCAL, "C:/", ruta_respaldo="E:/r", respaldo_existe=True, volumen_respaldo=USB), []
        )
        avisos = evaluar_destino(RUTA, LOCAL, "C:/", ruta_respaldo="Z:/no", respaldo_existe=False)
        self.assertTrue(avisos[0].bloqueante)

    def prueba_misma_unidad(self):
        self.assertTrue(misma_unidad("/", "/"))
        self.assertFalse(misma_unidad("C:/", None))


class PruebaAdvertenciaCierre(unittest.TestCase):
    def prueba_ocho_combinaciones(self):
        for administrado, guardado, capas in itertools.product((False, True), (False, True), (0, 1)):
            esperado = (not administrado) and (guardado or capas > 0)
            with self.subTest(administrado=administrado, guardado=guardado, capas=capas):
                self.assertEqual(requiere_advertencia(administrado, guardado, capas), esperado)
