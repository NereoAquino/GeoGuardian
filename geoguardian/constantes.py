"""Valores fijos de GeoGuardian. Modulo puro: solo biblioteca estandar."""

VERSION_COMPLEMENTO = "0.1.0"
VERSION_ESQUEMA = 3

NOMBRE_COMPLEMENTO = "GeoGuardian"

NOMBRE_ARCHIVO_PROYECTO = "Proyecto.qgz"
NOMBRE_GEOPAQUETE = "Proyecto.gpkg"
CARPETA_GEOGUARDIAN = ".geoguardian"
NOMBRE_MANIFIESTO = "manifiesto.json"
FORMATO_MANIFIESTO = "geoguardian-manifiesto"

# Carpetas creadas al inicializar (D-03).
CARPETAS_PROYECTO = ("datos", "salidas", "documentos", CARPETA_GEOGUARDIAN)

# Proyectos adoptados: origen -> administrado, en la configuracion del perfil de QGIS (D-22).
CLAVE_ADOPCIONES = "geoguardian/adopciones"

# Entradas personalizadas guardadas dentro del .qgz (D-08).
AMBITO_PROPIEDADES = "geoguardian"
CLAVE_ID_PROYECTO = "/id_proyecto"

TABLA_PROYECTO = "gg_proyecto"
TABLA_RECURSOS = "gg_recursos"
TABLA_EVENTOS = "gg_eventos"
TABLAS_CONTROL = (TABLA_PROYECTO, TABLA_RECURSOS, TABLA_EVENTOS)

# Proveedor QGIS de capas en memoria (valor de la API de QGIS).
PROVEEDOR_MEMORIA = "memory"

ETIQUETA_REGISTRO = "GeoGuardian"
