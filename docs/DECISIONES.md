# GeoGuardian — Registro de decisiones

Formato: cada decisión tiene contexto, opciones, propuesta y estado.
Estados: **Pendiente** (necesita aprobación de NEREO), **Propuesta** (valor por defecto razonable;
se aplica salvo objeción), **Aprobada**, **Rechazada**.

> **v0.1.0 estable (2026-10-19).** D-01 a D-39 están aprobadas e implementadas en GeoGuardian 0.1.0.
> D-33 a D-38 se validaron además con pruebas manuales en Windows. La funcionalidad de v0.1.0 está
> congelada; las propuestas nuevas se registran para v0.2.0.
>
> **v0.2.0 (en desarrollo).** D-40 a D-52 están aprobadas (NEREO, 2026-10-19) para el Hito 1:
> inventario y revisión de capas de solo lectura. El análisis previo está en el informe de revisión
> técnica del Hito 1.

---

## D-01 · Nomenclatura de tablas, campos, estados y manifiesto — **Aprobada** (2026-10-18)

**Contexto.** La regla del proyecto exige español en tablas, campos, constantes y estados.
La lista de funciones de v0.1.0 usa `gg_project`, `gg_assets`, `gg_events`,
`.geoguardian/manifest.json` y los estados `active`, `external`, `temporary`, `historical`,
`missing`. Ninguna API externa exige esos nombres, así que no califican como excepción.

**Opciones.**
- **A (recomendada): español.** `gg_proyecto`, `gg_recursos`, `gg_eventos`;
  `.geoguardian/manifiesto.json`; estados `activo`, `externo`, `temporal`, `historico`, `faltante`.
- **B: inglés tal como aparece en la lista.** Se documenta como excepción deliberada.

**Por qué A.** Es coherente con la regla general, y la lista parece haberse escrito antes de
fijar la regla. "Recursos" traduce *assets* sin ambigüedad (un recurso es cualquier fuente que
el proyecto usa: capa vectorial, ráster, servicio). Contra A: si en el futuro otros sistemas leen
estas tablas, el inglés sería más universal; hoy no hay ese consumidor.

**Resolución:** opción A.

---

## D-02 · Significado de los estados de recurso — **Aprobada** (2026-10-18)

**Propuesta.**

| Estado      | Significa | Ejemplo |
|-------------|-----------|---------|
| `activo`    | En el proyecto, archivo existe y está **dentro** de la carpeta del proyecto | `datos/manglares.shp`, capa dentro de `Proyecto.gpkg` |
| `externo`   | En el proyecto, existe, pero está **fuera** de la carpeta, o es un servicio remoto o base de datos | `D:\Descargas\inegi.shp`, WMS, XYZ, PostGIS |
| `temporal`  | Capa que se pierde al cerrar QGIS | capa en memoria (`memory`), salida `TEMPORARY_OUTPUT` de Procesos, archivo en la carpeta temporal del sistema |
| `historico` | Estuvo en el proyecto y se **eliminó**; el registro se conserva para trazabilidad | capa quitada del panel de capas |
| `faltante`  | En el proyecto, pero su archivo no existe o la capa es inválida | ruta rota tras mover una USB |

Prioridad cuando aplica más de uno: `faltante` > `temporal` > `activo` > `externo`.
`historico` solo se asigna al eliminar una capa.

**Punto a confirmar.** Interpreto `historical` como "eliminado del proyecto". Otra lectura posible
sería "versión anterior de un recurso", que pertenece a los checkpoints (fuera de alcance).

---

## D-03 · Carpetas creadas al inicializar — **Aprobada** (2026-10-18) · *nombre de carpeta y `.qgz` sustituidos por D-19/D-21*

`datos/`, `salidas/`, `documentos/` y `.geoguardian/`. En v0.1.0 quedan vacías (salvo
`.geoguardian/`); preparan la consolidación futura sin implementarla.
La carpeta del proyecto debe no existir o estar vacía; si no, el asistente se niega
(nunca se sobrescribe).

Nota Windows: una carpeta que empieza con punto **no** queda oculta en el Explorador.
No se le aplica atributo oculto en v0.1.0 (sería modificar atributos del sistema de archivos).

---

## D-04 · Inicializar sobre el proyecto abierto — **Aprobada** (2026-10-18)

**Contexto.** El estudiante puede abrir el asistente con capas ya cargadas.

**Opciones.**
- **A (recomendada): adoptar.** El proyecto actual se guarda como `Proyecto.qgz` en la carpeta
  nueva; sus capas se registran y clasifican (normalmente como `externo`). El `.qgz` original,
  si existía, no se toca.
- **B: solo proyecto vacío.** El asistente exige un proyecto nuevo sin capas.

**Por qué A.** Es el caso real del aula: el estudiante empieza a trabajar y después decide
"administrar". B obliga a rehacer trabajo. No se mueve ningún archivo en ninguno de los dos casos.

---

## D-05 · Cuándo se escribe en `Proyecto.gpkg` — **Aprobada** (2026-10-18)

**Opciones.**
- **A (recomendada): de inmediato.** Cada evento y cada cambio de recurso se escribe en el
  momento, en una transacción corta. El `.qgz` solo se escribe cuando el usuario guarda.
- **B: al guardar.** Los eventos se acumulan en memoria y se escriben con el proyecto.

**Por qué A.** Si QGIS se cierra de golpe, el registro sobrevive; es la base de la trazabilidad.
Lo que se escribe es el registro propio del complemento, no datos del estudiante ni archivos
fuente. Contra A: el `.gpkg` cambia aunque el estudiante no haya guardado, y su fecha de
modificación deja de coincidir con la del `.qgz`.

Detalles técnicos asociados: sin conexión permanente (abrir, escribir, cerrar) y `timeout` de 5 s
por si QGIS tiene el archivo abierto. El archivo se crea en modo de diario DELETE (sin `-wal`).

