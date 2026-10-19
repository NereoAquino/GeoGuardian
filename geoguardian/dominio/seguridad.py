"""Eliminacion de credenciales en textos de fuentes de datos (D-13). Modulo puro."""

import re

_PATRONES = (
    # password='...' o password="..." (URI de QGIS para bases de datos)
    (re.compile(r"(password\s*=\s*)'(?:[^'\\]|\\.)*'", re.IGNORECASE), r"\1'***'"),
    (re.compile(r'(password\s*=\s*)"(?:[^"\\]|\\.)*"', re.IGNORECASE), r'\1"***"'),
    # password=valor sin comillas, en URI o parametros de URL
    (re.compile(r"((?:password|pwd|passwd)\s*=\s*)(?!['\"*])[^\s&;']+", re.IGNORECASE), r"\1***"),
    # usuario:contrasena@ en URL
    (re.compile(r"(://[^/:@\s]+):[^/@\s]+@"), r"\1:***@"),
)


def ocultar_contrasenas(texto: str) -> str:
    for patron, reemplazo in _PATRONES:
        texto = patron.sub(reemplazo, texto)
    return texto
