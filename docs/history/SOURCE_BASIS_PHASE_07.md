# Base técnica de la Fase 7

La implementación de Fase 7 se limita a hechos confirmados en documentación oficial
de DIgSILENT y al white paper GIS Integration suministrado para el proyecto.

## Confirmado

- GIS puede alimentar un modelo PowerFactory mediante DGS.
- El conversor debe construir una red eléctrica topológicamente conectada.
- El modelo de red es node-breaker y debe mantener jerarquía cuando corresponda.
- PowerFactory utiliza `ElmTerm` como nodo/terminal.
- Para conectar un elemento de red a un `ElmTerm` se crea un `StaCubic` dentro del
  terminal y se enlaza el cubículo con el elemento.
- `ElmLne` representa líneas y puede utilizar `TypLne`.
- `ElmTr2` representa transformadores de dos devanados y `TypTr2` su tipo.
- `ElmCoup` representa un interruptor/acoplador.
- `ElmLod` es una carga general.
- `ElmGenstat` es un generador estático.
- `ElmXnet` es una red externa.
- `ElmSubstat` es una subestación.

## Deliberadamente no asumido

La Fase 7 NO fija los nombres de columnas DGS ni la estructura física de un archivo
ASCII/Excel/XML concreto. Esa información se obtendrá de un DGS mínimo exportado
por el esquema estructural DGS configurado durante la Fase 8.

Por tanto, `PowerFactoryModel` utiliza atributos y referencias semánticos, mientras
que `DgsMapper` permanece como frontera explícita de Fase 8.
