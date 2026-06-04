# Generador Incremental de E14

> Proceso automático que vuelca el estado del escrutinio sobre una plantilla XLSX de
> E14 y produce "cortes" periódicos para reportería / consumo de terceros.

## Qué hace

A partir de una **plantilla XLSX** (que define qué mesas van en qué filas y qué
candidatos en qué columnas), el generador toma cada cierto intervalo un **snapshot**
de la votación del escrutinio y produce un archivo XLSX con esos números: un **corte**.
Si el snapshot no cambió respecto al corte anterior (mismo hash), registra el corte
como `sin_cambios` y **no** vuelve a generar archivo.

## Configuración: la plantilla

- `POST /api/generador/plantilla` — subir la plantilla XLSX (solo admin).
  Se parsea (`_gen_parsear_plantilla`) y se guarda:
  - `gen_plantilla_e14`: metadatos de la plantilla (puede haber varias; una `activa`).
  - `gen_plantilla_mesas`: mapeo **fila XLSX → mesa** (resuelta a geografía + `idmesa`).
  - `gen_plantilla_candidatos`: mapeo **columna XLSX → codcandidato** (por alias del header).
- `GET /api/generador/plantilla/preview` — previsualizar el parseo antes de activar.

La resolución de mesas y candidatos (`_gen_resolver_mesas`, `_gen_resolver_candidatos`)
cruza los textos de la plantilla con la divipol y el catálogo de candidatos.

## El loop automático

- `POST /api/generador/iniciar` (solo admin) — pone `gen_estado.activo = TRUE` con un
  `intervalo_min` (1–60, default 5) y arranca un **hilo background** (`_gen_loop`).
- `_gen_loop` ejecuta un corte, espera el intervalo (leído dinámicamente de la BD) y
  repite, hasta que `activo = FALSE` o se detiene.
- `POST /api/generador/detener` (solo admin) — `activo = FALSE` y para el hilo.
- `POST /api/generador/ejecutar-ahora` — fuerza un corte inmediato.
- Al arrancar la app, `_gen_arrancar_si_activo` re-lanza el hilo si quedó activo
  (sobrevive reinicios del servicio).

## Un corte (`_gen_ejecutar_corte`)

1. Lee la plantilla activa y el estado (`gen_estado`).
2. Toma snapshot + hash de la votación actual (`_gen_snapshot_y_hash`): total de votos,
   mesas reportadas y un hash del contenido.
3. **¿Sin cambios?** Si el hash coincide con el último, registra el corte como
   `sin_cambios` (incrementa `skipped_consecutivos`) y termina sin archivo.
4. **¿Hay cambios?** Construye el XLSX (`_gen_construir_excel`) volcando los votos en
   las celdas según el mapeo fila/columna, lo guarda en disco, y registra el corte como
   `generado` en `gen_cortes` (con archivo, ruta, mesas reportadas, total de votos, hash).
5. Actualiza `gen_estado` (último corte, último hash).

## Estado e histórico

- `GET /api/generador/estado` — estado actual (activo, intervalo, plantilla, último corte).
- `GET /api/generador/cortes` — histórico de cortes.
- `GET /api/generador/cortes/<id>/descargar` — descargar el XLSX de un corte.

## Acceso

- **Operar** el generador (subir plantilla, iniciar, detener, ejecutar) → **solo admin**.
- El perfil especial **"Generador Incremental"** puede **ver y descargar** cortes
  (y el dashboard), pero el resto de la app le devuelve 403. Pensado para un usuario/
  servicio que solo consume los cortes.

> Pendiente: formato/convención exacta de la plantilla E14 esperada (estructura de
> filas/columnas, headers, alias de candidatos) **(a confirmar con Julián)**.
