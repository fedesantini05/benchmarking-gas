# Ecosistema: primera base local

Esta implementación NO es una plataforma corporativa desplegada. No usa IA,
no se conecta a SharePoint y no transmite documentos al repositorio.

## Componentes y estado

| Componente | Implementado en esta etapa | Pendiente |
|---|---|---|
| Catálogo | Identidades, filtros por país/nombre/regulador/integración y capacidades explícitas | Confirmar entidad/alcance y fuentes de toda la lista |
| Fuentes | Descubrir enlaces PDF desde índices registrados de Compagas y Efigas | Conectores de otros sitios/reguladores, JavaScript y paginación |
| Descarga | Copias locales por hash, límites, dominios registrados, sin sobrescribir originales | Inspeccionar entidad, año y tipo de estados dentro de cada PDF |
| Extracción | Adaptadores existentes para casos revisados | Generalización a períodos nuevos, OCR y esquema común de evidencia |
| Clasificación | Reglas y glosarios existentes, sin modificación automática | Bandeja de revisión y propuestas de términos nuevos |
| Generación | Conexión al lote de cinco casos, con fuentes locales autorizadas | Escritura validada de años nuevos y plantillas nuevas |
| Controles | Reproducción de libros aprobados, faltantes y fallos visibles | Auditoría de documento nuevo y aprobación humana registrada |
| Interfaz/API | Pantalla local, ejecutar e historial JSON | Autenticación empresarial, permisos, descarga cómoda de entregas |
| Ejecución | Una tarea a la vez, por empresa y con historial local | Cola persistente, recuperación tras reinicio, cancelación, despliegue |
| SharePoint | Ninguna conexión | Acceso aprobado por IT, almacenamiento y entrega corporativos |

## Lista del usuario

La lista completa se conserva sólo en `config/local/participantes.csv` y su
catálogo generado `config/local/company_catalog.json`, excluidos de Git.
Se mantienen los nombres y las columnas aportadas. Se normalizaron escapes de
puntos de URLs y espacios de presentación; no se completó la razón social de
ESGas ni se modificaron reguladores, integración o páginas sin verificación.
Esas columnas son datos aportados, NO una certificación de vigencia.

Un sitio compartido no identifica la entidad: por ejemplo, un grupo puede
publicar documentos de varias subsidiarias. La identificación dentro del PDF
es obligatoria antes de incorporar datos a una planilla. SGC conserva separada
la entidad del generador histórico (Corporation and Subsidiaries).
Sólo los cinco pilotos conservan períodos revisados; el resto requiere
incorporación. Conecta no está habilitada en este nuevo lote aunque exista su
adaptador histórico. Metrogas Chile debe continuar separada/en pausa.

## Arrancar la pantalla local

Desde la raíz del proyecto, con Python 3.12 y las dependencias instaladas:

```powershell
python ecosystem/cli.py --catalog config/local/company_catalog.json serve
```

Entrar a `http://127.0.0.1:8765`. Elegir filtros, empresas y años, luego
`Buscar documentos oficiales`. La descarga es opcional y local.
Las fuentes configuradas se limitan a Compagas y Efigas. Un enlace encontrado
es CANDIDATO: el año en título/URL podría ser publicación o comparativo, no el
ejercicio que necesitamos. No se aprueba ni se actualizan hashes automáticamente.
Los PDFs se guardan en `outputs/platform/ID_EMPRESA_DE_EJECUCION/` dentro de
la carpeta identificada por cada ejecución. Ver `job.json` para ubicación y hash.

Para generar los casos revisados, indicar el directorio del paquete local de
datos autorizado (contiene `config/local`, `data` y `references`):

```powershell
python ecosystem/cli.py --catalog config/local/company_catalog.json serve --data-root RUTA_AL_PAQUETE_LOCAL
```

La generación requiere el conjunto completo del caso: SGC 2020–2025; los otros
cuatro 2023–2025. Solicitar 2026 muestra revisión requerida y NO altera el mapeo.
La descarga de fuentes nuevas no alimenta automáticamente la generación antigua.
Los libros y controles se guardan bajo `outputs/platform`, excluidos de Git.
La interfaz permite consultar los controles; todavía no incluye descarga por
botón de cada libro. No sustituye una apertura y revisión en Excel de escritorio.

## Importación de futuras listas

CSV simple: columna `nombre`, opcional `pais` como código ISO de dos letras.

```powershell
python ecosystem/cli.py import-csv lista.csv --output config/local/catalogo_candidato.json
```

La importación conserva nombres, exige revisión y no habilita adaptadores.
No admite Excel todavía ni publica listas. El catálogo base con cinco pilotos
es `config/catalog.json`; el catálogo completo local se selecciona explícitamente.

## Seguridad y límites antes de desplegar

El servidor acepta sólo `127.0.0.1`, verifica Host, Origin y token de solicitud;
NO es un login corporativo. No exponerlo a Internet ni cambiar el enlace a
0.0.0.0. El descargador sólo consulta dominios HTTPS registrados, controla
redirecciones, tamaño, firma PDF y rechaza destinos no públicos. IT deberá
agregar control de salida de red, autenticación, autorización, aislamiento,
protección frente a cambios DNS, secretos y registro/auditoría corporativa.
No ejecuta instrucciones de documentos o HTML ni consulta sitios arbitrarios
introducidos por el operador. No elude bloqueos, autenticación ni CAPTCHA.

## Próximas etapas

1. Validar catálogo y fuentes empresa por empresa, empezando por los pilotos.
2. Probar descarga, revisión de entidad/ejercicio y reutilización del lector en
   un documento nuevo; no usar importes congelados como extracción futura.
3. Unificar evidencia por dato: concepto, importe original, unidad, página,
   alcance, documento/hash, fórmula, clasificación y aprobación.
4. Crear bandeja de faltantes y aprobación de glosarios/mapeos versionados.
5. Validar un año nuevo con fórmulas, signos y conciliaciones del usuario.
6. Integrar almacenamiento y login con IT; habilitar ejecución empresarial.
7. Incorporar el módulo técnico independiente y probar con otra persona.

Fuentes de índices verificadas el 08/10/2026:
- https://www.compagas.com.br/relacao-com-investidores.html
- https://www.efigas.com.co/informes-de-gestion-y-sostenibilidad/

## Verificación de esta etapa (08/10/2026)

- 79 pruebas automatizadas aprobadas, incluyendo catálogos, fuentes y bloqueos
  de años no revisados, además de las pruebas financieras anteriores.
- Catálogo local: 62 empresas y 9 países. Archivo no publicado.
- API/pantalla local: catálogo cargado y solicitud de SGC 2026 bloqueada para
  revisión, sin generar una planilla ni aprobar datos nuevos.
- Generación desde la API local: Ecogas Cuyo 2023–2025 completada, con comparación
  PASS contra la referencia revisada. Es reproducción, no extracción de años nuevos.
- Búsqueda en Efigas: enlaces candidatos a informes completos y resúmenes de
  2024/2025 encontrados. No inspeccionados ni aprobados como fuentes nuevas.
- Búsqueda en Compagas: timeout registrado como SOURCE_ERROR; no equivale a
  ausencia de estados contables. Su búsqueda en este equipo queda pendiente.
- Descarga validada con pruebas controladas; no se descargaron PDFs en esta
  etapa. No se modificaron los documentos ni libros originales.
