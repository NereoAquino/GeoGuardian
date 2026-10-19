"""Nombre academico: PRACTICA O PROYECTO - NOMBRE DEL ESTUDIANTE (D-19, D-20). Modulo puro."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

from .validacion import validar_nombre_carpeta

SEPARADOR = " - "
LONGITUD_MAXIMA_ARCHIVO = 80
PARTICULAS = frozenset({"de", "del", "la", "las", "los", "y", "e"})

# Separador entre practica y estudiante: un guion con espacio o '_' a ambos lados.
# "uso-de-suelo" no se parte.
_PATRON_SEPARADOR = re.compile(r"(?:\s|_)+[-–—](?:\s|_)+")
_PATRON_FICHA = re.compile(r"[^\s_]+")
_CARACTERES_INVALIDOS = set('<>:"/\\|?*')
_NOMBRES_RESERVADOS_WINDOWS = (
    {"CON", "PRN", "AUX", "NUL"}
    | {"COM{}".format(i) for i in range(1, 10)}
    | {"LPT{}".format(i) for i in range(1, 10)}
)


def sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    """Minusculas, sin acentos, '_' como espacio y espacios repetidos colapsados."""
    texto = sin_acentos(texto).casefold().replace("_", " ")
    return re.sub(r"\s+", " ", texto).strip()


def palabras(texto: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", normalizar(texto))


def palabras_significativas(texto: str) -> List[str]:
    significativas = [p for p in palabras(texto) if len(p) >= 2 and p not in PARTICULAS]
    return significativas or palabras(texto)


def contiene_estudiante(texto: str, estudiante: str) -> bool:
    """Al menos 2 palabras significativas del estudiante (o todas, si tiene menos de 2)."""
    requeridas = palabras_significativas(estudiante)
    if not requeridas:
        return False
    presentes = set(palabras(texto))
    encontradas = sum(1 for p in requeridas if p in presentes)
    return encontradas >= min(2, len(requeridas))


def componer(practica: str, estudiante: str) -> str:
    return re.sub(r"\s+", " ", "{}{}{}".format(practica.strip(), SEPARADOR, estudiante.strip()))


@dataclass(frozen=True)
class AnalisisNombre:
    practica_detectada: str
    contiene_estudiante: bool
    estructura_completa: bool
    nombre_propuesto: Optional[str]  # None si se conserva el nombre o no hay base para proponer


def analizar_nombre(nombre_actual: str, estudiante: str) -> AnalisisNombre:
    texto = re.sub(r"\s+", " ", (nombre_actual or "").strip())
    contiene = contiene_estudiante(texto, estudiante)
    partes = _PATRON_SEPARADOR.split(texto)
    if len(partes) >= 2:
        practica = SEPARADOR.join(p.strip() for p in partes[:-1]).strip()
        if palabras(practica) and contiene_estudiante(partes[-1], estudiante):
            return AnalisisNombre(practica, contiene, True, None)
    practica = quitar_estudiante(texto, estudiante)
    if not palabras(practica):
        return AnalisisNombre("", contiene, False, None)
    return AnalisisNombre(practica, contiene, False, componer(practica, estudiante))


def quitar_estudiante(texto: str, estudiante: str) -> str:
    """Quita del texto las palabras significativas del estudiante y los separadores sueltos."""
    del_estudiante = set(palabras_significativas(estudiante))
    fichas = [
        f for f in _PATRON_FICHA.findall(texto or "")
        if not (palabras(f) and all(p in del_estudiante for p in palabras(f)))
    ]

    def sobrante(ficha: str) -> bool:
        return not palabras(ficha) or normalizar(ficha) in PARTICULAS

    while fichas and sobrante(fichas[0]):
        fichas.pop(0)
    while fichas and sobrante(fichas[-1]):
        fichas.pop()
    resultado = " ".join(fichas)
    return re.sub(r"(\s-\s)+", SEPARADOR, resultado).strip()


def nombre_de_archivo(nombre_academico: str) -> str:
    """Nombre de carpeta y .qgz: sin acentos ni n con tilde, sin caracteres invalidos, maximo 80."""
    texto = "".join(
        c if c.isascii() and c.isprintable() and c not in _CARACTERES_INVALIDOS else " "
        for c in sin_acentos(nombre_academico)
    )
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = texto[:LONGITUD_MAXIMA_ARCHIVO].rstrip(" .")
    if texto.split(".")[0].strip().upper() in _NOMBRES_RESERVADOS_WINDOWS:
        texto += "_"
    return texto


def practica_de(nombre_academico: str, estudiante: str) -> str:
    """Parte de la practica de un nombre academico valido."""
    return analizar_nombre(nombre_academico, estudiante).practica_detectada


def validar_nombre_academico(nombre: str, estudiante: str) -> List[str]:
    if not (nombre or "").strip():
        return ["Escribe el nombre final del proyecto administrado"]
    errores = []
    analisis = analizar_nombre(nombre, estudiante)
    if not analisis.contiene_estudiante:
        errores.append("El nombre debe incluir el nombre del estudiante")
    if not analisis.estructura_completa:
        errores.append("El nombre debe tener la forma «NOMBRE DE LA PRACTICA O PROYECTO - NOMBRE DEL ESTUDIANTE»")
    archivo = nombre_de_archivo(nombre)
    if not archivo:
        errores.append("El nombre no produce un nombre de archivo válido")
    else:
        errores.extend(validar_nombre_carpeta(archivo))
    return errores
