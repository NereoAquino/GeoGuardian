"""Administracion del proyecto: inicializar, reconocer y guardar (F1-F6, F11)."""

from __future__ import annotations

import copy
import os
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from qgis.core import Qgis, QgsProject
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal

from ..constantes import AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO, NOMBRE_ARCHIVO_PROYECTO
from ..contexto import ContextoProyecto
from ..dominio.modelos import (
    EstadoRecurso,
    NivelSemaforo,
    ResumenProyecto,
    SolicitudInicializacion,
    TipoEvento,
)
from ..dominio.clasificacion import normalizar_ruta
from ..dominio.nombre_academico import nombre_de_archivo, practica_de, validar_nombre_academico
from ..dominio.recuperacion import (
    IdentidadUbicacion,
    Resultado,
    id_valido,
    identidad,
    recuperar,
    rutas_a_probar,
    unidad_ausente,
)
from ..dominio.semaforo import evaluar_semaforo
from ..dominio.tiempo import ahora_iso
from ..dominio.ubicacion import TipoUbicacion
from ..dominio.validacion import validar_datos_proyecto, validar_nombre_carpeta
from ..manifiesto.manifiesto import (
    ManifiestoInvalido,
    construir_manifiesto,
    escribir_manifiesto,
    leer_manifiesto,
)
from ..errores import informar_error, protegido
from ..monitoreo.monitor_capas import MonitorCapas
from ..persistencia.geopaquete import crear_geopaquete, problemas_esquema
from ..persistencia.migraciones import migrar
from .almacenamiento import Almacenamiento
from .estructura_carpetas import CarpetaNoDisponible, crear_estructura
from .identidad_proyecto import leer_ids
from .registro_adopciones import Adopcion, RegistroAdopciones


class ErrorInicializacion(Exception):
    pass


class ErrorGuardado(Exception):
    pass


