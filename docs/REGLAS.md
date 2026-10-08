# Reglas confirmadas por el usuario

## Estado de resultados

| Fila | Fórmula con filas de la misma columna |
|---|---|
| 2 | 3 + 13 |
| 3 | SUMA(4:12), salvo ausencia de desglose de clientes |
| 15 | 2 + 14 |
| 17 | 15 + 16 |
| 18 | 19 + 23 + 27 + 31 |
| 19 | 20 + 21 + 22 |
| 23 | 24 + 25 + 26 |
| 27 | 28 + 29 + 30 |
| 31 | 32 + 33 + 34 |
| 35 | SUMA(36:42) |
| 43 | 17 + 18 + 35 |
| 45 | 43 + 44 |
| 46 | 47 + 48 |
| 49 | 45 + 46 |
| 50 | 51 + 52 |
| 53 | 49 + 50 |

No reemplazar fórmulas de totales si existe desglose. En ventas sin apertura
por clientes, cargar el total publicado en fila 3. En pilares PMSO sin desglose
funcional, cargar el total de la categoría en 19, 23, 27 o 31 según corresponda.
SGC tiene una limitación documentada: sólo se publica O&M agregado y no hay base
histórica suficiente para estimar pilares, por lo que el total se carga en 18.

Todos los gastos son negativos. Reversiones positivas e ingresos operacionales
adicionales van en 13 según criterio confirmado. No confundir la fila 13 de EERR
con la fila 13 de balance. Desglosar tributos, tasas, regulación, operador técnico,
extraordinarios, incobrables y demás gastos de 36–42 fuera del PMSO cuando estén
informados. Revisar diferencia cambiaria y derivados dentro de la clasificación
financiera; no omitirlos ni contarlos dos veces.

Si falta un pilar PMSO y hay historia comparable, estimar por participación
histórica, conservar el total e identificar ESTIMATED, años base y fórmula.
Sin respaldo histórico, dejar MISSING/REVIEW; no inventar montos para conciliar.

## Balance

2=3+7; 3=SUMA(4:6); 7=8+9; 10=11+15; 11=SUMA(12:14);
15=16+17; 18=SUMA(19:21).

26=27-28; 27=3-4; 28=11-13; 29=30-31.

## Trazabilidad y controles

- Una copia acumulativa de la plantilla; preservar historia, estructura y originales.
- Verificar entidad, moneda, unidades, períodos y columnas antes de escribir.
- Usar el informe original del año. No adoptar comparativos de otro informe
  silenciosamente; el caso histórico de Contugas permanece inactivo por esta razón.
- Valores agregados mediante fórmulas con operandos publicados y conversión explícita.
- Observaciones y fuentes para todos los períodos cargados, con páginas/notas.
- Conciliar resultado neto con el publicado y balance con activo=pasivo+patrimonio.
- Toda diferencia debe explicarse; no introducir ajustes genéricos para cerrar.
- Distinguir PUBLISHED, CALCULATED, ESTIMATED, REVIEW y MISSING; ausencia no es cero.
- Las excepciones aprobadas para un PDF no se transfieren automáticamente a otros.

Estas reglas son normativa del proyecto, no una afirmación de que cada adaptador
histórico cumpla automáticamente todas ellas para documentos no probados.

## Efigas: excepción conservadora aprobada

ACTUALIZACIÓN 2026-10-07: el usuario autoriza cargar íntegro el costo de venta
y financiero combinado 2024/2025 en EERR fila 16, con observación explícita,
sin repetirlo en fila 52. Es una excepción de Efigas, no una regla para otras
empresas. Fila 17 representa ingreso menos costo combinado, no margen bruto
exclusivamente operativo. Conservar faltantes sin imputar componentes.
Los importes únicos publicados se escriben como fórmulas de literal (p.ej.
`=-530092`), con año/página/unidad en fuentes: no confundir esto con una apertura
contable. Mantener fórmulas entre celdas cuando hay datos suficientes; no crear
sumandos ni residuos para completar EBIT, EBITDA o resultado financiero.

DECISIÓN VIGENTE (reemplaza las dos instrucciones conservadoras siguientes):
el usuario pidió cargar todos los totales publicados cuando falta apertura,
no sólo ventas. Gastos operativos, componentes del balance, patrimonio y
resultado antes de impuestos se cargan como agregados, dejando detalles vacíos.
Conservar las fórmulas calculables con agregados conocidos. Si un total publicado
difiere internamente de sus componentes, usar ese total, documentar la diferencia
y no crear ajustes: aplica a activo y resultado neto de 2023. Los cálculos sin
datos suficientes conservan su operación dentro de IF(COUNT(...)=n,...,"")
para mostrarse vacíos, no como ceros. El costo combinado de venta y financiero
2024/2025 se carga en fila 16 bajo la excepción expresamente autorizada arriba,
sin considerarlo costo exclusivo de gas ni duplicarlo en fila 52. La salida
sigue siendo PARTIAL por falta
de reconciliación detallada, aunque sus agregados coincidan con los publicados.

Historia de las decisiones anteriores (ya reemplazadas en Efigas):

Conservar los totales calculados según el mapa anterior, incluso sin desglose.
Corrección posterior del usuario: en ventas sin apertura por clientes, cargar
el total publicado de ingresos operacionales en fila 3, como en 2022, y dejar
vacías las filas de clientes. Documentar el alcance mixto gas/financiación,
sin atribuirlo exclusivamente a distribución. Las filas 13 y 14 quedan vacías
sin imputar ingresos/deducciones adicionales al total ya cargado; su ausencia
se explica en Observaciones. Conservar fórmulas 2 y 15.
No reemplazar los demás totales por valores publicados. Entradas sin respaldo: `=NA()`;
totales afectados: `#N/A`, estado PARTIAL, nunca cero aparente ni conciliación PASS.
Los agregados publicados se documentan en Observaciones y auditoría, no se
distribuyen por residuos. Costo de venta y financiero combinado no se clasifica
íntegramente como gas ni como gasto financiero. Esta decisión no autoriza
alterar los años anteriores a 2023.

La plantilla recibida de Efigas NO tiene la misma numeración del modelo estándar:
contiene CAOM adicional en EERR 35–38; Otros Gastos es 39, EBITDA 47,
impuesto a la renta 56 y resultado neto 57. En balance, hay dividendos en 25;
capital de trabajo es 27 y activo inmovilizado 30. Adaptar por concepto,
sin insertar/eliminar filas ni alterar historia. Detenerse si cambia ese diseño.
