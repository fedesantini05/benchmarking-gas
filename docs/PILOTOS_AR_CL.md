# Ecogas Cuyo y Metrogas Chile

Actualización 2026-10-07: Ecogas aprobada e integrada a `run_company.py`; ver
`CASOS_APROBADOS_AR_CO.md`. Metrogas queda separada y en pausa por decisión
del usuario. No ejecutar su generador ni completar 2022/2023 en esta etapa.

Alcance autorizado: Ecogas Cuyo 2023–2025 y Metrogas Chile individual 2024–2025.
En Metrogas, 2022/2023 permanecen intactos. La auditoría 2024 (PDF p.3) y la
absorción de la última subsidiaria (p.29) confirman el alcance individual de
2024 pese a encabezados heredados que dicen consolidado.

La generación y los controles se ejecutan en Python, sin llamadas a IA.
Los operandos de estos dos pilotos fueron extraídos/revisados de los PDFs,
incluidas páginas escaneadas. Son mapeos supervisados ligados a los hashes
exactos de los documentos: **no es un extractor genérico desatendido** ni
un aprendizaje automático. Nuevos años o PDFs modificados requieren revisar
la extracción antes de habilitar su carga. El vocabulario AR/CL se documenta
en `spanish_cases/glossary_ar_cl.json`; todavía no está conectado al extractor
genérico de los adaptadores antiguos.

Reproducción de los pilotos: `python -m spanish_cases.reviewed_southern ecogas_cuyo`
o `python -m spanish_cases.reviewed_southern metrogas_chile`. Requiere el
inventario local validado en `cache/new_cases/inventory.json`. Por seguridad
se rechaza una salida ya existente; no se sobrescriben las entregas.

Las plantillas tienen CAOM en EERR 35–38: Otros Gastos es 39, EBITDA 47,
depreciaciones 48, EBIT 49, resultado financiero 50, impuestos 56 y neto 57.
Balance conserva 31 filas, capital de trabajo 26 y diferencia bruto/neto 29.
Se preserva la numeración real, no se insertan/eliminan filas.

Ecogas: notas originales de cada año, no comparativos reexpresados del año
siguiente. Consumo de materiales = apertura + compras - cierre. Tributos,
ENARGAS, juicios e incobrables separados del PMSO. Las activaciones no son
gastos del período. IIBB financiero va a tributos sin repetirlo en financiero.
Las depreciaciones de inversión se separan de otros egresos. Mantenimiento
sin apertura por naturaleza permanece en Otros PMSO, no se presume tercero.

Metrogas: reversos TGN/contingencia y deterioro positivo en Otros Ingresos.
Gastos financieros siempre negativos, con cambio/reajuste negativo; diferencia
de cambio positiva 2025 en ingresos financieros. M$1 de diferencia entre la
nota financiera y el estado principal 2024 se documenta; se usa el principal.
Materiales/terceros no separados: permanecen dentro de costos funcionales
publicados de Otros PMSO. No existe base histórica numérica para estimarlos
sin duplicar; marcar REVIEW en Observaciones. Sus subtotales sin apertura no
son evidencia de que tales gastos no existan.

Las salidas incorporan cachés de fórmula, notas/fuentes para cada año y
auditoría JSON con operandos, documentos/hash y conciliaciones. Todas las
celdas fuera del alcance deben permanecer iguales al original. La verificación
visual importa los XLSX en otro motor; no equivale a una prueba nativa en Excel.
