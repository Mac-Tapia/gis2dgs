# Security

## Credenciales

No almacene usuarios/contraseñas en `project.yaml`. Utilice variables de entorno:

```yaml
uri: $GIS2DGS_DB_URL
```

## SQL

Las consultas configuradas son tratadas como entrada confiable del operador. No
exponga un archivo de proyecto editable a usuarios no confiables si contiene SQL
arbitrario.

## Archivos

Ejecute el conversor sobre copias o exportaciones de las bases GIS/asset. El
pipeline es de lectura para las fuentes y no escribe de vuelta a la base de datos.

## DGS

El DGS de referencia es una plantilla de estructura. El writer genera un nuevo
archivo de salida y no debe sobrescribir la referencia de producción.

## Reporte de vulnerabilidades

En despliegues empresariales, gestione vulnerabilidades mediante el repositorio
interno y mantenga actualizadas las dependencias conforme a la política de TI.
