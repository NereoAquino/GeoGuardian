# GeoGuardian — Arquitectura (v0.1.0)

> Estado: **aprobada** el 2026-10-18 (todas las decisiones de [DECISIONES.md](DECISIONES.md)).
> **Publicada como v0.1.0 estable el 2026-10-19.** Las secciones 10 a 13 (rc2) describen la
> arquitectura vigente de 0.1.0.
> **v0.2.0-dev:** la sección 14 describe el Hito 1 (inventario y "Revisar capas", D-40 a D-52).

## 1. Propósito

GeoGuardian es un complemento de QGIS que deja al estudiante trabajar con libertad mientras
vigila la **integridad**, **trazabilidad** y **portabilidad** de su proyecto. La v0.1.0 introduce
un solo concepto: el **Proyecto administrado por GeoGuardian**. Un proyecto administrado es una
carpeta con estructura conocida, un `Proyecto.qgz`, un `Proyecto.gpkg` con las tablas de control
y un manifiesto en `.geoguardian/`.

En v0.1.0 GeoGuardian **observa y registra; no corrige**. No mueve, copia, borra ni modifica
archivos fuente, no consolida capas y no confirma ediciones.

## 2. Principios

1. **Observar, no intervenir.** El complemento solo escribe en sus propios archivos
   (`Proyecto.gpkg`, manifiesto) y en `Proyecto.qgz` cuando el usuario lo pide.
2. **Lógica fuera de la interfaz.** Las reglas (clasificación, semáforo) son funciones puras de
   Python sin dependencias de QGIS ni Qt, y por eso se prueban con pruebas unitarias simples.
3. **Dependencias en una sola dirección.** Interfaz → servicios QGIS → persistencia → dominio.
   El dominio no importa nada del resto.
4. **Descarga limpia.** Todo componente que conecta señales o crea widgets sabe deshacerlo;
   `unload()` deja QGIS como estaba.
5. **Solo biblioteca estándar y lo que trae QGIS.** `sqlite3`, `json`, `uuid`, `pathlib`,
   `datetime`, `dataclasses`, `enum`, PyQGIS, PyQt y `osgeo` (GDAL, incluido en QGIS).
6. **Español en identificadores**, sin acentos ni ñ. Las excepciones exigidas por APIs externas
   se listan en la sección 9.

## 3. Estructura de un proyecto administrado

```
<carpeta elegida por el estudiante>/
└── <NombreDelProyecto>/            ← carpeta nueva, debe no existir o estar vacía
    ├── Proyecto.qgz                ← proyecto QGIS, rutas relativas
    ├── Proyecto.gpkg               ← tablas gg_proyecto, gg_recursos, gg_eventos
    ├── .geoguardian/
    │   └── manifiesto.json         ← resumen portable (ver D-01 sobre el nombre)
    ├── datos/                      ← vacía en v0.1.0; destino natural de datos del proyecto
    ├── salidas/                    ← mapas, exportaciones
    └── documentos/                 ← reportes, notas
```

Los nombres de archivo `Proyecto.qgz` y `Proyecto.gpkg` son fijos; lo que identifica al proyecto
es el nombre de su carpeta y el `id_proyecto` (UUID) guardado en la base y en el manifiesto.

## 4. Módulos