*Ajuste en implementación (2026-10-18):* el diseño decía forzar `journal_mode=DELETE` en cada
conexión. Las pruebas en QGIS 3.28 mostraron que, cuando el estudiante carga una tabla de
`Proyecto.gpkg` como capa, QGIS pasa el archivo a WAL y forzar el cambio bloquea la base
("database is locked"). Ahora no se toca el modo de diario; QGIS lo regresa a DELETE al cerrar.
Ajuste aprobado por NEREO el 2026-10-18. Mientras QGIS tiene abierto `Proyecto.gpkg` pueden existir
`Proyecto.gpkg-wal` y `Proyecto.gpkg-shm` junto a él. **Pendiente para versiones futuras:** la gestión de
esos archivos (cerrar conexiones o hacer *checkpoint* antes de copiar) se evaluará cuando se implementen
el empaquetado y el respaldo.

---

## D-06 · Fuente de verdad: GeoPackage; manifiesto derivado — **Aprobada** (2026-10-18)

`Proyecto.gpkg` contiene el registro completo. El manifiesto es un resumen JSON que se regenera
al inicializar y al guardar; sirve para reconocer la carpeta como administrada sin abrir la base,
y para que herramientas futuras (entrega, revisión) lean lo esencial. Si discrepan
(`id_proyecto` distinto), el semáforo se pone en rojo; no se corrige automáticamente.

---

## D-07 · Cómo se crea el GeoPackage — **Aprobada** (2026-10-18)

El contenedor se crea con el controlador GPKG de GDAL (`osgeo.ogr`, incluido en QGIS), que
garantiza las tablas obligatorias del estándar. Las tablas `gg_*` y todas las lecturas y escrituras
usan `sqlite3` de la biblioteca estándar. Así el repositorio se prueba sin QGIS.

Alternativa descartada: escribir a mano las tablas `gpkg_*` con `sqlite3`. Evitaría GDAL, pero
arriesga producir un archivo que no cumpla el estándar.

---

## D-08 · Cómo se reconoce un proyecto administrado — **Aprobada** (2026-10-18)

Las tres condiciones a la vez:
1. El `.qgz` tiene la entrada personalizada `geoguardian/id_proyecto` (`QgsProject.writeEntry`).
2. Existe `.geoguardian/manifiesto.json` junto al `.qgz` con el mismo `id_proyecto`.
3. Existe `Proyecto.gpkg` con una fila en `gg_proyecto` con ese `id_proyecto`.

Si (1) se cumple y (2) o (3) fallan: proyecto administrado en estado **rojo** (inconsistente).
Si (1) no se cumple: proyecto no administrado (gris). Un proyecto administrado abierto en una
computadora sin GeoGuardian funciona como cualquier proyecto QGIS.

---

## D-09 · Herramienta de pruebas — **Aprobada** (2026-10-18)

`unittest` de la biblioteca estándar (pytest no viene con QGIS). Para respetar la nomenclatura,
archivos `prueba_*.py` y métodos `prueba_*`, con un ejecutor `pruebas/ejecutar_pruebas.py` que
configura `TestLoader.testMethodPrefix = "prueba"`.
Costo: el descubrimiento automático de pruebas de VS Code o PyCharm no las encuentra sin
configurarlo. Alternativa: aceptar el prefijo `test_` como excepción documentada.

---

## D-10 · Visibilidad de las tablas `gg_*` — **Aprobada** (2026-10-18)

Se registran en `gpkg_contents` como `attributes`, así el docente puede abrirlas desde el
Explorador de QGIS. Riesgo: el estudiante podría editarlas o borrarlas. En v0.1.0 no se protege
contra eso (protección o verificación de integridad sería ampliar alcance); el semáforo sí
detecta si faltan tablas o la fila de `gg_proyecto`.

---

## D-11 · Rutas relativas — **Aprobada** (2026-10-18)

`QgsProject.setFilePathStorage(Qgis.FilePathType.Relative)` (disponible desde QGIS 3.22).
Limitación conocida en Windows: un archivo en otra unidad (por ejemplo `D:` cuando el proyecto
está en `C:`) no puede expresarse como ruta relativa y QGIS lo guarda absoluto. Esas capas ya
quedan clasificadas como `externo`, así que el semáforo lo refleja.

---

## D-12 · Recursos externos ponen el semáforo en amarillo — **Aprobada** (2026-10-18)

Un recurso externo no rompe el proyecto hoy, pero sí su portabilidad (al copiar la carpeta a
otra computadora no viaja). Por eso amarillo, no verde ni rojo.

---

## D-13 · Contraseñas en fuentes de datos — **Aprobada** (2026-10-18)

Antes de guardar la fuente de una capa en `gg_recursos`, eventos o manifiesto, se elimina
cualquier contraseña: se usa `QgsMapLayer.publicSource()` y además `dominio/seguridad.ocultar_contrasenas`
(implementación de rc1). Nunca se escriben credenciales.

---

## D-14 · Fechas y horas — **Aprobada** (2026-10-18)

ISO 8601 con desplazamiento de la zona local, al segundo: `2026-10-18T15:54:13-06:00`.
Legible para el docente y sin ambigüedad.

---

## D-15 · Versión de QGIS y Qt — **Aprobada** (2026-10-18)

Mínimo QGIS 3.28 (`qgisMinimumVersion=3.28`). Se importa Qt siempre vía `qgis.PyQt` para
facilitar una futura compatibilidad con QGIS 4 / Qt6, sin declararla ni probarla en v0.1.0.

---

# Propuesta rc2 · Experiencia de usuario tras la prueba manual de rc1

> Estado: **aprobada** por NEREO el 2026-10-18 (D-16=A, D-17=A, D-19=A, D-22=A, D-23 con OneDrive,
> D-25 automática, D-27 sí; D-18, D-20, D-21, D-24 y D-26 como se propusieron).
> Origen: requisitos 1–17 de NEREO tras probar `0.1.0-rc1` en Windows.
> Al implementarse, la versión pasaría a `0.1.0-rc2`; la estable `0.1.0` sale después de repetir la
> prueba manual.

---

