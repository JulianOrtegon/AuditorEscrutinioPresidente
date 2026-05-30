-- ============================================================
-- Tablas para Cargue MMV - Escrutinio Presidencial 2026
-- ============================================================

-- Control de archivos de escrutinio cargados
CREATE TABLE control_escrutinio_presidencial_2026 (
    id              SERIAL PRIMARY KEY,
    facceso         DATE NOT NULL,
    nombrearchivo   VARCHAR(500) NOT NULL,
    registros       INTEGER DEFAULT 0,
    fecha           TIMESTAMP DEFAULT NOW(),
    usuario_cargue  VARCHAR(100),
    tiempo_carga    VARCHAR(50),
    estado          INTEGER DEFAULT 1,     -- 1 = cargado (los datos ya están estructurados, no requiere "procesar")
    tamano_mb       NUMERIC(10,2),
    UNIQUE (facceso, nombrearchivo)
);
CREATE INDEX idx_cesc_pres_facceso ON control_escrutinio_presidencial_2026(facceso);
CREATE INDEX idx_cesc_pres_archivo ON control_escrutinio_presidencial_2026(nombrearchivo);

-- Datos estructurados del escrutinio (formato CSV RNEC)
CREATE TABLE escrutinio_presidencial_2026 (
    facceso             DATE NOT NULL,
    idregistro          VARCHAR(100),
    codcorporacion      INTEGER,
    nomcorporacion      VARCHAR(150),
    codcircunscripcion  INTEGER,
    nomcircunscripcion  VARCHAR(150),
    coddepto            INTEGER,
    nomdepto            VARCHAR(80),
    codmipio            INTEGER,
    nommipio            VARCHAR(80),
    codzona             INTEGER,
    nomzona             VARCHAR(50),
    codpuesto           VARCHAR(10),
    nompuesto           VARCHAR(200),
    mesa                INTEGER,
    codcomuna           VARCHAR(20),
    nomcomuna           VARCHAR(80),
    codpartido          INTEGER,
    nompartido          VARCHAR(200),
    cedulacandidato     VARCHAR(30),
    nomcandidato        VARCHAR(200),
    codcandidato        INTEGER,
    votos               INTEGER DEFAULT 0,
    archivo             VARCHAR(500)
) PARTITION BY LIST (facceso);

CREATE INDEX idx_esc_pres_archivo ON escrutinio_presidencial_2026(archivo);
CREATE INDEX idx_esc_pres_geo ON escrutinio_presidencial_2026(coddepto, codmipio, codzona, codpuesto, mesa);
CREATE INDEX idx_esc_pres_cand ON escrutinio_presidencial_2026(codcandidato);
