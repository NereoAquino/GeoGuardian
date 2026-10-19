# GeoGuardian 0.1.0

Complemento de QGIS (3.28 o superior) que convierte un proyecto en un **Proyecto administrado**:
crea su estructura de carpetas, guarda el `.qgz` con nombre académico y rutas relativas, registra en
`Proyecto.gpkg` las capas que se agregan o quitan, y muestra un semáforo del estado del proyecto.

GeoGuardian **no** mueve, borra ni modifica archivos fuente, **no** confirma ediciones y **no**
consolida datos en esta versión.

> **Versión estable 0.1.0** (2026-10-19): primera versión estable, derivada de 0.1.0-rc2 sin cambios
> funcionales. Cambios en [CHANGELOG.md](CHANGELOG.md).

## Instalación

1. En QGIS: *Complementos → Administrar e instalar complementos → Instalar a partir de ZIP*.
2. Elige `dist/geoguardian-0.1.0.zip` e instala.
3. Aparece el panel **GeoGuardian** a la derecha y el menú *Complementos → GeoGuardian*.

## Uso

1. Con un proyecto abierto (vacío o con capas), elige *Inicializar proyecto…* (o **Inicializar ahora**
   en el aviso amarillo que aparece mientras el proyecto no está administrado).
2. El asistente tiene cuatro páginas. Con **Anterior** se puede volver sin perder lo capturado; nada
   se crea hasta pulsar **Crear proyecto administrado**.
   - **Datos**: nombre, correo, nombre de la práctica o proyecto, descripción, grupo y asignatura o
     módulo. La práctica se toma del título o del nombre del `.qgz` actual. La asignatura se elige
     de la lista (módulos M1 a M5 de la carrera de Técnico en SIG) o se escribe; la lista está en
     `geoguardian/dominio/catalogo_asignaturas.py`.
   - **Nombre final del proyecto administrado**: muestra el proyecto detectado y el estudiante,
     propone `<Práctica> - <Nombre del estudiante>` y avisa si falta el nombre.
   - **Ubicación**: en este equipo (Documentos, recomendado), unidad externa u otra carpeta. Muestra
     carpeta, sistema de archivos y espacio disponible; avisa (sin bloquear) de FAT32, OneDrive, poco
     espacio o rutas largas. Opcionalmente registra una copia de respaldo (solo se registra; no se
     copia nada en esta versión).
   - **Resumen** en bloques y botón **Crear proyecto administrado**.
3. GeoGuardian crea:
   ```
   <Carpeta padre>/<Nombre académico>/<Nombre académico>.qgz
   <Carpeta padre>/<Nombre académico>/Proyecto.gpkg   (gg_proyecto, gg_recursos, gg_eventos)
   <Carpeta padre>/<Nombre académico>/.geoguardian/manifiesto.json
   <Carpeta padre>/<Nombre académico>/datos/  salidas/  documentos/
   ```
   El `.qgz` original queda intacto. Si después se abre el original, GeoGuardian ofrece abrir la
   versión administrada (solo si ese archivo todavía existe).
4. La barra **GeoGuardian** muestra siempre el estado (icono, punto de color y texto); un clic
   muestra u oculta el panel y el tooltip dice el motivo principal.
5. Trabaja normalmente. Usa **Guardar ahora** (o Ctrl+S) para guardar y **Abrir carpeta** para ver
   la carpeta del proyecto.
6. Al cerrar QGIS con un proyecto sin administrar que tenga capas o archivo, GeoGuardian pregunta:
   *Inicializar ahora*, *Cerrar sin administrar* o *Cancelar*.

Si el proyecto administrado está en una USB y Windows le asigna otra letra, GeoGuardian lo
reconoce por la etiqueta del volumen y su identificador; si no lo encuentra, ofrece **Localizar
unidad o carpeta**.

Los proyectos creados con versiones anteriores (esquemas 1 y 2) se migran automáticamente al
esquema 3 al abrirlos.

### Semáforo

| Color | Significa |
|---|---|
| Gris · Proyecto no administrado | El proyecto no está administrado |
| Rojo · Proyecto con problemas | Hay recursos con archivos que no existen, o faltan/no coinciden `Proyecto.gpkg` o el manifiesto |
| Amarillo · Proyecto requiere atención | Capas temporales, ediciones sin confirmar, recursos fuera de la carpeta o cambios sin guardar |
| Verde · Proyecto en buen estado | Todo guardado y todos los recursos dentro de la carpeta del proyecto |

### Estados de los recursos

`activo` (dentro de la carpeta), `externo` (fuera de la carpeta o servicio remoto), `temporal`
(capa en memoria o en carpeta temporal), `historico` (capa retirada del proyecto) y `faltante`
(el archivo no existe o la capa no es válida).

## Desarrollo

```
geoguardian/        código del complemento (lo que va en el ZIP)
pruebas/            unitarias (sin QGIS) e integración (con QGIS)
herramientas/       construir_zip.py
docs/               ARQUITECTURA.md, DECISIONES.md, especificaciones/v0.1.0.md
```

- Pruebas unitarias (cualquier Python 3.9+): `python pruebas/ejecutar_pruebas.py`
- Pruebas de integración en Docker:
  ```
  docker run --rm -v "$PWD":/gg -e QT_QPA_PLATFORM=offscreen qgis/qgis:release-3_28 \
      python3 /gg/pruebas/ejecutar_pruebas.py --integracion
  ```
- Prueba manual en Windows: [pruebas/integracion/lista_manual.md](pruebas/integracion/lista_manual.md)
- ZIP instalable: `python herramientas/construir_zip.py` → `dist/geoguardian-0.1.0.zip`
  (la versión candidata validada se conserva en `dist/candidatas/geoguardian-0.1.0-rc2.zip`).

## Licencia

GeoGuardian se distribuye bajo la GNU General Public License, versión 2 o posterior (GPL-2.0-or-later).
El texto completo está en [LICENSE](LICENSE).