## D-16 · Nombre de los documentos de diseño — **Aprobada** (2026-10-18)

Los requisitos llaman a los documentos `DECISIONES.md`, `ARQUITECTURA.md` y
`especificaciones/v0.1.0.md`; existían como `DECISIONS.md`, `ARCHITECTURE.md` y `specs/`.

- **A (recomendada): renombrar** a `docs/DECISIONES.md`, `docs/ARQUITECTURA.md` y
  `docs/especificaciones/v0.1.0.md`, y corregir los enlaces internos y el README. Es coherente con
  la regla de nomenclatura en español; ninguna herramienta exige los nombres en inglés.
- **B: conservar** los nombres en inglés como excepción documentada.

**Resolución:** opción A. Documentos renombrados el 2026-10-18.

---

## D-17 · Cómo advertir al cerrar o cambiar un proyecto no administrado — **Aprobada** (2026-10-18)

**Hallazgo técnico.** En QGIS 3.28 un complemento **no puede cancelar** "Proyecto nuevo" ni
"Abrir proyecto" con la API pública: `QgsProject` no tiene una señal cancelable previa al cierre
(`aboutToBeCleared` no existe en 3.28; `removeAll` y `cleared` llegan cuando ya se está cerrando).
Sí es posible cancelar el **cierre de QGIS**: un filtro de eventos (`eventFilter`) sobre la ventana
principal recibe el `QCloseEvent` antes que QGIS y puede ignorarlo. Para "Abrir proyecto" existe
`iface.registerCustomProjectOpenHandler`, pero hay que comprobar con un prototipo si se invoca
antes de cerrar el proyecto actual; no se confía en ello sin verificarlo.

- **A (recomendada): dos mecanismos.**
  1. **Al cerrar QGIS:** diálogo modal con el mensaje de D-26 y las acciones
     `Inicializar ahora`, `Cerrar sin administrar`, `Cancelar`.
  2. **Antes de que el estudiante pueda perder la oportunidad:** en cuanto el proyecto no
     administrado cumple la condición de D-18 (se guarda o recibe su primera capa), se muestra un
     aviso persistente en la barra de mensajes y en el panel con el botón `Inicializar ahora`.
     Así el aviso llega **antes** de "Nuevo" o "Abrir", que no se pueden interceptar.
  3. Si el prototipo confirma que `CustomProjectOpenHandler` se invoca antes del cierre, también
     se muestra el diálogo modal al abrir otro proyecto (sin depender de ello).
**Resolución:** opción A. El punto 3 queda condicionado al prototipo de la especificación §11.2;
rc2 implementa los puntos 1 y 2.

- **B: interceptar las acciones internas de QGIS** (`actionNewProject`, `actionOpenProject`,
  proyectos recientes, arrastrar y soltar). Cubriría todo, pero depende de detalles internos que
  cambian entre versiones y es frágil. No recomendada.

---

## D-18 · Cuándo se muestra la advertencia — **Aprobada** (2026-10-18)

Función pura `requiere_advertencia(administrado, tiene_archivo, numero_capas)`:
se advierte si **no** está administrado **y** (`tiene_archivo` **o** `numero_capas > 0`).
Un proyecto nuevo, vacío y nunca guardado no genera advertencia (requisito 4).
`Cerrar sin administrar` no se recuerda: la advertencia vuelve en el siguiente cierre.

---

## D-19 · Nombre académico: formato de título y de archivos — **Aprobada** (2026-10-18)

Convención: `NOMBRE DE LA PRACTICA O PROYECTO - NOMBRE DEL ESTUDIANTE`.

| Uso | Propuesta |
|---|---|
| Título visible (`QgsProject.title()`, `gg_proyecto.nombre_academico`, panel) | Tal como lo escribe el estudiante, con acentos: `Manglares de Términos - Ana Pérez López` |
| Carpeta y `.qgz` | Mismo texto **sin acentos ni ñ**, sin `< > : " / \ \| ? *`, con espacios y ` - `: `Manglares de Terminos - Ana Perez Lopez.qgz` |

Preguntas:
- **Mayúsculas.** A (recomendada): respetar las mayúsculas que escriba el estudiante.
  B: convertir todo a MAYÚSCULAS, como en el texto de la convención.
- **Acentos en archivos.** Se recomienda quitarlos: los ZIP creados en Windows y abiertos en otros
  sistemas, algunas herramientas GDAL y la futura consolidación fallan con nombres no ASCII.

**Resolución:** A, se respetan las mayúsculas del estudiante; los nombres de archivo van sin acentos.

Longitud: máximo 80 caracteres para el nombre de archivo, y aviso si la ruta completa del
`.qgz` pasa de 200 caracteres (límite clásico de 260 de Windows).

---

## D-20 · Qué cuenta como "contiene suficientemente" — **Aprobada** (2026-10-18)

Comparación sobre texto normalizado: minúsculas, sin acentos, `_` y espacios repetidos
convertidos en un espacio. Palabras significativas: 2 letras o más, sin partículas
(`de`, `del`, `la`, `las`, `los`, `y`).

- **Estudiante presente:** al menos 2 palabras significativas de su nombre (o todas, si tiene
  menos de 2) aparecen en el nombre actual.
- **Estructura completa:** el nombre tiene la forma `X - Y`, `Y` contiene al estudiante y `X`
  queda no vacío.
- Si falta algo, se propone `<práctica detectada> - <nombre del estudiante>`, donde la práctica
  detectada es el nombre actual sin las palabras del estudiante. El estudiante puede editar la
  propuesta, pero la versión final debe cumplir estas mismas reglas.

---

## D-21 · `Proyecto.gpkg` conserva su nombre fijo — **Aprobada** (2026-10-18)

El requisito 8 cambia el nombre de la carpeta y del `.qgz`. Se propone que `Proyecto.gpkg` y
`.geoguardian/manifiesto.json` mantengan nombres fijos: son archivos de control, no entregables,
y un nombre fijo permite reconocer cualquier proyecto administrado. El manifiesto ya guarda el
nombre real del `.qgz` en `archivos.proyecto` (rc1 lo usa al verificar), así que no hay cambio
de formato.

