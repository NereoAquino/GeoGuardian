import os
import tempfile
import unittest

from geoguardian.dominio.clasificacion import clasificar_recurso, esta_dentro, ruta_relativa
from geoguardian.dominio.modelos import DescripcionFuente, EstadoRecurso as E


class PruebaClasificacion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = self._tmp.name
        self.proyecto = os.path.join(base, "Proyecto_Manglares")
        self.temporal = os.path.join(base, "tmp_sistema")
        self.externa = os.path.join(base, "Descargas")
        for carpeta in (self.proyecto, os.path.join(self.proyecto, "datos"), self.temporal, self.externa):
            os.makedirs(carpeta, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _archivo(self, carpeta, nombre="capa.shp"):
        ruta = os.path.join(carpeta, nombre)
        open(ruta, "w").close()
        return ruta

    def _clasificar(self, proveedor="ogr", ruta=None, existe=True, valida=True):
        d = DescripcionFuente(proveedor=proveedor, ruta_archivo=ruta, existe=existe, es_valida=valida)
        return clasificar_recurso(d, self.proyecto, [self.temporal])

    def prueba_archivo_dentro_es_activo(self):
        ruta = self._archivo(os.path.join(self.proyecto, "datos"))
        self.assertEqual(self._clasificar(ruta=ruta), E.ACTIVO)

    def prueba_archivo_fuera_es_externo(self):
        self.assertEqual(self._clasificar(ruta=self._archivo(self.externa)), E.EXTERNO)

    def prueba_servicio_remoto_es_externo(self):
        self.assertEqual(self._clasificar(proveedor="wms"), E.EXTERNO)

    def prueba_memoria_es_temporal(self):
        self.assertEqual(self._clasificar(proveedor="memory"), E.TEMPORAL)

    def prueba_archivo_en_carpeta_temporal_es_temporal(self):
        self.assertEqual(self._clasificar(ruta=self._archivo(self.temporal)), E.TEMPORAL)

    def prueba_archivo_inexistente_es_faltante(self):
        ruta = os.path.join(self.proyecto, "datos", "no_existe.shp")
        self.assertEqual(self._clasificar(ruta=ruta, existe=False), E.FALTANTE)

    def prueba_capa_invalida_es_faltante(self):
        self.assertEqual(self._clasificar(proveedor="wms", valida=False), E.FALTANTE)

    def prueba_faltante_tiene_prioridad_sobre_temporal(self):
        self.assertEqual(self._clasificar(proveedor="memory", valida=False), E.FALTANTE)

    def prueba_carpeta_con_prefijo_parecido_no_cuenta_como_dentro(self):
        hermana = self.proyecto + "_copia"
        os.makedirs(hermana)
        self.assertFalse(esta_dentro(os.path.join(hermana, "a.shp"), self.proyecto))

    def prueba_ruta_relativa_usa_barras(self):
        ruta = self._archivo(os.path.join(self.proyecto, "datos"))
        self.assertEqual(ruta_relativa(ruta, self.proyecto), "datos/capa.shp")
        self.assertIsNone(ruta_relativa(self._archivo(self.externa), self.proyecto))

    @unittest.skipUnless(os.name == "nt", "solo en Windows")
    def prueba_windows_no_distingue_mayusculas(self):
        ruta = self._archivo(os.path.join(self.proyecto, "datos"))
        self.assertTrue(esta_dentro(ruta.upper(), self.proyecto.lower()))
