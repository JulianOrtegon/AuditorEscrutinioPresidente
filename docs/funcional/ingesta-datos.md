# Ingesta de datos: preconteo y escrutinio

> Cómo entran los votos al sistema, desde el archivo crudo hasta la tabla de
> seguimiento que alimenta el cruce y el dashboard.

## Dos fuentes

1. **Preconteo MMV**: resultado de la noche electoral (formato MMV de la RNEC).
2. **Escrutinio RNEC**: resultado oficial, en CSV, cargado **día a día** mientras dura
   el escrutinio. Cada día se identifica por su `facceso` (fecha de acceso).

> La llegada de los archivos al servidor se hace por **ingesta SFTP externa** (timer
> del SO contra `192.168.0.54`, cadencia ~12 h según operación on-prem). Eso **no está
> en `app.py`**: la app solo consume los archivos ya presentes en disco. Detalle del
> timer **(a confirmar con Julián / runbook de infra)**.

## Pipeline de preconteo

| Paso | Endpoint / función | Resultado |
|------|--------------------|-----------|
| Cargar archivo(s) | `POST /api/mmv-preconteo/cargar` | Líneas crudas en `preconteo_cargue_presidencial_2026`; registro en `control_mmv_presidencial_2026` (estado 0 = raw). |
| Verificar | `POST /api/mmv-preconteo/verificar` | Valida antes de cargar; detecta el departamento del archivo (`_extraer_depto`). |
| Procesar | `POST /api/mmv-preconteo/procesar/<archivo>` y `procesar-todos` | Parsea las líneas raw (`_parse_mmv_line`) → datos estructurados en `preconteo_presidencial_2026`; marca estado 1. |
| Historial / eliminar | `GET /api/mmv-preconteo/historial`, `DELETE .../<archivo>`, `POST .../eliminar-batch` | Gestión de archivos cargados. |

Los archivos procesados se mueven a una carpeta `PROCESADO/<depto>/` en disco.

## Pipeline de escrutinio RNEC

A diferencia del preconteo, el CSV de escrutinio ya viene **estructurado** (22 campos
RNEC), así que la carga es directa (no hay paso "raw → procesar" separado).

| Paso | Endpoint / función | Resultado |
|------|--------------------|-----------|
| Cargar por upload | `POST /api/escrutinio/cargar` | Sube el CSV y lo procesa. |
| Cargar por ruta local | `POST /api/escrutinio/cargar-ruta` | Para **archivos grandes**: el CSV ya está en disco del servidor; se pasa la `ruta` + `facceso`. |
| Carga masiva | (pantalla "Carga Masiva — Escrutinio RNEC") | Varios archivos de una. |
| Procesamiento | `_procesar_csv_a_bd(ruta, nombre, facceso, tiene_encab)` | Crea la partición del día si falta (`_crear_particion_si_falta`), detecta separador y encabezado automáticamente, y hace `COPY` masivo a `escrutinio_presidencial_2026` (22 columnas RNEC). |

Detalles técnicos de la carga:
- **Tabla particionada por `facceso`**: cada día de escrutinio es una partición LIST.
- **Auto-detección de encabezado**: si la primera línea contiene tokens conocidos
  (`id`, `mesa`, `totalvotos`, etc.) o el primer campo no es numérico, se salta.
- **Auto-detección de separador** (`_detectar_separador`).
- **Carga por streaming + `COPY`** para soportar archivos de varios GB
  (`MAX_CONTENT_LENGTH = 4 GB`).

## De escrutinio crudo a seguimiento

Una vez cargado el día, se **puebla la tabla de seguimiento** con la función SQL
`fn_poblar_escrutinio_presidencial(facceso)` (definida en `db/07_seguimiento_escrutinio.sql`):

1. Asigna el **`numdia`** siguiente a ese `facceso` (1, 2, 3, ... hasta 30).
2. Suma los votos por `(idmesa, codpartido, codcandidato)` cruzando escrutinio con la
   divipol (clase `P`) y las mesas (`divipolmesa`).
3. Inserta filas faltantes en `seguimiento_escrutinio_presidencial_2026` y actualiza la
   columna `diaN` correspondiente.
4. Marca el día como procesado en `dias_escrutinio_presidencial`.

Endpoints relacionados:
- `GET /api/escrutinio/dias-procesados`, `/api/escrutinio/estado-por-dia`.
- `POST /api/escrutinio/repoblar-seguimiento/<facceso>` — re-correr el poblado de un día.

El resultado, la tabla `seguimiento_escrutinio_presidencial_2026` (preconteo + dia1..dia30
por mesa+candidato), es la base del [cruce de candidatos](cruce-rnec.md), del dashboard
y del [Generador Incremental](generador-e14.md).

## Otras ingestas

- **Comisiones / E24**: `POST /api/comisiones-pres/cargar-excel` (catálogo de comisiones);
  los PDFs E24 se sirven desde `E24_PRES_BASE_PATH` en disco.
- **AGE** (Acta General de Escrutinio): `POST /api/age-pres/cargar-carpeta` parsea
  archivos `.docx` (`_parsear_age_pres`) y guarda observaciones por mesa en
  `age_presidencial_2026`. Solo admin.
- **Imágenes E14**: se sirven desde `E14_PRES_BASE_PATH` (default
  `/mnt/elecciones-2026/presidencial`); la app las localiza vía la tabla
  `e14_index_presidencial` (poblada por un proceso de indexación externo — **a confirmar con Julián**).
