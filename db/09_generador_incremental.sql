-- ============================================================
-- Generador Incremental de E14 (basado en plantilla XLSX) — Presidencial 2026
-- ============================================================

CREATE TABLE IF NOT EXISTS gen_plantilla_e14 (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(255),
    ruta_servidor   VARCHAR(500),
    mesas_total     INT,
    candidatos_total INT,
    fecha_carga     TIMESTAMP DEFAULT NOW(),
    activa          BOOLEAN DEFAULT TRUE,
    usuario         VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS gen_plantilla_mesas (
    plantilla_id   INT REFERENCES gen_plantilla_e14(id) ON DELETE CASCADE,
    fila_xlsx      INT NOT NULL,
    mesa_id_str    VARCHAR(50),
    nomdepto       VARCHAR(200),
    nommipio       VARCHAR(200),
    nompuesto      VARCHAR(300),
    mesa_num       VARCHAR(10),
    coddepto       INT,
    codmipio       INT,
    codzona        INT,
    codpuesto      VARCHAR(10),
    mesa           INT,
    idmesa         INT,
    PRIMARY KEY (plantilla_id, fila_xlsx)
);
CREATE INDEX IF NOT EXISTS idx_genmesas_geo
  ON gen_plantilla_mesas(coddepto, codmipio, codzona, codpuesto, mesa);

CREATE TABLE IF NOT EXISTS gen_plantilla_candidatos (
    plantilla_id   INT REFERENCES gen_plantilla_e14(id) ON DELETE CASCADE,
    columna_xlsx   INT NOT NULL,
    header_text    VARCHAR(200),
    alias          VARCHAR(100),
    codcandidato   INT,
    PRIMARY KEY (plantilla_id, columna_xlsx)
);

CREATE TABLE IF NOT EXISTS gen_estado (
    id                    INT PRIMARY KEY DEFAULT 1 CHECK (id=1),
    activo                BOOLEAN DEFAULT FALSE,
    intervalo_min         INT DEFAULT 5,
    plantilla_id          INT REFERENCES gen_plantilla_e14(id),
    ultimo_corte_num      INT DEFAULT 0,
    ultimo_corte_at       TIMESTAMP,
    inicio_at             TIMESTAMP,
    skipped_consecutivos  INT DEFAULT 0,
    ultimo_hash           VARCHAR(64)
);
INSERT INTO gen_estado(id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS gen_cortes (
    id                BIGSERIAL PRIMARY KEY,
    plantilla_id      INT,
    num_corte         INT,
    tipo              VARCHAR(20),    -- 'generado' / 'sin_cambios'
    archivo           VARCHAR(300),
    ruta              VARCHAR(600),
    mesas_reportadas  INT,
    total_votos       BIGINT,
    hash_snapshot     VARCHAR(64),
    fecha             TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gencortes_fecha ON gen_cortes(fecha DESC);
