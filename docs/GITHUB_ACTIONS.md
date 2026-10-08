# Piloto de ejecución desde GitHub

Repositorio privado de prueba: `fedesantini05/benchmarking-gas`.
El código y las pruebas pueden publicarse; la ejecución con documentos NO está
activada ni probada en GitHub. No se creó una organización ni una release de datos.
El usuario indicó el 08/10/2026 que debe consultar antes de subir documentos.
Por eso ningún PDF, Excel ni paquete de datos está autorizado para publicación.

## Qué podrá hacer una persona del equipo

Una vez autorizado, instalado y probado por TI:

1. Entrar al repositorio privado de la empresa con su propia cuenta.
2. Abrir Actions → Procesar benchmarking → Run workflow.
3. Elegir `verificar` o `generar`; indicar `todas` o códigos separados por coma.
4. Esperar el resultado y descargar el archivo de resultados de esa ejecución.
5. Revisar resumen.html, control.json por empresa y las planillas generadas.
6. Subir la entrega aprobada a SharePoint manualmente.

No requiere Python en la computadora del operador. No utiliza una API de IA.
La generación ejecuta Python en un servidor de GitHub, no en SharePoint.
Ejecutar el workflow requiere permiso de escritura según GitHub; descargar
resultados requiere acceso al repositorio. TI debe definir roles, protección de
la rama principal y revisión del código. No compartir contraseñas ni cuentas.

## Alcance real

| Código | Caso habilitado |
|---|---|
| ecogas_cuyo | 2023–2025 |
| efigas | 2023–2025; información parcial y costos combinados observados |
| sgc | 2020–2025 |
| potigas | 2023–2025 |
| compagas | 2023–2025 |

Este piloto reproduce casos revisados: compara todas las partes internas de
cada Excel contra la referencia. PASS no convierte un faltante en dato completo.
Efigas continúa siendo parcial. No certifica apertura en Excel de escritorio.
Una nueva empresa, documento o año necesita revisar extracción, unidades,
clasificación y reglas; no basta cambiar un nombre o actualizar el hash.
Metrogas Chile, Contugas y Conecta no integran este lote de cinco casos.
No descarga informes oficiales, conecta SharePoint ni aprende automáticamente.

## Separación entre código y documentos

El código y sus pruebas van al repositorio privado. `.gitignore` excluye PDF,
XLSX, datos, referencias de trabajo, configuraciones locales y resultados.
Revisar el listado de archivos antes de cualquier commit: la exclusión no
reemplaza una revisión de privacidad, rutas personales y derechos de muestras.

La opción preparada para el piloto, SUJETA A AUTORIZACIÓN, es un ZIP de datos
como adjunto de una release privada, separado del historial del código. Incluye
33 archivos: cinco configuraciones relativas, cinco plantillas, 18 informes y
cinco referencias. No incluye código, ejecutables ni entornos instalados.
Separarlo del código NO elimina que los documentos se alojarían en GitHub.
Si la política exige SharePoint exclusivamente, NO subir este paquete: faltaría
implementar un acceso autorizado a SharePoint o un ejecutor corporativo.

El flujo exige repositorio privado y rama predeterminada, verifica SHA-256 del
ZIP y de cada documento, rechaza rutas inseguras/código, no sobrescribe salidas
y no entrega un Excel que difiera del aprobado. Continúa las otras empresas
pero marca fallida la ejecución global si alguna falla.

## Decisiones que faltan (empresa / PM / TI)

- Aprobar alojamiento del código y derechos sobre este desarrollo.
- Designar propietario institucional y al menos un administrador de respaldo.
- Crear organización/repositorio privado bajo control de la empresa.
- Autorizar o rechazar explícitamente PDF, plantillas y referencias en GitHub.
- Definir acceso, presupuesto de Actions/almacenamiento y retención.
- Revisar acciones de terceros; fijar sus versiones a commits auditados antes
  de activar el piloto, y planificar actualizaciones de dependencias.
- Mantener SharePoint como archivo de entregas, con responsable de validación.

## Instalación por TI, sólo después de aprobar

1. Publicar el contenido de `benchmarking_python` como raíz del repositorio
   privado. No publicar la carpeta Benchmarking Gas completa ni el paquete
   portable entregado, que contiene documentos.
2. Revisar la lista de archivos, secretos, rutas privadas y licencia antes de
   publicar. Verificar cada nuevo commit antes de enviarlo al repositorio.
3. Ejecutar el workflow de pruebas, sin datos de producción.
4. Si se aprobaron los documentos, revisar y subir el ZIP de datos a una release
   privada. No adjuntarlo a un repositorio público ni guardar datos en Git.
5. Crear estas VARIABLES DEL REPOSITORIO en Settings → Secrets and variables
   → Actions → Variables (no requieren contraseñas ni tokens personales):
   `BENCHMARK_DATA_TAG`, `BENCHMARK_DATA_ASSET`, `BENCHMARK_DATA_SHA256`.
   Tag y nombre del ZIP deben coincidir exactamente con la release y su adjunto;
   SHA-256 se toma del comprobante JSON de preparación local.
6. Mantener Actions habilitado y permisos del token limitados a lectura del
   contenido. El workflow usa el token automático del mismo repositorio.
7. Probar `verificar` en las cinco empresas. Revisar controles y límites.
8. Probar `generar`; descargar y abrir los cinco Excel en Excel de escritorio.
   Comparar fórmulas, signos, históricos y notas. Registrar aceptación del equipo.
9. Probar acceso desde otra cuenta del equipo y documentar soporte/responsables.

Los resultados del workflow se conservan siete días según su configuración;
no son el archivo permanente del proyecto. Las tarifas y límites dependen del
plan contratado: TI debe comprobarlos antes de habilitar ejecuciones.

## Evidencia local

Prueba del 08/10/2026: 61 pruebas automatizadas aprobadas y generación por lote
de las cinco empresas aprobada. Los cinco Excel coinciden en cada parte interna
con sus referencias (133 partes comparadas entre los cinco libros). Son reproducciones, no nuevas
auditorías ni una prueba de ejecución real en GitHub.

Los controles y paquetes nuevos se guardan en `outputs/github_preparation` y
los Excel de la prueba en `outputs/github_trial_2026-10-08`. Estas carpetas
están excluidas de Git. La prueba local no verifica permisos, release, descarga,
facturación ni disponibilidad real del servidor GitHub.

Referencias oficiales:
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow
- https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts
- https://docs.github.com/en/rest/releases/assets
