# Propuesta de variables de seguimiento (fase 2)

Estado: **borrador para validar**. Nada de esto está programado todavía.

El diccionario actual (25 variables) cubre la identificación del asunto y el delito. Esta propuesta agrega lo que pasa después: el mecanismo, las sesiones, el acuerdo y su cumplimiento. Cada variable cita el artículo que la respalda.

## Fuentes

| Ley | Qué se leyó | De dónde |
|---|---|---|
| Ley Nacional de Mecanismos Alternativos de Solución de Controversias en Materia Penal (LNMASCMP), última reforma DOF 01-04-2024 | Arts. 16 a 35 | PDF oficial de la Cámara de Diputados |
| LNMASCMP | Arts. 3, 9 a 15, 36 a 39 y 43 | mley.mx (copia no oficial) |
| Código Nacional de Procedimientos Penales (CNPP) | Arts. 186 a 190 | mley.mx (copia no oficial) |

Pendiente: que el área jurídica coteje contra el DOF lo leído en la copia no oficial. No se revisó la Ley General de Mecanismos Alternativos de Solución de Controversias (2024) ni las leyes estatales.

## Regla de confidencialidad

Las sesiones son confidenciales (art. 4 fr. III) y la ley indica que de ellas solo se registra el acuerdo alcanzado (art. 23). Por eso el sistema registrará **que** hubo una sesión (fecha, tipo, quién asistió, resultado), nunca **lo que se dijo** en ella. No habrá campo de notas libres en las sesiones.

## 1. Datos del procedimiento (uno por asunto)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| P1 | Fecha de la solicitud | Fecha | LNMASCMP art. 9 |
| P2 | Forma de la solicitud | Verbal · Escrita | Art. 9 |
| P3 | Etapa del proceso penal al derivar | Investigación inicial · Investigación complementaria · Etapa intermedia | CNPP arts. 188 y 190 |
| P4 | Supuesto de procedencia | Querella o equivalente · Delito culposo · Patrimonial sin violencia | CNPP art. 187 |
| P5 | Motivo de no admisión | Texto (solo si A7 = No) | Art. 12 |
| P6 | ¿Se pidió reconsideración? | Sí · No (solo si A7 = No) | Art. 12 |
| P7 | Breve relación de los hechos | Texto | Art. 13 |
| P8 | Mecanismo aplicado | Mediación · Conciliación · Junta restaurativa | Arts. 3 fr. IX, 21, 25 y 27 |
| P9 | ¿Se sustituyó el mecanismo? | Sí · No, y cuál fue el nuevo | Arts. 22 y 30 |
| P10 | Facilitador asignado | Catálogo de facilitadores | Art. 12 |
| P11 | Fecha de aceptación de sujetarse al mecanismo | Fecha | Art. 17 |

## 2. Invitación (una por cada requerido)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| I1 | Fecha de la invitación | Fecha | Art. 14 |
| I2 | Medio | Personal · Teléfono · Correo electrónico · Correspondencia · Otro | Art. 14 |
| I3 | Resultado | Aceptó · Rechazó · No localizado · Sin respuesta | Arts. 14 y 17 |

El sistema puede avisar cuando pasen 5 días hábiles desde el registro sin invitación (plazo del art. 14).

## 3. Sesiones (varias por asunto)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| S1 | Fecha | Fecha | Arts. 19 y 24 |
| S2 | Tipo | Preliminar · Conjunta · De revisión del acuerdo | Arts. 16, 19, 28 y 38 |
| S3 | Asistentes | Intervinientes del asunto | Art. 19 |
| S4 | ¿Hubo intérprete? | Sí · No | Art. 19 |
| S5 | Resultado | Continúa · Se alcanzó acuerdo · Concluye sin acuerdo | Arts. 22, 24 y 32 |

