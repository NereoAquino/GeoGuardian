"""Colores del semaforo, compartidos por el panel y el indicador de la barra."""

from ..dominio.modelos import NivelSemaforo

COLORES_NIVEL = {
    NivelSemaforo.GRIS: "#9e9e9e",
    NivelSemaforo.ROJO: "#c62828",
    NivelSemaforo.AMARILLO: "#f9a825",
    NivelSemaforo.VERDE: "#2e7d32",
}
