# Verificación de la preparación — 2026-10-06

## Resultado

- Entrada común/configuración: 2 pruebas correctas.
- Adaptadores históricos: 22 pruebas correctas.
- SGC nueva: 11 pruebas correctas.
- Total: 35 pruebas correctas, sin errores.
- Preflight de archivos de Conecta, Compagas, Potigas y SGC: FILES_PRESENT.
- Exclusiones de Git comprobadas para configuración local, PDF y Excel/salidas.

Entorno usado: Python del equipo, pypdf 6.10.0 y lxml 6.1.1.
No se realizó todavía una instalación limpia en una segunda computadora.
La configuración de GitHub Actions está preparada, pero no ejecutada en GitHub.

## Cambios de integración

Se copiaron los módulos históricos y la versión nueva de SGC a un paquete
independiente. Se agregó una entrada común que resuelve las rutas relativas,
selecciona SGC nueva y bloquea salidas existentes. Contugas sigue inactiva.

Las tres pruebas antiguas de SGC habían quedado desactualizadas: usaban todo el
diccionario de años en lugar de FACTS[2020] y omitían el argumento de columna.
Se corrigieron sólo esas llamadas en la copia, conservando las verificaciones
contables y las expectativas de fórmulas.

Las muestras de pruebas de SGC conservan los importes extraídos; sólo se eliminó
la ruta personal de cada registro. No se usan como fuente de producción.

## Qué no certifica esta ejecución

No se generaron nuevos Excel, no se modificaron plantillas ni se reejecutó la
extracción completa de los PDF. Las pruebas de datos congelados no demuestran
lectura genérica de nuevos informes. No se abrió Excel de escritorio ni se
publicó un repositorio remoto. El repositorio local todavía no tiene commit.

Siguiente control: instalación en otra PC y, cuando se levante la pausa de
llenado, una prueba integral con copias de fuentes y salidas nuevas.

## Actualización 2026-10-08: nombres legibles de fuentes

El generador de Efigas admite PDF descargados con nombres legibles únicamente
si su SHA-256 coincide con la fuente aprobada. El comparador admite en las
celdas de Fuente (O) sólo el texto exacto anterior y nuevo derivado de esos
archivos, períodos, páginas y unidades. Todas las demás partes y bytes,
incluidos valores, fórmulas, estilos y períodos históricos, siguen comparándose
estrictamente. No se excluye la columna O de la comparación.

Cada excepción queda registrada en `accepted_source_updates`. El cambio de
contenido de un PDF, página, unidad o cualquier otra celda exige revisión.
Se verificó la regeneración local de Efigas 2023–2025 con comparación PASS;
su información permanece PARTIAL por las limitaciones de los informes.
Pasaron 92 pruebas automatizadas. Excel de escritorio no fue verificado.
Los documentos y salidas locales no se publican en GitHub.
