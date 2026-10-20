"""Plan de incorporacion, v0.2.0 Hito 2 (D-56 a D-68): reglas puras, sin QGIS."""

import ast
import os
import re
import shutil
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace

from geoguardian.dominio.clasificacion_inventario import construir_inventario
from geoguardian.dominio.inventario import ContextoInventario, DatosSrc, EntradaCapa
from geoguardian.dominio.plan_incorporacion import (
    FID_CLAVE,
    FID_ENTERO_UNICO,
    FID_REPETIDO,
    FID_TIPO_INCOMPATIBLE,
    TEMPORAL_ARCHIVO,
    TEMPORAL_MEMORIA,
    TEXTO_BREVE,
    TEXTO_MOTIVO,
    TEXTO_ORIGEN_PLAN,
    DatosCapaPlan,
    DestinoPlan,
    Elegibilidad as El,
    MotivoAtencion as M,
    Seleccion as Se,
    ayuda_estado,
    con_seleccion,
    construir_plan,
    seleccion_tras_revisar,
    texto_conteo,
    texto_estado,
    texto_resumen_plan,
)

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UTM = DatosSrc(True, "EPSG:32615", "WGS 84 / UTM zone 15N")
GEO = DatosSrc(True, "EPSG:4326", "WGS 84")
SIN = DatosSrc(False)


class BasePlan(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="gg_plan_")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.carpeta = os.path.join(self.base, "Manglares - Ana")
        self.temporal = os.path.join(self.base, "tmp")
        self.externa = os.path.join(self.base, "descargas")
        for carpeta in (self.carpeta, os.path.join(self.carpeta, "datos"), self.temporal, self.externa):
            os.makedirs(carpeta, exist_ok=True)
        self.gpkg = self.archivo(self.carpeta, "Proyecto.gpkg")
        self.contexto = ContextoInventario(self.carpeta, (self.temporal,), geopaquete_utilizable=True)
        self.destino = DestinoPlan(self.gpkg, "id-1", True, frozenset({"gg_proyecto", "gg_recursos", "gg_eventos"}))

    def archivo(self, carpeta, nombre):
        ruta = os.path.join(carpeta, nombre)
        open(ruta, "w").close()
        return ruta

    def entrada(self, id_capa, **cambios):
        valores = dict(
            id_capa=id_capa, nombre=id_capa, tipo_capa="vectorial", proveedor="ogr", es_valida=True,
            es_espacial=True, src=UTM, src_fuente=UTM, src_igual_proyecto=True,
        )
        valores.update(cambios)
        if valores.get("ruta_local") and "existe" not in cambios:
            valores["existe"] = os.path.exists(valores["ruta_local"])
        return EntradaCapa(**valores)

    def externo(self, id_capa, nombre_archivo="municipios.shp", **cambios):
        ruta = os.path.join(self.externa, nombre_archivo)
        if not os.path.exists(ruta):
            open(ruta, "w").close()
        return self.entrada(id_capa, ruta_local=ruta, **cambios)

    def memoria(self, id_capa, **cambios):
        return self.entrada(id_capa, proveedor="memory", **cambios)

    def plan(self, entradas, datos=None, destino=None, seleccion=None):
        inventario = construir_inventario(entradas, self.contexto, UTM, "2026-10-20T10:00:00-06:00", "P")
        datos = dict(datos or {})
        for e in entradas:
            if e.id_capa not in datos:
                nombre = os.path.splitext(os.path.basename(e.ruta_local))[0] if e.ruta_local else ""
                datos[e.id_capa] = DatosCapaPlan(id_capa=e.id_capa, nombre_origen=nombre)
        return construir_plan(inventario, datos, destino or self.destino, "fecha", seleccion)

    def unidad(self, entradas, id_capa=None, **kwargs):
        plan = self.plan(entradas, **kwargs)
        return plan.unidad_de_capa(id_capa or entradas[0].id_capa)

    def datos(self, id_capa, **cambios):
        return DatosCapaPlan(id_capa=id_capa, **cambios)