## 4. Conclusión del mecanismo (una por asunto)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| C1 | Fecha de conclusión | Fecha | Art. 32 |
| C2 | Forma de conclusión | Acuerdo total · Acuerdo parcial · Anticipada sin acuerdo | Arts. 31, 32 y 33 |
| C3 | Causa de conclusión anticipada | Voluntad de un interviniente · Inasistencia injustificada en más de una ocasión · Posiciones irreductibles · Comportamiento irrespetuoso, agresivo o dilatorio · Revelación de información confidencial · Otra prevista en la ley | Art. 32 fr. I a IV y VI; art. 19 |

## 5. Acuerdo (uno por asunto, si lo hay)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| R1 | Fecha de celebración | Fecha | Art. 33 fr. I |
| R2 | Lugar de celebración | Texto | Art. 33 fr. I |
| R3 | Alcance | Total · Parcial | Art. 33 |
| R4 | Tipo de obligaciones | Dar · Hacer · No hacer (varias) | Art. 33 fr. IV |
| R5 | Contenido de la reparación | Reconocimiento de responsabilidad y disculpa · Compromiso de no repetición · Plan de restitución (varias) | Art. 29 |
| R6 | Monto de la reparación económica | Cantidad (opcional) | Art. 29 fr. III |
| R7 | Cumplimiento | Inmediato · Diferido | CNPP art. 189 |
| R8 | Fecha límite de cumplimiento | Fecha; máximo 3 años desde la firma; 1 año si es diferido y no se fijó plazo | Art. 33 fr. IV; CNPP art. 189 |
| R9 | Fecha de validación por licenciado en derecho del Órgano | Fecha | Art. 33 |
| R10 | Autoridad que aprueba | Ministerio Público · Juez de control | Art. 35; CNPP art. 190 |
| R11 | Fecha de aprobación | Fecha | CNPP art. 190 |

## 6. Seguimiento del acuerdo (varias acciones por acuerdo)

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| G1 | Fecha | Fecha | Art. 36 |
| G2 | Acción | Apercibimiento · Visita de verificación · Llamada telefónica · Recepción o entrega de documentos, pagos, bienes u objetos · Citación · Envío de correspondencia o comunicación · Otra | Art. 36 |
| G3 | Resultado | Texto breve | Art. 37 |

## 7. Cierre del acuerdo

| Clave | Variable | Valores | Fundamento |
|---|---|---|---|
| F1 | Estado de cumplimiento | En curso · Cumplido · Cumplido parcialmente · Incumplido | Arts. 35 y 37 |
| F2 | Fecha del cumplimiento o incumplimiento | Fecha | Art. 37 |
| F3 | Fecha de comunicación al MP o al juez | Fecha (si hubo incumplimiento) | Art. 39 |
| F4 | Efecto | Extinción de la acción penal · Sobreseimiento · Continuación del procedimiento penal | Art. 35; CNPP art. 189 |

## 8. Estatus del asunto (calculado, no se captura)

El art. 43 pide que la base de datos del Órgano reporte número de asuntos, estatus, resultado final y porcentaje de cumplimiento. El estatus se deriva de lo anterior:

Registrado → No admitido / En invitación → En sesiones → Concluido sin acuerdo / Acuerdo en cumplimiento → Acuerdo cumplido / Acuerdo incumplido.

## Ajustes a las 25 variables base (decididos el 9 de noviembre de 2026)

1. **V1 «Adulto/Adolescente»** se registra en dos niveles: en el asunto, el sistema de justicia por el que corre (adultos o justicia para adolescentes); en cada persona, si es adulta o adolescente.
2. **D9 «Instrumentos»**. El diccionario traía «Otro instrumento» y «Otro» por separado. Quedó una sola opción «Otro instrumento», y solo se pide especificar en esa y en «Dos o más instrumentos».
3. **A5 «Carpeta de investigación»** ya no es obligatoria. Se agregó el **NUC** (número único de caso), porque muchos asuntos llegan antes de que se abra la carpeta. Se exige al menos uno de los dos.
4. **Sedes**. Los capturistas de una misma sede ven y continúan los asuntos de sus compañeros.

Sigue abierto: **D11_4 y D11_5** tienen la misma etiqueta («Referencias») en el diccionario. Se capturan como «Referencias» y «Otros datos».