```
geoguardian/                         ← carpeta del complemento (nombre del ZIP instalable)
├── __init__.py                      classFactory(iface)  — exigido por QGIS
├── metadata.txt                     exigido por QGIS
├── complemento.py                   ComplementoGeoGuardian: initGui(), unload()
├── constantes.py                    nombres de archivos, carpetas, versión de esquema
├── contexto.py                      ContextoProyecto: rutas, repositorio y registro del proyecto abierto
├── errores.py                       protegido, informar_error: frontera de errores común
│
├── dominio/                         ── SIN QGIS NI QT ──
│   ├── modelos.py                   DatosProyecto, DescripcionFuente, Recurso, Evento,
│   │                                EstadoRecurso (Enum), NivelSemaforo (Enum), ResumenProyecto
│   ├── clasificacion.py             clasificar_recurso(descripcion, carpeta_proyecto) -> EstadoRecurso
│   ├── semaforo.py                  evaluar_semaforo(resumen) -> (NivelSemaforo, [motivos])
│   ├── validacion.py                validar_datos_proyecto(datos) -> [errores]
│   ├── seguridad.py                 ocultar_contrasenas(texto)  (D-13)
│   └── tiempo.py                    ahora_iso()  (D-14)
│
├── persistencia/                    ── sqlite3 + osgeo; sin Qt ──
│   ├── geopaquete.py                crear_geopaquete(ruta), aplicar_esquema(ruta), version_esquema()
│   └── repositorio.py               RepositorioGeoGuardian: proyecto, recursos, eventos (CRUD)
│
├── manifiesto/
│   └── manifiesto.py                construir_manifiesto(...), escribir_manifiesto(...),
│                                    leer_manifiesto(...)  (json, escritura atómica)
│
├── eventos/
│   └── registro_eventos.py          RegistroEventos.registrar(tipo, ...)  → repositorio
│
├── administracion/                  ── usa PyQGIS ──
│   ├── estructura_carpetas.py       crear_estructura(carpeta)  (pathlib; sin QGIS)
│   └── administrador_proyecto.py    AdministradorProyecto: inicializar(), detectar_administrado(),
│                                    guardar_ahora(), resumen_actual()
│
├── monitoreo/                       ── usa PyQGIS ──
│   ├── descriptor_fuente.py         describir_capa(QgsMapLayer) -> DescripcionFuente
│   └── monitor_capas.py             MonitorCapas(QObject): escucha QgsProject y emite
│                                    la señal estado_actualizado
│
└── interfaz/                        ── PyQt / QGIS GUI; sin reglas de negocio ──
    ├── asistente_inicializacion.py  AsistenteInicializacion(QWizard)
    ├── panel_estado.py              PanelEstado(QgsDockWidget): semáforo + "Guardar ahora"
    └── iconos/

pruebas/                             fuera del ZIP instalable
├── ejecutar_pruebas.py              cargador unittest (ver D-09)
├── unitarias/                       dominio, persistencia, manifiesto, estructura
└── integracion/                     dentro de QGIS (ver spec §8)
```

### Reglas de dependencia

| Paquete          | Puede importar                                     | No puede importar |
|------------------|----------------------------------------------------|-------------------|
| `dominio`        | biblioteca estándar, `constantes`                  | todo lo demás     |
| `persistencia`   | `dominio`, `sqlite3`, `osgeo` (solo al crear GPKG) | `qgis`, `PyQt`    |
| `manifiesto`     | `dominio`, `json`                                  | `qgis`, `PyQt`    |
| `eventos`        | `dominio`, `persistencia`                          | `qgis`, `PyQt`    |
| `contexto.py`    | `persistencia`, `eventos`                          | `qgis`, `PyQt`    |
| `errores.py`     | `dominio`, `constantes`, `qgis.core`               | `monitoreo`, `administracion`, `interfaz` |
| `monitoreo`      | todo lo anterior, `qgis.core`, `qgis.PyQt.QtCore`  | `administracion`, `interfaz` |
| `administracion` | todo lo anterior, incluido `monitoreo` (solo el tipo `MonitorCapas` y sus métodos) | `interfaz` |
| `interfaz`       | `administracion`, `dominio`, Qt, `qgis.gui`        | `persistencia` directa |
| `complemento.py` | todo; raíz de composición                          | —                 |

**Composición (definitiva, 2026-10-18).** `complemento.py` es la raíz de composición: crea
`MonitorCapas`, lo inyecta en `AdministradorProyecto(proyecto, monitor)` y crea `PanelEstado`.
Ningún componente construye a otro. El administrador *usa* el monitor (activar, adoptar capas,
reclasificar) porque los flujos de §6 exigen ese orden; esa es la única dependencia
`administracion → monitoreo`. La frontera de errores (`protegido`, `informar_error`) vive en
`errores.py`, que no depende de ningún componente. En `unload()` se libera primero el
administrador (desactiva el monitor) y después se destruye el monitor.

La interfaz nunca abre la base de datos ni decide estados: pide datos a
`AdministradorProyecto` y pinta lo que recibe.

## 5. Componentes y responsabilidades

**ComplementoGeoGuardian** (`complemento.py`). Raíz de composición: crea acciones (menú y
barra), el monitor, el administrador (al que inyecta el monitor) y el panel; los conecta; y en `unload()` los desconecta y destruye en orden
inverso. No contiene lógica.

