# Benchmarking de distribuidoras de gas — piloto Python sin IA

Procesamiento local de estados contables y generación de una copia de la planilla
CIER. No requiere API de IA. No busca informes en Internet, no conecta SharePoint
y no interpreta automáticamente cualquier empresa o año nuevo.

## Estado de los casos

| Empresa | Períodos del caso | Implementación |
|---|---|---|
| Conecta | 2023–2025 | Lector específico de PDF y generador histórico |
| Compagas | 2023–2025 | Datos revisados asociados a hashes de informes; no es extracción genérica |
| Potigas | 2023–2025 | Datos revisados asociados a hashes de informes; no es extracción genérica |
| SGC | 2020–2025 | Nuevo lector por etiquetas y generador; ejecución principal |
| Contugas | 2022–2024 | Prototipo histórico inactivo; 2023 comparativo del informe 2024 |
| Northwest | 2024–2025 | Prueba de compatibilidad de etiquetas; no genera planilla |
| Ecogas Cuyo | 2023–2025 | Mapeo revisado, operandos originales y hashes; integrado al ejecutor común |
| Efigas | 2023–2025 | Lector de informes de gestión por etiquetas; totales publicados y costos combinados autorizados |
| Metrogas Chile | 2024–2025 | Caso separado en pausa; no integrado al ejecutor común, 2022/2023 pendientes |

El nuevo ejecutor reúne los casos sin reemplazar las carpetas originales.
La implementación antigua de SGC se conserva en `legacy`, pero el ejecutor
principal utiliza `sgc/generar_planilla.py`.

## Instalación en Windows

Requisito de la versión probada: Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_tests.py
```

Las pruebas no generan Excel y no requieren los PDF originales: incluyen muestras
congeladas de extracción de SGC y pruebas de reglas. No certifican por sí solas
la extracción de futuros documentos ni una apertura en Excel de escritorio.

Ecogas y Efigas cuentan además con una prueba local que sí regenera un Excel
temporal desde la plantilla original. Se compara cada parte interna con la
versión aprobada (fórmulas, cachés, formatos, históricos, fuentes y notas).
No se utiliza el libro aprobado como base de generación y no se sobrescribe.
Ver `docs/CASOS_APROBADOS_AR_CO.md` para uso y limitaciones.

## Configuración y uso

1. Copiar `config/examples/EMPRESA.json` a `config/local/EMPRESA.json`.
2. Indicar plantilla, informes, períodos admitidos y una salida nueva.
3. Guardar los PDF/Excel fuera del repositorio o en `data`, que está excluida de Git.
4. Revisar los archivos antes de autorizar el procesamiento:

```powershell
.\.venv\Scripts\python.exe run_company.py compagas --check
```

Cuando se quiera generar una planilla:

```powershell
.\.venv\Scripts\python.exe run_company.py compagas
.\.venv\Scripts\python.exe run_company.py sgc
```

También admite `--config RUTA`. Las rutas relativas se resuelven desde la raíz
del proyecto, no desde la ubicación del JSON. Los archivos de configuración
locales no se publican. SGC admite `reference` opcional para comparar contra una
planilla aprobada; sin ella, la auditoría declara `reference_comparison: NOT_RUN`.
Contugas requiere `--allow-inactive`: no debe reactivarse sin revisar las fuentes.
SGC sólo admite el conjunto completo 2020–2025 en esta versión.

El ejecutor rechaza una salida existente o coincidente con la plantilla.
Mantener los originales y revisar los registros de auditoría antes de entregar.
No usar los ejecutores históricos directamente para el flujo normal.

## Organización

- `run_company.py`: entrada común y configuración portable.
- `sgc/`: versión nueva de SGC y prueba de etiquetas de Northwest.
- `legacy/`: adaptadores, diccionarios y pruebas anteriores conservados.
- `config/global_rules.json`: configuración histórica de reglas; no todos los
  adaptadores la leen automáticamente. La referencia normativa es `docs/REGLAS.md`.
- `config/examples/`: configuraciones publicables sin rutas personales.
- `tests/fixtures/sgc/`: muestras congeladas; no son fuentes de producción.
- `docs/`: metodología, límites e inventario para publicación.

Los scripts históricos de regresión que copian un Excel aprobado son únicamente
herramientas de comparación. No prueban extracción independiente ni aprendizaje.
Los diccionarios se amplían con revisión humana; no hay aprendizaje automático.

## Publicación

Repositorio privado de prueba, pendiente de integración con IT de la empresa.
La carga de código no incluye PDFs, libros Excel, contraseñas, entornos ni resultados de trabajo.
No se ha elegido licencia: confirmar derechos y política de la empresa antes
de publicar. Ver `docs/PUBLICACION.md`.

## Ejecución desde el navegador: preparación local

El workflow manual `Procesar benchmarking` y el ejecutor `cloud/run_batch.py`
están preparados para cinco casos revisados. La ejecución con documentos todavía
no está probada en GitHub. Su carga está pendiente de autorización.
Ver `docs/GITHUB_ACTIONS.md` para alcance, permisos y activación por TI.

## Relevamiento técnico

La incorporación del trabajo técnico está pendiente: ver
`docs/DATOS_TECNICOS.md` para documentar campos, fuentes y controles antes de
automatizarlo. No existe todavía un generador de planillas técnicas.

## Base del ecosistema local

`ecosystem/cli.py` incorpora catálogo, fuentes registradas, descargas locales,
historial de ejecuciones y una primera pantalla de selección. No es un portal
corporativo ni habilita años nuevos sin revisión. Ver `docs/ECOSISTEMA.md`.
El listado completo de participantes se mantiene en configuración local,
fuera de Git, hasta que se autorice su publicación.
