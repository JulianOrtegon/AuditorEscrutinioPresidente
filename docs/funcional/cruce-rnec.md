# Cruce RNEC y detección de mesas-riesgo

> Núcleo funcional del Auditor: comparar la votación del **preconteo** con la del
> **escrutinio oficial RNEC**, mesa a mesa, para señalar mesas a investigar.

## Idea central

Para cada mesa y candidato existe un valor de **preconteo** (noche electoral) y un
valor de **escrutinio** por cada día (`dia1`..`dia30`). La señal de riesgo es la
**diferencia**:

```
diferencia = valor_dia_escrutinio − preconteo
```

- `diferencia < 0` → el candidato **pierde** votos frente al preconteo en esa mesa.
- `diferencia > 0` → el candidato **gana** votos.

El analista normalmente busca el patrón clásico de sospecha: un candidato **pierde**
votos mientras su contrincante **gana** en la misma mesa.

## Pantalla "Comparar 2 Candidatos" — `POST /api/investigaciones-pres/comparar`

Compara dos candidatos (lado 1 y lado 2) sobre el mismo conjunto de mesas.

Parámetros relevantes:
- `codcandidato1`, `codcandidato2`: los dos candidatos a enfrentar.
- `coddepto`, `codmipio`: filtro geográfico opcional.
- `numdia`: día de escrutinio a comparar (por defecto, el **último** día procesado).
- Filtros de movimiento (combinables, en OR): `solo_pierde1`, `solo_gana1`,
  `solo_pierde2`, `solo_gana2`.
- `filtro_reclamacion`: `todas` / `con_evidencia` / `sin_evidencia`.
- Paginación: `pagina`, `por_pagina` (máx. 2000).

Para cada mesa devuelve: preconteo y valor del día de ambos candidatos, ambas
diferencias, datos geográficos (depto/mpio/zona/puesto/mesa), conteo de evidencias
por lado, usuario que cargó la evidencia, y las reservas (lock) por lado.
El orden por defecto prioriza las mesas con **mayor diferencia absoluta combinada**
(`ABS(dif1) + ABS(dif2)` descendente), es decir, las más llamativas primero.

> El valor del "día" se calcula con `_build_ultimo_valor_expr(numdia)`, que toma la
> columna `diaN` correspondiente (o la última no nula hasta ese día). Detalle exacto
> de la regla de "último valor" **(a confirmar con Julián)**.

## Pantalla "Mesas en Cero" — `POST /api/investigaciones-pres/mesas-cero`

Busca mesas donde un candidato tiene **0 votos** según la fuente elegida:
- `escrutinio` (default): 0 en el día N pero con votos en escrutinio (mesa reportada).
- `preconteo`: 0 en el preconteo.

Sirve para detectar ceros sospechosos (candidato que debería tener votos y aparece en 0).

## De cruce a investigación

Cuando el analista identifica mesas-riesgo:

- `POST /api/investigaciones-pres/crear` — crea investigaciones para mesas seleccionadas
  (par de candidatos, con sus preconteos, valores del día y diferencias).
- `POST /api/investigaciones-pres/crear-mesas-cero` — crea investigaciones desde el
  resultado de "Mesas en Cero".
- `GET /api/investigaciones-pres/listar-agrupadas` — listado agrupado.
- `GET /api/investigaciones-pres/detalle-grupo` — detalle de un grupo.
- `POST /api/investigaciones-pres/eliminar-grupo` — eliminar.

Cada investigación (`investigaciones_presidencial_2026`) guarda el snapshot de ambos
lados (candidato, partido, preconteo, valor del día, diferencia), el `numdia`, el
`estado_reclamacion` (`pendiente` por defecto), y la asignación a analistas.

## Soporte: reservas y evidencias

- **Reservas** (`reservas_mesa_presidencial_2026`): lock de una mesa+lado por usuario,
  para que dos analistas no trabajen la misma mesa.
- **Evidencias** (`evidencias_presidencial_2026`): imágenes/observaciones por mesa,
  tipadas (`E14`, `E24`, `NO_E14`, `SIN_EVIDENCIA`, otros). El cruce las cuenta y las
  usa para los filtros `con_evidencia` / `sin_evidencia`. Las marcadas `NO_E14` y
  `SIN_EVIDENCIA` no cuentan como evidencia válida.

> **Pendiente**: ¿existe un umbral numérico que define automáticamente "mesa-riesgo",
> o la selección es 100% criterio del analista sobre la tabla ordenada? **(a confirmar con Julián)**.