class PruebaElegibilidadPorOrigen(BasePlan):
    def comprobar(self, entrada, elegibilidad, seleccion, motivos=(), texto=None):
        unidad = self.unidad([entrada])
        self.assertEqual(unidad.elegibilidad, elegibilidad, entrada)
        self.assertEqual(unidad.seleccion, seleccion, entrada)
        self.assertEqual(unidad.motivos, tuple(motivos), entrada)
        if texto:
            self.assertEqual(texto_estado(unidad), texto)
        return unidad

    def prueba_archivo_en_la_carpeta_del_proyecto(self):
        ruta = self.archivo(os.path.join(self.carpeta, "datos"), "rios.shp")
        self.comprobar(self.entrada("c", ruta_local=ruta), El.INCORPORABLE, Se.PRESELECCIONADA,
                       texto="Se puede incorporar")

    def prueba_archivo_externo(self):
        self.comprobar(self.externo("c"), El.INCORPORABLE, Se.PRESELECCIONADA)

    def prueba_capa_en_memoria(self):
        unidad = self.comprobar(self.memoria("c"), El.INCORPORABLE, Se.PRESELECCIONADA,
                                texto="Capa temporal: se recomienda incorporar")
        self.assertEqual(unidad.tipo_temporal, TEMPORAL_MEMORIA)

    def prueba_archivo_temporal_de_procesos(self):
        ruta = self.archivo(self.temporal, "OUTPUT.gpkg")
        unidad = self.comprobar(self.entrada("c", ruta_local=ruta, nombre="Buffer 100 m"), El.INCORPORABLE,
                                Se.PRESELECCIONADA, texto="Capa temporal: se recomienda incorporar")
        self.assertEqual(unidad.tipo_temporal, TEMPORAL_ARCHIVO)
        self.assertEqual(unidad.nombre_destino, "Buffer 100 m")  # no "OUTPUT"

    def prueba_tabla_sin_geometria_se_preselecciona(self):
        self.comprobar(self.externo("c", "catalogo.dbf", es_espacial=False, src=SIN, src_fuente=SIN,
                                    src_igual_proyecto=False),
                       El.INCORPORABLE, Se.PRESELECCIONADA)

    def prueba_no_incorporables_por_origen(self):
        casos = [
            (self.entrada("a", ruta_local=self.gpkg, es_geopaquete_activo=True), M.YA_ADMINISTRADA,
             "Ya está en el proyecto"),
            (self.entrada("w", proveedor="WFS", contenedor="https://x/wfs"), M.RECURSO_EN_LINEA,
             "Se mantiene conectado"),
            (self.entrada("p", proveedor="postgres", contenedor="postgres://h:5432/db"), M.BASE_EXTERNA,
             "Se mantiene conectado"),
            (self.entrada("v", proveedor="virtual", contenedor="virtual"), M.VIRTUAL, "Se mantiene conectado"),
            (self.entrada("d", proveedor="raro", contenedor="x"), M.DESCONOCIDA, None),
        ]
        for entrada, motivo, texto in casos:
            self.comprobar(entrada, El.NO_INCORPORABLE, Se.NO_SELECCIONABLE, [motivo], texto)

    def prueba_no_disponibles(self):
        faltante = self.entrada("f", ruta_local=os.path.join(self.externa, "borrado.shp"))
        ausente = self.entrada("u", ruta_local=os.path.join(self.externa, "x.shp"), existe=False, unidad_ausente=True)
        invalida = self.externo("i", es_valida=False)
        for entrada in (faltante, ausente, invalida):
            self.comprobar(entrada, El.NO_INCORPORABLE, Se.NO_SELECCIONABLE, [M.NO_DISPONIBLE], "No disponible")

    def prueba_el_inventario_ya_omite_las_tablas_gg(self):
        tabla = self.entrada("g", ruta_local=self.gpkg, es_geopaquete_activo=True, es_tabla_control=True)
        plan = self.plan([tabla, self.memoria("m")])
        self.assertIsNone(plan.unidad_de_capa("g"))
        self.assertEqual(len(plan.unidades), 1)


