# Cambios de GeoGuardian

## 0.2.0-dev (en desarrollo)

Hito 1, decisiones D-40 a D-55 (ver `docs/DECISIONES.md`). Versión experimental.

**Hito 1 completado y validado** (2026-10-20): pruebas automatizadas en QGIS 3.28 y validación manual
en QGIS Windows (`docs/validacion_hito1_windows.md`).

- Botón **Revisar capas** en la barra de herramientas de GeoGuardian, activo en proyectos
  administrados. Abre un diálogo que muestra, sin cambiar nada, dónde está cada capa vectorial
  (Proyecto.gpkg, carpeta del proyecto, fuera de ella, temporal, servicio en internet, base de datos
  externa, virtual), si está disponible y si su SRC coincide con el del proyecto.
- Advierte cuando el SRC asignado a una capa es distinto del que declara su fuente.
- Las capas ráster, de malla y de nube de puntos aparecen como "No revisada en esta versión".
- El inventario vive solo en memoria y se construye al abrir el diálogo o al pulsar
  **Volver a revisar**: sin tablas, eventos, migraciones ni cambios en el manifiesto, el semáforo o
  el panel.
- Versión `0.2.0-dev`, marcada como experimental.

## 0.1.0 (2026-10-19)

Primera versión estable de GeoGuardian. Deriva de 0.1.0-rc2, validada con las pruebas
automatizadas y las pruebas manuales en Windows, y **no tiene cambios funcionales** respecto a ella.

- Versión `0.1.0` en `metadata.txt` y en `VERSION_COMPLEMENTO`; el complemento deja de marcarse
  como experimental.
- Se publica bajo la GNU GPL v2 o posterior (`GPL-2.0-or-later`, archivo `LICENSE`). Autor en
  `metadata.txt`: MTI. Nereo Aquino.
- El paquete instalable incluye el archivo LICENSE de GPL-2.0-or-later.
- Sin cambios en el esquema 3, las tablas, los campos, los estados, los eventos ni las migraciones.
- Pendiente para v0.2.0: consolidación de capas, copia de ráster, vectores dentro de
  `Proyecto.gpkg`, distinción entre archivo externo y servicio remoto, respaldo físico o
  sincronización, empaquetado y ZIP académico, docente configurable, metadatos ampliados y puntos
  de control o versionado.

## 0.1.0-rc2 (2026-10-19)

Decisiones D-16 a D-39 (ver `docs/DECISIONES.md`).

- Asistente de cuatro páginas: datos, nombre final del proyecto administrado, ubicación de trabajo
  y resumen en bloques, con navegación **Anterior / Siguiente / Cancelar** (D-28 a D-30, D-39).
- `Asignatura o módulo` como combo editable con los módulos M1 a M5 de la carrera de Técnico en SIG
  y la opción de escribir otro valor (D-39).
- Indicador permanente en la barra de herramientas y estados del panel (D-31, D-32).
- Unidades externas con letra cambiante: identidad por etiqueta de volumen y ruta relativa,
  validación por `id_proyecto` y `Localizar unidad o carpeta` (D-33, D-34). Esquema 3 con migración
  automática desde los esquemas 1 y 2.
- `Guardar ahora` usa el guardado nativo de QGIS: ya no aparece "El proyecto ha cambiado en el
  disco" (D-35).
- Aviso breve de versión administrada disponible, con prioridad sobre el aviso genérico (D-36).
- Estado "original con versión administrada": indicador, panel y diálogo de cierre propios; no se
  puede crear una segunda versión (D-37).
- La inicialización termina con el proyecto guardado del todo; cerrar QGIS no pide guardar (D-38).

## 0.1.0-rc1 (2026-10-18)

Primera versión candidata: decisiones D-01 a D-15.
