-- ============================================================
-- BD Auditor Escrutinio Presidencial 2026 — bootstrap
-- Correr UNA SOLA VEZ contra el servidor PG (NO contra una BD).
-- ============================================================

CREATE DATABASE "AuditorEscrutinioPresidencial2026_PROD"
    WITH ENCODING 'UTF8' LC_COLLATE 'es_ES.UTF-8' LC_CTYPE 'es_ES.UTF-8'
    TEMPLATE template0;

COMMENT ON DATABASE "AuditorEscrutinioPresidencial2026_PROD"
    IS 'Auditor Escrutinio Presidencial 2026 — datos elección presidencial';
