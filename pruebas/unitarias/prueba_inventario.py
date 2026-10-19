"""Inventario de capas, v0.2.0 Hito 1 (D-40 a D-52): reglas puras, sin QGIS."""

import ast
import os
import shutil
import tempfile
import unittest
from dataclasses import replace

from geoguardian.dominio.clasificacion import clasificar_recurso
from geoguardian.dominio.clasificacion_inventario import (
    clasificar_origen,
    construir_inventario,
    equivalente_v010,
    evaluar_disponibilidad,
    evaluar_src,
    identidad_de,
    resumen_por_origen,
    url_sin_credenciales,
)
from geoguardian.dominio.inventario import (
    TEXTO_DISPONIBILIDAD,
    TEXTO_ORIGEN,
    TEXTO_SRC,
    ContextoInventario,
    DatosSrc,
    Disponibilidad as D,
    EntradaCapa,
    EstadoSrc as S,
    OrigenFuente as O,
)
from geoguardian.dominio.modelos import DescripcionFuente, EstadoRecurso as E

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UTM = DatosSrc(True, "EPSG:32615", "WGS 84 / UTM zone 15N")
GEO = DatosSrc(True, "EPSG:4326", "WGS 84")
SIN = DatosSrc(False)


class BaseInventario(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="gg_inv_")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.carpeta = os.path.join(self.base, "Manglares - Ana")
        self.temporal = os.path.join(self.base, "tmp")
        self.externa = os.path.join(self.base, "descargas")
        for carpeta in (self.carpeta, os.path.join(self.carpeta, "datos"), self.temporal, self.externa):
            os.makedirs(carpeta, exist_ok=True)
        self.gpkg = self._archivo(self.carpeta, "Proyecto.gpkg")
        self.contexto = ContextoInventario(self.carpeta, (self.temporal,), geopaquete_utilizable=True)

    def _archivo(self, carpeta, nombre="capa.gpkg"):
        ruta = os.path.join(carpeta, nombre)
        open(ruta, "w").close()
        return ruta

    def entrada(self, id_capa="c1", **cambios):
        valores = dict(
            id_capa=id_capa, nombre=id_capa, tipo_capa="vectorial", proveedor="ogr", es_valida=True,
            es_espacial=True, src=UTM, src_fuente=UTM, src_igual_proyecto=True,
        )
        valores.update(cambios)
        if valores.get("ruta_local") and "existe" not in cambios:
            valores["existe"] = os.path.exists(valores["ruta_local"])
        return EntradaCapa(**valores)

    def origen(self, **cambios):
        return clasificar_origen(self.entrada(**cambios), self.contexto)


class PruebaOrigen(BaseInventario):
    def prueba_proyecto_gpkg_activo_y_validado_es_administrada(self):
        self.assertEqual(self.origen(ruta_local=self.gpkg, es_geopaquete_activo=True), O.ADMINISTRADA)

    def prueba_sin_geopaquete_validado_ninguna_es_administrada(self):
        self.contexto = replace(self.contexto, geopaquete_utilizable=False)
        self.assertEqual(self.origen(ruta_local=self.gpkg, es_geopaquete_activo=True), O.CARPETA_PROYECTO)

    def prueba_gpkg_ajeno_llamado_proyecto_no_es_administrado(self):
        ajeno_dentro = self._archivo(os.path.join(self.carpeta, "datos"), "Proyecto.gpkg")
        ajeno_fuera = self._archivo(self.externa, "Proyecto.gpkg")
        self.assertEqual(self.origen(ruta_local=ajeno_dentro), O.CARPETA_PROYECTO)
        self.assertEqual(self.origen(ruta_local=ajeno_fuera), O.ARCHIVO_EXTERNO)

    def prueba_tabla_de_control_nunca_es_administrada(self):
        self.assertEqual(
            self.origen(ruta_local=self.gpkg, es_geopaquete_activo=True, es_tabla_control=True),
            O.CARPETA_PROYECTO,
        )

    def prueba_archivo_en_carpeta_del_proyecto(self):
        ruta = self._archivo(os.path.join(self.carpeta, "datos"))
        self.assertEqual(self.origen(ruta_local=ruta), O.CARPETA_PROYECTO)

    def prueba_archivo_externo(self):
        self.assertEqual(self.origen(ruta_local=self._archivo(self.externa)), O.ARCHIVO_EXTERNO)

    def prueba_temporales(self):
        self.assertEqual(self.origen(proveedor="memory"), O.TEMPORAL)
        self.assertEqual(self.origen(ruta_local=self._archivo(self.temporal)), O.TEMPORAL)

    def prueba_virtual(self):
        self.assertEqual(self.origen(proveedor="virtual", contenedor="virtual"), O.VIRTUAL)

    def prueba_servicios_remotos(self):
        for proveedor in ("wfs", "WFS", "OAPIF", "arcgisfeatureserver"):
            self.assertEqual(self.origen(proveedor=proveedor), O.SERVICIO_REMOTO, proveedor)
        self.assertEqual(self.origen(proveedor="ogr", ruta_remota=True), O.SERVICIO_REMOTO)

    def prueba_bases_de_datos_externas_se_distinguen_de_servicios(self):
        for proveedor in ("postgres", "mssql", "oracle"):
            self.assertEqual(self.origen(proveedor=proveedor), O.BASE_DATOS_EXTERNA, proveedor)

    def prueba_proveedor_desconocido(self):
        self.assertEqual(self.origen(proveedor="complemento_raro"), O.DESCONOCIDA)


