-- ============================================================
-- Esquema base presidencial 2026
-- Correr DENTRO de AuditorEscrutinioPresidencial2026_PROD
-- ============================================================

-- ====== USUARIOS Y PERFILES ======
CREATE TABLE perfiles (
    id      SERIAL PRIMARY KEY,
    nombre  VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
    id              SERIAL PRIMARY KEY,
    cedula          VARCHAR(30) NOT NULL UNIQUE,
    contrasena      VARCHAR(64),
    nombres         VARCHAR(100),
    apellidos       VARCHAR(100),
    correo          VARCHAR(100),
    id_perfil       INTEGER REFERENCES perfiles(id),
    iddivipol       INTEGER,
    codcorporacion  INTEGER,
    session_token   VARCHAR(64),
    creado          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_usuarios_cedula ON usuarios(cedula);
CREATE INDEX idx_usuarios_perfil ON usuarios(id_perfil);

-- ====== DIVIPOL PRESIDENCIAL ======
CREATE TABLE divipol_presidencial_2026 (
    iddivipol    INTEGER PRIMARY KEY,
    clase        CHAR(1) NOT NULL,            -- D / M / Z / P
    coddepto     INTEGER,
    codmipio     INTEGER,
    codzona      INTEGER,
    codpuesto    VARCHAR(2),
    nomdepto     VARCHAR(50),
    nommipio     VARCHAR(50),
    nompuesto    VARCHAR(100),
    nummesas     INTEGER,
    potfemenino  INTEGER,
    potmasculino INTEGER,
    pottotal     INTEGER,
    jal          INTEGER,
    nomjal       VARCHAR(30),
    indicador    INTEGER,
    expandida    INTEGER
);
CREATE INDEX idx_divpres_clase ON divipol_presidencial_2026(clase);
CREATE INDEX idx_divpres_depto ON divipol_presidencial_2026(coddepto, clase);
CREATE INDEX idx_divpres_dmz   ON divipol_presidencial_2026(coddepto, codmipio, codzona);

CREATE TABLE divipolmesa_presidencial_2026 (
    idmesa     INTEGER PRIMARY KEY,
    iddivipol  INTEGER NOT NULL REFERENCES divipol_presidencial_2026(iddivipol),
    mesa       INTEGER NOT NULL,
    jornada    INTEGER
);
CREATE INDEX idx_dmpres_iddivipol ON divipolmesa_presidencial_2026(iddivipol);
