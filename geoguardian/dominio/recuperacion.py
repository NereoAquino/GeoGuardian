"""Identidad de una ubicacion y recuperacion cuando cambia la letra de unidad (D-33, D-34).

Modulo puro: no consulta discos. La letra de unidad es circunstancial; la identidad es la
etiqueta del volumen mas la ruta dentro del volumen, y la confirma el id_proyecto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional

from .ubicacion import InfoVolumen

MENSAJE_UNIDAD_NO_ENCONTRADA = (
    "No se encuentra la unidad utilizada por este proyecto. Windows puede haberle asignado otra "
    "letra o la unidad puede estar desconectada."
)
BOTON_LOCALIZAR = "Localizar unidad o carpeta"

_PATRON_UNIDAD = re.compile(r"^([A-Za-z]:)(?:[\\/]|$)")
_PATRON_UNC = re.compile(r"^([\\/]{2}[^\\/]+[\\/][^\\/]+)(?:[\\/]|$)")


@dataclass(frozen=True)
class IdentidadUbicacion:
    """Donde esta un archivo: ruta absoluta (circunstancial) e identidad del volumen."""

    ruta: str
    etiqueta_volumen: str = ""
    sistema_archivos: str = ""
    ruta_en_volumen: str = ""

    def a_dict(self) -> Dict[str, str]:
        return {
            "ruta": self.ruta,
            "etiqueta_volumen": self.etiqueta_volumen,
            "sistema_archivos": self.sistema_archivos,
            "ruta_en_volumen": self.ruta_en_volumen,
        }

    @classmethod
    def de_dict(cls, datos) -> Optional["IdentidadUbicacion"]:
        if isinstance(datos, str):
            return cls(ruta=datos) if datos else None  # formato anterior: solo la ruta
        if not isinstance(datos, dict) or not datos.get("ruta"):
            return None
        return cls(
            ruta=str(datos["ruta"]),
            etiqueta_volumen=str(datos.get("etiqueta_volumen") or ""),
            sistema_archivos=str(datos.get("sistema_archivos") or ""),
            ruta_en_volumen=str(datos.get("ruta_en_volumen") or ""),
        )


def _barras(ruta: str) -> str:
    return (ruta or "").replace("\\", "/")


def ruta_en_volumen(ruta: str, raiz_volumen: str) -> str:
    """Ruta relativa a la raiz del volumen, con '/'. Vacia si `ruta` no esta en ese volumen."""
    ruta_b = _barras(ruta)
    raiz_b = _barras(raiz_volumen).rstrip("/")
    if not ruta_b:
        return ""
    prefijo = raiz_b + "/"
    if not ruta_b.casefold().startswith(prefijo.casefold()):
        return ""
    return ruta_b[len(prefijo):].strip("/")


def reconstruir(raiz_volumen: str, relativa: str) -> str:
    """Ruta absoluta de `relativa` dentro de otro volumen (con '/'; Windows la acepta)."""
    return _barras(raiz_volumen).rstrip("/") + "/" + relativa.strip("/")


def identidad(ruta: str, volumen: Optional[InfoVolumen]) -> IdentidadUbicacion:
    if volumen is None:
        return IdentidadUbicacion(ruta=ruta)
    return IdentidadUbicacion(
        ruta=ruta,
        etiqueta_volumen=volumen.etiqueta,
        sistema_archivos=volumen.sistema_archivos,
        ruta_en_volumen=ruta_en_volumen(ruta, volumen.raiz),
    )


def raiz_unidad(ruta: str) -> Optional[str]:
    """`E:/` o `//servidor/recurso/` si la ruta empieza por una unidad de Windows; si no, None."""
    texto = ruta or ""
    for patron in (_PATRON_UNIDAD, _PATRON_UNC):
        coincidencia = patron.match(texto)
        if coincidencia:
            return _barras(coincidencia.group(1)) + "/"
    return None


def unidad_ausente(ruta: str, existe: Callable[[str], bool]) -> bool:
    """La ruta esta en una unidad de Windows que ahora no existe (desconectada u otra letra)."""
    raiz = raiz_unidad(ruta)
    return raiz is not None and not existe(raiz)


def id_valido(ids_leidos: Dict[str, str], id_esperado: str) -> bool:
    """Todas las fuentes leidas (.qgz, manifiesto, GPKG) coinciden con el id esperado (D-34.3)."""
    return bool(id_esperado) and bool(ids_leidos) and all(v == id_esperado for v in ids_leidos.values())


class Resultado(str, Enum):
    ENCONTRADA = "encontrada"
    VARIAS = "varias"
    ID_DISTINTO = "id_distinto"
    NO_ENCONTRADA = "no_encontrada"


@dataclass
class Recuperacion:
    resultado: Resultado
    ruta: Optional[str] = None  # solo con ENCONTRADA
    candidatas: List[str] = field(default_factory=list)  # con VARIAS


def recuperar(
    registrada: IdentidadUbicacion,
    id_esperado: str,
    volumenes: Iterable[InfoVolumen],
    existe: Callable[[str], bool],
    leer_ids: Callable[[str], Dict[str, str]],
) -> Recuperacion:
    """Resuelve donde esta ahora un proyecto administrado registrado (D-34, reglas 1-6)."""
    if existe(registrada.ruta) and id_valido(leer_ids(registrada.ruta), id_esperado):
        return Recuperacion(Resultado.ENCONTRADA, ruta=registrada.ruta)

    etiqueta = registrada.etiqueta_volumen.strip()
    if not etiqueta or not registrada.ruta_en_volumen or not id_esperado:
        return Recuperacion(Resultado.NO_ENCONTRADA)

    validas: List[str] = []
    otro_proyecto = False
    vistas = set()
    for volumen in volumenes:
        if volumen.etiqueta.strip().casefold() != etiqueta.casefold():
            continue
        candidata = reconstruir(volumen.raiz, registrada.ruta_en_volumen)
        clave = candidata.casefold()
        if clave in vistas or not existe(candidata):
            continue
        vistas.add(clave)
        if id_valido(leer_ids(candidata), id_esperado):
            validas.append(candidata)
        else:
            otro_proyecto = True

    if len(validas) == 1:
        return Recuperacion(Resultado.ENCONTRADA, ruta=validas[0])
    if len(validas) > 1:
        return Recuperacion(Resultado.VARIAS, candidatas=validas)
    if otro_proyecto:
        return Recuperacion(Resultado.ID_DISTINTO)
    return Recuperacion(Resultado.NO_ENCONTRADA)


def rutas_a_probar(carpeta_elegida: str, registrada: IdentidadUbicacion) -> List[str]:
    """Donde buscar el .qgz cuando el estudiante localiza a mano (D-34.7).

    Se acepta la raiz de la unidad, la carpeta del proyecto o la carpeta que la contiene.
    """
    nombre_qgz = _barras(registrada.ruta).rsplit("/", 1)[-1]
    partes = _barras(registrada.ruta).rsplit("/", 2)
    carpeta_proyecto = partes[-2] if len(partes) >= 2 else ""
    rutas = []
    if registrada.ruta_en_volumen:
        rutas.append(reconstruir(carpeta_elegida, registrada.ruta_en_volumen))
    if nombre_qgz:
        rutas.append(reconstruir(carpeta_elegida, nombre_qgz))
        if carpeta_proyecto:
            rutas.append(reconstruir(carpeta_elegida, carpeta_proyecto + "/" + nombre_qgz))
    unicas = []
    for ruta in rutas:
        if ruta.casefold() not in (u.casefold() for u in unicas):
            unicas.append(ruta)
    return unicas