**AdministradorProyecto**. Único punto que toca `QgsProject` para leer o escribir el proyecto:
- `inicializar(datos, carpeta)`: valida, crea estructura, crea GPKG y esquema, inserta
  `gg_proyecto`, configura rutas relativas, guarda `Proyecto.qgz`, escribe manifiesto, registra
  evento `proyecto_inicializado` y adopta las capas ya abiertas (D-04).
- `detectar_administrado()`: al abrir un proyecto, decide si es administrado
  (propiedad personalizada en el `.qgz` + manifiesto junto a él + `gg_proyecto` coincidentes).
- `guardar_ahora()`: reclasifica recursos, escribe `Proyecto.qgz` con `QgsProject.write()`,
  regenera manifiesto, registra `proyecto_guardado`. **No confirma ediciones**.
- `resumen_actual()`: construye `ResumenProyecto` para el semáforo.

**MonitorCapas**. Escucha `QgsProject.layersAdded` y `QgsProject.layersWillBeRemoved`
(y `removeAll`, que QGIS emite al cerrar o cambiar de proyecto: en ese caso se desactiva para no
marcar como históricas las capas de un proyecto que solo se cerró), además
de `isDirtyChanged` y las señales de edición de cada capa vectorial (`editingStarted`,
`editingStopped`, `layerModified`). Por cada capa nueva: `describir_capa` → `clasificar_recurso`
→ alta en `gg_recursos` → evento `capa_agregada`. Por cada capa que se quita: marca el recurso
como `historico` → evento `capa_eliminada`. Emite `estado_actualizado` para que el panel se
repinte. Solo está activo cuando el proyecto abierto es administrado.

**Clasificación** (`dominio/clasificacion.py`). Función pura. Entrada: `DescripcionFuente`
(proveedor, ruta del archivo si la hay, si existe, si la capa es válida, si es servicio remoto)
y la carpeta del proyecto. Reglas en la spec §5.

**Semáforo** (`dominio/semaforo.py`). Función pura. Entrada: `ResumenProyecto` (conteos por
estado, proyecto con cambios sin guardar, capas con ediciones sin confirmar, consistencia
manifiesto/base). Salida: nivel y lista de motivos legibles. Reglas en la spec §6.

**Persistencia**. `crear_geopaquete` usa el controlador GPKG de GDAL para obtener un
GeoPackage válido según el estándar; las tablas `gg_*` y todas las lecturas y escrituras usan
`sqlite3` con transacciones cortas (abrir, escribir, cerrar). No se mantiene una conexión abierta.
El esquema lleva versión (`PRAGMA user_version` no se usa porque GeoPackage lo reserva;
la versión va en `gg_proyecto.version_esquema`).

**Manifiesto**. Archivo derivado. La fuente de verdad es `Proyecto.gpkg` (D-06). Se regenera
al inicializar y en cada guardado. Escritura atómica: archivo temporal en la misma carpeta y
`os.replace`.

**RegistroEventos**. Fachada sobre el repositorio que añade fecha y hora (ISO 8601 con zona
horaria local), versión del complemento y serializa `detalle` como JSON. Escribe de inmediato
(D-05).

**Interfaz**. `AsistenteInicializacion` recoge datos y carpeta, muestra errores de
`validar_datos_proyecto` y llama a `AdministradorProyecto.inicializar`. `PanelEstado` muestra
semáforo, motivos, conteos por estado y el botón **Guardar ahora**.

## 6. Flujos principales

### 6.1 Inicialización

```
Estudiante ─► AsistenteInicializacion ─► validar_datos_proyecto
                                   │ ok
                                   ▼
                     AdministradorProyecto.inicializar
                       1. crear_estructura(carpeta)          (falla si no está vacía)
                       2. crear_geopaquete + aplicar_esquema
                       3. insertar gg_proyecto (UUID nuevo)
                       4. QgsProject: rutas relativas + propiedad id_proyecto
                       5. QgsProject.write("…/Proyecto.qgz")
                       6. registrar capas ya abiertas (clasificar + alta)
                       7. escribir manifiesto
                       8. evento proyecto_inicializado
                       9. MonitorCapas.activar()
```
Si falla un paso, se registra el error, se informa al usuario y **no se borra** nada de lo ya
creado (es carpeta nueva del propio complemento, pero se respeta el requisito de no borrar).

