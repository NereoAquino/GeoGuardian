"""GeoGuardian: gestion, trazabilidad y entrega de proyectos QGIS."""


def classFactory(iface):  # noqa: N802  (nombre exigido por QGIS)
    # Importacion diferida: permite importar los subpaquetes puros
    # (dominio, persistencia, manifiesto) sin tener QGIS instalado.
    from .complemento import ComplementoGeoGuardian

    return ComplementoGeoGuardian(iface)
