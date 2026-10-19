# Lista de cotejo manual en Windows (aula)

Repetir con QGIS 3.28 LTR y con la LTR vigente. Marca cada punto.

> Las secciones marcadas rc2 se validaron con 0.1.0-rc2 en Windows (D-33 a D-39). Para 0.1.0 estable
> basta con la sección *Instalación* y un recorrido breve del asistente.

## Instalación
- [ ] Desinstalar cualquier versión anterior de GeoGuardian e instalar `geoguardian-0.1.0.zip` desde *Instalar a partir de ZIP* sin errores.
- [ ] *Administrar e instalar complementos* muestra GeoGuardian **0.1.0** (no experimental).
- [ ] Aparece el panel GeoGuardian en gris con el botón **Inicializar proyecto**.

## Inicialización
- [ ] Con dos capas abiertas (una de `C:\` y una capa temporal de Procesos), inicializar en `Documentos`.
- [ ] La carpeta se llama `<Práctica> - <Estudiante>` y contiene `<Práctica> - <Estudiante>.qgz`, `Proyecto.gpkg`, `.geoguardian\manifiesto.json`, `datos`, `salidas`, `documentos`.
- [ ] El panel queda en amarillo con "1 capa temporal…" y "1 capa esta fuera…".
- [ ] Intentar inicializar en una carpeta con archivos: el asistente no deja continuar y la carpeta no cambia.

## Nombre de la práctica o proyecto y ubicación de trabajo (rc2)
- [ ] Con un proyecto `Manglares.qgz`, el asistente propone `Manglares - <Nombre del estudiante>`.
- [ ] Un nombre con acentos (`Práctica Señal - José Núñez`) crea carpeta y archivo sin acentos y el título conserva los acentos.
- [ ] Opción *Disco local*: propone `Documentos` y muestra unidad, sistema de archivos y espacio libre.
- [ ] Con una USB en FAT32: aparece el aviso FAT32 y se puede continuar.
- [ ] Con una USB en NTFS o exFAT: no aparece el aviso FAT32.
- [ ] Con `Documentos` dentro de OneDrive: aparece el aviso de OneDrive y se puede continuar.
- [ ] Carpeta de respaldo en otra unidad: se registra sin aviso; en la misma unidad aparece aviso; una carpeta inexistente no deja continuar.
- [ ] El `.qgz` original no cambia (fecha de modificación igual). Al reabrirlo aparece la barra con **Abrir versión administrada**.
- [ ] Borrar o renombrar la versión administrada y reabrir el original: la barra **no** aparece.
- [ ] Botón **Abrir carpeta** abre el Explorador de Windows en la carpeta del proyecto.

## Ajustes de UX (rc2, 2026-10-19)
- [ ] Página de nombre: se ven por separado *Proyecto detectado*, *Estudiante* y *Nombre final sugerido*; el campo ocupa todo el ancho y se puede editar.
- [ ] Página de ubicación: *¿Dónde quieres trabajar?* con sus explicaciones; carpeta, sistema de archivos y espacio disponible debajo; bloque *Copia de respaldo — opcional* separado.
- [ ] Resumen en bloques sin texto encimado; botón **Crear proyecto administrado**.
- [ ] Tras crear: aparece *Proyecto administrado creado* y el título de la ventana de QGIS muestra el `.qgz` administrado.
- [ ] La barra **GeoGuardian** muestra icono, punto y texto; cambia de gris a verde/amarillo al trabajar; el tooltip dice el motivo principal.
- [ ] Clic en el indicador muestra y oculta el panel; con la barra de herramientas en iconos grandes, el indicador crece con ella.
- [ ] Panel: frase de estado igual al indicador y `Recursos en el proyecto: N` antes de los conteos.

## USB con letra cambiante (rc2, D-33/D-34)
Preparar una USB con etiqueta (p. ej. `USB_ANA`) y adoptar un proyecto guardado en `C:` creando la versión administrada en la USB.
- [ ] En `Proyecto.gpkg` → `gg_proyecto`: `etiqueta_volumen` = `USB_ANA` y `ruta_en_volumen` sin letra de unidad.
- [ ] Cambiar la letra de la USB en *Administración de discos* (p. ej. de `E:` a `F:`) y abrir el original: se ofrece la versión en `F:`.
- [ ] Abrir directamente el `.qgz` en `F:`: `gg_eventos` registra `ubicacion_actualizada` una sola vez.
- [ ] Desconectar la USB y abrir el original: aparece "No se encuentra la unidad utilizada por este proyecto…" con **Localizar unidad o carpeta**.
- [ ] Localizar eligiendo la raíz de la USB, la carpeta del proyecto o otra carpeta cualquiera: solo las dos primeras se aceptan.
- [ ] Otra USB con la misma etiqueta y otro proyecto en la misma ruta: no se reasocia.
- [ ] Una capa cargada desde la USB desconectada: el motivo dice que la unidad no se encuentra (sigue en rojo como faltante).

## Asistente: navegación y asignatura (rc2, D-39)
- [ ] Primera página: solo **Siguiente** y **Cancelar**. Páginas intermedias: **Anterior**, **Siguiente** y **Cancelar**. Resumen: **Anterior**, **Crear proyecto administrado** y **Cancelar**.
- [ ] Llenar todo, llegar al Resumen y volver con **Anterior** hasta Datos: los campos, la ubicación y la unidad siguen como estaban.
- [ ] Cambiar el nombre del estudiante o de la práctica y avanzar: el nombre final sugerido se actualiza y el Resumen lo refleja.
- [ ] Borrar el correo al volver: **Siguiente** se desactiva hasta corregirlo.
- [ ] Mientras se navega, no aparece ninguna carpeta nueva en el destino y el proyecto no cambia.
- [ ] **Asignatura o módulo**: la lista muestra M1 a M5; elegir uno y crear el proyecto: `gg_proyecto.asignatura` y `manifiesto.json` tienen ese texto exacto.
- [ ] Escribir una asignatura que no está en la lista: se acepta y se guarda igual.

## Guardar ahora nativo (rc2, D-35)
- [ ] Abrir un proyecto administrado, poner una capa en edición y agregar una entidad.
- [ ] Pulsar **Guardar ahora**: el panel avisa de ediciones sin confirmar.
- [ ] La capa sigue en edición y la entidad sigue sin confirmar.
- [ ] `gg_eventos` registra un solo `proyecto_guardado` con origen `boton`; un `Ctrl+S` después registra otro con origen `qgis`.
- [ ] Cerrar QGIS (descartando o guardando las ediciones de la capa): **no** aparece "El proyecto ha cambiado en el disco".
- [ ] Fin de la inicialización (D-38): proyecto nuevo sin guardar, cargar capas, inicializar y, **sin** ninguna acción posterior (ni Guardar ahora, ni Ctrl+S, ni cambios), cerrar QGIS. No aparece "¿Quiere guardar el proyecto actual?" ni "El proyecto ha cambiado en el disco".
- [ ] Repetir cargando una capa justo antes de pulsar Inicializar.
- [ ] En `gg_eventos` hay un `proyecto_inicializado` y ningún `proyecto_guardado` por ese guardado final.
- [ ] Repetir tras recuperación de unidad: cambiar la letra de la USB de `G:` a `H:`, abrir el `.qgz` en `H:` (se registra `ubicacion_actualizada` una vez), Guardar ahora, cerrar QGIS: sin el aviso.

## Aviso de versión administrada (rc2, D-36)
- [ ] Abrir el original adoptado: la barra azul dice solo "GeoGuardian: este proyecto tiene una versión administrada disponible." con **Abrir versión administrada**, sin nombre ni ruta.
- [ ] El panel muestra "Versión administrada disponible", el nombre, "Ubicación: …" con la ruta completa y la nota de trazabilidad.
- [ ] Con el original adoptado abierto **no** aparece la barra amarilla de proyecto no administrado, ni al abrirlo ni al agregar capas después.
- [ ] Con la USB de la versión administrada desconectada, abrir el original: aparece solo el aviso de recuperación con **Localizar unidad o carpeta**, sin la barra amarilla.
- [ ] Abrir después un proyecto sin asociación y con capas: vuelve la barra amarilla normal.
- [ ] Pulsar **Abrir versión administrada** (en la barra o en el panel): se abre la versión administrada y desaparece el mensaje azul; otros mensajes de QGIS siguen visibles.

## Original con versión administrada (rc2, D-37)
- [ ] Abrir el original adoptado: el indicador de la barra dice **Versión administrada disponible** y el panel no muestra "Inicializa el proyecto para que GeoGuardian lo supervise" ni el botón de inicializar.
- [ ] *Complementos → GeoGuardian → Inicializar proyecto* está deshabilitado.
- [ ] Cerrar QGIS: aparece "Este proyecto tiene una versión administrada" con **Abrir versión administrada**, **Cerrar proyecto** y **Cancelar** (sin *Inicializar ahora*).
- [ ] **Abrir versión administrada** deja QGIS abierto con la versión administrada; **Cancelar** (y Esc) deja QGIS abierto con el original; **Cerrar proyecto** cierra QGIS.
- [ ] No se crea ninguna carpeta nueva de proyecto administrado en todo el recorrido.

## Aviso de cierre (rc2)
- [ ] Con un proyecto sin administrar y con capas, cerrar QGIS: aparece el diálogo con *Inicializar ahora* / *Cerrar sin administrar* / *Cancelar*.
- [ ] *Cancelar* (y Esc) deja QGIS abierto; *Inicializar ahora* abre el asistente; *Cerrar sin administrar* cierra QGIS.
- [ ] Con un proyecto vacío sin archivo o con uno administrado, QGIS cierra sin el diálogo.

## Migración al esquema 3 (rc2)
- [ ] Esquema 1 → 3: abrir con la rc2 definitiva un proyecto creado con la rc1. El panel no queda en rojo, `gg_proyecto.version_esquema` = 3 y `gg_eventos` registra `esquema_migrado` con versión anterior 1 y nueva 3.
- [ ] Esquema 2 → 3: abrir un proyecto creado con la primera entrega de la rc2. Se conservan `nombre_academico` y las rutas, `version_esquema` = 3 y `esquema_migrado` registra versión anterior 2 y nueva 3.
- [ ] En ambos casos, `gg_proyecto` tiene ahora `etiqueta_volumen` y `ruta_en_volumen` completas.
- [ ] Cerrar y reabrir cada proyecto: no se registra una segunda migración (sigue habiendo un solo `esquema_migrado`).

## Prototipo §11.2 (solo informativo)
- [ ] Ejecutar el prototipo de `registerCustomProjectOpenHandler` de la especificación §11.2 y anotar si se ejecuta antes de que QGIS cierre el proyecto actual.

## Monitoreo
- [ ] Copiar un shapefile a `datos\` y cargarlo: cuenta como Activo.
- [ ] Quitar una capa: el conteo de Históricos sube.
- [ ] Abrir `Proyecto.gpkg` → `gg_eventos` en el Explorador: aparecen los eventos con fecha y hora local.

## Guardado y ediciones
- [ ] Poner una capa en edición, agregar una entidad y pulsar **Guardar ahora**: aparece el aviso de ediciones sin confirmar y la capa sigue en edición.
- [ ] Ctrl+S también registra `proyecto_guardado` (origen `qgis`).

## Portabilidad
- [ ] Cargar una capa desde una USB (`E:\`), guardar, retirar la USB y reabrir: el panel queda en rojo y la capa cuenta como Faltante.
- [ ] Copiar la carpeta del proyecto a otra computadora con GeoGuardian: abre en verde o amarillo (sin rojo si no hay capas externas).
- [ ] Abrir el proyecto en una computadora sin GeoGuardian: funciona como cualquier proyecto QGIS.

## Descarga
- [ ] Desactivar el complemento en el Administrador de complementos: el panel y el menú desaparecen sin errores en *Registro de mensajes*.
- [ ] Volver a activarlo: el panel reconoce el proyecto abierto.