---

## D-22 · El proyecto administrado como archivo oficial en sesiones posteriores — **Aprobada** (2026-10-18)

Inicializar un proyecto guardado equivale a "Guardar como" en la carpeta nueva: el original no
se modifica ni se elimina, y la versión administrada queda abierta (requisitos 9 y 10).
Riesgo: el estudiante puede volver a abrir el original desde *Proyectos recientes* y seguir
trabajando allí.

- **A (recomendada):** guardar en la configuración del perfil de QGIS (`QgsSettings`, no en
  archivos del proyecto) la correspondencia `ruta_proyecto_origen → ruta_proyecto_administrado`.
  Al abrir un original ya adoptado, la barra de mensajes avisa y ofrece `Abrir versión
  administrada`. No se bloquea ni se modifica el original.
- **B:** solo registrar ambas rutas en `gg_proyecto`; no se avisa al reabrir el original.

**Resolución:** A. Precisión de NEREO: antes de ofrecer `Abrir versión administrada` se verifica
siempre que el archivo registrado exista; si no existe, no se ofrece.

---

## D-23 · Ubicación de trabajo, espacio libre y FAT32 — **Aprobada** (2026-10-18)

- **Disco local — recomendado:** la unidad de la carpeta *Documentos* del usuario
  (`QStandardPaths.DocumentsLocation`); carpeta padre por omisión: *Documentos*.
- **Unidad externa:** lista de volúmenes de `QStorageInfo.mountedVolumes()` distintos del de
  Documentos, listos y con escritura. **No se detecta si una unidad es "removible"**: Qt 5 no lo
  expone y en Windows los discos USB grandes se reportan como fijos. El estudiante elige; el
  asistente muestra la advertencia de rendimiento, desconexión y espacio.
- **Otra carpeta:** selector libre.
- **Espacio libre:** `QStorageInfo(ruta).bytesAvailable()`, mostrado en GB. Aviso amarillo con
  menos de 5 GB libres; no bloquea.
- **FAT32:** **viable y no frágil** con `QStorageInfo.fileSystemType()` (API de Qt). Valores:
  `FAT32` en Windows, `vfat` en Linux, `msdos` en macOS. Aviso: "no admite archivos de más de
  4 GB (imágenes satelitales, ortomosaicos)". Se probó en QGIS 3.28 que la API está disponible.
- **OneDrive (nuevo, para aprobar):** si la ruta está dentro de `%OneDrive%`,
  `%OneDriveCommercial%` u `%OneDriveConsumer%` (variables que define el cliente de OneDrive), se
  advierte que la sincronización puede bloquear o duplicar `Proyecto.gpkg` y subir datos pesados.
  Es frecuente en Windows que *Documentos* esté redirigido a OneDrive.

**Resolución:** aprobado, incluido OneDrive. Precisión de NEREO: el aviso de OneDrive es
informativo y no bloqueante. Se aprueban la detección de FAT32 con Qt y la presentación del
espacio disponible.

---

## D-24 · Ruta de respaldo opcional — **Aprobada** (2026-10-18)

Se guarda en `gg_proyecto.ruta_respaldo` y en el manifiesto. Validación: la carpeta existe; aviso
si está en la misma unidad que el proyecto (un respaldo en el mismo disco no protege de fallos).
**GeoGuardian no escribe nada en esa carpeta** en v0.1.0; ni siquiera prueba si es escribible.

---

## D-25 · Migración del esquema 1 → 2 — **Aprobada** (2026-10-18)

Al abrir un proyecto rc1 (`gg_proyecto.version_esquema = 1`), GeoGuardian agrega las columnas
nuevas con `ALTER TABLE ... ADD COLUMN` (todas admiten nulo) en una sola transacción, sube
`version_esquema` a 2 y registra el evento nuevo `esquema_migrado`. Valores para proyectos rc1:
`ruta_proyecto_administrado` = ruta actual del `.qgz`; `nombre_academico`, `ruta_proyecto_origen`,
`ruta_respaldo` y `tipo_ubicacion` quedan nulos. El `.qgz` rc1 **no se renombra**.

- Compatibilidad hacia atrás: rc1 lee por nombre de columna y no valida la versión, así que un
  proyecto migrado sigue abriendo con rc1.
- Si la migración falla, se revierte, el semáforo queda en rojo y se registra `error_complemento`.
- Pregunta: ¿se aprueba que la migración ocurra **automáticamente** al abrir (escribe en
  `Proyecto.gpkg`, como ya autoriza D-05), o se prefiere un botón `Actualizar proyecto`?
  Recomendada: automática.

**Resolución:** automática. Precisión de NEREO: la migración es transaccional e idempotente, y
`version_esquema` se actualiza solo después de completar todos los cambios.

---

## D-26 · Texto de la advertencia — **Aprobada** (2026-10-18)

> **Este proyecto todavía no está administrado**
>
> GeoGuardian detectó que este proyecto todavía no está administrado. Si lo cierras ahora,
> GeoGuardian no podrá garantizar la integridad, trazabilidad ni posterior consolidación de sus
> archivos. ¿Deseas inicializarlo antes de cerrar?
>
> *GeoGuardian organiza tu proyecto en una carpeta propia, registra qué datos usa y te avisa si
> alguno puede perderse, para que puedas entregarlo completo.*
>
> [Inicializar ahora] [Cerrar sin administrar] [Cancelar]

`Inicializar ahora` cancela el cierre y abre el asistente; al terminar, QGIS queda abierto con el
proyecto administrado (no se cierra solo). `Cancelar` es la opción por omisión (Esc).

---

## D-27 · Acceso a la carpeta desde el panel — **Aprobada** (2026-10-18)

El requisito 16 dice "ofrecer posteriormente acceso a su carpeta".
- **A (recomendada):** incluir ya en rc2 el botón `Abrir carpeta` (abre el explorador del sistema
  con `QDesktopServices.openUrl`; no modifica nada).
