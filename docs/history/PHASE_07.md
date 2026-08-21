# Fase 7 — Mapping canónico a estructura PowerFactory

## Objetivo

Transformar `NetworkModel + ElectricalLibrary` en una representación PowerFactory
node-breaker mantenible, sin acoplarla todavía a las columnas concretas de un DGS.

## Clases PowerFactory utilizadas

- `ElmNet`: red.
- `ElmSubstat`: subestación.
- `ElmTerm`: terminal/barra.
- `StaCubic`: cubículo de conexión.
- `ElmLne` / `TypLne`: línea y tipo de línea.
- `ElmTr2` / `TypTr2`: transformador de dos devanados y su tipo.
- `ElmCoup`: interruptor/acoplador.
- `ElmLod`: carga general.
- `ElmGenstat`: generador estático/DER canónico.
- `ElmXnet`: red externa/fuente.

## Decisión arquitectónica

La Fase 7 no escribe DGS. Produce `PowerFactoryModel` con:

- clase PowerFactory real;
- nombre;
- foreign key determinista;
- atributos semánticos;
- referencias semánticas;
- jerarquía de padres;
- `StaCubic` explícitos para cada conexión.

La Fase 8 será responsable de traducir esos atributos/referencias a las columnas
exactas observadas en un DGS de referencia exportado por PowerFactory.

## Node-breaker

Para un elemento de dos terminales:

`ElmTerm -> StaCubic -> ElmLne/ElmTr2/ElmCoup <- StaCubic <- ElmTerm`

Para una carga, generación o fuente:

`ElmTerm -> StaCubic -> ElmLod/ElmGenstat/ElmXnet`

## IDs estables

`ForeignKeyFactory` construye claves deterministas, por ejemplo:

`GIS2DGS:bus:B001`

La estabilidad del foreign key permite preparar posteriormente actualización,
comparación y merge sin depender exclusivamente de `loc_name`.

## Configuración

`config/powerfactory_mapping.yaml` contiene las clases y políticas de mapping.
No contiene nombres de columnas DGS.

## Limitación deliberada

Los nombres exactos de columnas/tablas DGS no se inventan. Para cerrar la Fase 8
se requiere un DGS mínimo exportado desde la versión real de PowerFactory.
