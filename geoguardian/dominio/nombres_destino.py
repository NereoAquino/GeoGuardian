"""Nombre que tendria cada unidad dentro de Proyecto.gpkg (D-62). Modulo puro: sin QGIS ni Qt.

No escribe nada: solo propone. Conserva espacios, acentos, ñ y emoji; corrige unicamente lo que
GDAL, SQLite o QGIS no aceptan (comprobado con QGIS 3.28 / GDAL 3.4):
- `|` separa parametros en la fuente de QGIS: una tabla con `|` no se puede cargar.
- `"` se escribe, pero rompe filtros y fuentes; control: invisibles y problematicos.
- GDAL rechaza nombres que empiezan por `gpkg`; SQLite, por `sqlite_`; `rtree_` choca con los
  indices espaciales y `gg_` es de GeoGuardian.
- GDAL compara nombres de tabla sin distinguir mayusculas: escribir `Municipios` reemplazo a
  `municipios`. Por eso los conflictos se comparan con `casefold()`.
"""

from __future__ import annotations

import unicodedata
from typing import Dict, Iterable, NamedTuple, Optional, Sequence, Tuple

NOMBRE_VACIO = "capa"
PREFIJO_SEGURO = "capa_"
PREFIJOS_RESERVADOS = ("gpkg", "sqlite_", "rtree_", "gg_")
CARACTERES_SUSTITUIDOS = ("|", '"')


class NombrePropuesto(NamedTuple):
    nombre: str
    base: str
    # Por que no se uso `base`: "existe" (ya esta en Proyecto.gpkg), "plan" (otra unidad del mismo
    # plan lo usa) o "" (sin conflicto).
    conflicto: str = ""


def clave_comparacion(nombre: str) -> str:
    return unicodedata.normalize("NFC", nombre).casefold()


def es_reservado(nombre: str) -> bool:
    return clave_comparacion(nombre).startswith(PREFIJOS_RESERVADOS)


def nombre_valido(texto: str) -> str:
    """Nombre de tabla valido y reproducible; no cambia lo que ya es valido."""
    nombre = unicodedata.normalize("NFC", texto or "").strip()
    nombre = "".join(
        "_" if c in CARACTERES_SUSTITUIDOS or unicodedata.category(c) == "Cc" else c for c in nombre
    ).strip()
    if not nombre:
        return NOMBRE_VACIO
    if es_reservado(nombre):
        return PREFIJO_SEGURO + nombre
    return nombre


def resolver_nombres(
    bases: Sequence[Tuple[str, str]], ocupados: Iterable[str]
) -> Dict[str, NombrePropuesto]:
    """Nombre libre para cada (clave_unidad, base), en orden de clave: nombre, nombre_2, ...

    `ocupados` son los nombres que ya existen en Proyecto.gpkg (tablas, vistas, indices, gg_*...).
    Los nombres asignados a otras unidades del plan tambien cuentan como ocupados. El resultado no
    depende del orden de entrada.
    """
    existentes = {clave_comparacion(n) for n in ocupados}
    usados = set(existentes)
    resultado: Dict[str, NombrePropuesto] = {}
    for clave, base_original in sorted(bases, key=lambda par: par[0]):
        base = nombre_valido(base_original)
        candidato = base
        sufijo = 1
        while clave_comparacion(candidato) in usados:
            sufijo += 1
            candidato = "{}_{}".format(base, sufijo)
        conflicto = ""
        if candidato != base:
            conflicto = "existe" if clave_comparacion(base) in existentes else "plan"
        usados.add(clave_comparacion(candidato))
        resultado[clave] = NombrePropuesto(candidato, base, conflicto)
    return resultado


def esta_ocupado(nombre: str, ocupados: Iterable[str]) -> bool:
    objetivo = clave_comparacion(nombre)
    return any(clave_comparacion(n) == objetivo for n in ocupados)


def texto_destino(propuesto: Optional[NombrePropuesto]) -> str:
    """'municipios_4 (municipios ya existe)'."""
    if propuesto is None:
        return "—"
    if propuesto.conflicto == "existe":
        return "{} ({} ya existe)".format(propuesto.nombre, propuesto.base)
    if propuesto.conflicto == "plan":
        return "{} ({} ya se usa en este plan)".format(propuesto.nombre, propuesto.base)
    return propuesto.nombre