- **B:** dejarlo para una versión posterior; en rc2 solo se muestra la ruta.

**Resolución:** A, se incluye en rc2.

---

# rc2 · Ajustes de UX antes de cerrar la RC (2026-10-19)

> Origen: mensaje de NEREO del 2026-10-19 (ajustes 1–9). D-28 a D-32 recogen lo que NEREO definió
> y quedan **aprobadas** como parte de rc2; solo precisan detalles de implementación que no cambian
> la arquitectura. D-33 y D-34 (ajuste 3, unidades externas) cambian el esquema y añaden un flujo
> nuevo; se propusieron aparte y NEREO las aprobó el mismo día (opción A, con búsqueda automática).
> Sigue fuera de alcance: consolidación, respaldo real, autoguardado y empaquetado.

---

## D-28 · Terminología y pantalla del nombre — **Aprobada** (2026-10-19)

- En la interfaz, "Nombre académico" pasa a **"Nombre de la práctica o proyecto"** (lo que el
  estudiante escribe en la página de datos) y **"Nombre final del proyecto administrado"** (práctica
  + estudiante).
- La página muestra en bloques separados: *Proyecto detectado*, *Estudiante*, *Nombre final
  sugerido* (campo editable a todo el ancho) y, solo si aplica, la advertencia de que falta el
  estudiante o la estructura no cumple la convención. La convención visible sigue siendo
  `NOMBRE DE LA PRACTICA O PROYECTO - NOMBRE DEL ESTUDIANTE`.
- La validación ya compara sin distinguir mayúsculas, acentos ni espacios repetidos (D-20); se
  conserva y se añaden pruebas.
- **Precisión:** los identificadores internos no cambian (`nombre_academico` en `gg_proyecto`, el
  manifiesto y el código), para no tocar el esquema 2 ni la migración. Solo cambia el texto visible.

## D-29 · Pantalla de ubicación — **Aprobada** (2026-10-19)

Jerarquía: pregunta *¿Dónde quieres trabajar?* con `En este equipo — recomendado`, `Unidad externa`
y `Otra carpeta`, cada una con su explicación breve (textos de NEREO). Debajo, en texto secundario:
carpeta seleccionada, sistema de archivos y espacio disponible. Separado visualmente, el bloque
*Copia de respaldo — opcional* con el texto "GeoGuardian guardará esta ubicación para una función
posterior. En esta versión todavía no copia ni sincroniza archivos."
El valor interno `disco_local` de `tipo_ubicacion` no cambia.

## D-30 · Resumen y mensaje posterior a la creación — **Aprobada** (2026-10-19)

- El resumen se presenta en bloques: *Proyecto que administrará GeoGuardian*, *A partir de ahora
  trabajarás con* (`<nombre final>.qgz`, ruta completa y la indicación destacada), *Proyecto original*
  (ruta y advertencia de no seguir editándolo) y *GeoGuardian creará*. El botón final dice
  `Crear proyecto administrado`.
- Tras crear el proyecto se muestra *Proyecto administrado creado* con el nombre del `.qgz`.
- **Precisión sobre "abrir inmediatamente la versión administrada":** desde rc2 la inicialización
  equivale a "Guardar como" (D-21/F14), así que al terminar el proyecto activo **ya es** el `.qgz`
  administrado (`QgsProject.fileName()` apunta a él y QGIS actualiza el título de la ventana). No se
  vuelve a leer el archivo desde disco porque eso descartaría las capas temporales del estudiante,
  que QGIS no guarda en el `.qgz`. Se añade una prueba que verifica que el proyecto activo es el
  administrado. Si la prueba manual en Windows muestra que hace falta recargar, se consultará.

## D-31 · Indicador permanente en la barra de herramientas — **Aprobada** (2026-10-19)

- Un único `QToolButton` en una barra propia *GeoGuardian*: el icono compuesto (logo + punto del
  color del semáforo) y el texto del estado. Al ser un solo control, un clic en cualquier parte
  muestra u oculta el panel; es enfocable con teclado y tiene nombre accesible.
- Sustituye al icono suelto de "Panel GeoGuardian" que rc1 añadía a la barra de complementos (sería
  redundante); la acción sigue en el menú *Complementos → GeoGuardian*.
- Textos: gris `Proyecto no administrado`, verde `Proyecto en buen estado`, amarillo
  `Proyecto requiere atención`, rojo `Proyecto con problemas`. El color nunca va solo.
- Tooltip: `GeoGuardian — <estado>: <motivo principal>.` El detalle sigue en el panel.
- **Precisión (motivo principal):** es el primer motivo de la lista del semáforo. Para que no sea
  casi siempre "Hay cambios sin guardar", el orden de los motivos amarillos pasa a ser: capas
  temporales (riesgo de pérdida), ediciones sin confirmar, recursos fuera de la carpeta, cambios sin
  guardar. Los rojos siguen primero. El nivel del semáforo no cambia.
- Los motivos se redactan en términos de *recursos* y con acentos, p. ej. "10 recursos se encuentran
  fuera de la carpeta administrada".

## D-32 · Estados del panel lateral — **Aprobada** (2026-10-19)

El panel usa las mismas cuatro frases que el indicador (sustituyen a "Revisar antes de entregar",
"Requiere atención" y "Todo en orden"). Muestra primero `Recursos en el proyecto: N` y después
Activos, Externos, Temporales, Faltantes e Históricos. Botones `Guardar ahora` y `Abrir carpeta`.
**Precisión:** N cuenta los recursos que siguen en el proyecto (activos + externos + temporales +
faltantes); los históricos son capas ya retiradas y se muestran aparte.

---

## D-33 · Identidad de la ubicación en unidades externas — **Aprobada** (2026-10-19)

Problema: en Windows la letra (`E:`, `F:`) de una USB puede cambiar entre sesiones. Las rutas
internas del proyecto ya son relativas (D-11), así que abrir el `.qgz` desde otra letra funciona.
Lo que sí guarda rutas absolutas es: `gg_proyecto` (`ruta_proyecto_origen`,
`ruta_proyecto_administrado`, `ruta_respaldo`) y el registro de adopciones en `QgsSettings` (D-22).

