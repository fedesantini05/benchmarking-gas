# Casos aprobados: Ecogas Cuyo y Efigas

El usuario confirmó ambas planillas el 7 de octubre de 2026. Alcance: 2023–2025.
Metrogas Chile permanece separada y en pausa, sin cambios en esta etapa.

## Ejecutar desde VS Code

Abrir la carpeta `benchmarking_python`. En la terminal, con el entorno Python
del proyecto activado:

Para elegir empresa y acción sin recordar los comandos, ejecutar `python menu.py`.
El menú permite verificar o generar una copia nueva, sólo de 2023–2025.
Las copias se guardan con nombre único en `outputs/verification/copias`.

```powershell
python run_tests.py
python run_company.py ecogas_cuyo --check
python run_company.py efigas --check
python run_company.py ecogas_cuyo --verify-approved
python run_company.py efigas --verify-approved
```

`--check` sólo verifica presencia de archivos, no valida su contenido.
`--verify-approved` requiere la configuración local de cada empresa con las
rutas de plantilla, PDF y Excel aprobado, y sus SHA-256. Se detiene si alguno
cambió; no renueva automáticamente la aprobación. Regenera desde los originales,
compara todas las partes del XLSX y conserva un informe JSON en
`outputs/verification`. La copia temporal generada se elimina al terminar.
`PASS` significa reproducción exacta del contenido interno aprobado, no que se
haya realizado una nueva auditoría contable ni una apertura en Excel de escritorio.

Para producir otra copia permanente, elegir una salida nueva en el JSON y ejecutar
`python run_company.py EMPRESA`, sin `--verify-approved`. Nunca sobrescribir los
originales ni la referencia aprobada. Las rutas relativas son respecto de
`benchmarking_python`, no respecto del JSON. Los archivos de `config/local`
están excluidos de Git porque contienen rutas propias de esta computadora.

## Qué se comprueba

- Igualdad de todas las partes internas del Excel: cifras, fórmulas, cachés,
  formatos, columnas históricas, otras hojas y observaciones/fuentes.
- Conservación fuera del alcance en el generador OOXML.
- Ecogas: neto y antes de impuestos, activo total/corriente, pasivo corriente,
  patrimonio y ecuación patrimonial, contra importes revisados de cada PDF.
- Efigas: agregados publicados, ausencia de doble conteo financiero y faltantes
  preservados. Sus datos insuficientes siguen siendo `PARTIAL`, aunque la prueba
  de reproducción resulte `PASS`.
- Reglas de signo y trazabilidad mediante pruebas unitarias: tributos e incobrables
  fuera de PMSO, reversiones positivas en otros ingresos, mantenimiento por función,
  materiales por apertura + compras - cierre, y mapa confirmado de fórmulas.

Las plantillas reales tienen CAOM: Otros Gastos es fila 39 y neto es 57.
En Ecogas el capital de trabajo es fila 26 y bruto menos neto es 29.
En Efigas, por una fila adicional del balance, son 27 y 30 respectivamente.
Se respeta el significado de las filas, no se aplica una numeración a ciegas.

## Vocabulario y excepciones

`spanish_cases/glossary_ar_cl.json` conserva Argentina y Chile y ahora incorpora
Colombia. El lector de Efigas utiliza las etiquetas de Colombia desde ese archivo.
Ecogas conserva su mapeo revisado por naturaleza y función; el glosario argentino
documenta vocabulario, pero no extrae autónomamente nuevos PDFs escaneados.
No hay aprendizaje automático: los términos se incorporan mediante revisión humana.

Sólo para Efigas, según autorización del usuario:

- Ingresos publicados incluyen gas y financiación no bancaria sin apertura.
- Costos 2024/2025 incluyen venta y financiero combinados en fila 16, con observación;
  no se repiten en gastos financieros. No representan costo exclusivo de gas.
- Totales sin desglose se cargan con fórmula `=importe`, no con sumandos inventados.
- Los detalles faltantes permanecen vacíos; no se usan residuos para conciliarlos.
- Las diferencias publicadas de redondeo se documentan; el neto publicado prevalece
  cuando la información no permite reconstruirlo exactamente.

Estas excepciones no se transfieren a otras empresas colombianas. Nuevas empresas,
años, plantillas o informes modificados requieren revisar extracción y mapeo.

## Verificación realizada el 7 de octubre de 2026

- 53 pruebas de Python correctas: 15 de entrada/pilotos, 22 históricas y 16 de SGC.
- Ecogas: regeneración desde plantilla y operandos revisados, 25 partes internas
  comparadas contra la aprobada, sin diferencias.
- Efigas: nueva lectura de los tres PDF y generación desde plantilla, 25 partes
  internas comparadas contra la aprobada, sin diferencias.
- No se modificaron los Excel aprobados ni los originales.
- No se repitió el renderizado: las partes de los XLSX, incluidas fórmulas y
  cachés, resultaron idénticas a las versiones ya revisadas. No se abrió Excel
  de escritorio. La igualdad del archivo no valida documentos futuros.

## Próxima etapa

Probar el menú de selección con otra persona de la empresa y verificar instalación
en una segunda computadora. Después, ampliar lectores para nuevos documentos y sólo al final
conectar búsqueda oficial y SharePoint. Este piloto todavía no descarga informes,
no actualiza la nube y no acepta períodos futuros sin revisión.
