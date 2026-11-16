# GEOGUARDIAN-UX-001 — Especificación de comunicación y organización de capas

**Versión:** 0.1 — consolidación conceptual  
**Fecha:** 15 de noviembre de 2026  
**Proyecto:** GeoGuardian 0.2.0-dev — Hito 2  
**Origen:** [NORTE-PILOTO-001 — dictamen aprobado con observaciones](https://github.com/NereoAquino/norte/blob/main/docs/pilotos/NORTE-PILOTO-001-CIERRE.md)  
**Hallazgos:** UX-01 (comprensión de «incorporación»), UX-02 (diferencia entre SRC de QGIS y SRC del archivo)  
**Estado:** **UX-01 y UX-02 aprobadas conceptualmente por el responsable humano; implementación NO autorizada.**

> Este documento define la intención funcional y la comunicación deseada. No describe una funcionalidad ya implementada, no cambia las decisiones técnicas vigentes D-59, D-65, D-69 y D-70, ni acredita la aprobación de CA-06. La terminología final y los detalles de interfaz deberán revisarse antes de autorizar cambios de código.

## 1. Objetivo

Facilitar que un estudiante entienda **qué encontró GeoGuardian, por qué importa, qué propone hacer y qué ocurrirá con los datos**. Mantener la claridad pedagógica sin prometer acciones que el Hito 2 todavía no realiza.

La primera vez que aparezca un término técnico, explicarlo en español claro e indicar su nombre entre paréntesis.

## 2. UX-01 — Explicar la organización de capas

### 2.1 Textos de interfaz propuestos

| Elemento actual | Texto propuesto |
|---|---|
| Contexto inicial no explicado | **Organiza las capas de tu proyecto** |
| Botón «Preparar incorporación» | **Ver plan de organización** |
| Título «Plan de incorporación» | **Plan de organización de capas** |
| Columna «Incorporar» | **Organizar** |
| Estado «Se puede incorporar» | **Se puede organizar** |

Estos reemplazos son **propuestas**, no modificaciones realizadas. La aplicación deberá distinguir el plan informativo del eventual procedimiento de copia o consolidación de una etapa futura.

### 2.2 Explicación sugerida al estudiante

> GeoGuardian revisó las capas de tu proyecto y encontró algunas que podrían organizarse mejor.
>
> Para facilitar que conserves y transportes tus datos, te propone reunir **copias de las capas vectoriales compatibles** en un archivo de datos geográficos llamado **GeoPackage** (`Proyecto.gpkg`).
>
> **Los archivos originales se conservarán.**
>
> **Por ahora solamente veremos el plan.** Todavía no se copiará ni modificará ningún archivo.

El texto debe adaptarse a la situación realmente detectada: no afirmar que hay capas externas, faltantes o problemas cuando no existan. No se debe prometer que todos los tipos de datos pueden almacenarse juntos; las capas ráster quedan fuera de la incorporación del Hito 2.

### 2.3 Explicación de la propuesta

Mostrar de forma reconocible:
- **Qué se propone organizar:** capas o fuentes compatibles seleccionadas.
- **Para qué:** reducir riesgos de referencias rotas al trasladar o entregar el proyecto.
- **Dónde se organizarían:** `Proyecto.gpkg`, indicando el nombre propuesto de destino.
- **Qué ocurre ahora:** únicamente se muestra un plan, conservado en memoria.
- **Qué no ocurre:** no se copian, mueven, reproyectan, reenlazan ni modifican datos originales.

La preparación del plan, por sí sola, **no garantiza** que el proyecto sea portable o esté listo para entrega.

## 3. UX-02 — Explicar los sistemas de referencia de coordenadas

Un **sistema de referencia de coordenadas (SRC)** permite interpretar la ubicación de los datos geográficos. La interfaz distinguirá:

- **SRC asignado en QGIS:** el que QGIS emplea para interpretar la capa en la sesión.
- **SRC declarado por la fuente:** el que está registrado de forma válida en el archivo o proveedor de datos.

### 3.1 Mensajes propuestos

| Situación | Mensaje para el estudiante | Regla que debe conservarse |
|---|---|---|
| SRC de archivo y capa coinciden | «El SRC del archivo coincide con el asignado en QGIS.» | No implica validación geodésica independiente de las coordenadas. |
| Archivo sin SRC válido, pero asignado en QGIS | «El archivo original no tiene un SRC definido. Revisa las coordenadas antes de organizar esta capa.» | La capa sigue visible; **no seleccionable ni incorporable** (D-69). |
| SRC del archivo distinto al asignado en QGIS | «El SRC del archivo y el asignado en QGIS no coinciden. Comprueba cuál corresponde a estos datos.» | Bloqueo según D-59. |
| SRC válido de fuente distinto al del proyecto | «Esta capa utiliza un SRC diferente al del proyecto. Se conservará su SRC original.» | Incorporable con advertencia, sin preselección automática (D-59). |

Se debe evitar el mensaje ambiguo «EPSG:32718 · igual al proyecto» cuando resulte insuficiente para explicar que el archivo carece de SRC. Puede mostrarse el identificador de QGIS, pero acompañado de una **indicación explícita sobre el SRC de la fuente**.

### 3.2 Ayuda contextual

Propuesta de ayuda **«¿Por qué aparece esta advertencia?»**, con cuatro respuestas comprensibles:

1. Qué encontró GeoGuardian.
2. Qué consecuencia podría tener.
3. Qué necesita comprobar o corregir el estudiante.
4. Si la capa sigue siendo seleccionable o está bloqueada.

No se agregarán advertencias innecesarias a capas elegibles sin problemas. GeoGuardian no debe asignar, corregir ni reproyectar SRC automáticamente.

## 4. Reglas técnicas que permanecen intactas

La futura mejora de comunicación **no deberá alterar**:

- La identificación, agrupación y selección de capas compatibles.
- El bloqueo por SRC inválido o inconsistente (D-59 y D-69).
- La admisión con advertencia de un SRC válido diferente al del proyecto (D-59).
- La revalidación y bloqueo de planes desactualizados hasta «Volver a revisar» (D-70).
- El tratamiento de capas temporales, externas y no vectoriales según las reglas vigentes.
- La naturaleza **exclusivamente informativa y en memoria** del plan (D-65 y D-68).
- La conservación de archivos originales y la ausencia de copia, reproyección, movimiento, reenlace o modificaciones en el Hito 2.

El ajuste conceptual de las etiquetas documentadas en D-65 quedó formalizado como **D-71 — Aprobada conceptualmente; implementación pendiente** en [DECISIONES.md](DECISIONES.md). El registro histórico de D-65 permanece intacto. D-71 **no autoriza** ejecutar cambios de código.

## 5. Criterios de aceptación futuros

**UX-01 — Comprensión del propósito:** tras ver la interfaz, una persona usuaria de perfil estudiantil puede explicar qué datos se propone organizar, para qué, dónde se reunirían y que **todavía no se hará ninguna copia**.

**UX-02 — Comprensión de SRC:** la persona distingue el SRC asignado en QGIS del SRC declarado en la fuente; puede explicar por qué una fuente sin SRC válido se bloquea y que un SRC diferente al del proyecto no necesariamente es un error.

**Regresión técnica:** las funciones correspondientes a CA-01 a CA-05 deben conservar el comportamiento aprobado en los escenarios examinados durante NORTE-PILOTO-001. Las pruebas de comprensión requieren **nueva evidencia de usuario**; el resultado previo **CA-06 sigue no aprobado**.

La revisión de implementación debería comprobar que los mensajes se adaptan a la situación real sin afirmar acciones no ejecutadas.

## 6. Trazabilidad y control de cambios

- [GeoGuardian — registro de validación NORTE-PILOTO-001](validacion_hito2_windows_norte.md).
- [NORTE — dictamen aprobado](https://github.com/NereoAquino/norte/blob/main/docs/pilotos/NORTE-PILOTO-001-CIERRE.md).
- [GeoGuardian — decisiones vigentes D-59, D-65, D-69 y D-70](DECISIONES.md).

**Autorización recibida:** aprobación conceptual de UX-01 y UX-02; autorización expresa para **registrar esta especificación** en la documentación de GeoGuardian y vincularla al piloto.

**No autorizado:** modificar código, aplicar cambios visuales, publicar paquetes, fusionar ramas, alterar las reglas aprobadas o declarar nuevamente aprobado CA-06 sin una prueba posterior.
