"""Registro de eventos: fecha, version y escritura inmediata (D-05)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from ..constantes import VERSION_COMPLEMENTO
from ..dominio.modelos import Evento, TipoEvento
from ..dominio.tiempo import ahora_iso
from ..persistencia.repositorio import RepositorioGeoGuardian


class RegistroEventos:
    def __init__(self, repositorio: RepositorioGeoGuardian, reloj: Callable[[], str] = ahora_iso):
        self._repositorio = repositorio
        self._reloj = reloj

    def registrar(
        self,
        tipo: TipoEvento,
        descripcion: str,
        id_capa: Optional[str] = None,
        detalle: Optional[Dict[str, Any]] = None,
    ) -> Evento:
        evento = Evento(
            tipo_evento=TipoEvento(tipo),
            descripcion=descripcion,
            fecha_hora=self._reloj(),
            version_complemento=VERSION_COMPLEMENTO,
            id_capa=id_capa,
            detalle=detalle,
        )
        self._repositorio.insertar_evento(evento)
        return evento