class PruebaDisponibilidad(BaseInventario):
    def prueba_disponible(self):
        self.assertEqual(evaluar_disponibilidad(self.entrada(ruta_local=self.gpkg)), D.DISPONIBLE)

    def prueba_archivo_que_no_existe(self):
        ruta = os.path.join(self.externa, "no_existe.shp")
        self.assertEqual(evaluar_disponibilidad(self.entrada(ruta_local=ruta, es_valida=False)), D.FALTANTE)

    def prueba_unidad_ausente(self):
        entrada = self.entrada(ruta_local="E:/datos/a.shp", existe=False, unidad_ausente=True, es_valida=False)
        self.assertEqual(evaluar_disponibilidad(entrada), D.UNIDAD_AUSENTE)

    def prueba_capa_invalida_sin_archivo(self):
        self.assertEqual(evaluar_disponibilidad(self.entrada(proveedor="wfs", es_valida=False)), D.INVALIDA)

    def prueba_los_ejes_son_independientes(self):
        """Un archivo externo o un servicio tambien pueden faltar o fallar (D-41)."""
        ruta = os.path.join(self.externa, "borrado.shp")
        externo = self.entrada(ruta_local=ruta, es_valida=False)
        self.assertEqual(clasificar_origen(externo, self.contexto), O.ARCHIVO_EXTERNO)
        self.assertEqual(evaluar_disponibilidad(externo), D.FALTANTE)
        servicio = self.entrada(proveedor="wfs", es_valida=False)
        self.assertEqual(clasificar_origen(servicio, self.contexto), O.SERVICIO_REMOTO)
        self.assertEqual(evaluar_disponibilidad(servicio), D.INVALIDA)


class PruebaSrc(BaseInventario):
    def src(self, src_proyecto=UTM, origen=O.CARPETA_PROYECTO, **cambios):
        return evaluar_src(self.entrada(**cambios), origen, src_proyecto)

    def prueba_coincide(self):
        self.assertEqual(self.src(), S.COINCIDE)

    def prueba_diferente(self):
        self.assertEqual(self.src(src=GEO, src_igual_proyecto=False), S.DIFERENTE)

    def prueba_capa_sin_src(self):
        self.assertEqual(self.src(src=SIN, src_igual_proyecto=False), S.CAPA_SIN_SRC)

    def prueba_proyecto_sin_src(self):
        self.assertEqual(self.src(src_proyecto=SIN, src_igual_proyecto=False), S.PROYECTO_SIN_SRC)

    def prueba_no_aplica(self):
        self.assertEqual(self.src(es_espacial=False), S.NO_APLICA)  # tabla sin geometria
        self.assertEqual(self.src(es_valida=False), S.NO_APLICA)
        self.assertEqual(self.src(tipo_capa="raster"), S.NO_APLICA)

    def prueba_src_propio_de_servicio(self):
        self.assertEqual(
            self.src(origen=O.SERVICIO_REMOTO, proveedor="wfs", src=GEO, src_igual_proyecto=False),
            S.SRC_DE_SERVICIO,
        )
        self.assertEqual(self.src(origen=O.SERVICIO_REMOTO, proveedor="wfs"), S.COINCIDE)

    def prueba_advertencia_src_asignado_distinto_de_la_fuente(self):
        entrada = self.entrada(ruta_local=self.gpkg, src=GEO, src_fuente=UTM, src_igual_fuente=False,
                               src_igual_proyecto=False)
        capa = construir_inventario([entrada], self.contexto, UTM, "f").capas[0]
        self.assertEqual(capa.src_fuente_distinto, UTM)

    def prueba_sin_advertencia_si_la_fuente_no_tiene_src(self):
        entrada = self.entrada(ruta_local=self.gpkg, src=GEO, src_fuente=SIN, src_igual_fuente=True)
        self.assertIsNone(construir_inventario([entrada], self.contexto, UTM, "f").capas[0].src_fuente_distinto)


