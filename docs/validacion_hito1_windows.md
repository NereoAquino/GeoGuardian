# GeoGuardian v0.2.0 · Validación manual del Hito 1 en QGIS Windows

> Hito 1 — Inventario y clasificación vectorial de solo lectura. Validación realizada por NEREO y
> registrada el 2026-10-20. Especificación: [especificaciones/v0.2.0.md](especificaciones/v0.2.0.md).
> Decisiones: [DECISIONES.md](DECISIONES.md) (D-40 a D-55).

## 1. Entorno de prueba

| Elemento | Valor |
|---|---|
| Validación manual | QGIS de escritorio sobre Windows (versiones exactas de QGIS y Windows no registradas) |
| Validación automatizada | QGIS 3.28.15 en Docker (`qgis/qgis:release-3_28`), 148 unitarias y 67 de integración |
| Complemento instalado | GeoGuardian `0.2.0-dev`, `experimental=True`, instalado desde ZIP |

## 2. Paquete probado

| Elemento | Valor |
|---|---|
| ZIP | `geoguardian-0.2.0-dev.zip` (81 989 bytes, 50 archivos) |
| SHA-256 | `7f744630dc62d4fc0ca3f048dd7ef7e9a8f39f0d765d03675f018b565f23c0ea` |
| Commit | `958a9aa` (código instalable idéntico byte a byte al de `068a5e3`) |

## 3. Caso A · Proyecto administrado con una única capa ráster

- GeoGuardian siguió reconociendo el proyecto administrado; el semáforo y el panel de v0.1.0
  funcionaron.
- "Revisar capas" abrió correctamente y mostró `0 capas revisadas` y
  `1 capa no revisada en esta versión`.
- La capa ráster apareció como «No revisada en esta versión (ráster)».
- "Volver a revisar" actualizó la revisión sin modificar la capa ni cambiar su clasificación.

**Resultado:** correcto según D-47 y el alcance vectorial del Hito 1.

## 4. Caso B · Proyecto real con rásteres y un vector externo en otro SRC

- Proyecto: *MAPA DE INDICES ESPECTRALES - NEREO ADENNY AQUINO SANTANA*.
- SRC del proyecto: `EPSG:32719 — WGS 84 / UTM zone 19S`.
- Varias capas ráster: todas aparecieron como «No revisada en esta versión (ráster)».
- Capa vectorial externa `Area_para_SCP`, en `EPSG:32619 — WGS 84 / UTM zone 19N`. GeoGuardian la
  clasificó como «Archivo fuera de la carpeta del proyecto», «Disponible» y
  «EPSG:32619 · distinto al proyecto».

**Resultado:** aprobado. La diferencia de SRC es informativa: no significa que el SRC sea incorrecto,
no modifica el semáforo y no provoca reproyección. Decidir si se reproyecta corresponde al
estudiante (D-48, D-54).

## 5. Caso C · Shapefile sin `.prj`

Se hizo una copia vectorial, `AREA SCP DE PRUEBA.shp`, y se renombró su `.prj` agregándole `_` para
que QGIS no lo reconociera.

- La capa abrió correctamente en QGIS.
- GeoGuardian mostró «La capa no tiene SRC».
- Consola de Python de QGIS, con la capa activa:

```python
capa = iface.activeLayer()
print(capa.crs().authid(), capa.crs().isValid())
print(capa.dataProvider().crs().authid(), capa.dataProvider().crs().isValid())
```

| Comprobación | Resultado |
|---|---|
| `capa.crs().isValid()` | `False` |
| `capa.dataProvider().crs().isValid()` | `False` |

**Resultado:** con la configuración real usada en Windows, QGIS no asignó automáticamente un SRC
válido al Shapefile sin `.prj`. GeoGuardian detectó la ausencia de SRC sin heredar ni inventar el del
proyecto, y `dataProvider().crs()` se comportó correctamente. Esto cierra el punto pendiente de
D-48/D-54 para este escenario. Otras configuraciones de *SRC para capas nuevas* no se probaron.

## 6. Regresión observable de v0.1.0

- El proyecto administrado siguió siendo reconocido.
- El panel y el semáforo siguieron funcionando.
- Al agregar una capa externa nueva, el monitor de v0.1.0 actualizó normalmente el conteo de
  recursos externos.
- "Revisar capas" no sustituyó ni modificó el comportamiento del monitor.
- No se observaron cambios automáticos de SRC, cambios de fuente, ni movimientos o copias de
  archivos.

Se mantiene la separación aprobada entre `MonitorCapas` / `EstadoRecurso` / semáforo (v0.1.0) y el
inventario de v0.2.0 (D-42).

## 7. Conclusión

**Hito 1 — Inventario y clasificación vectorial de solo lectura: COMPLETADO Y VALIDADO.**
Validado con pruebas automatizadas en QGIS 3.28 y manualmente en QGIS de escritorio sobre Windows.
D-40 a D-55 quedan congeladas. La versión sigue siendo `0.2.0-dev` con `experimental=True` hasta que
v0.2.0 esté completa.
