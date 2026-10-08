# Incorporación del relevamiento técnico

El repositorio de prueba es compartido por los relevamientos financiero y técnico.
Actualmente sólo existe el procesamiento financiero. El módulo técnico aún no
está implementado: no interpretar sus datos usando las reglas financieras.

La persona responsable del relevamiento técnico puede empezar documentando:

1. Los campos de sus planillas: definición, unidad y fórmula, si corresponde.
2. Empresa exacta, país, período y cobertura (distribución, grupo u otra).
3. Fuente oficial y página/tabla que respalda cada dato.
4. Tratamiento de faltantes, cambios de unidad y revisiones históricas.
5. Controles de consistencia y ejemplos que hayan sido revisados manualmente.

No cargar sus Excel ni documentos fuente hasta tener autorización empresarial.
Compartir primero definiciones y una estructura sin datos reales.
Las propuestas pueden registrarse como Issues del repositorio; los cambios
de reglas deben revisarse antes de incorporarlos al código.

Después de acordar el diccionario técnico, se diseñarán su lector, mapeo y
generador independiente. Podrá compartir el catálogo de empresas y mecanismos
de auditoría/ejecución; no debe reutilizar clasificaciones contables por defecto.