class AdministradorProyecto(QObject):
    estado_actualizado = pyqtSignal()
    error_ocurrido = pyqtSignal(str)
    administracion_cambiada = pyqtSignal(bool)
    # Se abrio un original ya adoptado; lleva la ruta (existente) de su version administrada.
    version_administrada_disponible = pyqtSignal(str)
    # Se abrio un original adoptado y no se encontro su version administrada (D-34); lleva la
    # ruta del original, para Localizar unidad o carpeta.
    unidad_no_encontrada = pyqtSignal(str)
    # Varias unidades con la misma etiqueta contienen el proyecto valido: ruta del original y candidatas.
    candidatas_administradas = pyqtSignal(str, list)

    def __init__(
        self,
        proyecto: QgsProject,
        monitor: MonitorCapas,
        registro_adopciones: Optional[RegistroAdopciones] = None,
        almacen: Optional[Almacenamiento] = None,
        padre: Optional[QObject] = None,
    ):
        """`monitor` y `registro_adopciones` los crea la raiz de composicion (complemento.py).

        `almacen` da acceso a volumenes y archivos; las pruebas lo sustituyen para simular
        unidades que cambian de letra (D-33).
        """
        super().__init__(padre)
        self._proyecto = proyecto
        self._monitor = monitor
        self._adopciones = registro_adopciones
        self._almacen = almacen if almacen is not None else Almacenamiento()
        self._monitor.estado_actualizado.connect(self.estado_actualizado)
        self._monitor.error_ocurrido.connect(self.error_ocurrido)
        self._contexto: Optional[ContextoProyecto] = None
        self._id_proyecto = ""
        self._problemas: List[str] = []
        self._guardando = False
        # Guardar ahora pasa por el guardado nativo de QGIS: el origen se recuerda hasta que
        # llega projectSaved, y alli se registra una sola vez.
        self._origen_guardado: Optional[str] = None
        self._version_administrada = ""  # original abierto con asociacion valida (D-37)
        self._pendientes_guardado: Optional[int] = None
        self._conexiones = []
        self._liberado = False
        self._version_migrada: Optional[int] = None

    # --- ciclo de vida -----------------------------------------------------

    def conectar_senales(self) -> None:
        senales = [
            (self._proyecto.readProject, self._al_leer_proyecto),
            (self._proyecto.cleared, self._al_limpiar_proyecto),
            (self._proyecto.isDirtyChanged, self._al_cambiar_sin_guardar),
            (self._proyecto.projectSaved, self._al_guardar_desde_qgis),
            # Para la advertencia de proyecto no administrado (F12).
            (self._proyecto.layersAdded, self._al_cambiar_sin_guardar),
            (self._proyecto.layersRemoved, self._al_cambiar_sin_guardar),
        ]
        for senal, ranura in senales:
            senal.connect(ranura)
            self._conexiones.append((senal, ranura))

    def liberar(self) -> None:
        """Deja QGIS como estaba: sin conexiones ni monitor activo."""
        self._liberado = True
        for senal, ranura in self._conexiones:
            try:
                senal.disconnect(ranura)
            except (TypeError, RuntimeError):
                pass
        self._conexiones = []
        self._monitor.desactivar()
        for senal, ranura in (
            (self._monitor.estado_actualizado, self.estado_actualizado),
            (self._monitor.error_ocurrido, self.error_ocurrido),
        ):
            try:
                senal.disconnect(ranura)
            except (TypeError, RuntimeError):
                pass
        self._contexto = None

    # --- consultas ---------------------------------------------------------

    @property
    def es_administrado(self) -> bool:
        return self._contexto is not None

    @property
    def version_administrada(self) -> str:
        """Ruta de la version administrada valida del original abierto, o vacia (D-37)."""
        return self._version_administrada

    @property
    def contexto(self) -> Optional[ContextoProyecto]:
        return self._contexto

    @property
    def monitor(self) -> MonitorCapas:
        return self._monitor

    def nombre_actual_proyecto(self) -> str:
        """Titulo del proyecto o, si esta vacio, nombre del .qgz sin extension (F13)."""
        titulo = (self._proyecto.title() or "").strip()
        if titulo:
            return titulo
        archivo = self._proyecto.fileName()
        return Path(archivo).stem if archivo else ""

    def ruta_proyecto_actual(self) -> str:
        return self._proyecto.fileName() or ""

    def resumen_actual(self) -> ResumenProyecto:
        tiene_archivo = bool(self._proyecto.fileName())
        numero_capas = len(self._proyecto.mapLayers())
        if self._contexto is None:
            return ResumenProyecto(
                administrado=False,
                tiene_archivo=tiene_archivo,
                numero_capas=numero_capas,
                version_administrada=self._version_administrada,
            )
        contexto = self._contexto
        fila = contexto.fila_proyecto or {}
        conteo = contexto.repositorio.conteo_por_estado() if contexto.geopaquete_utilizable else {}
        return ResumenProyecto(
            faltantes_sin_unidad=self._faltantes_sin_unidad() if conteo.get(EstadoRecurso.FALTANTE) else 0,
            tiene_archivo=tiene_archivo,
            numero_capas=numero_capas,
            nombre_academico=str(fila.get("nombre_academico") or fila.get("titulo") or self._proyecto.title()),
            ruta_proyecto=str(contexto.ruta_proyecto),
            carpeta=str(contexto.carpeta),
            administrado=True,
            conteo=conteo,
            cambios_sin_guardar=self._proyecto.isDirty(),
            capas_con_ediciones=self._monitor.capas_con_ediciones(),
            problemas_consistencia=list(self._problemas),
            titulo=str(fila.get("titulo") or self._proyecto.title()),
            nombre_estudiante=str(fila.get("nombre_estudiante") or ""),
        )

    def _faltantes_sin_unidad(self) -> int:
        """Faltantes cuya unidad de Windows no esta conectada (D-34): no se dan por perdidos."""
        return sum(
            1
            for recurso in self._contexto.repositorio.recursos_vigentes()
            if recurso.estado == EstadoRecurso.FALTANTE
            and unidad_ausente((recurso.fuente or "").split("|")[0], self._almacen.existe)
        )

    def _identidad(self, ruta: str) -> IdentidadUbicacion:
        return identidad(ruta, self._almacen.info_volumen(ruta))

    def estado_semaforo(self) -> Tuple[NivelSemaforo, List[str], ResumenProyecto]:
        resumen = self.resumen_actual()
        nivel, motivos = evaluar_semaforo(resumen)
        return nivel, motivos, resumen

    # --- inicializacion ----------------------------------------------------

    def inicializar(self, solicitud: SolicitudInicializacion) -> Path:
        """Crea el proyecto administrado. El proyecto original no se modifica (F14)."""
        if self.es_administrado:
            raise ErrorInicializacion("El proyecto abierto ya esta administrado por GeoGuardian")
        if self._version_administrada:
            # Evita crear por accidente una segunda version administrada del mismo original (D-37).
            raise ErrorInicializacion(
                "Este proyecto ya tiene una versión administrada: {}. Ábrela para continuar "
                "trabajando.".format(self._version_administrada)
            )
        datos = solicitud.datos
        nombre_academico = (solicitud.nombre_academico or "").strip()
        errores = validar_datos_proyecto(datos) + validar_nombre_academico(
            nombre_academico, datos.nombre_estudiante
        )
        nombre_archivo = nombre_de_archivo(nombre_academico)
        if nombre_archivo and not errores:
            errores += validar_nombre_carpeta(nombre_archivo)
        padre = solicitud.carpeta_padre
        if not padre or not Path(padre).is_dir():
            errores.append("La carpeta donde se creara el proyecto no existe")
        respaldo = (solicitud.ruta_respaldo or "").strip() or None
        if respaldo and not Path(respaldo).is_dir():
            errores.append("La carpeta de respaldo no existe")
        if errores:
            raise ErrorInicializacion("\n".join(errores))

        carpeta = Path(padre) / nombre_archivo
        try:
            crear_estructura(carpeta)
        except (CarpetaNoDisponible, OSError) as error:
            raise ErrorInicializacion(str(error))

        proyecto = self._proyecto
        ruta_origen = proyecto.fileName() or None
        contexto = ContextoProyecto(carpeta, nombre_archivo + ".qgz")
        fecha = ahora_iso()
        id_proyecto = str(uuid.uuid4())
        datos_guardados = copy.copy(datos)
        datos_guardados.titulo = practica_de(nombre_academico, datos.nombre_estudiante) or datos.titulo
        ubicacion = self._identidad(str(contexto.ruta_proyecto))
        ubicacion_respaldo = self._identidad(respaldo) if respaldo else IdentidadUbicacion(ruta="")
        crear_geopaquete(contexto.ruta_geopaquete, fecha)
        contexto.repositorio.insertar_proyecto(
            id_proyecto,
            datos_guardados,
            fecha,
            Qgis.QGIS_VERSION,
            nombre_academico=nombre_academico,
            ruta_proyecto_origen=ruta_origen,
            ruta_proyecto_administrado=str(contexto.ruta_proyecto),
            ruta_respaldo=respaldo,
            tipo_ubicacion=TipoUbicacion(solicitud.tipo_ubicacion).value,
            etiqueta_volumen=ubicacion.etiqueta_volumen,
            sistema_archivos=ubicacion.sistema_archivos,
            ruta_en_volumen=ubicacion.ruta_en_volumen,
            etiqueta_volumen_respaldo=ubicacion_respaldo.etiqueta_volumen or None,
            ruta_respaldo_en_volumen=ubicacion_respaldo.ruta_en_volumen or None,
        )
        contexto.fila_proyecto = contexto.repositorio.obtener_proyecto()
        contexto.geopaquete_utilizable = True

        capas_previas = list(proyecto.mapLayers().values())
        proyecto.setFilePathStorage(Qgis.FilePathType.Relative)
        proyecto.setTitle(nombre_academico)
        proyecto.writeEntry(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO, id_proyecto)
        self._guardando = True
        try:
            # Equivale a "Guardar como": el .qgz original queda intacto y el nuevo pasa a ser
            # el proyecto activo (F14).
            guardado = proyecto.write(str(contexto.ruta_proyecto))
        finally:
            self._guardando = False
        if not guardado:
            proyecto.removeEntry(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO)
            mensaje = "QGIS no pudo guardar {}: {}".format(contexto.ruta_proyecto, proyecto.error())
            informar_error(self, contexto.registro, "inicializar", ErrorInicializacion(mensaje))
            raise ErrorInicializacion(mensaje)

        self._contexto = contexto
        self._id_proyecto = id_proyecto
        self._problemas = []
        contexto.registro.registrar(
            TipoEvento.PROYECTO_INICIALIZADO,
            "Se inicializo el proyecto «{}»".format(nombre_academico),
            detalle={
                "carpeta": str(carpeta),
                "capas_adoptadas": len(capas_previas),
                "ruta_proyecto_origen": ruta_origen,
                "tipo_ubicacion": TipoUbicacion(solicitud.tipo_ubicacion).value,
            },
        )
        self._monitor.activar(contexto)
        self._monitor.registrar_capas(capas_previas)  # D-04: se adoptan sin mover archivos
        self._escribir_manifiesto()
        if self._adopciones is not None:
            try:
                origen = self._identidad(ruta_origen) if ruta_origen else None
                self._adopciones.agregar(origen, ubicacion, id_proyecto)
            except Exception as error:  # noqa: BLE001  (no impide la inicializacion)
                self.informar_error("registrar_adopcion", error)
        self.administracion_cambiada.emit(True)
        self.estado_actualizado.emit()
        return carpeta

    def completar_inicializacion(self, guardar_nativo: Callable[[], object]) -> bool:
        """Ultimo guardado de la inicializacion, con el guardado nativo de QGIS (D-38).

        La primera escritura es un "Guardar como" a la carpeta nueva; despues QGIS aplica cambios
        diferidos (por ejemplo, la lista de capas del lienzo) que vuelven a marcar el proyecto
        como modificado. Este guardado los incluye y deja sincronizada la fecha del archivo que
        QGIS recuerda. Forma parte de la inicializacion: no registra un `proyecto_guardado`.
        """
        if self._contexto is None:
            return False
        self._guardando = True
        try:
            guardar_nativo()
        finally:
            self._guardando = False
        return not self._proyecto.isDirty()

    # --- reconocimiento al abrir ------------------------------------------

    def detectar_administrado(self) -> bool:
        """Reconoce un proyecto administrado (D-08) y activa el monitor si se puede."""
        self._monitor.desactivar()
        self._contexto = None
        self._problemas = []
        self._version_administrada = ""
        id_proyecto = self._proyecto.readEntry(AMBITO_PROPIEDADES, CLAVE_ID_PROYECTO, "")[0]
        archivo = self._proyecto.fileName()
        if not id_proyecto or not archivo:
            self.administracion_cambiada.emit(False)
            self.estado_actualizado.emit()
            self._avisar_si_es_original_adoptado(archivo)
            return False

        ruta = Path(archivo)
        contexto = ContextoProyecto(ruta.parent, ruta.name)
        self._id_proyecto = id_proyecto
        self._contexto = contexto
        self._problemas = self._verificar_consistencia()
        if contexto.geopaquete_utilizable:
            self._monitor.activar(contexto)
            if self._version_migrada is not None:
                contexto.registro.registrar(
                    TipoEvento.ESQUEMA_MIGRADO,
                    "Se actualizo Proyecto.gpkg al esquema {}".format(contexto.fila_proyecto["version_esquema"]),
                    detalle={
                        "version_anterior": self._version_migrada,
                        "version_nueva": contexto.fila_proyecto["version_esquema"],
                    },
                )
            try:
                self._actualizar_ubicacion()
            except Exception as error:  # noqa: BLE001  (no impide abrir el proyecto)
                self.informar_error("actualizar_ubicacion", error)
            contexto.registro.registrar(
                TipoEvento.PROYECTO_ABIERTO,
                "Se abrio el proyecto",
                detalle={"version_qgis": Qgis.QGIS_VERSION, "archivo": ruta.name},
            )
            self._monitor.reclasificar()
        self.administracion_cambiada.emit(True)
        self.estado_actualizado.emit()
        return True

    def _actualizar_ubicacion(self) -> None:
        """Registra donde esta ahora el .qgz; la letra de unidad pudo cambiar (D-33)."""
        contexto = self._contexto
        fila = contexto.fila_proyecto or {}
        actual = self._identidad(str(contexto.ruta_proyecto))
        anterior = fila.get("ruta_proyecto_administrado") or ""
        registrada = (
            anterior,
            fila.get("etiqueta_volumen") or "",
            fila.get("sistema_archivos") or "",
            fila.get("ruta_en_volumen") or "",
        )
        nueva = (actual.ruta, actual.etiqueta_volumen, actual.sistema_archivos, actual.ruta_en_volumen)
        if registrada != nueva:
            contexto.repositorio.actualizar_ubicacion(*nueva)
            contexto.fila_proyecto = contexto.repositorio.obtener_proyecto()
            if anterior and normalizar_ruta(anterior) != normalizar_ruta(actual.ruta):
                contexto.registro.registrar(
                    TipoEvento.UBICACION_ACTUALIZADA,
                    "El proyecto se abrio desde otra ubicacion",
                    detalle={"ruta_anterior": anterior, "ruta_nueva": actual.ruta},
                )
            self._escribir_manifiesto()
        if self._adopciones is not None:
            self._adopciones.actualizar_administrado(self._id_proyecto, actual)

    def _verificar_consistencia(self) -> List[str]:
        contexto = self._contexto
        problemas = problemas_esquema(contexto.ruta_geopaquete)
        contexto.geopaquete_utilizable = False
        self._version_migrada = None
        if not problemas:
            try:
                self._version_migrada = migrar(contexto.ruta_geopaquete, str(contexto.ruta_proyecto))
            except Exception as error:  # noqa: BLE001
                informar_error(self, None, "migrar_esquema", error)
                return problemas + ["No se pudo actualizar Proyecto.gpkg al esquema nuevo: {}".format(error)]
        if not problemas:
            fila = contexto.repositorio.obtener_proyecto()
            if fila is None:
                problemas.append("Falta el registro del proyecto en Proyecto.gpkg")
            elif fila["id_proyecto"] != self._id_proyecto:
                problemas.append("Proyecto.gpkg pertenece a otro proyecto")
            else:
                contexto.fila_proyecto = fila
                contexto.geopaquete_utilizable = True
        try:
            manifiesto = leer_manifiesto(contexto.ruta_manifiesto)
        except ManifiestoInvalido as error:
            problemas.append(str(error))
        else:
            if manifiesto["id_proyecto"] != self._id_proyecto:
                problemas.append("El manifiesto pertenece a otro proyecto")
            esperado = (manifiesto.get("archivos") or {}).get("proyecto", NOMBRE_ARCHIVO_PROYECTO)
            if esperado != contexto.archivo_proyecto:
                problemas.append(
                    "El archivo del proyecto se llama {} pero el manifiesto espera {}".format(
                        contexto.archivo_proyecto, esperado
                    )
                )
        return problemas

    # --- guardado ----------------------------------------------------------

    def guardar_ahora(self, guardar_nativo: Callable[[], object]) -> int:
        """Guarda el .qgz con el guardado nativo de QGIS, sin confirmar ediciones.

        `guardar_nativo` es la accion "Guardar proyecto" de QGIS (complemento.py pasa
        `iface.actionSaveProject().trigger`). Asi QGIS actualiza su propia referencia de la fecha
        de modificacion y no avisa despues de que "el proyecto ha cambiado en el disco".
        El registro `proyecto_guardado` (origen "boton") y el manifiesto se hacen al recibir
        `projectSaved`, una sola vez. Devuelve las capas con ediciones pendientes.
        """
        if not self.es_administrado:
            raise ErrorGuardado("El proyecto no esta administrado por GeoGuardian")
        if not self._contexto.geopaquete_utilizable:
            raise ErrorGuardado(
                "No se puede guardar con GeoGuardian: " + "; ".join(self._problemas)
            )
        self._monitor.reclasificar()
        self._origen_guardado = "boton"
        self._pendientes_guardado = None
        try:
            guardar_nativo()  # el guardado del proyecto no toca los buferes de edicion
        finally:
            self._origen_guardado = None
        if self._pendientes_guardado is None:
            raise ErrorGuardado("QGIS no guardó el proyecto")
        return self._pendientes_guardado

    def _despues_de_guardar(self, origen: str) -> int:
        contexto = self._contexto
        contexto.repositorio.actualizar_fecha_proyecto(ahora_iso())
        contexto.fila_proyecto = contexto.repositorio.obtener_proyecto()
        pendientes = self._monitor.capas_con_ediciones()
        contexto.registro.registrar(
            TipoEvento.PROYECTO_GUARDADO,
            "Se guardo el proyecto",
            detalle={"origen": origen, "capas_con_ediciones": pendientes},
        )
        self._escribir_manifiesto()
        self._problemas = self._verificar_consistencia()
        self.estado_actualizado.emit()
        return pendientes

    def _escribir_manifiesto(self) -> None:
        """Regenera el manifiesto a partir de Proyecto.gpkg, su fuente de verdad (D-06)."""
        contexto = self._contexto
        fila = contexto.repositorio.obtener_proyecto()
        conteo = contexto.repositorio.conteo_por_estado()
        nivel, _motivos = evaluar_semaforo(
            ResumenProyecto(
                administrado=True,
                conteo=conteo,
                cambios_sin_guardar=self._proyecto.isDirty(),
                capas_con_ediciones=self._monitor.capas_con_ediciones(),
            )
        )
        escribir_manifiesto(
            contexto.ruta_manifiesto,
            construir_manifiesto(fila, conteo, nivel, Qgis.QGIS_VERSION, contexto.archivo_proyecto),
        )

    # --- ranuras -----------------------------------------------------------

    def informar_error(self, operacion: str, error: Exception) -> None:
        registro = self._contexto.registro if self._contexto and self._contexto.geopaquete_utilizable else None
        informar_error(self, registro, operacion, error)

    @protegido
    def _al_leer_proyecto(self, *_args) -> None:
        # Se difiere para que QGIS termine de cargar el proyecto y sus capas.
        QTimer.singleShot(0, self._detectar_si_sigue_cargado)

    @protegido
    def _detectar_si_sigue_cargado(self) -> None:
        if not self._liberado:
            self.detectar_administrado()

    @protegido
    def _al_limpiar_proyecto(self) -> None:
        self._monitor.desactivar()
        self._contexto = None
        self._problemas = []
        self._version_administrada = ""
        self.administracion_cambiada.emit(False)
        self.estado_actualizado.emit()

    @protegido
    def _al_cambiar_sin_guardar(self, *_args) -> None:
        self.estado_actualizado.emit()

    def _avisar_si_es_original_adoptado(self, archivo: str) -> None:
        """Si `archivo` es un original adoptado, ofrece su version administrada (D-22, D-34)."""
        if self._adopciones is None or not archivo:
            return
        origen = self._identidad(archivo)
        adopcion = self._adopciones.buscar(origen)
        if adopcion is None:
            return
        if self._mismo_archivo(adopcion.administrado.ruta, archivo):
            return
        if not adopcion.id_proyecto:
            self._avisar_adopcion_anterior(adopcion, origen)
            return
        recuperacion = recuperar(
            adopcion.administrado,
            adopcion.id_proyecto,
            self._almacen.volumenes(),
            self._almacen.existe,
            leer_ids,
        )
        if recuperacion.resultado == Resultado.ENCONTRADA:
            ruta = os.path.normpath(recuperacion.ruta)
            self._reasociar(adopcion, origen, ruta)
            self._version_administrada = ruta
            self.version_administrada_disponible.emit(ruta)
        elif recuperacion.resultado == Resultado.VARIAS:
            self.candidatas_administradas.emit(archivo, [os.path.normpath(r) for r in recuperacion.candidatas])
        else:
            # ID_DISTINTO o NO_ENCONTRADA: nunca se reasocia sola ni se borra la asociacion.
            self.unidad_no_encontrada.emit(archivo)

    def _avisar_adopcion_anterior(self, adopcion: Adopcion, origen: IdentidadUbicacion) -> None:
        """Asociacion sin id_proyecto (formato anterior): solo si la ruta registrada existe."""
        ruta = adopcion.administrado.ruta
        if not self._almacen.existe(ruta):
            return
        ids = set(leer_ids(ruta).values())
        if len(ids) != 1:
            return
        self._adopciones.reemplazar(adopcion, Adopcion(origen, self._identidad(ruta), ids.pop()))
        self._version_administrada = ruta
        self.version_administrada_disponible.emit(ruta)

    def _reasociar(self, adopcion: Adopcion, origen: IdentidadUbicacion, ruta_administrado: str) -> None:
        nueva = Adopcion(origen, self._identidad(ruta_administrado), adopcion.id_proyecto)
        if nueva != adopcion:
            self._adopciones.reemplazar(adopcion, nueva)

    @staticmethod
    def _mismo_archivo(a: str, b: str) -> bool:
        return bool(a and b) and normalizar_ruta(a) == normalizar_ruta(b)

    def localizar_version_administrada(self, ruta_origen: str, carpeta: str) -> Optional[str]:
        """Busca en `carpeta` la version administrada de `ruta_origen` y valida su id (D-34.7).

        Devuelve la ruta del .qgz si es el proyecto esperado; si no, None y no cambia nada.
        """
        if self._adopciones is None or not ruta_origen or not carpeta:
            return None
        origen = self._identidad(ruta_origen)
        adopcion = self._adopciones.buscar(origen)
        if adopcion is None or not adopcion.id_proyecto:
            return None
        for candidata in rutas_a_probar(carpeta, adopcion.administrado):
            if self._almacen.existe(candidata) and id_valido(leer_ids(candidata), adopcion.id_proyecto):
                ruta = os.path.normpath(candidata)
                self._reasociar(adopcion, origen, ruta)
                self._version_administrada = ruta
                return ruta
        return None

    @protegido
    def _al_guardar_desde_qgis(self) -> None:
        if self._contexto is None:
            self.estado_actualizado.emit()  # la advertencia de no administrado puede cambiar
            return
        if self._guardando:
            return
        if Path(self._proyecto.fileName()) != self._contexto.ruta_proyecto:
            # "Guardar como" a otra ubicacion: se vuelve a verificar donde quedo.
            self.detectar_administrado()
            return
        if not self._contexto.geopaquete_utilizable:
            return
        origen = self._origen_guardado or "qgis"
        self._origen_guardado = None  # un mismo guardado se registra una sola vez
        self._monitor.reclasificar()
        self._pendientes_guardado = self._despues_de_guardar(origen)