class PruebaConstruccion(BaseInventario):
    def prueba_capas_no_vectoriales_no_se_revisan(self):
        raster = self.entrada("r1", tipo_capa="raster", proveedor="gdal", ruta_local=self._archivo(self.externa, "r.tif"))
        inventario = construir_inventario([raster], self.contexto, UTM, "f")
        self.assertEqual(len(inventario.capas), 1)
        self.assertFalse(inventario.capas[0].revisada)
        self.assertEqual(inventario.fuentes, ())

    def prueba_tablas_de_control_se_omiten_y_se_cuentan(self):
        tabla = self.entrada("gg", ruta_local=self.gpkg, es_geopaquete_activo=True, es_tabla_control=True,
                             subcapa="gg_eventos", es_espacial=False)
        inventario = construir_inventario([tabla], self.contexto, UTM, "f")
        self.assertEqual(inventario.capas, ())
        self.assertEqual(inventario.tablas_control_omitidas, 1)

    def prueba_identidad_contenedor_mas_subcapa(self):
        ruta = self._archivo(os.path.join(self.carpeta, "datos"), "varias.gpkg")
        a1 = self.entrada("a1", ruta_local=ruta, subcapa="rios")
        a2 = self.entrada("a2", ruta_local=ruta, subcapa="rios")
        b = self.entrada("b", ruta_local=ruta, subcapa="lagos")
        inventario = construir_inventario([a1, a2, b], self.contexto, UTM, "f")
        self.assertEqual(len(inventario.fuentes), 2)
        rios = inventario.fuente_de(inventario.capas[0])
        self.assertEqual(rios.ids_capas, ("a1", "a2"))
        self.assertEqual({f.contenedor for f in inventario.fuentes}, {ruta})  # contenedor aparte (D-44)
        self.assertEqual(rios.ruta_relativa, "datos/varias.gpkg")

    def prueba_parametros_relevantes_distinguen_fuentes(self):
        ruta = self._archivo(self.externa, "puntos.csv")
        xy = self.entrada("xy", ruta_local=ruta, proveedor="delimitedtext", parametros=(("xField", "x"),))
        lonlat = self.entrada("ll", ruta_local=ruta, proveedor="delimitedtext", parametros=(("xField", "lon"),))
        self.assertEqual(len(construir_inventario([xy, lonlat], self.contexto, UTM, "f").fuentes), 2)

    def prueba_cada_capa_en_memoria_es_su_propia_fuente(self):
        m1 = self.entrada("m1", proveedor="memory", contenedor="memoria")
        m2 = self.entrada("m2", proveedor="memory", contenedor="memoria")
        self.assertEqual(len(construir_inventario([m1, m2], self.contexto, UTM, "f").fuentes), 2)

    def prueba_disponibilidad_de_la_fuente_es_la_peor_de_sus_capas(self):
        ruta = self._archivo(self.externa)
        buena = self.entrada("a", ruta_local=ruta, subcapa="x")
        mala = self.entrada("b", ruta_local=ruta, subcapa="x", es_valida=False)
        fuente = construir_inventario([buena, mala], self.contexto, UTM, "f").fuentes[0]
        self.assertEqual(fuente.disponibilidad, D.INVALIDA)

    def prueba_resumen_por_origen(self):
        entradas = [
            self.entrada("a", ruta_local=self.gpkg, es_geopaquete_activo=True, subcapa="sitios"),
            self.entrada("b", proveedor="memory"),
            self.entrada("c", proveedor="memory"),
            self.entrada("r", tipo_capa="raster", proveedor="gdal"),
        ]
        inventario = construir_inventario(entradas, self.contexto, UTM, "f")
        self.assertEqual(resumen_por_origen(inventario), [(O.ADMINISTRADA, 1), (O.TEMPORAL, 2)])

    def prueba_todos_los_estados_tienen_texto_para_el_estudiante(self):
        self.assertEqual(set(TEXTO_ORIGEN), set(O))
        self.assertEqual(set(TEXTO_DISPONIBILIDAD), set(D))
        self.assertEqual(set(TEXTO_SRC), set(S))


