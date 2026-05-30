-- ============================================================
-- Tablas catálogo elección presidencial 2026
-- Correr DENTRO de AuditorEscrutinioPresidencial2026_PROD
-- ============================================================

-- ====== CORPORACION ======
CREATE TABLE corporacion_presidencial_2026 (
    codcorporacion INTEGER PRIMARY KEY,
    nomcorporacion VARCHAR(100) NOT NULL
);

-- ====== CIRCUNSCRIPCION ======
CREATE TABLE circunscripcion_presidencial_2026 (
    codcircunscripcion INTEGER PRIMARY KEY,
    nomcircunscripcion VARCHAR(100) NOT NULL
);

-- ====== PARTIDOS ======
CREATE TABLE partidos_presidencial_2026 (
    codpartido INTEGER PRIMARY KEY,
    nompartido VARCHAR(200) NOT NULL,
    tipo       CHAR(1)                    -- N = Nacional
);

-- ====== CANDIDATOS ======
-- Para presidencial cada partido inscribe formula (presidente + vicepresidente).
-- formula_pos: 1 = presidente, 2 = vicepresidente.
CREATE TABLE candidatos_presidencial_2026 (
    idcandidato     SERIAL PRIMARY KEY,
    codcorporacion  INTEGER REFERENCES corporacion_presidencial_2026(codcorporacion),
    codcircunscripcion INTEGER REFERENCES circunscripcion_presidencial_2026(codcircunscripcion),
    codpartido      INTEGER REFERENCES partidos_presidencial_2026(codpartido),
    codcandidato    INTEGER NOT NULL,
    formula_pos     INTEGER DEFAULT 1,    -- 1=presidente, 2=vicepresidente
    nombres         VARCHAR(100),
    apellidos       VARCHAR(100),
    nomcandidato    VARCHAR(300),         -- nombre completo cacheado
    cedula          BIGINT,
    sexo            CHAR(1),
    num_tarjeton    INTEGER,
    UNIQUE (codcorporacion, codpartido, codcandidato, formula_pos)
);
CREATE INDEX idx_candpres_partido ON candidatos_presidencial_2026(codpartido);
CREATE INDEX idx_candpres_cedula  ON candidatos_presidencial_2026(cedula);