### 6.2 Capa agregada / eliminada

```
QgsProject.layersAdded ─► MonitorCapas ─► describir_capa ─► clasificar_recurso
                                       ─► repositorio.alta_recurso ─► evento capa_agregada
                                       ─► estado_actualizado ─► PanelEstado se repinta

QgsProject.layersWillBeRemoved ─► MonitorCapas ─► repositorio.marcar_historico
                                              ─► evento capa_eliminada ─► estado_actualizado
```

### 6.3 Guardar ahora

```
PanelEstado [Guardar ahora] ─► AdministradorProyecto.guardar_ahora
   1. reclasificar recursos vigentes (detecta faltantes nuevos)
   2. marcar origen=boton e iface.actionSaveProject().trigger()   ← guardado nativo (D-35)
QgsProject.projectSaved ─► AdministradorProyecto._al_guardar_desde_qgis
   3. reclasificar, regenerar manifiesto
   4. evento proyecto_guardado (origen boton/qgis, nº de capas con ediciones sin confirmar)
   5. estado_actualizado
```
El guardado nativo no toca los buffers de edición y mantiene sincronizada la fecha de
modificación que QGIS recuerda del `.qgz`. `Ctrl+S` sigue el mismo camino desde el paso 3 con
`origen=qgis`. Cada guardado produce un solo evento porque solo la señal lo registra.

Al terminar la inicialización, `complemento.py` pide a `AdministradorProyecto.completar_inicializacion`
un último guardado nativo en diferido (D-38): incluye lo que QGIS aplica después de la primera
escritura y no registra `proyecto_guardado`.

### 6.4 Abrir un proyecto

`iface.projectRead` → `detectar_administrado()` → si lo es: evento `proyecto_abierto`,
reclasificación de recursos (registra `estado_recurso_cambiado` si algo cambió), activar monitor.
Si no lo es: monitor inactivo, panel en gris con el botón "Inicializar proyecto".

## 7. Ciclo de vida y `unload()`

`initGui()` crea en este orden: acciones → `MonitorCapas` → `AdministradorProyecto(proyecto, monitor)` →
`PanelEstado`, y conecta `iface.projectRead`, `iface.newProjectCreated` y la señal de guardado.
Cada conexión se guarda en una lista `self._conexiones`.

`unload()` en orden inverso:
1. Desconecta todas las señales de `self._conexiones` (incluidas las conectadas a cada capa).
2. `MonitorCapas.desactivar()`.
3. Retira y destruye `PanelEstado` (`iface.removeDockWidget`, `deleteLater`).
4. Retira acciones del menú y de la barra.
5. Suelta referencias. No hay conexiones SQLite abiertas que cerrar (D-05).

Una prueba de integración carga y descarga el complemento varias veces y verifica que no quedan
receptores conectados a las señales de `QgsProject`.

## 8. Lo que v0.1.0 no hace (fuera de alcance)

Consolidación de capas, empaquetado y ZIP de entrega, autoguardado, puntos de control
(checkpoints), reparación de rutas, copia de datos a `datos/`, confirmación de ediciones,
detección de copias entre estudiantes, visor de eventos, traducciones.

## 9. Excepciones de nomenclatura en inglés

| Identificador | Motivo |
|---|---|
| `classFactory`, `initGui`, `unload` | Contrato de complementos de QGIS |
| `metadata.txt`, `__init__.py` | Exigidos por QGIS / Python |
| Métodos sobrescritos de Qt (`closeEvent`, `validatePage`, …) | API de Qt |
| `unittest.TestCase`, `setUp`, `tearDown` | API de `unittest` |
| `.qgz`, `.gpkg`, `gpkg_contents`, `gpkg_*` | Formatos y tablas del estándar GeoPackage |
| Nombres de proveedores QGIS (`ogr`, `gdal`, `memory`, `wms`, `postgres`…) | Valores de la API de QGIS |
| Prefijo `gg_` de tablas | Abreviatura de GeoGuardian (nombre propio) |
| `eventFilter`, `QCloseEvent` (propuesta rc2) | API de Qt |

## 10. rc2 · Cambios de arquitectura (aprobados el 2026-10-18)