Propuesta: registrar, junto a cada ruta absoluta, la identidad del volumen obtenida con
`QStorageInfo`: **etiqueta del volumen**, **sistema de archivos** y **ruta relativa dentro del
volumen**, para el proyecto administrado y para el respaldo. El `id_proyecto` (que ya existe en el
`.qgz`, el GPKG y el manifiesto) sirve para confirmar que una carpeta encontrada es realmente el
mismo proyecto.

- **A (recomendada): esquema 3.** Columnas nuevas y anulables en `gg_proyecto`
  (`etiqueta_volumen`, `sistema_archivos`, `ruta_en_volumen`, `etiqueta_volumen_respaldo`,
  `ruta_respaldo_en_volumen`), las mismas en el manifiesto, y migración 2 → 3 con el mismo mecanismo
  de D-25 (transaccional, idempotente, `version_esquema` al final; un GPKG de esquema 1 pasa por
  1 → 2 → 3). El registro de adopciones guarda por entrada `{ruta, etiqueta, ruta_en_volumen,
  id_proyecto}` y sigue leyendo las entradas antiguas.
- **B: ampliar el esquema 2 sin cambiar la versión.** Menos código, pero los proyectos que ya
  creaste con rc2 quedarían con "esquema 2" sin esas columnas y la migración no tendría cómo
  distinguirlos.

Al abrir un proyecto administrado desde otra letra, GeoGuardian actualizaría en silencio las rutas
absolutas de `gg_proyecto` y lo anotaría en `gg_eventos` (evento nuevo `ubicacion_actualizada`).

## D-34 · Cuando no se encuentra la unidad registrada — **Aprobada** (2026-10-19)

Se aplica a la asociación *proyecto original → versión administrada* (D-22). Al abrir el original:
1. Si la ruta registrada existe y su manifiesto tiene el mismo `id_proyecto`: se ofrece como hoy.
2. Si no existe:
   - **A (recomendada):** buscar entre las unidades conectadas una con la misma etiqueta que tenga el
     proyecto en la misma ruta relativa y el mismo `id_proyecto`. Si aparece, se ofrece abrirla y se
     actualiza el registro. Si no aparece, se muestra: "No se encuentra la unidad utilizada por este
     proyecto. Windows puede haberle asignado otra letra o la unidad puede estar desconectada." con
     el botón `Localizar unidad o carpeta`.
   - **B:** sin búsqueda automática; mostrar siempre el mensaje y `Localizar unidad o carpeta`.
3. `Localizar unidad o carpeta` abre un selector de carpeta; GeoGuardian solo acepta la carpeta si
   contiene el proyecto con el mismo `id_proyecto`, y entonces actualiza el registro.
4. La asociación nunca se borra automáticamente: una unidad no encontrada no se da por perdida.

Las capas cuyo archivo está en una unidad no conectada siguen como `faltante` (D-02, el semáforo
sigue en rojo), pero su motivo diría que no se encuentra la unidad en vez de que el archivo no
existe. La ruta de respaldo solo se registra en esta versión, así que no se verifica al abrir.

**Resolución de D-33 y D-34 (NEREO, 2026-10-19):** opción A en ambas, esquema 3 y búsqueda
automática, con estas reglas:
1. La letra de unidad (`E:`, `F:`…) es circunstancial; no forma parte de la identidad del proyecto.
   La identidad es la etiqueta del volumen + la ruta relativa dentro del volumen, y la confirma el
   `id_proyecto`.
2. Si la ruta absoluta registrada deja de existir, se buscan las unidades conectadas cuya etiqueta
   coincida con la registrada y se reconstruye en ellas la ruta relativa conocida.
3. Antes de aceptar una candidata se valida su `id_proyecto` con todas las fuentes disponibles:
   el `.qgz`, `manifiesto.json` y `Proyecto.gpkg`. Las que existan deben coincidir con el esperado.
4. Si la etiqueta coincide pero el `id_proyecto` no, no se reasocia.
5. Si más de una unidad con esa etiqueta contiene el proyecto válido, no se elige ninguna: se
   muestran las candidatas y se pasa a la recuperación manual. (Si varias unidades comparten la
   etiqueta pero solo una contiene el proyecto con el `id_proyecto` esperado, esa es la única
   coincidencia válida y se acepta.)
6. Sin coincidencia válida se muestra "No se encuentra la unidad utilizada por este proyecto.
   Windows puede haberle asignado otra letra o la unidad puede estar desconectada." con
   `Localizar unidad o carpeta`.
7. Lo que el estudiante localice a mano también se valida por `id_proyecto` antes de actualizar la
   asociación. Se acepta la raíz de la unidad, la carpeta del proyecto o la carpeta que la contiene.

**Precisiones de implementación:**
- La asociación del registro de adopciones guarda la identidad del original y de la versión
  administrada, más el `id_proyecto`. Así, el original también se reconoce si su propia unidad
  cambia de letra.
- Las asociaciones creadas con la versión anterior de rc2 no tienen `id_proyecto`. Si la ruta
  registrada existe, se completan leyendo el `id_proyecto` de ese archivo. Si no existe, no se pueden
  validar y no se ofrece nada; basta con abrir directamente el proyecto administrado, que vuelve a
  registrar su ubicación.
- Al abrir un proyecto administrado desde otra ubicación, GeoGuardian actualiza `gg_proyecto`, el
  manifiesto y el registro de adopciones, y anota `ubicacion_actualizada` en `gg_eventos`.

## D-35 · `Guardar ahora` usa el guardado nativo de QGIS — **Aprobada** (NEREO, 2026-10-19)

Causa del aviso "El proyecto ha cambiado en el disco": QGIS guarda su propia referencia de la fecha
de modificación del `.qgz`. La acción nativa de guardado la actualiza; una llamada directa a
`QgsProject.write()` desde el complemento la deja desincronizada.

