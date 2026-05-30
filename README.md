# Auditor Escrutinio Presidencial 2026

Aplicación de auditoría y seguimiento del escrutinio para la **elección presidencial 2026**.
Hermana de [`calculoumbral-congreso2026`](../calculoumbral-congreso2026/) — comparte servidor y stack, pero usa BD independiente.

## Stack
- Backend: Flask (`app.py`) + psycopg + waitress
- Frontend: SPA monolítica vanilla JS (`public/index.html`)
- BD: PostgreSQL en `192.168.0.54` → `AuditorEscrutinioPresidencial2026_PROD`
- Deploy: `./deploy.sh` → servidor `192.168.0.58:5002`, servicio systemd `auditorpresidencial.service`

## Módulos planeados
- 🗺️ Divipol presidencial (cargue + visor)
- 📥 Cargue MMV preconteo
- 📥 Cargue MMV escrutinio
- 📄 Visor E14, Visor E24
- 🔍 Investigaciones
- 📎 Evidencias

## Setup inicial (orden)
1. `db/01_crear_bd.sql` → crear BD
2. `db/02_esquema_base.sql` → tablas base + divipol
3. `db/03_migrar_usuarios_desde_congreso.sh` → copiar usuarios/perfiles desde la BD Congreso
4. Cargar divipol presidencial (archivo Registraduría)
5. Deploy: `./deploy.sh`

## Convenciones
- Endpoints: `/api/<modulo>-<accion>`
- Tablas presidenciales con sufijo `_presidencial_2026`
- Respuestas JSON: `{success: true/false, data?: ..., error?: ...}`
