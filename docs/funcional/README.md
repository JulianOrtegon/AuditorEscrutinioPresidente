# Documentación funcional — Auditor Escrutinio Presidencial 2026

> Panorama funcional del sistema, pensado para que un PO, analista o agente
> entienda **qué hace** el Auditor sin tener que leer el código.
> Documentación reconstruida leyendo `app.py`, `db/` y `public/index.html`.
> Donde el código es ambiguo se marca explícitamente **(a confirmar con Julián)**.

## 1. Propósito del sistema

El **Auditor Escrutinio Presidencial 2026** es una herramienta interna de auditoría
del escrutinio de la **elección presidencial de Colombia 2026**. Su objetivo central
es **detectar mesas de riesgo**: mesas donde la votación cambió de forma sospechosa
entre el **preconteo** (resultado de la noche electoral) y el **escrutinio oficial**
de la Registraduría (RNEC), para soportar la presentación de reclamaciones.

El flujo de valor, a alto nivel:

1. Se cargan a la BD dos fuentes de votación: **preconteo MMV** y **escrutinio RNEC**
   (este último día por día, durante los días que dura el escrutinio).
2. El sistema construye una tabla de **seguimiento por mesa y candidato**
   (preconteo + un valor por cada día de escrutinio, `dia1`..`dia30`).
3. El módulo de **investigaciones** cruza dos candidatos mesa a mesa y calcula
   la **diferencia** (día de escrutinio − preconteo). Las mesas con diferencias
   relevantes son las candidatas a investigar.
4. Los analistas adjuntan **evidencias** (imágenes E14 por mesa, E24 por comisión,
   observaciones AGE) y crean **investigaciones** sobre los pares de candidatos /
   mesas señaladas.
5. El **Generador Incremental de E14** produce, periódicamente y de forma automática,
   archivos XLSX ("cortes") que vuelcan el estado del escrutinio sobre una plantilla
   de E14, para consumo de terceros / reportería.

> El Auditor Presidencial es **hermano** del Auditor de Congreso
> (`AuditorEscrutinioCongreso2026`): comparten servidor y stack, y los **usuarios y
> perfiles se migran** desde la BD de Congreso (ver `db/03_migrar_usuarios_desde_congreso.sh`),
> pero cada uno tiene su **BD independiente**.

## 2. Actores y roles

Los roles se modelan con la tabla `perfiles` (nombre libre) asociada a cada usuario.
La autenticación es por **cédula + contraseña** (SHA-256), con sesión de servidor (cookie Flask).

| Rol | Cómo se identifica en el código | Qué puede hacer |
|-----|---------------------------------|-----------------|
| **Administrador** | `id_perfil == 1` (`_is_admin()`) | Todo. Único que puede administrar usuarios/perfiles, escanear/cargar AGE, y operar el Generador Incremental (subir plantilla, iniciar/detener/ejecutar). |
| **Analista / usuario estándar** | cualquier perfil con sesión válida, distinto de los dos casos especiales | Consultas, comparaciones, crear investigaciones, cargar evidencias, ver E14/E24. |
| **Perfil "Generador Incremental"** | `perfil == 'Generador Incremental'` | Acceso **restringido**: solo puede ver/descargar el Generador Incremental y el dashboard; el resto de `/api/` le devuelve 403. No puede **operar** el generador (eso sigue siendo solo-admin). |

> El significado funcional/negocio de los demás perfiles (más allá del admin y el
> restringido) **(a confirmar con Julián)** — el código solo distingue por nombre/id.

## 3. Módulos y pantallas

La interfaz es una **SPA monolítica en vanilla JS** (`public/index.html`, ~4.6k líneas).
Pantallas detectadas (por sus encabezados):

| Pantalla | Función |
|----------|---------|
| **Dashboard** | Métricas globales: mesas universo, cobertura preconteo/escrutinio, evidencias por tipo, investigaciones por estado, AGE, comisiones, top departamentos/candidatos. |
| **Administración (usuarios y perfiles)** | CRUD de usuarios y perfiles, reset de contraseña. Solo admin. |
| **Generador Incremental E14** | Subir plantilla XLSX, iniciar/detener el generador automático, ver estado, listar y descargar cortes, ejecutar un corte manual. |
| **Divipol Presidencial** | Cargue y visor de la división política electoral (departamento → municipio → zona → puesto → mesa). |
| **Cargue MMV — Preconteo** | Carga (individual y masiva) de archivos MMV de preconteo, historial, verificar, procesar (raw → estructurado), eliminar. |
| **Carga de Archivos — Escrutinio RNEC** | Carga de CSV de escrutinio RNEC: por upload, por carga masiva y por **ruta local** (archivos grandes); historial; estado de procesamiento por día. |
| **Consulta Votación Preconteo** | Consulta filtrable de votos de preconteo (depto/mpio/zona/puesto/candidato). |
| **Consulta Votación Escrutinio** | Igual pero sobre el escrutinio (último día / día N). |
| **Visor E14** | Búsqueda y visualización de imágenes E14 por divipol o por mesa. |
| **Visor E24** | Visualización de PDFs E24 (por comisión escrutadora). |
| **Comparar 2 Candidatos** | Cruce mesa a mesa de dos candidatos: preconteo vs día de escrutinio, diferencias, filtros gana/pierde y por evidencia. Núcleo de la detección de riesgo. |
| **Mesas en Cero** | Mesas donde un candidato tiene 0 votos según la fuente elegida (escrutinio o preconteo). |
| **Investigaciones** | Listado agrupado de investigaciones, detalle de grupo, crear/eliminar, asignación a analistas. |
| **Evidencias** | Consulta de evidencias por investigación; exportar a Excel (listado/grupo) y a ZIP. |
| **Comisiones Escrutinio** | Cargue (Excel) y consulta del catálogo de comisiones escrutadoras + E24 disponibles. |
| **Observaciones AGE** | Acta General de Escrutinio: escanear/cargar carpeta de `.docx`, consultar observaciones por mesa. |

