# Alcance del release v0.8.1

## Incluido

1. Entorno VS Code y empaquetado Python.
2. Modelo eléctrico canónico.
3. Lectores GIS.
4. Normalización y mapping GIS → dominio.
5. Motor topológico y tracing.
6. Motor de validación.
7. Biblioteca eléctrica.
8. Modelo PowerFactory node-breaker semántico.
9. Esquema DGS neutral respecto de versión.
10. Mapping PowerFactoryModel → DgsDocument.
11. Validación DGS.
12. Inspector de DGS Excel.
13. Writer DGS Excel basado en esquema/template.
14. Pruebas unitarias e integración.
15. Script de auditoría reproducible.

## No incluido

- automatización mediante `import powerfactory`/API Python (Fase 9);
- actualización incremental CREATE/UPDATE/DELETE (fase posterior);
- GUI (fase posterior).

## Dependencias de aceptación externa

- DGS real de referencia para completar las columnas del proyecto del usuario;
- base PostGIS real para ejecutar la prueba de aceptación opcional.

Estas dependencias no impiden auditar el motor, pero sí son necesarias antes de
declarar aceptación operacional en una instalación productiva específica.
