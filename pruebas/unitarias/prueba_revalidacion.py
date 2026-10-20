"""Revalidacion del plan de incorporacion, v0.2.0 Hito 2 (D-64): reglas puras, sin QGIS."""

import os
import unittest
from dataclasses import replace

from geoguardian.dominio.plan_incorporacion import EstadoArchivo
from geoguardian.dominio.revalidacion import (
    AVISO_CAMBIOS,
    AVISO_DESTINO,
    MotivoCambio as C,
    revalidar,
)
from pruebas.unitarias.prueba_plan_incorporacion import BasePlan


class PruebaRevalidacion(BasePlan):
    def setUp(self):
        super().setUp()
        self.rios = self.externo("rios", "rios.shp")
        self.lagos = self.externo("lagos", "lagos.shp")
        self.entradas = [self.rios, self.lagos]
        self.datos_base = {
            "rios": self.datos("rios", nombre_origen="rios", src_capa="EPSG:32615", src_fuente="EPSG:32615",
                               campos=(("nombre", "String"),),
                               archivos=(EstadoArchivo(self.rios.ruta_local, True, 10, 100),)),
            "lagos": self.datos("lagos", nombre_origen="lagos", src_capa="EPSG:32615", src_fuente="EPSG:32615"),
        }
        self.anterior = self.plan(self.entradas, self.datos_base)

    def actual(self, entradas=None, destino=None, **datos):
        mezcla = dict(self.datos_base)
        for id_capa, cambios in datos.items():
            mezcla[id_capa] = replace(mezcla[id_capa], **cambios)
        return self.plan(entradas or self.entradas, mezcla, destino=destino)

    def motivos(self, resultado, clave_de="rios"):
        clave = self.anterior.unidad_de_capa(clave_de).clave_unidad
        for cambio in resultado.cambios:
            if cambio.clave_unidad == clave:
                return cambio.motivos
        return ()

    def prueba_sin_cambios_el_plan_sigue_vigente(self):
        resultado = revalidar(self.anterior, self.actual())
        self.assertTrue(resultado.vigente)
        self.assertEqual(resultado.cambios, ())
        self.assertEqual(resultado.texto(), "")
        self.assertIsNotNone(resultado.plan_actual)

    def prueba_sin_plan_actual_el_destino_cambio(self):
        resultado = revalidar(self.anterior, None)
        self.assertFalse(resultado.vigente)
        self.assertTrue(resultado.destino_cambiado)
        self.assertEqual(resultado.texto(), AVISO_DESTINO)

    def prueba_otro_proyecto_u_otro_geopaquete(self):
        for destino in (replace(self.destino, id_proyecto="id-2"), replace(self.destino, ruta="/otra/Proyecto.gpkg"),
                        replace(self.destino, geopaquete_utilizable=False)):
            resultado = revalidar(self.anterior, self.actual(destino=destino))
            self.assertFalse(resultado.vigente, destino)
            self.assertTrue(resultado.destino_cambiado, destino)

    def prueba_capa_quitada(self):
        resultado = revalidar(self.anterior, self.actual(entradas=[self.lagos]))
        self.assertFalse(resultado.vigente)
        self.assertEqual(resultado.texto(), AVISO_CAMBIOS)
        self.assertEqual(self.motivos(resultado), (C.CAPA_ELIMINADA,))

    def prueba_fuente_cambiada(self):
        resultado = revalidar(self.anterior, self.actual(rios=dict(fuente_publica="/otro/rios.shp")))
        self.assertIn(C.FUENTE_CAMBIADA, self.motivos(resultado))

    def prueba_filtro_cambiado_aunque_la_unidad_cambie_de_clave(self):
        resultado = revalidar(self.anterior, self.actual(rios=dict(subset='"tipo" = 1')))
        self.assertFalse(resultado.vigente)
        self.assertIn(C.FILTRO_CAMBIADO, self.motivos(resultado))

    def prueba_src_cambiado(self):
        resultado = revalidar(self.anterior, self.actual(rios=dict(src_capa="EPSG:4326")))
        self.assertIn(C.SRC_CAMBIADO, self.motivos(resultado))

    def prueba_edicion_iniciada_y_cambios(self):
        for cambios in (dict(en_edicion=True), dict(con_cambios=True)):
            resultado = revalidar(self.anterior, self.actual(rios=cambios))
            motivos = self.motivos(resultado)
            self.assertIn(C.EDICION_INICIADA, motivos)
            self.assertIn(C.YA_NO_SELECCIONABLE, motivos)

    def prueba_campos_cambiados(self):
        resultado = revalidar(self.anterior, self.actual(rios=dict(campos=(("nombre", "String"), ("area", "Real")))))
        self.assertEqual(self.motivos(resultado), (C.CAMPOS_CAMBIADOS,))

    def prueba_archivo_modificado(self):
        archivos = (EstadoArchivo(self.rios.ruta_local, True, 12, 200),)
        resultado = revalidar(self.anterior, self.actual(rios=dict(archivos=archivos)))
        self.assertEqual(self.motivos(resultado), (C.ARCHIVO_MODIFICADO,))

    def prueba_datos_en_memoria_cambiados(self):
        memoria = self.memoria("m")
        datos = {"m": self.datos("m", num_entidades=3, extension="0,0 : 1,1")}
        anterior = self.plan([memoria], datos)
        actual = self.plan([memoria], {"m": replace(datos["m"], num_entidades=4)})
        resultado = revalidar(anterior, actual)
        self.assertEqual(resultado.cambios[0].motivos, (C.DATOS_CAMBIADOS,))

    def prueba_advertencias_nuevas(self):
        resultado = revalidar(self.anterior, self.actual(rios=dict(campos_calculados=("area",))))
        self.assertIn(C.ADVERTENCIAS_NUEVAS, self.motivos(resultado))

    def prueba_nombre_ocupado_en_el_destino(self):
        destino = replace(self.destino, nombres_ocupados=self.destino.nombres_ocupados | {"RIOS"})
        resultado = revalidar(self.anterior, self.actual(destino=destino))
        self.assertFalse(resultado.destino_cambiado)
        motivos = self.motivos(resultado)
        self.assertIn(C.NOMBRE_OCUPADO, motivos)
        self.assertIn(C.NOMBRE_CAMBIADO, motivos)
        self.assertEqual(resultado.plan_actual.unidad_de_capa("rios").nombre_destino, "rios_2")

    def prueba_capa_nueva_con_la_misma_fuente(self):
        copia = replace(self.rios, id_capa="rios_copia", nombre="rios copia")
        datos = dict(self.datos_base, rios_copia=replace(self.datos_base["rios"], id_capa="rios_copia"))
        resultado = revalidar(self.anterior, self.plan(self.entradas + [copia], datos))
        self.assertEqual(self.motivos(resultado), (C.CAPAS_DISTINTAS,))

    def prueba_reordenar_el_panel_no_es_un_cambio(self):
        copia = replace(self.rios, id_capa="rios_copia", nombre="rios copia")
        datos = dict(self.datos_base, rios_copia=replace(self.datos_base["rios"], id_capa="rios_copia"))
        anterior = self.plan([self.rios, copia, self.lagos], datos)
        self.assertTrue(revalidar(anterior, self.plan([copia, self.lagos, self.rios], datos)).vigente)

    def prueba_solo_se_revalidan_las_unidades_seleccionadas(self):
        clave_lagos = self.anterior.unidad_de_capa("lagos").clave_unidad
        solo_rios = self.plan(self.entradas, self.datos_base,
                              seleccion=[self.anterior.unidad_de_capa("rios").clave_unidad])
        self.assertNotIn(clave_lagos, solo_rios.seleccionadas)
        resultado = revalidar(solo_rios, self.actual(lagos=dict(en_edicion=True)))
        self.assertTrue(resultado.vigente)

    def prueba_texto_de_cada_motivo(self):
        from geoguardian.dominio.revalidacion import TEXTO_CAMBIO
        self.assertEqual(set(TEXTO_CAMBIO), set(C))
        self.assertTrue(all(TEXTO_CAMBIO[m].endswith(".") for m in C))
        self.assertNotIn("reproyect", " ".join(TEXTO_CAMBIO.values()).lower())

    def prueba_no_modifica_los_planes(self):
        antes = (self.anterior, os.listdir(self.externa))
        revalidar(self.anterior, self.actual(rios=dict(en_edicion=True)))
        self.assertEqual(antes, (self.anterior, os.listdir(self.externa)))


if __name__ == "__main__":
    unittest.main()
