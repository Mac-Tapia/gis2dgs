# Base técnica — Fase 8

La implementación conserva una frontera explícita entre el modelo PowerFactory
semántico y la serialización física DGS.

## Base del white paper suministrado

El white paper *GIS Integration — How to get GIS Data into PowerFactory* establece
que el resultado del conversor es un modelo PowerFactory basado en DGS, que puede
almacenarse en una base intermedia o en un archivo y que DGS cubre las clases y
propiedades relevantes para el análisis eléctrico.

## Documentación oficial DIgSILENT consultada

- Knowledge Base: *Is it possible to import load characteristics using the DGS
  interface?* — confirma ejemplos DGS en Microsoft Excel y ASCII, además de otros
  formatos.
- Knowledge Base: *How can I import dynamic models via DGS?* — confirma el flujo de
  importación DGS mediante Microsoft Excel y remite a la documentación DGS incluida
  en Help → Additional Packages → DGS Data Exchange Format.
- Data Converters — describe DGS como formato flexible de intercambio para GIS/SCADA.
- Knowledge Base: *For the communication with my SCADA system I intend to use the
  foreign key...* — indica que los foreign keys son case-sensitive, únicos dentro
  del proyecto y recomienda no superar 40 caracteres.

## Decisión de ingeniería

La documentación pública confirma formatos y capacidades, pero no proporciona en la
página web una tabla universal de columnas aplicable a toda versión/perfil de
PowerFactory. Por ello el proyecto utiliza un **template DGS exportado desde la
instalación objetivo** y un perfil externo configurable. Esta decisión evita codificar
nombres de columnas no verificados.
