# GeoGuardian 0.2.0-dev — Validación manual del Hito 2 en Windows (NORTE-PILOTO-001)

**Fecha:** 15/11/2026  
**Marco:** NORTE v0.1, nivel 2 (herramienta técnica)  
**Entorno:** Windows 11; QGIS 3.44.15-Solothurn; GeoGuardian 0.2.0-dev  
**Estado:** Validación ejecutada; dictamen humano de cierre aprobado **con observaciones**.  
**Documento rector del resultado:** [NORTE-PILOTO-001 — Dictamen de cierre](https://github.com/NereoAquino/norte/blob/main/docs/pilotos/NORTE-PILOTO-001-CIERRE.md).

> Este archivo es un **registro documental** de las comprobaciones realizadas en el proyecto piloto. No sustituye las pruebas automatizadas, no autoriza cambios de código ni implica la aceptación sin reservas del Hito 2. Las capturas se aportaron en la conversación del piloto y no se han incorporado a este repositorio.

## Resultados verificados

| ID | Resultado | Evidencia resumida |
|---|---|---|
| CA-01 — Selección | **Aprobado** | Una capa vectorial válida y externa (`Curvas.shp`) apareció disponible y seleccionada como incorporable. |
| CA-02 — Plan | **Aprobado** | «Preparar incorporación» presentó un destino propuesto dentro de `Proyecto.gpkg` y comunicó que todavía no copiaba datos. |
| CA-03 — SRC | **Aprobado** | Una copia sin `.prj`, con `EPSG:32718` asignado únicamente en QGIS, quedó bloqueada con el aviso «SRC definido solo en QGIS» (D-69). |
| CA-04 — Revalidación | **Aprobado** | Tras modificar la fecha del archivo de prueba, se detectó «El archivo cambió», se invalidó el plan y se exigió «Volver a revisar»; después de la revisión se habilitó de nuevo (D-70). |
| CA-05 — Protección | **Aprobado en el escenario verificado** | El contenido de `Proyecto.gpkg` coincidió por SHA-256 antes y después de preparar de nuevo el plan; no apareció una nueva tabla de datos `Curvas`. Comparación de `Curvas.shp` original y copia también coincidente. No se verificaron individualmente todos los archivos asociados. |
| CA-06 — Comprensión | **No aprobado** | Se comprendió la intención general, pero se señaló que «incorporación» no explica qué se organiza, por qué ni para qué. |

## Hallazgos pendientes de evaluación

**Actualización documental posterior al cierre:** UX-01 y UX-02 fueron **aprobadas conceptualmente** por el responsable humano; su alcance y criterios se consolidan en [GEOGUARDIAN-UX-001 — Especificación de comunicación y organización de capas](GEOGUARDIAN-UX-001.md). **No existe autorización para implementar código**. Esta aprobación conceptual no modifica el resultado CA-06 (no aprobado) del piloto.

### UX-01 — Aclarar el propósito para el estudiante (CA-06)

- **Problema:** la acción «Preparar incorporación» no presenta por sí misma el contexto educativo ni el beneficio de reunir capas compatibles.
- **Propuesta:** estudiar «Preparar organización de capas» y un texto que explique qué se propone reunir en `Proyecto.gpkg`, que se conservarán los originales y que **el Hito 2 solo prepara el plan**.
- **Restricción:** no afirmar que todo tipo de dato (incluidos rásteres) se guarda en ese GeoPackage. Sin implementación autorizada.

### UX-02 — Distinguir SRC de la capa y SRC de la fuente (CA-03)

- **Problema:** en la misma fila se muestran «EPSG:32718 · igual al proyecto» y «SRC definido solo en QGIS», textos compatibles técnicamente pero posiblemente confusos.
- **Propuesta:** explicar expresamente el SRC que QGIS asignó a la capa frente al SRC que declara el archivo original. Sin implementación autorizada.

### INC-01 — Bloqueo de QGIS durante el procedimiento

- QGIS dejó de responder durante una operación manual de asignación del SRC. Se había indicado un atajo que en ese entorno activaba otra acción.
- Tras reiniciar, el proyecto administrado volvió a ser reconocido y una copia de `Proyecto.gpkg` superó `PRAGMA integrity_check` (`ok`).
- Se identificó un registro `capa_agregada` en `gg_eventos` coincidente con una modificación de `Proyecto.gpkg`. Es una explicación posible del cambio de contenido; no prueba causalidad del bloqueo.
- **No se atribuye la incidencia a GeoGuardian sin evidencia técnica adicional.**

## Decisión del piloto y trazabilidad

**Aceptado por el responsable humano el 15/11/2026:** cerrar el piloto NORTE-PILOTO-001 **con observaciones**; mantener CA-06 no aprobado y CA-05 limitado a lo comprobado. No se autorizó corregir funciones, modificar reglas de NORTE, fusionar ramas ni publicar una versión del complemento.

Las observaciones pueden evaluarse en una etapa posterior, mediante autorización específica.

**Referencias técnicas:** [decisiones D-65, D-69, D-70](DECISIONES.md) y [CHANGELOG del Hito 2](../CHANGELOG.md).
