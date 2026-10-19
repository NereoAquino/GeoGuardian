"""Validacion de los datos del asistente. Modulo puro."""

from __future__ import annotations

import re
import unicodedata
from typing import List

from .modelos import DatosProyecto

LONGITUD_MAXIMA_CARPETA = 100

_PATRON_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CARACTERES_INVALIDOS = set('<>:"/\\|?*')
_NOMBRES_RESERVADOS_WINDOWS = (
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM{}".format(i) for i in range(1, 10)}
    | {"LPT{}".format(i) for i in range(1, 10)}
)

_CAMPOS_OBLIGATORIOS = (
    ("nombre_estudiante", "El nombre del estudiante es obligatorio"),
    ("correo", "El correo es obligatorio"),
    ("titulo", "El titulo del proyecto es obligatorio"),
    ("grupo", "El grupo es obligatorio"),
    ("asignatura", "La asignatura o modulo es obligatoria"),
)


def validar_datos_proyecto(datos: DatosProyecto) -> List[str]:
    errores = []
    for campo, mensaje in _CAMPOS_OBLIGATORIOS:
        if not (getattr(datos, campo) or "").strip():
            errores.append(mensaje)
    correo = (datos.correo or "").strip()
    if correo and not _PATRON_CORREO.match(correo):
        errores.append("El correo no tiene la forma nombre@dominio.ext")
    return errores


def validar_nombre_carpeta(nombre: str) -> List[str]:
    nombre = nombre or ""
    if not nombre.strip():
        return ["El nombre de la carpeta es obligatorio"]
    errores = []
    if any(c in _CARACTERES_INVALIDOS or ord(c) < 32 for c in nombre):
        errores.append('El nombre de la carpeta no puede contener < > : " / \\ | ? *')
    if nombre.split(".")[0].strip().upper() in _NOMBRES_RESERVADOS_WINDOWS:
        errores.append("El nombre de la carpeta esta reservado por Windows")
    if nombre != nombre.strip() or nombre.endswith("."):
        errores.append("El nombre de la carpeta no puede empezar o terminar con espacio ni terminar con punto")
    if len(nombre) > LONGITUD_MAXIMA_CARPETA:
        errores.append(
            "El nombre de la carpeta no puede pasar de {} caracteres".format(LONGITUD_MAXIMA_CARPETA)
        )
    return errores


def sugerir_nombre_carpeta(titulo: str) -> str:
    """Titulo sin acentos, con '_' en lugar de espacios y caracteres invalidos."""
    sin_acentos = unicodedata.normalize("NFKD", titulo or "")
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    limpio = "".join(
        c if (c.isalnum() and c.isascii()) or c in "-_" else "_" for c in sin_acentos.strip()
    )
    limpio = re.sub(r"_+", "_", limpio).strip("_")
    return limpio[:LONGITUD_MAXIMA_CARPETA]