> Decisiones D-16 a D-27 de [DECISIONES.md](DECISIONES.md), aprobadas.

### 10.1 Módulos nuevos o modificados

```
geoguardian/
├── dominio/
│   ├── nombre_academico.py     NUEVO · analizar_nombre(nombre_actual, estudiante) -> AnalisisNombre
│   │                                   nombre_de_archivo(nombre_academico) -> str   (D-19, D-20)
│   ├── ubicacion.py            NUEVO · evaluar_destino(InfoVolumen, ruta) -> [Aviso]
│   │                                   (espacio, FAT32, OneDrive, misma unidad que respaldo, longitud de ruta)
│   └── advertencia_cierre.py   NUEVO · requiere_advertencia(administrado, tiene_archivo, n_capas)  (D-18)
├── persistencia/
│   ├── geopaquete.py           MODIFICADO · esquema 2 para proyectos nuevos
│   └── migraciones.py          NUEVO · version_actual(ruta), migrar(ruta, fecha) -> bool        (D-25)
├── administracion/
│   ├── administrador_proyecto.py  MODIFICADO · inicializar() recibe SolicitudInicializacion
│   │                                         (datos, nombre académico, ubicación, respaldo)
│   ├── almacenamiento.py       NUEVO · adaptador de QStorageInfo/QStandardPaths -> InfoVolumen
│   └── registro_adopciones.py  NUEVO · QgsSettings: origen -> administrado                         (D-22)
├── interfaz/
│   ├── asistente_inicializacion.py  MODIFICADO · 4 páginas (ver §10.3)
│   ├── dialogo_cierre.py       NUEVO · diálogo de D-26; devuelve la acción elegida
│   └── panel_estado.py         MODIFICADO · proyecto activo, ruta, `Abrir carpeta` (D-27), aviso de no administrado
├── filtro_cierre.py            NUEVO · QObject.eventFilter sobre la ventana principal (D-17)
└── complemento.py              MODIFICADO · crea e instala/desinstala FiltroCierre y RegistroAdopciones
```

Reglas de dependencia: los tres módulos nuevos de `dominio` son puros (reciben datos, no
consultan el sistema). `almacenamiento.py` es el único que toca `QStorageInfo` y variables de
entorno, para que las reglas de ubicación se prueben sin discos reales. `filtro_cierre.py` vive
junto a `complemento.py` porque depende de la ventana principal (`iface`); solo llama a
`administracion` y a `interfaz`. `complemento.py` sigue siendo la raíz de composición.

### 10.2 Flujo de cierre (D-17, D-18, D-26)

```
QGIS: cerrar ventana ─► FiltroCierre.eventFilter(QCloseEvent)
        │ requiere_advertencia(...) es falso ─► dejar pasar (QGIS pregunta lo suyo después)
        │ verdadero ─► DialogoCierre
               ├─ Cancelar ───────────────► ignorar el evento (QGIS sigue abierto)
               ├─ Cerrar sin administrar ─► dejar pasar
               └─ Inicializar ahora ──────► ignorar el evento y abrir el asistente

Proyecto no administrado se guarda o recibe su primera capa
        ─► aviso persistente en barra de mensajes y panel con `Inicializar ahora`
```
`unload()` desinstala el filtro antes que cualquier otra cosa.

### 10.3 Flujo de inicialización revisado

```
Asistente
  1. Datos: estudiante, correo, práctica/proyecto (precargado: QgsProject.title() o nombre del .qgz),
     descripción, grupo, asignatura
  2. Nombre académico: analizar_nombre() → muestra si falta el estudiante o la estructura,
     propone "<práctica> - <estudiante>"; editable; debe cumplir D-20
  3. Ubicación: Disco local — recomendado | Unidad externa | Otra carpeta; espacio libre y avisos
     de evaluar_destino(); ruta de respaldo opcional
  4. Resumen: carpeta y archivos que se crearán, ruta del original que no se modificará
AdministradorProyecto.inicializar(solicitud)
  - ruta_proyecto_origen = QgsProject.fileName() antes de guardar (vacía si nunca se guardó)
  - carpeta = <padre>/<nombre_de_archivo>;  .qgz = <nombre_de_archivo>.qgz
  - igual que rc1: estructura, Proyecto.gpkg (esquema 2), entradas, write(), adopción, manifiesto
  - ruta_proyecto_administrado = ruta del nuevo .qgz;  RegistroAdopciones.agregar(origen, administrado)
```

