import os
import sqlite3
import tempfile
import unittest

from geoguardian.constantes import VERSION_COMPLEMENTO
from geoguardian.dominio.modelos import DatosProyecto, EstadoRecurso as E, Recurso, TipoEvento
from geoguardian.eventos.registro_eventos import RegistroEventos
from geoguardian.persistencia.geopaquete import (
    ErrorGeopaquete,
    crear_geopaquete,
    problemas_esquema,
    tablas_presentes,
)
from geoguardian.persistencia.repositorio import RepositorioGeoGuardian

from .apoyo import contenedor_falso

FECHA = "2026-10-18T15:54:13-06:00"


def recurso(id_capa="capa_1", estado=E.EXTERNO):
    return Recurso(
        id_capa=id_capa, nombre="Manglares", tipo_capa="vectorial", proveedor="ogr",
        fuente="/datos/m.shp", ruta_relativa=None, estado=estado,
        fecha_alta=FECHA, fecha_verificacion=FECHA,
    )


class PruebaPersistencia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self._tmp.name, "Proyecto.gpkg")
        crear_geopaquete(self.ruta, FECHA, crear_contenedor=contenedor_falso)
        self.repo = RepositorioGeoGuardian(self.ruta)

    def tearDown(self):
        self._tmp.cleanup()

    def prueba_esquema_y_gpkg_contents(self):
        self.assertTrue({"gg_proyecto", "gg_recursos", "gg_eventos"} <= tablas_presentes(self.ruta))
        self.assertEqual(problemas_esquema(self.ruta), [])
        con = sqlite3.connect(self.ruta)
        filas = con.execute("SELECT table_name, data_type, last_change FROM gpkg_contents").fetchall()
        con.close()
        self.assertEqual({f[1] for f in filas}, {"attributes"})
        self.assertEqual(filas[0][2], "2026-10-18T21:54:13.000Z")

    def prueba_no_sobrescribe(self):
        with self.assertRaises(ErrorGeopaquete):
            crear_geopaquete(self.ruta, FECHA, crear_contenedor=contenedor_falso)

    def prueba_problemas_esquema(self):
        self.assertTrue(problemas_esquema(os.path.join(self._tmp.name, "otro.gpkg")))
        con = sqlite3.connect(self.ruta)
        con.execute("DROP TABLE gg_eventos")
        con.commit()
        con.close()
        self.assertIn("gg_eventos", problemas_esquema(self.ruta)[0])

    def prueba_proyecto_ida_y_vuelta(self):
        datos = DatosProyecto("Ana Pérez", "ana@x.mx", "Manglares", "Descripción", "5A", "Módulo II")
        self.repo.insertar_proyecto("uuid-1", datos, FECHA, "3.28.15")
        fila = self.repo.obtener_proyecto()
        self.assertEqual(fila["nombre_estudiante"], "Ana Pérez")
        self.assertEqual(fila["version_esquema"], 3)
        self.repo.actualizar_fecha_proyecto("2026-10-19T10:00:00-06:00")
        self.assertEqual(self.repo.obtener_proyecto()["fecha_actualizacion"], "2026-10-19T10:00:00-06:00")

    def prueba_sin_fila_de_proyecto(self):
        self.assertIsNone(self.repo.obtener_proyecto())

    def prueba_alta_y_baja_de_recursos(self):
        self.repo.alta_recurso(recurso("a"))
        self.repo.alta_recurso(recurso("b", E.TEMPORAL))
        anterior = self.repo.marcar_historico("a", "2026-10-18T16:00:00-06:00")
        self.assertEqual(anterior.estado, E.EXTERNO)
        self.assertEqual([r.id_capa for r in self.repo.recursos_vigentes()], ["b"])
        historico = [r for r in self.repo.todos_los_recursos() if r.id_capa == "a"][0]
        self.assertEqual(historico.estado, E.HISTORICO)
        self.assertEqual(historico.fecha_baja, "2026-10-18T16:00:00-06:00")
        conteo = self.repo.conteo_por_estado()
        self.assertEqual((conteo[E.HISTORICO], conteo[E.TEMPORAL], conteo[E.ACTIVO]), (1, 1, 0))
        self.assertIsNone(self.repo.marcar_historico("no_existe", FECHA))

    def prueba_actualizar_recurso(self):
        r = recurso()
        self.repo.alta_recurso(r)
        r.estado = E.FALTANTE
        self.repo.actualizar_recurso(r)
        self.assertEqual(self.repo.recurso_vigente("capa_1").estado, E.FALTANTE)

    def prueba_estado_invalido_rechazado_por_la_base(self):
        con = sqlite3.connect(self.ruta)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO gg_recursos (id_capa, nombre, tipo_capa, proveedor, fuente, estado,"
                " fecha_alta, fecha_verificacion) VALUES ('x','x','x','x','x','active','f','f')"
            )
        con.close()

    def prueba_registro_eventos(self):
        registro = RegistroEventos(self.repo, reloj=lambda: FECHA)
        registro.registrar(TipoEvento.CAPA_AGREGADA, "Se agregó Manglares", id_capa="a",
                           detalle={"nombre": "Manglares", "estado": "externo"})
        registro.registrar(TipoEvento.PROYECTO_GUARDADO, "Guardado")
        eventos = self.repo.eventos()
        self.assertEqual(len(eventos), 2)
        self.assertEqual(eventos[0].detalle["nombre"], "Manglares")
        self.assertEqual(eventos[0].fecha_hora, FECHA)
        self.assertEqual(eventos[0].version_complemento, VERSION_COMPLEMENTO)
        self.assertEqual(len(self.repo.eventos(TipoEvento.PROYECTO_GUARDADO)), 1)

    def prueba_sin_archivos_wal(self):
        self.repo.alta_recurso(recurso())
        self.assertEqual(sorted(os.listdir(self._tmp.name)), ["Proyecto.gpkg"])