## 4. Flujo de datos

```
                 (ingesta externa por SFTP → servidor .54, fuera de app.py)
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                         ▼
   Preconteo MMV                                          Escrutinio RNEC (CSV)
   (archivos raw)                                         día a día (facceso)
        │ procesar                                              │ _procesar_csv_a_bd
        ▼                                                       ▼
 preconteo_presidencial_2026                       escrutinio_presidencial_2026
                                                   (particionada por facceso)
        │                                                       │
        └───────────────────────────┬───────────────────────────┘
                                     ▼
            fn_poblar_escrutinio_presidencial(facceso)
            (asigna numdia 1..30, suma votos por mesa/candidato)
                                     ▼
            seguimiento_escrutinio_presidencial_2026
            (1 fila por mesa+candidato: preconteo, dia1..dia30)
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
   Comparar 2 candidatos     Generador Incremental    Dashboard / consultas
   (diferencia día−preconteo)  (snapshot → XLSX)       (métricas, cobertura)
            ▼
   Investigaciones + Evidencias (E14/E24/AGE)
```

**Ingesta SFTP**: según la operación on-prem, los archivos de la RNEC llegan al servidor
de BD (`192.168.0.54`) por **SFTP con un timer del SO cada ~12 h**. Esa ingesta es
**infraestructura externa** (systemd timer / script de SO); **no vive en `app.py`**.
La app consume esos archivos por las rutas de carga (`/api/escrutinio/cargar-ruta`,
carga masiva) y por las rutas de E14/E24 en disco. La cadencia y el detalle del timer
**(a confirmar con Julián / runbook de infra)**.

## 5. Entidades de BD principales

BD: `AuditorEscrutinioPresidencial2026_PROD` (PostgreSQL en `192.168.0.54`).
Convención: tablas presidenciales con sufijo `_presidencial_2026`.

| Tabla | Rol funcional |
|-------|---------------|
| `usuarios`, `perfiles` | Autenticación y roles. Migradas desde Congreso. |
| `divipol_presidencial_2026` | División política electoral (clase D/M/Z/P), potenciales de votación por mesa. |
| `divipolmesa_presidencial_2026` | Mesas individuales, ligadas a su divipol (clase P = puesto). |
| `corporacion_/circunscripcion_/partidos_/candidatos_presidencial_2026` | Catálogos electorales. Candidatos con `formula_pos` (1=presidente, 2=vicepresidente). |
| `control_mmv_presidencial_2026`, `preconteo_cargue_presidencial_2026`, `preconteo_presidencial_2026` | Pipeline de preconteo: control de archivos → líneas raw → datos estructurados. |
| `control_escrutinio_presidencial_2026`, `escrutinio_presidencial_2026` | Pipeline de escrutinio RNEC. La tabla de datos está **particionada por `facceso`** (fecha de acceso/día). |
| `dias_escrutinio_presidencial` | Catálogo de días procesados (numdia ↔ facceso). |
| `seguimiento_escrutinio_presidencial_2026` | **Tabla central de análisis**: por mesa+candidato, preconteo + `dia1..dia30`. |
| `investigaciones_presidencial_2026` | Grupos de mesas a investigar (par de candidatos, diferencias, estado de reclamación, asignación). |
| `evidencias_presidencial_2026` | Evidencias por mesa (E14/E24/NO_E14/SIN_EVIDENCIA), con ruta o base64. |
| `reservas_mesa_presidencial_2026` | Lock de mesa por usuario (evita doble trabajo). |
| `asignaciones_presidencial_2026` | Mesas asignadas a analistas. |
| `age_presidencial_2026` | Acta General de Escrutinio (observaciones RNEC importadas de `.docx`). |
| `gen_plantilla_e14`, `gen_plantilla_mesas`, `gen_plantilla_candidatos`, `gen_estado`, `gen_cortes` | Generador Incremental de E14 (plantilla, mapeo mesas/candidatos, estado del loop, histórico de cortes). |

