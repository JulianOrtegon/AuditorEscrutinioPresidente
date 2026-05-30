#!/bin/bash
# Copia las tablas usuarios y perfiles desde la BD Congreso a la BD Presidencial.
# Idempotente: usa COPY a CSV intermedio.
# Requisitos: variables DB_HOST, DB_USER, DB_PASSWORD en env, psql instalado.

set -e

DB_HOST="${DB_HOST:-192.168.0.54}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-postgres}"
SRC="AuditorEscrutinioCongreso2026_PROD"
DST="AuditorEscrutinioPresidencial2026_PROD"
TMP=$(mktemp -d)

export PGPASSWORD="$DB_PASSWORD"
PSQL_SRC="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $SRC"
PSQL_DST="psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DST"

echo "[1/4] Exportando perfiles desde $SRC..."
$PSQL_SRC -c "\copy (SELECT id,nombre FROM perfiles ORDER BY id) TO '$TMP/perfiles.csv' CSV HEADER"

echo "[2/4] Exportando usuarios desde $SRC..."
$PSQL_SRC -c "\copy (SELECT id,cedula,contrasena,nombres,apellidos,correo,id_perfil,iddivipol,codcorporacion FROM usuarios ORDER BY id) TO '$TMP/usuarios.csv' CSV HEADER"

echo "[3/4] Truncando perfiles/usuarios destino y reimportando..."
$PSQL_DST <<EOF
TRUNCATE usuarios, perfiles RESTART IDENTITY CASCADE;
\copy perfiles(id,nombre) FROM '$TMP/perfiles.csv' CSV HEADER
\copy usuarios(id,cedula,contrasena,nombres,apellidos,correo,id_perfil,iddivipol,codcorporacion) FROM '$TMP/usuarios.csv' CSV HEADER
SELECT setval('perfiles_id_seq', COALESCE((SELECT MAX(id) FROM perfiles),1));
SELECT setval('usuarios_id_seq', COALESCE((SELECT MAX(id) FROM usuarios),1));
EOF

echo "[4/4] Resumen:"
$PSQL_DST -c "SELECT (SELECT COUNT(*) FROM perfiles) AS perfiles, (SELECT COUNT(*) FROM usuarios) AS usuarios"

rm -rf "$TMP"
echo "OK — migración completada."