class PruebaCredenciales(BaseInventario):
    def prueba_url_sin_credenciales(self):
        url = url_sin_credenciales("https://ana:secreto@ejemplo.mx/wfs?MAP=a.map&token=abc&Password=x&SERVICE=WFS")
        self.assertEqual(url, "https://ejemplo.mx/wfs?MAP=a.map&SERVICE=WFS")

    def prueba_identidad_de_servicio_sin_contrasena(self):
        entrada = self.entrada(proveedor="wfs", contenedor="https://ejemplo.mx/wfs password='x'", subcapa="a:b")
        clave = identidad_de(entrada).clave
        self.assertNotIn("'x'", clave)
        self.assertIn("ejemplo.mx/wfs", clave)


class PruebaCoherenciaConV010(BaseInventario):
    """D-42: traducida a EstadoRecurso, la clasificacion nueva coincide con clasificar_recurso."""

    def casos(self):
        dentro = self._archivo(os.path.join(self.carpeta, "datos"))
        fuera = self._archivo(self.externa)
        temporal = self._archivo(self.temporal)
        borrado = os.path.join(self.externa, "borrado.shp")
        return [
            dict(ruta_local=self.gpkg, es_geopaquete_activo=True),
            dict(ruta_local=dentro),
            dict(ruta_local=fuera),
            dict(ruta_local=temporal),
            dict(ruta_local=borrado, es_valida=False),
            dict(ruta_local=borrado, es_valida=True),
            dict(ruta_local=fuera, es_valida=False),
            dict(proveedor="memory"),
            dict(proveedor="memory", es_valida=False),
            dict(proveedor="virtual"),
            dict(proveedor="wfs"),
            dict(proveedor="wfs", es_valida=False),
            dict(proveedor="postgres"),
            dict(proveedor="ogr", ruta_remota=True),
            dict(proveedor="complemento_raro"),
        ]

    def prueba_misma_clasificacion_que_v010(self):
        for caso in self.casos():
            entrada = self.entrada(**caso)
            descripcion = DescripcionFuente(
                proveedor=entrada.proveedor,
                ruta_archivo=entrada.ruta_local,
                existe=entrada.existe,
                es_valida=entrada.es_valida,
            )
            esperado = clasificar_recurso(descripcion, self.carpeta, [self.temporal])
            nuevo = equivalente_v010(clasificar_origen(entrada, self.contexto), evaluar_disponibilidad(entrada))
            self.assertEqual(nuevo, esperado, caso)

    def prueba_equivalencias(self):
        self.assertEqual(equivalente_v010(O.ADMINISTRADA, D.DISPONIBLE), E.ACTIVO)
        self.assertEqual(equivalente_v010(O.BASE_DATOS_EXTERNA, D.DISPONIBLE), E.EXTERNO)
        self.assertEqual(equivalente_v010(O.TEMPORAL, D.UNIDAD_AUSENTE), E.FALTANTE)


class PruebaSoloLectura(unittest.TestCase):
    """D-40: el inventario no importa nada que escriba (persistencia, manifiesto, eventos, sqlite3)."""

    PROHIBIDOS = ("persistencia", "manifiesto", "eventos", "sqlite3", "administracion")

    def _importaciones(self, ruta):
        with open(ruta, encoding="utf-8") as archivo:
            arbol = ast.parse(archivo.read())
        nombres = []
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres += [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres.append(nodo.module or "")
        return nombres

    def prueba_modulos_del_inventario_no_importan_escritura(self):
        modulos = [
            os.path.join(RAIZ, "geoguardian", "dominio", "inventario.py"),
            os.path.join(RAIZ, "geoguardian", "dominio", "clasificacion_inventario.py"),
            os.path.join(RAIZ, "geoguardian", "interfaz", "dialogo_revisar_capas.py"),
        ]
        carpeta = os.path.join(RAIZ, "geoguardian", "inventario")
        modulos += [os.path.join(carpeta, n) for n in os.listdir(carpeta) if n.endswith(".py")]
        for ruta in modulos:
            for nombre in self._importaciones(ruta):
                for prohibido in self.PROHIBIDOS:
                    self.assertNotIn(prohibido, nombre.split("."), "{} importa {}".format(ruta, nombre))


if __name__ == "__main__":
    unittest.main()
