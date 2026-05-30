-- ============================================================
-- Tablas para Cargue MMV - Preconteo Presidencial 2026
-- (réplica del patrón Congreso, adaptada a estructura presidencial)
-- ============================================================

-- Control de archivos cargados
CREATE TABLE control_mmv_presidencial_2026 (
    nombrearchivo VARCHAR(200) PRIMARY KEY,
    fecha         DATE NOT NULL,
    registros     INTEGER NOT NULL DEFAULT 0,
    estado        INTEGER NOT NULL DEFAULT 0,    -- 0 = cargado raw, 1 = procesado
    usuario       VARCHAR(50)
);

-- Líneas crudas tal como vienen del archivo
CREATE TABLE preconteo_cargue_presidencial_2026 (
    id      BIGSERIAL PRIMARY KEY,
    archivo VARCHAR(200) NOT NULL,
    dato    TEXT NOT NULL
);
CREATE INDEX idx_preccargue_pres_archivo ON preconteo_cargue_presidencial_2026(archivo);

-- Datos estructurados (resultado de procesar las líneas raw)
-- Para presidencial: 1 corporación, 1 circunscripción, así que simplificamos.
CREATE TABLE preconteo_presidencial_2026 (
    coddepto      INTEGER NOT NULL,
    codmipio      INTEGER NOT NULL,
    codzona       INTEGER,
    codpuesto     VARCHAR(2),
    mesa          INTEGER NOT NULL,
    boletin       INTEGER,
    codpartido    INTEGER,
    codcandidato  INTEGER,
    votos         INTEGER NOT NULL DEFAULT 0,
    archivo       VARCHAR(200)
);
CREATE INDEX idx_precpres_geo  ON preconteo_presidencial_2026(coddepto, codmipio, codzona, codpuesto, mesa);
CREATE INDEX idx_precpres_cand ON preconteo_presidencial_2026(codcandidato);
CREATE INDEX idx_precpres_arch ON preconteo_presidencial_2026(archivo);