class PruebaSrc(BasePlan):
    def prueba_src_diferente_seleccionable_no_preseleccionada(self):
        unidad = self.unidad([self.externo("c", src=GEO, src_fuente=GEO, src_igual_proyecto=False)])
        self.assertEqual((unidad.elegibilidad, unidad.seleccion), (El.CON_ADVERTENCIA, Se.SELECCIONABLE))
        self.assertEqual(unidad.motivos, (M.SRC_DIFERENTE,))
        self.assertEqual(texto_estado(unidad), "SRC diferente al proyecto")

    def prueba_temporal_con_src_diferente_no_se_preselecciona(self):
        unidad = self.unidad([self.memoria("c", src=GEO, src_fuente=GEO, src_igual_proyecto=False)])
        self.assertEqual(unidad.seleccion, Se.SELECCIONABLE)

    def prueba_src_asignado_distinto_del_de_la_fuente(self):
        unidad = self.unidad([self.externo("c", src=GEO, src_fuente=UTM, src_igual_proyecto=False,
                                           src_igual_fuente=False)])
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)
        self.assertEqual(unidad.motivos, (M.SRC_ASIGNADO_DISTINTO,))
        self.assertIn("Revisa el SRC asignado", ayuda_estado(unidad))

    def prueba_archivo_sin_src(self):
        unidad = self.unidad([self.externo("c", src=SIN, src_fuente=SIN, src_igual_proyecto=False)])
        self.assertEqual((unidad.elegibilidad, unidad.motivos), (El.NO_INCORPORABLE, (M.SIN_SRC,)))
        self.assertIn("Define correctamente su sistema de coordenadas", ayuda_estado(unidad))
        self.assertNotIn("reproyect", ayuda_estado(unidad).lower())

    def prueba_temporal_sin_src(self):
        unidad = self.unidad([self.memoria("c", src=SIN, src_fuente=SIN, src_igual_proyecto=False)])
        self.assertEqual((unidad.elegibilidad, unidad.motivos), (El.NO_INCORPORABLE, (M.TEMPORAL_SIN_SRC,)))
        self.assertIn("Esta capa temporal no tiene SRC", ayuda_estado(unidad))

    def prueba_proyecto_sin_src(self):
        inventario = construir_inventario([self.externo("c")], self.contexto, SIN, "f", "P")
        plan = construir_plan(inventario, {"c": self.datos("c")}, self.destino, "f")
        self.assertEqual(plan.unidades[0].motivos, (M.PROYECTO_SIN_SRC,))
        self.assertEqual(plan.unidades[0].seleccion, Se.SELECCIONABLE)

    def prueba_src_definido_solo_en_qgis(self):
        unidad = self.unidad([self.externo("c")], datos={"c": self.datos("c", src_fuente_valido=False)})
        self.assertEqual(unidad.motivos, (M.SRC_DEFINIDO_EN_QGIS,))
        self.assertEqual(unidad.seleccion, Se.SELECCIONABLE)

    def prueba_tabla_sin_geometria_no_evalua_src(self):
        unidad = self.unidad([self.externo("c", "t.csv", es_espacial=False, src=SIN, src_fuente=SIN)],
                             datos={"c": self.datos("c", src_fuente_valido=False)})
        self.assertEqual(unidad.motivos, ())


class PruebaEdicion(BasePlan):
    def prueba_modo_edicion_sin_cambios(self):
        unidad = self.unidad([self.memoria("c")], datos={"c": self.datos("c", en_edicion=True)})
        self.assertEqual((unidad.elegibilidad, unidad.motivos), (El.BLOQUEADA, (M.EN_EDICION,)))
        self.assertEqual(texto_estado(unidad), "Está en modo edición")
        self.assertIn("Termina la edición antes de incorporarla", ayuda_estado(unidad))

    def prueba_cambios_sin_guardar(self):
        unidad = self.unidad([self.memoria("c")], datos={"c": self.datos("c", en_edicion=True, con_cambios=True)})
        self.assertEqual((unidad.elegibilidad, unidad.motivos), (El.BLOQUEADA, (M.CAMBIOS_SIN_GUARDAR,)))
        self.assertIn("Guarda o descarta los cambios", ayuda_estado(unidad))

    def prueba_una_capa_en_edicion_bloquea_toda_la_unidad(self):
        capas = [self.externo("a"), self.externo("b"), self.externo("c")]
        unidad = self.unidad(capas, datos={"b": self.datos("b", nombre_origen="municipios", en_edicion=True)})
        self.assertEqual(unidad.ids_capas, ("a", "b", "c"))
        self.assertEqual(unidad.elegibilidad, El.BLOQUEADA)

    def prueba_incompatibilidad_y_edicion_a_la_vez(self):
        unidad = self.unidad([self.externo("c", src=SIN, src_fuente=SIN)],
                             datos={"c": self.datos("c", en_edicion=True)})
        self.assertEqual(unidad.elegibilidad, El.NO_INCORPORABLE)
        self.assertEqual(unidad.motivos, (M.SIN_SRC, M.EN_EDICION))


