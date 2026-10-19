"""Reglas del semaforo (especificacion v0.1.0, seccion 6; F21, F22). Modulo puro."""

from __future__ import annotations

from typing import List, Tuple

from .modelos import EstadoRecurso, NivelSemaforo, ResumenProyecto

ESTADOS_EN_PROYECTO = (
    EstadoRecurso.ACTIVO,
    EstadoRecurso.EXTERNO,
    EstadoRecurso.TEMPORAL,
    EstadoRecurso.FALTANTE,
)

FRASES_NIVEL = {
    NivelSemaforo.GRIS: "Proyecto no administrado",
    NivelSemaforo.VERDE: "Proyecto en buen estado",
    NivelSemaforo.AMARILLO: "Proyecto requiere atención",
    NivelSemaforo.ROJO: "Proyecto con problemas",
}

MOTIVO_NO_ADMINISTRADO = "Inicializa el proyecto para que GeoGuardian lo supervise"
FRASE_VERSION_DISPONIBLE = "Versión administrada disponible"
MOTIVO_VERSION_DISPONIBLE = "Abre la versión administrada para continuar trabajando"
MOTIVO_EN_ORDEN = "El proyecto está guardado y todos sus recursos están en su carpeta"


def _plural(cantidad: int, singular: str, plural: str) -> str:
    return singular if cantidad == 1 else plural


def recursos_en_proyecto(resumen: ResumenProyecto) -> int:
    """Recursos que siguen en el proyecto; los historicos ya se retiraron (D-32)."""
    return sum(resumen.cantidad(estado) for estado in ESTADOS_EN_PROYECTO)


def evaluar_semaforo(resumen: ResumenProyecto) -> Tuple[NivelSemaforo, List[str]]:
    """Devuelve el nivel y los motivos; el primero es el motivo principal (D-31)."""
    if not resumen.administrado:
        if resumen.version_administrada:
            return NivelSemaforo.GRIS, [MOTIVO_VERSION_DISPONIBLE]  # no invitar a otra inicializacion
        return NivelSemaforo.GRIS, [MOTIVO_NO_ADMINISTRADO]

    rojos: List[str] = list(resumen.problemas_consistencia)
    amarillos: List[str] = []

    faltantes = resumen.cantidad(EstadoRecurso.FALTANTE)
    sin_unidad = min(resumen.faltantes_sin_unidad, faltantes)
    if sin_unidad:
        rojos.append(
            "{} {} en una unidad que no se encuentra (puede estar desconectada o tener otra letra)".format(
                sin_unidad, _plural(sin_unidad, "recurso está", "recursos están")
            )
        )
    faltantes -= sin_unidad
    if faltantes:
        rojos.append(
            "{} {} a archivos que no existen o no se pueden leer".format(
                faltantes, _plural(faltantes, "recurso apunta", "recursos apuntan")
            )
        )

    # Orden de D-31: primero lo que puede perderse, al final los cambios sin guardar.
    temporales = resumen.cantidad(EstadoRecurso.TEMPORAL)
    if temporales:
        amarillos.append(
            "{} {} al cerrar QGIS".format(
                temporales,
                _plural(temporales, "capa temporal se perderá", "capas temporales se perderán"),
            )
        )
    if resumen.capas_con_ediciones:
        n = resumen.capas_con_ediciones
        amarillos.append(
            "{} {} sin confirmar".format(
                n, _plural(n, "capa tiene ediciones", "capas tienen ediciones")
            )
        )
    externos = resumen.cantidad(EstadoRecurso.EXTERNO)
    if externos:
        amarillos.append(
            "{} {} fuera de la carpeta administrada".format(
                externos, _plural(externos, "recurso se encuentra", "recursos se encuentran")
            )
        )
    if resumen.cambios_sin_guardar:
        amarillos.append("Hay cambios sin guardar")

    if rojos:
        return NivelSemaforo.ROJO, rojos + amarillos
    if amarillos:
        return NivelSemaforo.AMARILLO, amarillos
    return NivelSemaforo.VERDE, [MOTIVO_EN_ORDEN]


def texto_indicador(nivel: NivelSemaforo, motivos: List[str], frase: str = "") -> Tuple[str, str]:
    """Texto visible y tooltip del indicador de la barra (D-31): solo el motivo principal."""
    frase = frase or FRASES_NIVEL[nivel]
    if not motivos:
        return frase, "GeoGuardian — {}.".format(frase)
    return frase, "GeoGuardian — {}: {}.".format(frase, motivos[0].rstrip("."))
