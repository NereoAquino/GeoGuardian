"""Catalogo de asignaturas o modulos que ofrece el asistente (D-39). Modulo puro.

Es el unico lugar donde se definen las opciones: para cambiarlas basta con editar esta tupla. El
estudiante puede elegir una o escribir otra; el valor se guarda tal cual en
`gg_proyecto.asignatura` y en el manifiesto.
"""

from typing import List

# Modulos profesionales de la carrera de Tecnico en Sistemas de Informacion Geografica.
ASIGNATURAS = (
    "M1 — Maneja e integra información geográfica",
    "M2 — Produce y mantiene información georreferenciada para proyectos",
    "M3 — Realiza análisis espacial para proyectos",
    "M4 — Genera cartografía temática para proyectos",
    "M5 — Obtiene, gestiona y manipula información geográfica a distancia",
)


def opciones_asignatura() -> List[str]:
    return list(ASIGNATURAS)