class PruebaCampos(BasePlan):
    def motivos(self, **datos):
        return self.unidad([self.externo("c")], datos={"c": self.datos("c", **datos)}).motivos

    def prueba_fid(self):
        self.assertEqual(self.motivos(estado_fid=FID_CLAVE), ())
        self.assertEqual(self.motivos(estado_fid=FID_ENTERO_UNICO), ())
        self.assertEqual(self.motivos(estado_fid=FID_REPETIDO), (M.CAMPO_FID_REPETIDO,))
        self.assertEqual(self.motivos(estado_fid=FID_TIPO_INCOMPATIBLE), (M.CAMPO_FID_TIPO,))

    def prueba_campos_repetidos_sin_distinguir_mayusculas(self):
        self.assertEqual(self.motivos(campos=(("ID", "Integer"), ("id", "Integer"))), (M.CAMPOS_REPETIDOS,))
        self.assertEqual(self.motivos(campos=(("id", "Integer"), ("nombre", "String"))), ())

    def prueba_campo_geom(self):
        self.assertEqual(self.motivos(campos=(("GEOM", "String"),)), (M.CAMPO_GEOM,))
        tabla = self.unidad([self.externo("t", "t.dbf", es_espacial=False, src=SIN, src_fuente=SIN)],
                            datos={"t": self.datos("t", campos=(("geom", "String"),))})
        self.assertEqual(tabla.motivos, ())  # sin geometria no hay columna geom que choque

    def prueba_geometrias_mezcladas(self):
        self.assertEqual(self.motivos(geometrias_mezcladas=True), (M.GEOMETRIAS_MEZCLADAS,))
        con_tipo = self.motivos(geometrias_mezcladas=True, tipo_geometria="Point")
        self.assertEqual(con_tipo, (M.FILTRO_GEOMETRIA,))

    def prueba_campos_calculados_solo_advierten(self):
        unidad = self.unidad([self.externo("c")], datos={"c": self.datos("c", campos_calculados=("doble",))})
        self.assertEqual((unidad.elegibilidad, unidad.motivos), (El.CON_ADVERTENCIA, (M.CAMPOS_CALCULADOS,)))
        self.assertIn("dejarán de recalcularse automáticamente", ayuda_estado(unidad))


