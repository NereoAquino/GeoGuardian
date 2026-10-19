"""Lecturas y escrituras de las tablas gg_* (sin Qt ni QGIS)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from ..constantes import (
    TABLA_EVENTOS,
    TABLA_PROYECTO,
    TABLA_RECURSOS,
    VERSION_COMPLEMENTO,
    VERSION_ESQUEMA,
)
from ..dominio.modelos import DatosProyecto, EstadoRecurso, Evento, Recurso, TipoEvento
from .geopaquete import transaccion


class RepositorioGeoGuardian:
    def __init__(self, ruta_geopaquete: Union[str, Path]):
        self.ruta = Path(ruta_geopaquete)

    # --- gg_proyecto -------------------------------------------------------

    def insertar_proyecto(
        self,
        id_proyecto: str,
        datos: DatosProyecto,
        fecha: str,
        version_qgis: str,
        nombre_academico: Optional[str] = None,
        ruta_proyecto_origen: Optional[str] = None,
        ruta_proyecto_administrado: Optional[str] = None,
        ruta_respaldo: Optional[str] = None,
        tipo_ubicacion: Optional[str] = None,
        etiqueta_volumen: Optional[str] = None,
        sistema_archivos: Optional[str] = None,
        ruta_en_volumen: Optional[str] = None,
        etiqueta_volumen_respaldo: Optional[str] = None,
        ruta_respaldo_en_volumen: Optional[str] = None,
    ) -> None:
        with transaccion(self.ruta) as con:
            con.execute(
                "INSERT INTO {t} (id_proyecto, titulo, descripcion, nombre_estudiante, correo,"
                " grupo, asignatura, fecha_creacion, fecha_actualizacion, version_esquema,"
                " version_complemento, version_qgis, nombre_academico, ruta_proyecto_origen,"
                " ruta_proyecto_administrado, ruta_respaldo, tipo_ubicacion, etiqueta_volumen,"
                " sistema_archivos, ruta_en_volumen, etiqueta_volumen_respaldo, ruta_respaldo_en_volumen)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)".format(t=TABLA_PROYECTO),
                (
                    id_proyecto,
                    datos.titulo.strip(),
                    (datos.descripcion or "").strip(),
                    datos.nombre_estudiante.strip(),
                    datos.correo.strip(),
                    datos.grupo.strip(),
                    datos.asignatura.strip(),
                    fecha,
                    fecha,
                    VERSION_ESQUEMA,
                    VERSION_COMPLEMENTO,
                    version_qgis,
                    nombre_academico,
                    ruta_proyecto_origen,
                    ruta_proyecto_administrado,
                    ruta_respaldo,
                    tipo_ubicacion,
                    etiqueta_volumen,
                    sistema_archivos,
                    ruta_en_volumen,
                    etiqueta_volumen_respaldo,
                    ruta_respaldo_en_volumen,
                ),
            )

    def actualizar_ubicacion(
        self, ruta_proyecto_administrado: str, etiqueta_volumen: str, sistema_archivos: str, ruta_en_volumen: str
    ) -> None:
        """Ubicacion actual del .qgz administrado (D-33): la letra de unidad puede haber cambiado."""
        with transaccion(self.ruta) as con:
            con.execute(
                "UPDATE {t} SET ruta_proyecto_administrado = ?, etiqueta_volumen = ?,"
                " sistema_archivos = ?, ruta_en_volumen = ?".format(t=TABLA_PROYECTO),
                (ruta_proyecto_administrado, etiqueta_volumen, sistema_archivos, ruta_en_volumen),
            )

    def obtener_proyecto(self) -> Optional[Dict[str, object]]:
        with transaccion(self.ruta) as con:
            filas = con.execute("SELECT * FROM {t}".format(t=TABLA_PROYECTO)).fetchall()
        if len(filas) != 1:
            return None
        return dict(filas[0])

    def actualizar_fecha_proyecto(self, fecha: str) -> None:
        with transaccion(self.ruta) as con:
            con.execute(
                "UPDATE {t} SET fecha_actualizacion = ?".format(t=TABLA_PROYECTO), (fecha,)
            )

    # --- gg_recursos -------------------------------------------------------

    def alta_recurso(self, recurso: Recurso) -> int:
        with transaccion(self.ruta) as con:
            cursor = con.execute(
                "INSERT INTO {t} (id_capa, nombre, tipo_capa, proveedor, fuente, ruta_relativa,"
                " estado, fecha_alta, fecha_baja, fecha_verificacion)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)".format(t=TABLA_RECURSOS),
                (
                    recurso.id_capa,
                    recurso.nombre,
                    recurso.tipo_capa,
                    recurso.proveedor,
                    recurso.fuente,
                    recurso.ruta_relativa,
                    EstadoRecurso(recurso.estado).value,
                    recurso.fecha_alta,
                    recurso.fecha_baja,
                    recurso.fecha_verificacion,
                ),
            )
            recurso.id_recurso = cursor.lastrowid
        return recurso.id_recurso

    def recursos_vigentes(self) -> List[Recurso]:
        """Recursos que siguen en el proyecto (todo lo que no es historico)."""
        return self._recursos(
            "WHERE estado != ? ORDER BY id_recurso", (EstadoRecurso.HISTORICO.value,)
        )

    def todos_los_recursos(self) -> List[Recurso]:
        return self._recursos("ORDER BY id_recurso", ())

    def recurso_vigente(self, id_capa: str) -> Optional[Recurso]:
        recursos = self._recursos(
            "WHERE id_capa = ? AND estado != ? ORDER BY id_recurso DESC LIMIT 1",
            (id_capa, EstadoRecurso.HISTORICO.value),
        )
        return recursos[0] if recursos else None

    def actualizar_recurso(self, recurso: Recurso) -> None:
        """Actualiza estado, nombre, fuente y fecha de verificacion de un recurso existente."""
        with transaccion(self.ruta) as con:
            con.execute(
                "UPDATE {t} SET nombre = ?, fuente = ?, ruta_relativa = ?, estado = ?,"
                " fecha_baja = ?, fecha_verificacion = ? WHERE id_recurso = ?".format(
                    t=TABLA_RECURSOS
                ),
                (
                    recurso.nombre,
                    recurso.fuente,
                    recurso.ruta_relativa,
                    EstadoRecurso(recurso.estado).value,
                    recurso.fecha_baja,
                    recurso.fecha_verificacion,
                    recurso.id_recurso,
                ),
            )

    def marcar_historico(self, id_capa: str, fecha: str) -> Optional[Recurso]:
        """Pasa a historico el recurso vigente de la capa; devuelve su estado previo."""
        recurso = self.recurso_vigente(id_capa)
        if recurso is None:
            return None
        anterior = Recurso(**vars(recurso))
        recurso.estado = EstadoRecurso.HISTORICO
        recurso.fecha_baja = fecha
        recurso.fecha_verificacion = fecha
        self.actualizar_recurso(recurso)
        return anterior

    def conteo_por_estado(self) -> Dict[EstadoRecurso, int]:
        conteo = {estado: 0 for estado in EstadoRecurso}
        with transaccion(self.ruta) as con:
            filas = con.execute(
                "SELECT estado, COUNT(*) AS n FROM {t} GROUP BY estado".format(t=TABLA_RECURSOS)
            ).fetchall()
        for fila in filas:
            conteo[EstadoRecurso(fila["estado"])] = fila["n"]
        return conteo

    def _recursos(self, condicion: str, parametros: tuple) -> List[Recurso]:
        with transaccion(self.ruta) as con:
            filas = con.execute(
                "SELECT * FROM {t} {c}".format(t=TABLA_RECURSOS, c=condicion), parametros
            ).fetchall()
        return [
            Recurso(
                id_recurso=f["id_recurso"],
                id_capa=f["id_capa"],
                nombre=f["nombre"],
                tipo_capa=f["tipo_capa"],
                proveedor=f["proveedor"],
                fuente=f["fuente"],
                ruta_relativa=f["ruta_relativa"],
                estado=EstadoRecurso(f["estado"]),
                fecha_alta=f["fecha_alta"],
                fecha_baja=f["fecha_baja"],
                fecha_verificacion=f["fecha_verificacion"],
            )
            for f in filas
        ]

    # --- gg_eventos --------------------------------------------------------

    def insertar_evento(self, evento: Evento) -> int:
        detalle = (
            json.dumps(evento.detalle, ensure_ascii=False, sort_keys=True)
            if evento.detalle is not None
            else None
        )
        with transaccion(self.ruta) as con:
            cursor = con.execute(
                "INSERT INTO {t} (fecha_hora, tipo_evento, id_capa, descripcion, detalle,"
                " version_complemento) VALUES (?, ?, ?, ?, ?, ?)".format(t=TABLA_EVENTOS),
                (
                    evento.fecha_hora,
                    TipoEvento(evento.tipo_evento).value,
                    evento.id_capa,
                    evento.descripcion,
                    detalle,
                    evento.version_complemento,
                ),
            )
            evento.id_evento = cursor.lastrowid
        return evento.id_evento

    def eventos(self, tipo: Optional[TipoEvento] = None) -> List[Evento]:
        condicion, parametros = ("", ())
        if tipo is not None:
            condicion, parametros = ("WHERE tipo_evento = ?", (TipoEvento(tipo).value,))
        with transaccion(self.ruta) as con:
            filas = con.execute(
                "SELECT * FROM {t} {c} ORDER BY id_evento".format(t=TABLA_EVENTOS, c=condicion),
                parametros,
            ).fetchall()
        return [
            Evento(
                id_evento=f["id_evento"],
                fecha_hora=f["fecha_hora"],
                tipo_evento=TipoEvento(f["tipo_evento"]),
                id_capa=f["id_capa"],
                descripcion=f["descripcion"],
                detalle=json.loads(f["detalle"]) if f["detalle"] else None,
                version_complemento=f["version_complemento"],
            )
            for f in filas
        ]