### 10.4 Apertura revisada

```
detectar_administrado()
  ├─ si Proyecto.gpkg tiene esquema 1 → migraciones.migrar() → evento esquema_migrado
  ├─ (resto igual que rc1)
  └─ si NO está administrado y RegistroAdopciones conoce esta ruta como origen
         → aviso con `Abrir versión administrada`
```

## 11. rc2 · Ajustes de UX (2026-10-19)

> D-28 a D-32 de [DECISIONES.md](DECISIONES.md). No cambian persistencia ni el esquema; las
> unidades externas (D-33, D-34) se describen en §12.

```
geoguardian/
├── dominio/
│   └── semaforo.py             MODIFICADO · frases de D-31, orden de motivos, texto_indicador(),
│                                            recursos_en_proyecto()
├── interfaz/
│   ├── indicador_barra.py      NUEVO · IndicadorBarra(QToolButton): icono + punto + texto (D-31)
│   ├── colores.py              NUEVO · colores del semáforo compartidos por panel e indicador
│   ├── asistente_inicializacion.py  MODIFICADO · páginas de nombre, ubicación y resumen (D-28–D-30)
│   └── panel_estado.py         MODIFICADO · frases y conteo de D-32
└── complemento.py              MODIFICADO · crea la barra "GeoGuardian" con el indicador; el clic
                                             alterna el panel; muestra "Proyecto administrado creado"
```

Flujo del indicador:
```
AdministradorProyecto.estado_actualizado ─► complemento.refrescar_panel()
        ├─ PanelEstado.mostrar(nivel, motivos, resumen)
        └─ IndicadorBarra.mostrar(nivel, motivos)  ── texto_indicador() (puro)
IndicadorBarra.clicked ─► PanelEstado.setUserVisible(not visible)
```
`unload()` retira la barra (`removeToolBar` y `deleteLater`) después del panel. El indicador no
consulta el proyecto: solo presenta lo que le pasa `complemento.py`.


## 12. rc2 · Unidades externas con letra cambiante (D-33, D-34, aprobadas el 2026-10-19)

```
geoguardian/
├── dominio/
│   └── recuperacion.py         NUEVO · puro: IdentidadUbicacion, ruta_en_volumen(), reconstruir(),
│                                       raiz_unidad(), recuperar(identidad, id, volumenes, existe, leer_ids)
├── persistencia/
│   ├── geopaquete.py           MODIFICADO · esquema 3 para proyectos nuevos
│   └── migraciones.py          MODIFICADO · columnas del esquema 3; 1 → 3 y 2 → 3 en una transacción
├── administracion/
│   ├── identidad_proyecto.py   NUEVO · solo biblioteca estándar: lee id_proyecto del .qgz (XML),
│   │                                   del manifiesto y del GPKG
│   ├── almacenamiento.py       MODIFICADO · etiqueta del volumen (QStorageInfo.name()), lista de
│   │                                   volúmenes montados y clase Almacenamiento inyectable
│   ├── registro_adopciones.py  MODIFICADO · entradas {origen, administrado, id_proyecto}; lee el
│   │                                   formato anterior
│   └── administrador_proyecto.py  MODIFICADO · registra la identidad al inicializar, la actualiza al
│                                   abrir, resuelve la versión administrada y localiza a mano
└── complemento.py              MODIFICADO · avisos de unidad no encontrada y de varias candidatas,
                                             `Localizar unidad o carpeta` (QFileDialog)
```

Dependencias: `dominio/recuperacion.py` no toca discos; recibe `existe` y `leer_ids` como
funciones. `AdministradorProyecto` recibe un `Almacenamiento` (por omisión, el de Qt), lo que permite
probar el cambio de letra con volúmenes simulados.