class PruebaUnidades(BasePlan):
    def prueba_varias_capas_una_fuente_una_unidad(self):
        capas = [self.externo("a", nombre="Municipios población"), self.externo("b", nombre="Municipios región"),
                 self.externo("c", nombre="Municipios destacados")]
        plan = self.plan(capas)
        self.assertEqual(len(plan.unidades), 1)
        unidad = plan.unidades[0]
        self.assertEqual(unidad.ids_capas, ("a", "b", "c"))
        self.assertEqual(unidad.nombre_destino, "municipios")
        self.assertIn("Se incorpora junto con", ayuda_estado(unidad))

    def prueba_filtros_distintos_unidades_distintas(self):
        capas = [self.externo("a", nombre="Todos"), self.externo("b", nombre="Norte"), self.externo("c", nombre="Sur")]
        datos = {
            "a": self.datos("a", nombre_origen="municipios"),
            "b": self.datos("b", nombre_origen="municipios", subset='"zona" = \'N\''),
            "c": self.datos("c", nombre_origen="municipios", subset='"zona" = \'S\''),
        }
        plan = self.plan(capas, datos=datos)
        self.assertEqual(len(plan.unidades), 3)
        sin_filtro, norte, sur = (plan.unidad_de_capa(i) for i in "abc")
        self.assertEqual(sin_filtro.seleccion, Se.PRESELECCIONADA)
        for unidad in (norte, sur):
            self.assertEqual(unidad.motivos, (M.FILTRO,))
            self.assertEqual(unidad.seleccion, Se.SELECCIONABLE)
        self.assertEqual((sin_filtro.nombre_destino, norte.nombre_destino, sur.nombre_destino),
                         ("municipios", "Norte", "Sur"))

    def prueba_mismo_filtro_comparte_unidad(self):
        capas = [self.externo("a"), self.externo("b")]
        datos = {i: self.datos(i, subset='"id" > 1') for i in "ab"}
        self.assertEqual(len(self.plan(capas, datos=datos).unidades), 1)

    def prueba_geometrytype_distinto_unidades_distintas(self):
        capas = [self.externo("p", "pozos.geojson", nombre="Pozos"), self.externo("l", "pozos.geojson", nombre="Ductos")]
        datos = {"p": self.datos("p", tipo_geometria="Point"), "l": self.datos("l", tipo_geometria="LineString")}
        plan = self.plan(capas, datos=datos)
        self.assertEqual(len(plan.unidades), 2)
        self.assertEqual(plan.unidad_de_capa("p").nombre_destino, "Pozos")

    def prueba_geopackage_externo_con_varias_tablas(self):
        ruta = self.archivo(self.externa, "base.gpkg")
        capas = [self.entrada("r", ruta_local=ruta, subcapa="rios"), self.entrada("l", ruta_local=ruta, subcapa="lagos"),
                 self.entrada("t", ruta_local=ruta, subcapa="catalogo", es_espacial=False, src=SIN)]
        datos = {i: self.datos(i, nombre_origen=n) for i, n in (("r", "rios"), ("l", "lagos"), ("t", "catalogo"))}
        plan = self.plan(capas, datos=datos)
        self.assertEqual(sorted(u.nombre_destino for u in plan.unidades), ["catalogo", "lagos", "rios"])

    def prueba_geopackage_sin_layername_se_une_a_su_tabla(self):
        ruta = self.archivo(self.externa, "unica.gpkg")
        capas = [self.entrada("x", ruta_local=ruta, subcapa="rios"), self.entrada("y", ruta_local=ruta)]
        datos = {"x": self.datos("x", nombre_origen="rios"),
                 "y": self.datos("y", nombre_origen="rios", subcapa_real="rios")}
        plan = self.plan(capas, datos=datos)
        self.assertEqual(len(plan.unidades), 1)
        self.assertEqual(set(plan.unidades[0].ids_capas), {"x", "y"})

    def prueba_geopackage_sin_layername_ambiguo_no_se_une(self):
        ruta = self.archivo(self.externa, "varias.gpkg")
        capas = [self.entrada("x", ruta_local=ruta, subcapa="rios"), self.entrada("y", ruta_local=ruta)]
        self.assertEqual(len(self.plan(capas).unidades), 2)

    def prueba_cada_capa_en_memoria_es_su_unidad(self):
        plan = self.plan([self.memoria("a", nombre="Buffer"), self.memoria("b", nombre="Buffer")])
        self.assertEqual(len(plan.unidades), 2)
        self.assertEqual(sorted(u.nombre_destino for u in plan.unidades), ["Buffer", "Buffer_2"])


class PruebaNombresEnElPlan(BasePlan):
    def prueba_conflicto_con_tablas_existentes(self):
        destino = replace(self.destino, nombres_ocupados=frozenset({"municipios", "Municipios_2", "municipios_3", "gg_eventos"}))
        unidad = self.unidad([self.externo("c")], destino=destino)
        self.assertEqual(unidad.nombre_destino, "municipios_4")
        self.assertTrue(unidad.conflicto_resuelto)

    def prueba_no_incorporables_sin_destino(self):
        unidad = self.unidad([self.entrada("w", proveedor="wfs", contenedor="https://x")])
        self.assertIsNone(unidad.destino)

    def prueba_la_seleccion_no_cambia_los_nombres(self):
        capas = [self.externo("a", "rios.shp"), self.memoria("b", nombre="rios")]
        con_todo = self.plan(capas)
        sin_nada = self.plan(capas, seleccion=())
        self.assertEqual([u.nombre_destino for u in con_todo.unidades], [u.nombre_destino for u in sin_nada.unidades])

    def prueba_bloqueadas_reservan_su_nombre(self):
        capas = [self.externo("a", "rios.shp"), self.memoria("b", nombre="rios")]
        plan = self.plan(capas, datos={"b": self.datos("b", en_edicion=True)})
        self.assertEqual(sorted(u.nombre_destino for u in plan.unidades), ["rios", "rios_2"])