> **Discrepancia detectada**: `app.py` consulta una tabla `e14_index_presidencial`
> (índice de imágenes E14 por mesa/divipol) que **no aparece en los scripts de `db/`**.
> Probablemente se crea/puebla por un proceso de indexación de imágenes externo.
> **(a confirmar con Julián)** — origen y mantenimiento de `e14_index_presidencial`.

## 6. Endpoints / funciones clave (alto nivel)

Convención de API: `POST/GET /api/<modulo>-<accion>`, respuesta JSON
`{success: bool, data?|filas?, error?}`. Endpoints agrupados por módulo:

- **Auth**: `/api/login`, `/api/logout`, `/api/session`.
- **Divipol**: `/api/divipol`, `/api/divipol/{departamentos,municipios,zonas,puestos,mesas,resumen}`.
- **Preconteo MMV**: `/api/mmv-preconteo/{historial,verificar,cargar,procesar,procesar-todos,eliminar-batch}`.
- **Escrutinio RNEC**: `/api/escrutinio/{historial,verificar,cargar,cargar-ruta,estado-por-dia,dias-procesados,repoblar-seguimiento/<facceso>}`.
- **Consultas**: `/api/consulta-preconteo/*`, `/api/consulta-escrutinio/*`.
- **Investigaciones** (núcleo): `/api/investigaciones-pres/{comparar,mesas-cero,crear,crear-mesas-cero,listar-agrupadas,detalle-grupo,eliminar-grupo}`.
- **E14**: `/api/e14-pres/{buscar,buscar-por-mesa,ver/<token>,pagina-imagen,monitor/*}`.
- **Comisiones / E24**: `/api/comisiones-pres/*`.
- **AGE**: `/api/age-pres/{escanear,cargar-carpeta,progreso,resumen,filtros,consultar,vaciar}`.
- **Evidencias (export)**: `/api/evidencias-pres/{exportar-excel-listado,exportar-excel-grupo,exportar-zip-grupo}`.
- **Generador Incremental**: `/api/generador/{plantilla,plantilla/preview,iniciar,detener,estado,cortes,cortes/<id>/descargar,ejecutar-ahora}`.
- **Administración**: `/api/admin/{perfiles,usuarios}` (CRUD + reset password).
- **Dashboard**: `/api/dashboard/metricas` (cacheada con TTL).
- **Salud**: `/api/health`.

La lógica funcional más rica está documentada por separado:
- [Cruce y detección de mesas-riesgo](cruce-rnec.md)
- [Generador Incremental de E14](generador-e14.md)
- [Ingesta de datos (preconteo y escrutinio)](ingesta-datos.md)

## 7. Integración on-prem (despliegue)

- **Stack**: Flask (`app.py`, monolito ~4k líneas) + `psycopg` (pool) + `waitress`
  (WSGI prod) + SPA vanilla JS. Sin frontend build; `public/` se sirve estático.
- **Servidor de app**: `192.168.0.58`. Servicio systemd `auditorpresidencial.service`
  (`ExecStart=python3 app.py --waitress`), `Restart=always`.
- **BD**: PostgreSQL en `192.168.0.54`, BD `AuditorEscrutinioPresidencial2026_PROD`.
- **Despliegue**: `./deploy.sh` copia `app.py`, `public/index.html`, `requirements.txt`
  y `.env.example` por `scp` al servidor, instala dependencias y reinicia el servicio;
  hace healthcheck contra `/api/health`.
- **Dominio público**: `https://auditor.tyseapps.com` (reverse proxy externo, no en este repo).
- **Almacenamiento en disco** (no en BD): imágenes E14 en `E14_PRES_BASE_PATH`
  (default `/mnt/elecciones-2026/presidencial`), PDFs E24 en `E24_PRES_BASE_PATH`
  (default `/opt/softwareEscrutinios/E24_PRES`), uploads temporales en `uploads/`.

> **Discrepancias de puerto** (a alinear con Julián / runbook de ops):
> - `README.md`, `.env.example`, `deploy.sh` y el `.service` apuntan a **puerto 5002**.
> - La memoria de operación on-prem registra el Auditor en **`.58:5003`**.
> No se modificó nada; queda documentado para verificación. **(a confirmar con Julián)**.

## 8. Cobertura de esta documentación

**Documentado a partir del código:** propósito, roles (admin / estándar / generador-restringido),
inventario completo de pantallas y endpoints, flujo de datos preconteo→escrutinio→seguimiento→cruce,
entidades de BD, lógica de cruce de candidatos, generador incremental, y despliegue on-prem.

**Pendiente / a confirmar con Julián:**
1. Semántica de negocio de los perfiles distintos de admin.
2. Origen y mantenimiento de la tabla `e14_index_presidencial` (no está en `db/`).
3. Detalle del timer/script de ingesta SFTP (cadencia, qué deja en disco, qué dispara la carga).
4. Discrepancia de puerto 5002 (repo) vs 5003 (operación on-prem).
5. Reglas de negocio para "diferencia relevante" (¿hay umbral que define mesa-riesgo, o es criterio del analista?).
