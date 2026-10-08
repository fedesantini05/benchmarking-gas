# Preparación para GitHub

Este paquete se armó a partir del proyecto histórico `cier_automation` y del
lector nuevo `automatizacion_sgc`. Ambos originales permanecen sin modificaciones.

Antes de publicar:

1. Aprobar organización propietaria, repositorio privado y personas con acceso.
2. Revisar derechos de código, diccionarios y muestras públicas de pruebas.
3. Ejecutar `python run_tests.py` y verificar instalación en una segunda PC.
4. Revisar `git status --short` y los archivos que se incorporarán antes del commit.
5. No incorporar `config/local`, PDFs, XLSX, `data`, salidas, cachés ni credenciales.
6. Decidir licencia según política corporativa, sin asumir una licencia abierta.
7. Crear el repositorio remoto y publicar sólo con autorización del usuario.

Se preparó la primera carga de código al repositorio privado de prueba
`fedesantini05/benchmarking-gas`; la integración corporativa queda pendiente de IT.
No contiene conexión SharePoint,
búsqueda de informes oficiales, interfaz de usuario ni soporte universal.

## Límites y trabajo posterior

- Compagas y Potigas: datos previamente revisados ligados al hash de un PDF;
  nuevas fuentes requieren desarrollo/validación, no sólo cambiar el año.
- Conecta: lector específico; verificar formato de informes futuros.
- SGC: lector dinámico de etiquetas, mapeo 2020–2025 y excepción puntual 2025
  aprobada; no es un adaptador universal ni un mapeo libre de años.
- Northwest: prueba de extracción de EERR; balance y Excel pendientes.
- Contugas: archivo histórico inactivo, comparativo 2023 y ausencia de 2025.
- Los scripts auxiliares heredados conservan sus rutas/convenciones históricas.
  La entrada portable soportada es `run_company.py`; no todos los auxiliares
  son herramientas de usuario final.
- GitHub almacena/versiona el código y Actions puede ejecutar Python si se
  configura. No sustituye SharePoint. El piloto manual preparado localmente se
  explica en `GITHUB_ACTIONS.md`; no está activado y la carga de documentos
  requiere autorización de la empresa.