- `Guardar ahora` dispara `iface.actionSaveProject().trigger()`, igual que `Ctrl+S`.
- Antes de guardar se reclasifican los recursos y se cuentan las capas con ediciones sin confirmar.
  Nunca se llama a `commitChanges()`.
- El evento `proyecto_guardado` y el manifiesto se generan una sola vez, en la señal `projectSaved`.
  El botón solo marca `origen=boton` para ese guardado; un `Ctrl+S` posterior queda como
  `origen=qgis`.
- Si QGIS no llega a guardar (por ejemplo, porque el guardado se canceló), no se registra nada y el
  panel avisa del error.
- La creación del proyecto administrado (`inicializar`) sigue escribiendo con `QgsProject.write()`
  porque guarda en una ruta nueva; queda fuera de esta decisión.

## D-36 · Aviso breve de versión administrada disponible — **Aprobada** (NEREO, 2026-10-19)

Al abrir un proyecto original que tiene versión administrada:
- Barra de mensajes (azul): "GeoGuardian: este proyecto tiene una versión administrada disponible."
  con el botón `Abrir versión administrada`. Sin nombre, ruta ni explicaciones.
- Panel lateral: "Versión administrada disponible", el nombre del proyecto administrado,
  "Ubicación: <ruta completa>", "Para mantener la trazabilidad, continúa trabajando con esta
  versión." y el botón `Abrir versión administrada`.
- Al abrir correctamente la versión administrada se retira solo el mensaje que creó GeoGuardian
  (`popWidget` de ese mensaje, nunca `clearWidgets()`), y el bloque del panel.
- La búsqueda y validación de D-33/D-34 no cambia.
- **Prioridad de avisos (NEREO, 2026-10-19):** el mensaje específico tiene prioridad sobre el
  genérico. Con una asociación válida a una versión administrada no se muestra la barra amarilla de
  proyecto no administrado, solo la barra azul breve. Si la versión asociada no se localiza, se
  muestra el aviso de recuperación (`Localizar unidad o carpeta`, D-34) y tampoco el amarillo. Al
  abrir otro proyecto sin asociación vuelve el comportamiento normal (D-17 A.2).
- **Pendiente de comprobar (NEREO, 2026-10-19):** la escritura inicial del asistente sigue con
  `QgsProject.write()`. Se comprobará a mano si, tras crear el proyecto administrado y cerrar QGIS
  sin guardar, aparece el aviso de modificación externa; solo entonces se corregirá.

## D-37 · Estado "original con versión administrada" — **Aprobada** (NEREO, 2026-10-19)

Si el proyecto abierto es un original con una asociación válida (D-33/D-34 encontró su versión
administrada y validó el `id_proyecto`):
- Panel: no se muestra `Inicializa el proyecto para que GeoGuardian lo supervise` ni el botón de
  inicializar; el motivo es "Abre la versión administrada para continuar trabajando" y se muestra el
  bloque de D-36.
- Indicador de la barra: `Versión administrada disponible` en lugar de `Proyecto no administrado`.
- Barra de mensajes: solo la barra azul breve de D-36.
- Cierre de QGIS: diálogo "Este proyecto tiene una versión administrada" con `Abrir versión
  administrada` (cancela el cierre y la abre), `Cerrar proyecto` (cierra QGIS) y `Cancelar`. No se
  ofrece `Inicializar ahora`.
- No se puede crear una segunda versión administrada: la acción `Inicializar proyecto` queda
  deshabilitada, el asistente no se abre (se vuelve a mostrar la barra azul) y
  `AdministradorProyecto.inicializar` lo rechaza.
- Si la versión asociada no se localiza, se mantiene el aviso de recuperación de D-34; este estado
  solo aplica con una asociación válida.

## D-38 · La inicialización termina con el proyecto guardado del todo — **Aprobada** (NEREO, 2026-10-19)

Síntoma (prueba manual): proyecto nuevo con capas, inicializar y cerrar QGIS sin hacer nada más
mostraba "¿Quiere guardar el proyecto actual?".

Causa (reproducida en QGIS 3.28 real): la primera escritura de la inicialización es un "Guardar
como" a la carpeta nueva y deja el proyecto sin cambios. Justo después, QGIS aplica en diferido la
lista de capas del lienzo (`QgsMapCanvas.layersChanged`) y con ello marca el proyecto como
modificado. Ninguna operación de GeoGuardian posterior a la escritura (propiedades, rutas
relativas, título, monitor, manifiesto, asociación original→administrado) modifica `QgsProject`.

Solución:
- Las propiedades, las rutas relativas y el título se fijan antes de la primera escritura (sin
  cambios).
- Al cerrar el asistente, GeoGuardian deja que QGIS termine lo pendiente y hace el último guardado
  con el flujo nativo (`iface.actionSaveProject().trigger()`), como D-35. Así se guarda también lo
  que QGIS cambió y QGIS registra la fecha del archivo. No se limpia el indicador de cambios.
- Ese guardado forma parte de la inicialización: no registra un `proyecto_guardado` aparte.
- Después se muestra el mensaje de proyecto creado (D-30).
- D-33 a D-37 no cambian.

## D-39 · Navegación del asistente y combo de asignatura — **Aprobada** (NEREO, 2026-10-19)

Último ajuste antes de v0.1.0 estable. La lógica de inicialización (D-38) no cambia.

**Navegación**
- Primera página: `Siguiente` + `Cancelar`. Páginas intermedias: `Anterior` + `Siguiente` +
  `Cancelar`. Resumen: `Anterior` + `Crear proyecto administrado` + `Cancelar`.
- El asistente usa el estilo clásico de Qt en todas las plataformas. El estilo Aero de Windows
  sustituye `Anterior` por una flecha en el título.
- Al regresar se conservan todos los datos, la ubicación elegida y la unidad externa seleccionada.
- Al avanzar de nuevo se recalculan las validaciones, los avisos y el resumen.
- Si cambian el estudiante o la práctica o proyecto, se regenera el nombre final sugerido, aunque el
  estudiante lo hubiera editado. Si no cambian, se conserva su edición.