```
Abrir un original adoptado
  RegistroAdopciones.buscar(ruta, identidad del original) ─► entrada
  recuperar(entrada.administrado, entrada.id_proyecto, volúmenes)
     ├─ ENCONTRADA(ruta) ─► actualizar registro ─► version_administrada_disponible(ruta)
     ├─ VARIAS(rutas)    ─► candidatas_administradas(rutas)  (aviso + Localizar)
     └─ NO_ENCONTRADA / ID_DISTINTO ─► unidad_no_encontrada(origen)  (aviso + Localizar)
Localizar unidad o carpeta ─► AdministradorProyecto.localizar_version_administrada(origen, carpeta)
     └─ valida id_proyecto ─► actualizar registro ─► version_administrada_disponible(ruta)
```

## 13. rc2 · Cierre: asistente (D-39, 2026-10-19)

```
geoguardian/
├── dominio/
│   └── catalogo_asignaturas.py      NUEVO · ASIGNATURAS (M1–M5), opciones_asignatura()
└── interfaz/
    └── asistente_inicializacion.py  MODIFICADO · estilo clásico, Anterior/Siguiente/Cancelar,
                                     combo editable de asignatura, sugerencia que se recalcula
```

El asistente no guarda estado propio entre páginas: cada página relee de las anteriores en
`initializePage`, así que al volver y avanzar se recalculan las validaciones y el resumen. Solo
`PaginaResumen.validatePage` llama a `AdministradorProyecto.inicializar`. El último guardado de
D-38 no cambia.

## 14. v0.2.0 · Hito 1: inventario y "Revisar capas" (D-40 a D-52, aprobadas el 2026-10-19)

```
geoguardian/
├── dominio/
│   ├── inventario.py                NUEVO · OrigenFuente, Disponibilidad, EstadoSrc (Enum);
│   │                                EntradaCapa, IdentidadFuente, FuenteInventariada,
│   │                                CapaInventariada, Inventario (dataclasses inmutables)
│   └── clasificacion_inventario.py  NUEVO · clasificar_origen, evaluar_disponibilidad, evaluar_src,
│                                    identidad_de, construir_inventario, equivalente_v010 (pruebas)
├── inventario/                      NUEVO · ── usa PyQGIS; solo lee ──
│   ├── lector_capas.py              leer_capa(QgsMapLayer, contexto, src) -> EntradaCapa
│   └── servicio_inventario.py       ServicioInventario: construir() bajo demanda
├── interfaz/
│   └── dialogo_revisar_capas.py     NUEVO · DialogoRevisarCapas(QDialog)
└── complemento.py                   MODIFICADO · acción "Revisar capas" en la barra de GeoGuardian
```

**Flujo.** La acción solo está activa en proyectos administrados. Al pulsarla, `complemento.py` crea
el diálogo (una vez) y le pasa `_construir_inventario`, que llama a `ServicioInventario.construir()`.
El servicio recorre las capas en el orden del árbol, `leer_capa` traduce cada `QgsMapLayer` a una
`EntradaCapa` (datos planos, sin QGIS) y `construir_inventario` clasifica y agrupa en el dominio puro.
"Volver a revisar" repite el proceso. No se conecta ninguna señal (D-49). Si cambia el proyecto
administrado, el diálogo se cierra.

**Solo lectura (D-40).** Los módulos del inventario no importan `persistencia`, `manifiesto`,
`eventos`, `administracion` ni `sqlite3` (lo comprueba una prueba). Un error al revisar se informa en
el registro de mensajes de QGIS y en la barra de mensajes, nunca en `gg_eventos`.

**SRC de la fuente.** En QGIS 3.28 `sourceCrs()` devuelve el SRC asignado a la capa, no el de la
fuente. El SRC original se lee de `dataProvider().crs()`.

**Por qué la barra de herramientas y no el menú.** El menú *Complementos → GeoGuardian* conserva sus
tres acciones de v0.1.0, que las pruebas de línea base cuentan al descargar el complemento.

### Reglas de dependencia (adiciones)

| Paquete | Puede importar | No puede importar |
|---|---|---|
| `dominio` (inventario) | biblioteca estándar, `constantes`, otros módulos de `dominio` | todo lo demás |
| `inventario` | `dominio`, `contexto`, `constantes`, `monitoreo.descriptor_fuente` (solo funciones públicas), `qgis.core` | `persistencia`, `manifiesto`, `eventos`, `administracion`, `interfaz`, `sqlite3` |
| `interfaz/dialogo_revisar_capas.py` | `dominio`, Qt | `inventario`, `persistencia` (recibe la función que construye) |
