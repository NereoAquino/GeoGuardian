"""Utilidades compartidas por las pruebas unitarias."""

import sqlite3


def contenedor_falso(ruta):
    """Sustituye a GDAL en pruebas: crea solo la tabla gpkg_contents del estandar."""
    con = sqlite3.connect(str(ruta))
    con.execute(
        "CREATE TABLE gpkg_contents (table_name TEXT NOT NULL PRIMARY KEY, data_type TEXT NOT NULL,"
        " identifier TEXT UNIQUE, description TEXT DEFAULT '', last_change DATETIME NOT NULL,"
        " min_x DOUBLE, min_y DOUBLE, max_x DOUBLE, max_y DOUBLE, srs_id INTEGER)"
    )
    con.commit()
    con.close()


# Esquema exacto de gg_* en GeoGuardian 0.1.0-rc1 (version_esquema = 1), para probar la migracion.
ESQUEMA_RC1 = (
    """CREATE TABLE gg_proyecto (
        id_proyecto TEXT PRIMARY KEY, titulo TEXT NOT NULL, descripcion TEXT,
        nombre_estudiante TEXT NOT NULL, correo TEXT NOT NULL, grupo TEXT NOT NULL,
        asignatura TEXT NOT NULL, fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
        version_esquema INTEGER NOT NULL, version_complemento TEXT NOT NULL, version_qgis TEXT NOT NULL)""",
    """CREATE TABLE gg_recursos (
        id_recurso INTEGER PRIMARY KEY AUTOINCREMENT, id_capa TEXT NOT NULL, nombre TEXT NOT NULL,
        tipo_capa TEXT NOT NULL, proveedor TEXT NOT NULL, fuente TEXT NOT NULL, ruta_relativa TEXT,
        estado TEXT NOT NULL CHECK (estado IN ('activo','externo','temporal','historico','faltante')),
        fecha_alta TEXT NOT NULL, fecha_baja TEXT, fecha_verificacion TEXT NOT NULL)""",
    """CREATE TABLE gg_eventos (
        id_evento INTEGER PRIMARY KEY AUTOINCREMENT, fecha_hora TEXT NOT NULL, tipo_evento TEXT NOT NULL,
        id_capa TEXT, descripcion TEXT NOT NULL, detalle TEXT, version_complemento TEXT NOT NULL)""",
    "INSERT INTO gg_proyecto VALUES ('uuid-rc1', 'Manglares', '', 'Ana Perez', 'ana@x.mx', '5A',"
    " 'Modulo II', 'f1', 'f1', 1, '0.1.0-rc1', '3.28.15')",
)


def geopaquete_rc1(ruta):
    contenedor_falso(ruta)
    con = sqlite3.connect(str(ruta))
    for sentencia in ESQUEMA_RC1:
        con.execute(sentencia)
    con.commit()
    con.close()


def geopaquete_rc2(ruta):
    """Proyecto.gpkg como lo creaba la primera entrega de rc2 (version_esquema = 2)."""
    geopaquete_rc1(ruta)
    con = sqlite3.connect(str(ruta))
    for columna in ("nombre_academico", "ruta_proyecto_origen", "ruta_proyecto_administrado",
                    "ruta_respaldo", "tipo_ubicacion"):
        con.execute("ALTER TABLE gg_proyecto ADD COLUMN {} TEXT".format(columna))
    con.execute(
        "UPDATE gg_proyecto SET version_esquema = 2, nombre_academico = 'Manglares - Ana Perez',"
        " ruta_proyecto_administrado = 'E:/rc2/Manglares.qgz', tipo_ubicacion = 'unidad_externa'"
    )
    con.commit()
    con.close()
