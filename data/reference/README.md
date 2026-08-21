# Referencia DGS

Coloque aquí un DGS **Microsoft Excel (.xlsx/.xlsm)** exportado desde PowerFactory,
por ejemplo:

`dgs_reference.xlsx`

La Fase 8 usa este libro como **referencia estructural**: hojas/tablas, columnas,
claves, referencias y convenciones de representación. El conversor no solicita ni
almacena un número de versión de DIgSILENT/PowerFactory para decidir el esquema.

Por defecto, `DgsWriter` clona el libro de referencia y modifica únicamente las
hojas/columnas declaradas en `config/dgs_mapping.yaml`, preservando el resto.

No incluya modelos de producción con información confidencial en Git.