class PruebaSeleccion(BasePlan):
    def entradas(self):
        return [
            self.externo("ok"),
            self.externo("src", "otro.shp", src=GEO, src_fuente=GEO, src_igual_proyecto=False),
            self.entrada("wfs", proveedor="wfs", contenedor="https://x"),
        ]

    def prueba_preseleccion(self):
        plan = self.plan(self.entradas())
        self.assertEqual(plan.seleccionadas, {plan.unidad_de_capa("ok").clave_unidad})

    def prueba_con_seleccion_ignora_lo_no_seleccionable(self):
        plan = self.plan(self.entradas())
        todas = [u.clave_unidad for u in plan.unidades]
        seleccion = con_seleccion(plan, todas).seleccionadas
        self.assertNotIn(plan.unidad_de_capa("wfs").clave_unidad, seleccion)
        self.assertIn(plan.unidad_de_capa("src").clave_unidad, seleccion)

    def prueba_volver_a_revisar(self):
        anterior = self.plan(self.entradas())
        clave_src = anterior.unidad_de_capa("src").clave_unidad
        clave_ok = anterior.unidad_de_capa("ok").clave_unidad
        anterior = con_seleccion(anterior, {clave_src})  # el estudiante desmarca ok y marca src
        nuevas = self.entradas() + [self.memoria("nueva")]
        nuevo = self.plan(nuevas)
        seleccion = seleccion_tras_revisar(anterior, nuevo)
        self.assertIn(clave_src, seleccion)  # advertencia ya aceptada
        self.assertNotIn(clave_ok, seleccion)  # lo desmarcado sigue desmarcado
        self.assertIn(nuevo.unidad_de_capa("nueva").clave_unidad, seleccion)  # nueva: preseleccion

    def prueba_volver_a_revisar_desmarca_advertencias_nuevas_y_bloqueos(self):
        anterior = self.plan([self.externo("a"), self.memoria("b")])
        nuevo = self.plan(
            [self.externo("a", src=GEO, src_fuente=GEO, src_igual_proyecto=False), self.memoria("b")],
            datos={"b": self.datos("b", en_edicion=True)},
        )
        self.assertEqual(seleccion_tras_revisar(anterior, nuevo), frozenset())

    def prueba_lo_desbloqueado_recibe_la_preseleccion(self):
        anterior = self.plan([self.memoria("b")], datos={"b": self.datos("b", en_edicion=True)})
        nuevo = self.plan([self.memoria("b")])
        self.assertEqual(seleccion_tras_revisar(anterior, nuevo), nuevo.preseleccion())

    def prueba_sin_plan_anterior(self):
        nuevo = self.plan(self.entradas())
        self.assertEqual(seleccion_tras_revisar(None, nuevo), nuevo.preseleccion())


class PruebaTextos(BasePlan):
    PROHIBIDAS = ("provider", "proveedor", "datasource", "uri", "ogr", "qgsvectorlayer", "memory")

    def prueba_textos_sin_terminos_tecnicos(self):
        textos = list(TEXTO_BREVE.values()) + list(TEXTO_MOTIVO.values()) + list(TEXTO_ORIGEN_PLAN.values())
        nombres_internos = {m.name.lower() for m in M} | {m.value for m in M}
        for texto in textos:
            palabras = set(re.findall(r"[a-z_]+", texto.lower()))
            for prohibida in self.PROHIBIDAS:
                self.assertNotIn(prohibida, palabras, texto)
            self.assertFalse(palabras & {n for n in nombres_internos if "_" in n}, texto)
            self.assertNotIn("incorrect", texto.lower())

    def prueba_todos_los_motivos_tienen_texto(self):
        for motivo in M:
            self.assertIn(motivo, TEXTO_BREVE)
            self.assertIn(motivo, TEXTO_MOTIVO)

    def prueba_conteo(self):
        capas = [self.externo("a"), self.externo("b"), self.memoria("m"),
                 self.externo("s", "otro.shp", src=GEO, src_fuente=GEO, src_igual_proyecto=False)]
        plan = self.plan(capas)
        self.assertEqual(texto_conteo(plan), "2 elementos por incorporar (3 capas relacionadas)")
        plan = con_seleccion(plan, [u.clave_unidad for u in plan.unidades])
        self.assertEqual(texto_conteo(plan),
                         "3 elementos por incorporar (4 capas relacionadas) · 1 advertencia pendiente")
        self.assertEqual(texto_conteo(con_seleccion(plan, ())), "Ningún elemento seleccionado para incorporar.")

    def prueba_resumen_de_la_vista_previa(self):
        destino = replace(self.destino, nombres_ocupados=frozenset({"municipios"}))
        capas = [self.externo("a"), self.memoria("m"), self.externo("s", "otro.shp", src=GEO, src_fuente=GEO,
                                                                   src_igual_proyecto=False)]
        plan = self.plan(capas, destino=destino)
        plan = con_seleccion(plan, [u.clave_unidad for u in plan.unidades])
        self.assertEqual(
            texto_resumen_plan(plan),
            "Se incorporarán 3 elementos en Proyecto.gpkg. Una capa temporal quedará guardada permanentemente. "
            "Un elemento tiene un SRC diferente al proyecto. Un elemento usará otro nombre porque el suyo ya "
            "está ocupado. Los archivos originales no serán modificados.",
        )


