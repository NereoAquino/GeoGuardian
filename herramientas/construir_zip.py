"""Construye el ZIP instalable del complemento: dist/geoguardian-<version>.zip.

Uso: python herramientas/construir_zip.py
Instalar en QGIS: Complementos > Administrar e instalar complementos > Instalar a partir de ZIP.
"""

import configparser
import os
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(RAIZ, "geoguardian")
EXCLUIR = ("__pycache__", ".pyc", ".pyo")


def principal():
    metadatos = configparser.ConfigParser()
    metadatos.read(os.path.join(CARPETA, "metadata.txt"), encoding="utf-8")
    version = metadatos["general"]["version"]
    destino = os.path.join(RAIZ, "dist", "geoguardian-{}.zip".format(version))
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as archivo_zip:
        for raiz, carpetas, archivos in os.walk(CARPETA):
            carpetas[:] = sorted(c for c in carpetas if c not in EXCLUIR)
            for nombre in sorted(archivos):
                if nombre.endswith(EXCLUIR):
                    continue
                ruta = os.path.join(raiz, nombre)
                archivo_zip.write(ruta, os.path.relpath(ruta, RAIZ))
    print(destino)


if __name__ == "__main__":
    principal()