- Nada se crea ni se modifica hasta pulsar `Crear proyecto administrado`.

**Asignatura o módulo**
- `QComboBox` editable: se elige del catálogo o se escribe otro valor. Lo escrito no se agrega al
  catálogo.
- El catálogo está en un solo lugar, `dominio/catalogo_asignaturas.py` (`ASIGNATURAS`). Lo forman los
  cinco módulos profesionales de la carrera de Técnico en Sistemas de Información Geográfica:
  - M1 — Maneja e integra información geográfica
  - M2 — Produce y mantiene información georreferenciada para proyectos
  - M3 — Realiza análisis espacial para proyectos
  - M4 — Genera cartografía temática para proyectos
  - M5 — Obtiene, gestiona y manipula información geográfica a distancia
- El valor se guarda tal cual en `gg_proyecto.asignatura` y en `manifiesto.json` (`asignatura`).
  El esquema de datos no cambia.
- El nombre del docente queda para v0.2.0, porque necesita un campo propio y una migración.


---

# v0.2.0 · Hito 1: inventario y revisión de capas

## D-40 · Inventario exclusivamente en memoria — **Aprobada** (NEREO, 2026-10-19)

El inventario se construye y se descarta en memoria. No se crean tablas ni eventos, no hay
migraciones y el manifiesto no cambia. "Solo lectura" significa que revisar no escribe en
`Proyecto.gpkg`, `Proyecto.qgz`, `manifiesto.json` ni en ninguna fuente, y no marca el proyecto como
modificado.

## D-41 · Origen y disponibilidad son ejes independientes — **Aprobada** (NEREO, 2026-10-19)

- **Origen** (`OrigenFuente`): administrada, carpeta del proyecto, archivo externo, temporal,
  servicio remoto, base de datos externa, virtual, desconocida.
- **Disponibilidad** (`Disponibilidad`): disponible, faltante, unidad ausente, inválida.

Una fuente externa puede faltar y una administrada puede ser inválida; ninguno de los dos ejes
absorbe al otro.

## D-42 · El inventario corre en paralelo a v0.1.0 — **Aprobada** (NEREO, 2026-10-19)

No se modifican `EstadoRecurso`, `clasificar_recurso`, `describir_capa`, `gg_recursos`, el semáforo
ni el manifiesto. `equivalente_v010` traduce origen y disponibilidad a `EstadoRecurso` solo para
las pruebas de coherencia, que comprueban que ambas clasificaciones coinciden.

## D-43 · Nombres `CapaInventariada` y `FuenteInventariada` — **Aprobada** (NEREO, 2026-10-19)

Sustituyen a los provisionales *LayerDescriptor* y *ResourceDescriptor*. No se reutiliza `Recurso`,
que es la fila de `gg_recursos`.

## D-44 · Identidad de una fuente — **Aprobada** (NEREO, 2026-10-19)

Identidad = contenedor + subcapa o conjunto de datos + parámetros relevantes. El contenedor (archivo,
base de datos, URL) se conserva como atributo independiente. En archivos la ruta se normaliza. En
servicios y bases de datos la identidad no lleva credenciales (usuario, contraseña, tokens, claves
de API, `authcfg`). Cada capa en memoria es su propia fuente.

## D-45 · Regla de fuente administrada — **Aprobada** (NEREO, 2026-10-19)

Una fuente es administrada solo si está en el `Proyecto.gpkg` del contexto activo,
`geopaquete_utilizable` es verdadero y no es una tabla `gg_*`. Si el GPKG no está validado, nada es
administrado. Un `Proyecto.gpkg` de otro proyecto es un archivo como cualquier otro.

## D-46 · Servicio remoto y base de datos externa son orígenes distintos — **Aprobada** (NEREO, 2026-10-19)

`SERVICIO_REMOTO`: WFS, OGC API Features, ArcGIS, teselas vectoriales y archivos remotos (`/vsicurl/`,
`http(s)://`). `BASE_DATOS_EXTERNA`: PostgreSQL/PostGIS, SQL Server, Oracle, SAP HANA, DB2.

## D-47 · Capas no vectoriales — **Aprobada** (NEREO, 2026-10-19)

Ráster, malla, nube de puntos y otros tipos se listan como "No revisada en esta versión". No se
clasifican ni se compara su SRC.

## D-48 · Revisión de SRC informativa — **Aprobada** (NEREO, 2026-10-19)

Nunca toca el semáforo y nunca corrige, asigna ni reproyecta. Estados: coincide, diferente, capa sin
SRC, proyecto sin SRC, no aplica, SRC propio de servicio. Si el SRC asignado a la capa y el de su
fuente son válidos y distintos, se muestra una advertencia de revisión específica. La comparación
usa la de QGIS; una prueba comprueba que EPSG y su WKT equivalente se consideran iguales en 3.28,
así que no hizo falta una comparación propia.

## D-49 · Construcción solo bajo demanda — **Aprobada** (NEREO, 2026-10-19)

El inventario se construye al abrir "Revisar capas" y al pulsar "Volver a revisar". No hay recálculo
continuo con `layerModified`, `crsChanged` ni otras señales. Solo para proyectos administrados.

## D-50 · Diálogo "Revisar capas" — **Aprobada** (NEREO, 2026-10-19)

Diálogo nuevo. No se modifican `PanelEstado`, `IndicadorBarra`, el semáforo ni el manifiesto.

## D-51 · Versión de desarrollo — **Aprobada** (NEREO, 2026-10-19)

`0.2.0-dev` con `experimental=True`. Una prueba comprueba que `metadata.txt` coincide con
`VERSION_COMPLEMENTO`.

## D-52 · Reutilizar `monitoreo/descriptor_fuente.py` — **Aprobada** (NEREO, 2026-10-19)

Se importan sus funciones públicas sin moverlas y sin importar funciones privadas. La decodificación
adicional vive en el adaptador nuevo `inventario/lector_capas.py`.