class PruebaInmutable(BasePlan):
    def prueba_plan_y_unidades_inmutables(self):
        plan = self.plan([self.externo("a")])
        with self.assertRaises(FrozenInstanceError):
            plan.seleccionadas = frozenset()
        with self.assertRaises(FrozenInstanceError):
            plan.unidades[0].nombre_base = "x"


class PruebaSoloLecturaHito2(unittest.TestCase):
    """D-67, D-68: el plan no importa nada que escriba; sqlite3 solo en el lector de solo lectura."""

    PROHIBIDOS = ("persistencia", "manifiesto", "eventos", "administracion")
    ESCRITURA = re.compile(r"\b(insert|update|delete|create|drop|alter|replace|attach|vacuum|reindex)\b", re.I)

    def modulos(self):
        rutas = [os.path.join(RAIZ, "geoguardian", "dominio", n)
                 for n in ("plan_incorporacion.py", "nombres_destino.py", "revalidacion.py")]
        rutas.append(os.path.join(RAIZ, "geoguardian", "interfaz", "dialogo_incorporacion.py"))
        carpeta = os.path.join(RAIZ, "geoguardian", "incorporacion")
        rutas += [os.path.join(carpeta, n) for n in os.listdir(carpeta) if n.endswith(".py")]
        return rutas

    def arbol(self, ruta):
        with open(ruta, encoding="utf-8") as archivo:
            return ast.parse(archivo.read())

    def prueba_no_importan_escritura(self):
        for ruta in self.modulos():
            for nodo in ast.walk(self.arbol(ruta)):
                nombres = []
                if isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom):
                    nombres = [nodo.module or ""]
                for nombre in nombres:
                    partes = nombre.split(".")
                    for prohibido in self.PROHIBIDOS:
                        self.assertNotIn(prohibido, partes, "{} importa {}".format(ruta, nombre))
                    if "sqlite3" in partes:
                        self.assertTrue(ruta.endswith("lector_geopaquete.py"), ruta)

    def prueba_el_dialogo_recibe_las_funciones(self):
        ruta = os.path.join(RAIZ, "geoguardian", "interfaz", "dialogo_incorporacion.py")
        for nodo in ast.walk(self.arbol(ruta)):
            if isinstance(nodo, ast.ImportFrom):
                paquete = (nodo.module or "").split(".")[0]  # dominio.inventario es dominio puro
                self.assertNotIn(paquete, ("inventario", "incorporacion", "persistencia"), nodo.module)

    def prueba_lector_geopaquete_solo_lee(self):
        ruta = os.path.join(RAIZ, "geoguardian", "incorporacion", "lector_geopaquete.py")
        cadenas = [n.value for n in ast.walk(self.arbol(ruta))
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        consultas = [c for c in cadenas if c.lstrip().upper().startswith(("SELECT", "PRAGMA", "WITH"))]
        self.assertTrue(consultas)
        for consulta in consultas:
            self.assertTrue(consulta.lstrip().upper().startswith("SELECT"), consulta)
            self.assertIsNone(self.ESCRITURA.search(consulta), consulta)
        self.assertIn("?mode=ro", cadenas[0] if "?mode=ro" in cadenas[0] else "".join(cadenas))


if __name__ == "__main__":
    unittest.main()
